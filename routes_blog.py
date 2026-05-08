import re

from flask import Blueprint, render_template, jsonify, abort, make_response, request, redirect, flash, url_for
from flask_login import current_user

from models import Post, db, Comment, PostLike, PostShare, CommentLike
from extensions import executor
from utils import slugify, verify_recaptcha, send_email_notification, send_comment_like_notification, get_client_ip, vercel_edge_cache


def is_admin():
    # Only authenticated users are admins
    return current_user.is_authenticated

# Define the blueprint
blog = Blueprint('blog', __name__)


def get_active_posts():
    from sqlalchemy import func, outerjoin
    
    # Subquery for Likes
    likes_sub = db.session.query(
        PostLike.post_id, 
        func.count(PostLike.id).label('likes_count')
    ).filter(PostLike.is_deleted == False).group_by(PostLike.post_id).subquery()

    # Subquery for Shares
    shares_sub = db.session.query(
        PostShare.post_id, 
        func.count(PostShare.id).label('shares_count')
    ).group_by(PostShare.post_id).subquery()

    # Subquery for Comments
    comments_sub = db.session.query(
        Comment.post_id, 
        func.count(Comment.id).label('comments_count')
    ).filter(Comment.is_approved == True, Comment.is_deleted == False).group_by(Comment.post_id).subquery()

    # Main Query
    posts = db.session.query(Post, 
                           func.coalesce(likes_sub.c.likes_count, 0).label('num_likes'),
                           func.coalesce(shares_sub.c.shares_count, 0).label('num_shares'),
                           func.coalesce(comments_sub.c.comments_count, 0).label('num_comments'))\
        .outerjoin(likes_sub, Post.id == likes_sub.c.post_id)\
        .outerjoin(shares_sub, Post.id == shares_sub.c.post_id)\
        .outerjoin(comments_sub, Post.id == comments_sub.c.post_id)\
        .filter(Post.is_deleted == False)\
        .order_by(Post.date_created.desc())\
        .all()
    
    # Attach the counts to the post objects so templates don't hit the DB
    result = []
    for post, nl, ns, nc in posts:
        post.num_likes = nl
        post.num_shares = ns
        post.num_comments = nc
        result.append(post)
    return result


def get_latest_posts(limit=3):
    return Post.query.filter_by(is_deleted=False).order_by(Post.date_created.desc()).limit(limit).all()


def get_threaded_comments(post_id, include_unapproved=False):
    # 1. Fetch all comments for the post (including deleted ones)
    query = Comment.query.filter_by(post_id=post_id)
    if not include_unapproved:
        query = query.filter_by(is_approved=True)
    all_comments = query.order_by(Comment.date_created.asc()).all()
    
    # 2. Map comments and initialize reply lists
    comment_dict = {c.id: c for c in all_comments}
    for c in all_comments:
        c.replies_list = []
    
    # 3. Build the hierarchical tree
    top_level = []
    for c in all_comments:
        if c.parent_id is None:
            top_level.append(c)
        elif c.parent_id in comment_dict:
            comment_dict[c.parent_id].replies_list.append(c)

    # 4. Recursive helper: A comment is "visible" if it's not deleted 
    # OR if it has at least one visible descendant.
    def check_visibility(comment):
        # Cache active descendants to avoid re-calculating
        active_replies = [r for r in comment.replies_list if check_visibility(r)]
        comment.active_replies_list = active_replies
        
        if not comment.is_deleted:
            return True
        return len(active_replies) > 0

    # 5. Filter top level and trigger recursion
    return [c for c in top_level if check_visibility(c)]


@blog.route('/main_life_professional_business_leadership_executive_coaching_blog')
def list_posts_old():
    """Redirect old SEO-heavy blog URL to the new clean /blog URL"""
    return redirect(url_for('blog.list_posts'), code=301)


@blog.route('/blog')
@vercel_edge_cache(s_maxage=1, swr=86400)
def list_posts():
    """Displays the grid of blog blocks"""
    # 1. Query all active posts, sorted by newest first
    all_posts = get_active_posts()
    return render_template('main_life_professional_business_leadership_executive_coaching_blog.html',
                           posts=all_posts,
                           canonical_url="https://www.yourlifepathways.com" + url_for('blog.list_posts'))


@blog.route('/blog_test')
def blog_test():
    return render_template('blog_test.html', noindex=True)


@blog.route('/blog/<string:slug>')
@vercel_edge_cache(s_maxage=1, swr=86400)
def view_post(slug):
    print(f"Viewing post: {slug}")
    # Find the post by slug in the list
    post = Post.query.filter_by(slug=slug, is_deleted=False).first_or_404()

    if not post:
        abort(404)

    # Get all active posts ordered by date
    all_posts = get_active_posts()
    post_slugs = [p.slug for p in all_posts]
    try:
        current_index = post_slugs.index(slug)
        prev_post = all_posts[current_index - 1] if current_index > 0 else None
        next_post = all_posts[current_index + 1] if current_index < len(all_posts) - 1 else None
    except ValueError:
        prev_post = None
        next_post = None

    # Fetch threaded comments, including unapproved only for admin
    comments = get_threaded_comments(post.id, include_unapproved=is_admin())
    # Prepare counts using minimal queries
    approved_count = Comment.query.filter_by(post_id=post.id, is_approved=True, is_deleted=False).count()
    likes_count = PostLike.query.filter_by(post_id=post.id, is_deleted=False).count()
    shares_count = PostShare.query.filter_by(post_id=post.id).count()

    print(f"Post interaction stats: Likes:{likes_count}, Shares:{shares_count}, Comments:{approved_count}")

    # Prepare meta data for SEO
    meta_title = f"{post.title} | YourLifePathways Blog"
    meta_description = post.summary[:155] + "..." if post.summary and len(post.summary) > 155 else post.summary
    if not meta_description:
        meta_description = f"Read {post.title} on the YourLifePathways blog. Insightful coaching and leadership advice by Erez Asif."
    # Use post's canonical_url if set (for syndicated content), otherwise use our site's URL
    canonical_url = post.canonical_url or f"https://www.yourlifepathways.com/blog/{post.slug}"

    return render_template('blog_detail.html', post=post, comments=comments, approved_count=approved_count, likes_count=likes_count, shares_count=shares_count, is_admin=is_admin(), prev_post=prev_post, next_post=next_post, meta_title=meta_title, meta_description=meta_description, canonical_url=canonical_url)


@blog.route('/like/<int:post_id>', methods=['POST'])
def like_post(post_id):
    try:
        print(f"Like route called for post_id: {post_id}")
        cookie_name = f'liked_post_{post_id}'

        post = Post.query.get_or_404(post_id)
        print(f"Post found: {post.title}")

        if request.cookies.get(cookie_name):
            # Already liked, so remove the like (toggle off)
            existing_like = PostLike.query.filter_by(post_id=post_id, visitor_ip=request.remote_addr).first()
            if existing_like:
                existing_like.is_deleted = True
                db.session.commit()
                print("Like soft-deleted")

                # Send email notification for unlike in background
                executor.submit(
                    send_email_notification,
                    name="Anonymous User",
                    email=None,
                    message=f"A like was removed for the post: {post.title} from IP: {get_client_ip()}",
                    recaptcha_result={"success": True},
                    subject=f"Unlike on Post: {post.title}",
                    ip_address=get_client_ip()
                )

            new_count = post.likes_data.filter_by(is_deleted=False).count()
            response = make_response(jsonify({"success": True, "new_count": new_count, "liked": False}))
            response.set_cookie(cookie_name, '', max_age=0)  # Remove cookie
            return response
        else:
            # Not liked yet, check if there's a soft-deleted like to revive, otherwise add new
            existing_deleted_like = PostLike.query.filter_by(post_id=post_id, visitor_ip=request.remote_addr, is_deleted=True).first()
            if existing_deleted_like:
                # Revive the soft-deleted like
                existing_deleted_like.is_deleted = False
                db.session.commit()
                print("Like revived")
            else:
                # Add new like
                new_like = PostLike(
                    post_id=post_id,
                    visitor_ip=request.remote_addr
                )
                db.session.add(new_like)
                db.session.commit()
                print("New like added")

            new_count = post.likes_data.filter_by(is_deleted=False).count()
            print(f"Like count updated, new_count: {new_count}")

            # Send email notification for new like in background
            executor.submit(
                send_email_notification,
                name="Anonymous User",
                email=None,
                message=f"A new like was received for the post: {post.title} from IP: {get_client_ip()}",
                recaptcha_result={"success": True},
                subject=f"New Like on Post: {post.title}",
                ip_address=get_client_ip()
            )

            response = make_response(jsonify({"success": True, "new_count": new_count, "liked": True}))
            response.set_cookie(cookie_name, 'true', max_age=31536000)
            return response
    except Exception as e:
        print(f"Error in like_post: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@blog.route('/like/comment/<int:comment_id>', methods=['POST'])
def like_comment(comment_id):
    cookie_name = f'liked_comment_{comment_id}'
    try:
        comment = Comment.query.filter_by(id=comment_id, is_approved=True, is_deleted=False).first_or_404()
        post = Post.query.get_or_404(comment.post_id)
        visitor_ip = get_client_ip()

        existing = CommentLike.query.filter_by(comment_id=comment_id, visitor_ip=visitor_ip).first()
        send_notification = False

        if existing and not existing.is_deleted:
            if request.cookies.get(cookie_name):
                existing.is_deleted = True
                liked = False
                max_age = 0
            else:
                liked = True
                max_age = 31536000
        elif existing and existing.is_deleted:
            existing.is_deleted = False
            liked = True
            max_age = 31536000
            if not existing.notification_sent:
                existing.notification_sent = True
                send_notification = True
        else:
            new_like = CommentLike(comment_id=comment_id, visitor_ip=visitor_ip, notification_sent=True)
            db.session.add(new_like)
            liked = True
            max_age = 31536000
            send_notification = True

        db.session.commit()

        new_count = CommentLike.query.filter_by(comment_id=comment_id, is_deleted=False).count()

        if send_notification and comment.email:
            executor.submit(send_comment_like_notification, comment.name, comment.email, post.title, post.slug)

        response = make_response(jsonify({"success": True, "new_count": new_count, "liked": liked}))
        response.set_cookie(cookie_name, 'true' if liked else '', max_age=max_age)
        return response
    except Exception as e:
        print(f"Error in like_comment: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@blog.route('/share/<int:post_id>', methods=['POST'])
def share_post(post_id):
    cookie_name = f'shared_post_{post_id}'

    post = Post.query.get_or_404(post_id)

    if request.cookies.get(cookie_name):
        # Prevent multiple shares from same browser - don't count again
        pass
    else:
        # Create share record with metadata
        new_share = PostShare(
            post_id=post_id,
            visitor_ip=request.remote_addr,
            user_agent=str(request.user_agent)
        )
        db.session.add(new_share)
        db.session.commit()

    # Send email notification for share in background
    executor.submit(
        send_email_notification,
        name="Anonymous User",
        email=None,
        message=f"A share was clicked for the post: {post.title} from IP: {get_client_ip()}",
        recaptcha_result={"success": True},
        subject=f"Share Click on Post: {post.title}",
        ip_address=get_client_ip()
    )

    response = make_response(jsonify({"success": True, "new_count": post.shares_data.count()}))
    response.set_cookie(cookie_name, 'true', max_age=31536000)  # Cookie expires in 1 year
    return response


@blog.route('/blog/<slug>/comment', methods=['POST'])
def add_comment(slug):
    # 🔍 First, find the post using the slug
    post = Post.query.filter_by(slug=slug).first_or_404()

    if request.form.get('honeypot'):
        return redirect(url_for('blog.view_post', slug=slug))

    # Recaptcha verification
    recaptcha_response = request.form.get('g-recaptcha-response')
    recaptcha_result = verify_recaptcha(recaptcha_response)
    if not recaptcha_result.get("success"):
        return jsonify({"success": False, "message": "Captcha validation failed. Please try again."})

    name = request.form.get('name', '').strip()
    email = request.form.get('email')
    content = request.form.get('content')
    parent_id = request.form.get('parent_id', type=int)

    # 🛑 Reserved Names Check
    reserved_names = ["admin", "erez", "erez asif", "yourlifepathways"]
    if name.lower() in reserved_names and not current_user.is_authenticated:
        return jsonify({
            "success": False, 
            "message": f"The name '{name}' is reserved. Please use a different name."
        })

    if name and content:
        new_comment = Comment(
            name=name,
            email=email,
            content=content,
            post_id=post.id,
            parent_id=parent_id
        )
        db.session.add(new_comment)
        db.session.commit()
        
        # Send email notification in background
        executor.submit(
            send_email_notification,
            name=name,
            email=email,
            message=content,
            recaptcha_result=recaptcha_result,
            subject=f"New Blog Comment: {post.title}",
            ip_address=get_client_ip()
        )

        return jsonify({"success": True, "message": "Thank you! Your comment has been submitted for moderation."})

    return jsonify({"success": False, "message": "Something went wrong. Please try again."})


@blog.route('/blog/comment/<int:comment_id>/approve', methods=['POST'])
def approve_comment(comment_id):
    if not is_admin():
        abort(403)
    comment = Comment.query.get_or_404(comment_id)
    comment.is_approved = True
    db.session.commit()
    flash('Comment approved.')
    return redirect(url_for('blog.view_post', slug=comment.post.slug))


@blog.route('/blog/comment/<int:comment_id>/reject', methods=['POST'])
def reject_comment(comment_id):
    if not is_admin():
        abort(403)
    comment = Comment.query.get_or_404(comment_id)
    comment.is_approved = False
    db.session.commit()
    flash('Comment rejected.')
    return redirect(url_for('blog.view_post', slug=comment.post.slug))
