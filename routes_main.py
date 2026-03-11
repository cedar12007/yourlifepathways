import os

# Only import Blueprint and request-related tools from flask
from flask import Blueprint, render_template, request, jsonify, make_response, url_for, redirect

# Import from your local files
from extensions import db
from models import Post
# from models import ContactMessage
from utils import check_rate_limit, verify_recaptcha, send_email_notification, REDIS_ENABLED, get_client_ip, vercel_edge_cache

# Ensure this is a string, not a list
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@vercel_edge_cache(s_maxage=1, swr=86400)
def index():
    latest_posts = Post.query.filter_by(is_deleted=False).order_by(Post.date_created.desc()).limit(3).all()
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
        latest_posts=Post.query.filter_by(is_deleted=False).order_by(Post.date_created.desc()).limit(3).all(),
        page_title="Book a Free Discovery Call | YourLifePathways",
        page_description="Schedule your free, no-obligation 30-minute discovery call with Erez Asif. Start your journey to professional and personal growth today.",
        scroll_target="#contact",
        canonical_url=url_for('main.index', _external=True) + "#contact"
    )


@main_bp.route('/overview')
@vercel_edge_cache(s_maxage=1, swr=86400)
def overview():
    return render_template(
        'index.html',
        latest_posts=Post.query.filter_by(is_deleted=False).order_by(Post.date_created.desc()).limit(3).all(),
        page_title="Executive & Life Coaching Overview | YourLifePathways",
        page_description="Helping career professionals and growth-minded individuals reclaim their spark and live with purpose.",
        scroll_target="#intro",
        canonical_url=url_for('main.index', _external=True) + "#intro"
    )


@main_bp.route('/about')
@vercel_edge_cache(s_maxage=1, swr=86400)
def about():
    return render_template(
        'index.html',
        latest_posts=Post.query.filter_by(is_deleted=False).order_by(Post.date_created.desc()).limit(3).all(),
        page_title="About Erez Asif | YourLifePathways",
        page_description="Learn about Erez Asif's 25 years of experience in leadership, hiring, and coaching.",
        scroll_target="#about_me",
        canonical_url=url_for('main.index', _external=True) + "#about_me"
    )


@main_bp.route('/community-involvement-and-mentorship')
@vercel_edge_cache(s_maxage=1, swr=86400)
def community_involvement_and_mentorship():
    return render_template(
        'index.html',
        latest_posts=Post.query.filter_by(is_deleted=False).order_by(Post.date_created.desc()).limit(3).all(),
        page_title="Community & Mentorship | YourLifePathways",
        page_description="Giving back through Big Brothers Big Sisters, youth coaching, and pro-bono interview prep interview prep services.",
        scroll_target="#community",
        canonical_url=url_for('main.index', _external=True) + "#community"
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

    # 2. reCAPTCHA Verification
    recaptcha_result = verify_recaptcha(recaptcha_response)
    print("recaptcha_response: " + str(recaptcha_response))
    if not recaptcha_result.get("success"):
        print(str(recaptcha_result))
        return jsonify({"success": False, "message": "Captcha validation failed."}), 400

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


@main_bp.app_errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404
