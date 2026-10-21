import os

# Only import Blueprint and request-related tools from flask
from flask import Blueprint, render_template, request, jsonify, make_response, url_for, redirect, send_file, current_app

# Import from your local files
from extensions import db, executor
from models import Post, EmailOpen
# from models import ContactMessage
from utils import check_rate_limit, verify_recaptcha, send_email_notification, REDIS_ENABLED, get_client_ip, get_ip_location, vercel_edge_cache

# Ensure this is a string, not a list
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@vercel_edge_cache(s_maxage=1, swr=86400)
def index():
    latest_posts = Post.query.filter_by(is_deleted=False).order_by(Post.date_created.desc()).limit(8).all()
    return render_template('index.html', latest_posts=latest_posts)


@main_bp.route('/index.html')
def index_redirect():
    return redirect(url_for('main.index'), code=301)


@main_bp.route('/discovery-call')
@vercel_edge_cache(s_maxage=1, swr=86400)
def discovery_call():
    # Render the index page but with specific SEO title/desc and auto-scroll
    return render_template(
        'index.html',
        latest_posts=Post.query.filter_by(is_deleted=False).order_by(Post.date_created.desc()).limit(8).all(),
        page_title="Book a Free Discovery Call | YourLifePathways",
        page_description="Schedule your free, no-obligation 30-minute discovery call with Erez Asif. Start your journey to professional and personal growth today.",
        scroll_target="#contact",
        canonical_url="https://www.yourlifepathways.com" + url_for('main.index') + "#contact"
    )


@main_bp.route('/overview')
@vercel_edge_cache(s_maxage=1, swr=86400)
def overview():
    return render_template(
        'index.html',
        latest_posts=Post.query.filter_by(is_deleted=False).order_by(Post.date_created.desc()).limit(8).all(),
        page_title="Executive & Life Coaching Overview | YourLifePathways",
        page_description="Helping career professionals and growth-minded individuals reclaim their spark and live with purpose.",
        scroll_target="#intro",
        canonical_url="https://www.yourlifepathways.com" + url_for('main.index') + "#intro"
    )


@main_bp.route('/about')
@vercel_edge_cache(s_maxage=1, swr=86400)
def about():
    return render_template(
        'index.html',
        latest_posts=Post.query.filter_by(is_deleted=False).order_by(Post.date_created.desc()).limit(8).all(),
        page_title="About Erez Asif | YourLifePathways",
        page_description="Learn about Erez Asif's 25 years of experience in leadership, hiring, and coaching.",
        scroll_target="#about_me",
        canonical_url="https://www.yourlifepathways.com" + url_for('main.index') + "#about_me"
    )


@main_bp.route('/community-involvement-and-mentorship')
@vercel_edge_cache(s_maxage=1, swr=86400)
def community_involvement_and_mentorship():
    return render_template(
        'index.html',
        latest_posts=Post.query.filter_by(is_deleted=False).order_by(Post.date_created.desc()).limit(8).all(),
        page_title="Community & Mentorship | YourLifePathways",
        page_description="Giving back through Big Brothers Big Sisters, youth coaching, and pro-bono interview prep services.",
        scroll_target="#community",
        canonical_url="https://www.yourlifepathways.com" + url_for('main.index') + "#community"
    )


@main_bp.route('/educational-institutions')
@vercel_edge_cache(s_maxage=1, swr=86400)
def educational_institutions():
    return render_template(
        'educational_institutions.html',
        latest_posts=Post.query.filter_by(is_deleted=False).order_by(Post.date_created.desc()).limit(8).all(),
        page_title="Educational Institutions | YourLifePathways",
        page_description="Mentorship-focused, academic, and supportive coaching for educational institutions.",
        meta_title="Educational Institutions | YourLifePathways",
        meta_description="Mentorship-focused, academic, and supportive coaching for educational institutions."
    )


@main_bp.route('/non-profits-and-mission-driven-organizations')
@vercel_edge_cache(s_maxage=1, swr=86400)
def non_profits_and_mission_driven_organizations():
    return render_template(
        'non_profits.html',
        latest_posts=Post.query.filter_by(is_deleted=False).order_by(Post.date_created.desc()).limit(8).all(),
        page_title="Non-Profits & Mission-Driven Orgs | YourLifePathways",
        page_description="Community-rooted, empathetic, and impact-driven strategic leadership sessions for local non-profit and mission-driven leaders.",
        meta_title="Non-Profits & Mission-Driven Orgs | YourLifePathways",
        meta_description="Community-rooted, empathetic, and impact-driven strategic leadership sessions for local non-profit and mission-driven leaders."
    )


@main_bp.route("/validate-captcha", methods=["POST"])
def validate_captcha():
    data = request.json

    # Honeypot check
    if data.get('honeypot'):
        return jsonify({"success": False, "message": "Spam detected."}), 400

    name = data.get("name")
    email = data.get("email")
    message = data.get("message")
    recaptcha_response = data.get("g-recaptcha-response")
    ip_address = get_client_ip()
    print("validate_captcha function called")
    # 1. Redis Rate Limiting
    if REDIS_ENABLED:
        if not check_rate_limit(ip_address):
            return jsonify({"success": False, "message": "Submission limit exceeded. Please try again later."}), 429

    # 2. reCAPTCHA Verification (Score >= 0.5)
    recaptcha_result = verify_recaptcha(recaptcha_response)
    score = recaptcha_result.get("score", 0.0)
    print(f"reCAPTCHA score: {score}, result: {recaptcha_result}")
    if not recaptcha_result.get("success") or score < 0.5:
        return jsonify({"success": False, "message": "Security verification failed. Please try again."}), 400

    # 3. Process Success: Save to DB and Send Email
    try:
        # Save to SQLite via SQLAlchemy
        # new_msg = ContactMessage(name=name, email=email, message=message)
        # db.session.add(new_msg)
        # db.session.commit()

        # Send SMTP Email
        send_email_notification(name, email, message, recaptcha_result, ip_address=ip_address)
        print("sent email")
        return jsonify({"success": True, "message": "Thank you! Your message has been received."})

    except Exception as e:
        db.session.rollback()
        print(f"Error processing submission: {e}")
        return jsonify({"success": False, "message": "Internal server error."}), 500


@main_bp.route('/sitemap.xml')
def sitemap():
    # Get all active posts
    posts = Post.query.filter_by(is_deleted=False).order_by(Post.date_created.desc()).all()

    # Base URL - adjust for production
    base_url = "https://www.yourlifepathways.com"

    # Static pages
    urls = [
        {"loc": f"{base_url}/", "lastmod": "2026-02-02", "changefreq": "monthly", "priority": "1.0"},
        {"loc": f"{base_url}/blog", "lastmod": "2026-02-02", "changefreq": "weekly", "priority": "0.8"},
        {"loc": f"{base_url}/educational-institutions", "lastmod": "2026-04-04", "changefreq": "monthly", "priority": "0.7"},
        {"loc": f"{base_url}/non-profits-and-mission-driven-organizations", "lastmod": "2026-04-04", "changefreq": "monthly", "priority": "0.7"},
    ]

    # Add blog posts
    for post in posts:
        urls.append({
            "loc": f"{base_url}/blog/{post.slug}",
            "lastmod": post.date_created.strftime('%Y-%m-%d'),
            "changefreq": "monthly",
            "priority": "0.6"
        })

    # Generate XML
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_content += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    for url in urls:
        xml_content += '  <url>\n'
        xml_content += f'    <loc>{url["loc"]}</loc>\n'
        xml_content += f'    <lastmod>{url["lastmod"]}</lastmod>\n'
        xml_content += f'    <changefreq>{url["changefreq"]}</changefreq>\n'
        xml_content += f'    <priority>{url["priority"]}</priority>\n'
        xml_content += '  </url>\n'

    xml_content += '</urlset>'

    response = make_response(xml_content)
    response.headers['Content-Type'] = 'application/xml'
    return response


@main_bp.route('/robots.txt')
def robots():
    robots_content = """User-agent: *
Allow: /

Sitemap: https://www.yourlifepathways.com/sitemap.xml"""
    response = make_response(robots_content)
    response.headers['Content-Type'] = 'text/plain'
    return response


@main_bp.route('/BingSiteAuth.xml')
def bing_site_auth():
    bing_content = """<?xml version="1.0"?>
<users>
	<user>D49AD5CBA7A62DBB632CFB8979302D8C</user>
</users>"""
    response = make_response(bing_content)
    response.headers['Content-Type'] = 'application/xml'
    return response


@main_bp.route('/signature/headshot.png')
@main_bp.route('/signature/profile_pic_email_signature_150px.png')
@main_bp.route('/static/images/profile/profile_pic_email_signature_150px.png')
def track_signature_headshot():
    # 1. Grab metadata
    ref = request.args.get('ref') or request.args.get('id') or request.args.get('tag') or 'gmail_signature'
    ip = get_client_ip()
    ua = request.headers.get('User-Agent', '')

    # 2. Async background logging so the image serves with 0ms latency
    def log_open_task(app_context, ip_addr, user_ag, reference):
        with app_context:
            loc = get_ip_location(ip_addr) if ip_addr else None
            try:
                entry = EmailOpen(ref=reference, ip_address=ip_addr, location=loc, user_agent=user_ag)
                db.session.add(entry)
                db.session.commit()
                current_app.logger.info(f"📧 [Email Open Logged] Ref: {reference} | IP: {ip_addr} ({loc})")
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error logging email open: {e}")

    try:
        executor.submit(log_open_task, current_app._get_current_object().app_context(), ip, ua, ref)
    except Exception:
        pass

    # 3. Serve the actual 150px headshot with no-cache headers
    img_path = os.path.join(current_app.root_path, 'static', 'images', 'profile', 'profile_pic_email_signature_150px.png')
    if not os.path.exists(img_path):
        img_path = os.path.join(current_app.root_path, 'static', 'images', 'profile', 'profile_pic.jpg')

    response = send_file(img_path, mimetype='image/png')
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@main_bp.app_errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404
