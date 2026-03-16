import os
import re
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, render_template
from flask import redirect, url_for
from flask_login import LoginManager, current_user

from extensions import db, executor

app = Flask(__name__)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'main.index' # Silent redirect if unauthorized

from models import User

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///site.db') 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key')
app.config['RECAPTCHA_SITE_KEY'] = os.getenv('RECAPTCHA_SITE_KEY', '')
app.config['RECAPTCHA_SECRET_KEY'] = os.getenv('RECAPTCHA_SECRET_KEY', '')

# Initialize the extensions with the app
db.init_app(app)

# Import models down here or inside the routes to ensure
# they use the 'db' instance we just initialized.
from models import Post
from routes_blog import blog
from routes_main import main_bp
from routes_admin import admin_bp

with app.app_context():
    db.create_all()

app.register_blueprint(blog)
app.register_blueprint(main_bp)
app.register_blueprint(admin_bp)

# Make reCAPTCHA site key available to all templates
@app.context_processor
def inject_recaptcha():
    return {
        'recaptcha_site_key': app.config.get('RECAPTCHA_SITE_KEY', '')
    }

from flask import request
from models import SiteVisit, PostView, Post
from utils import get_client_ip

# Using executor from extensions.py

@app.before_request
def log_visit():
    # 0. Check if logging is enabled via environment variable
    if os.getenv('TRAFFIC_LOGGING', 'no').lower() != 'yes':
        return

    # Check session-based exclusion (for users who started with /admin)
    from flask import session
    if session.get('skip_tracking'):
        return

    # 1. Skip static files, favicon, custom logging endpoint, AND authenticated admins
    if any(request.path.startswith(prefix) for prefix in ['/static', '/favicon.ico', '/log_event']):
        return
        
    # Mark user as admin/exclude if they hit the admin path
    if request.path.startswith('/admin'):
        session['skip_tracking'] = True
        return
    
    # Also skip if user is logged in (admin)
    if current_user.is_authenticated:
        return
    
    # 2. Domain Restriction: ONLY log if accessing these specific domains
    host = request.host.lower()
    allowed_domains = ['yourlifepathways.com', 'www.yourlifepathways.com']
    
    is_allowed_domain = any(domain in host for domain in allowed_domains)
    is_local = 'localhost' in host or '127.0.0.1' in host
    log_local = os.getenv('TRAFFIC_LOGGING_LOCAL', 'no').lower() == 'yes'

    if not is_allowed_domain and not (is_local and log_local):
        return

    # 2. Get data immediately while request context is available
    ip = get_client_ip()
    url = request.url
    endpoint = request.endpoint
    view_args = request.view_args.copy() if request.view_args else {}
    ua = request.headers.get('User-Agent', 'Unknown')
    
    # 3. Enhanced Referrer Logic (Capture UTM sources for ads/campaigns)
    referrer = request.referrer or request.args.get('referrer')
    utm_source = request.args.get('utm_source')
    utm_medium = request.args.get('utm_medium')
    
    if utm_source:
        # If we have UTM tags but no referrer, create a synthetic social referrer
        if not referrer or any(host in referrer for host in ['yourlifepathways.com', 'localhost', '127.0.0.1']):
            referrer = f"social://{utm_source}"
            if utm_medium:
                referrer += f"/{utm_medium}"

    def save_log_task(app_context, ip, url, ua, endpoint, view_args, referrer):
        from utils import get_ip_location
        
        # 1. DO GEOLOCATION FIRST (Slow network I/O)
        location = get_ip_location(ip)
        
        # 2. OPEN DB CONTEXT ONLY FOR THE WRITE (Fast)
        with app_context:
            try:

                # 1. DO GEOLOCATION FIRST (Slow network I/O)
                location = get_ip_location(ip)
                # Save general visit
                visit = SiteVisit(url=url, visitor_ip=ip, visitor_location=location, user_agent=ua, referrer=referrer)
                db.session.add(visit)
                
                # If it's a blog post, log that too
                if endpoint == 'blog.view_post':
                    slug = view_args.get('slug')
                    post = Post.query.filter_by(slug=slug).first()
                    if post:
                        p_view = PostView(post_id=post.id, visitor_ip=ip, visitor_location=location, user_agent=ua)
                        db.session.add(p_view)
                
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"    - Background logging error: {e}")

    # Use a thread pool executor instead of spawning new threads manually
    executor.submit(save_log_task, app.app_context(), ip, url, ua, endpoint, view_args, referrer)

@app.route('/log_event', methods=['GET'])
def log_event():
    target_url = request.args.get('url')
    if not target_url or os.getenv('TRAFFIC_LOGGING', 'no').lower() != 'yes':
        return '', 204
    
    # Also skip if user is logged in (admin) or has the session flag
    from flask import session
    if current_user.is_authenticated or session.get('skip_tracking'):
        return '', 204
    
    # Domain/Local check (match log_visit logic)
    host = request.host.lower()
    allowed_domains = ['yourlifepathways.com', 'www.yourlifepathways.com']
    
    is_allowed_domain = any(domain in host for domain in allowed_domains)
    is_local = 'localhost' in host or '127.0.0.1' in host
    log_local = os.getenv('TRAFFIC_LOGGING_LOCAL', 'no').lower() == 'yes'

    if not is_allowed_domain and not (is_local and log_local):
         return '', 204
    
    # Security: Ensure the reported URL actually belongs to our domain
    # This prevents logging 'http://google.com' if someone manually calls the API
    if not any(d in target_url for d in allowed_domains) and not (is_local and '127.0.0.1' in target_url or 'localhost' in target_url):
        return '', 204

    print(f"[LOG_EVENT] Received URL: {target_url}")
    
    ip = get_client_ip()
    
    # DDOS PROTECTION: Rate limit per IP (in-memory, resets on restart)
    # Allow max 30 events per minute per IP
    from collections import defaultdict
    import time
    
    if not hasattr(app, '_event_rate_limiter'):
        app._event_rate_limiter = defaultdict(list)
    
    now = time.time()
    # Clean old entries (older than 60 seconds)
    app._event_rate_limiter[ip] = [t for t in app._event_rate_limiter[ip] if now - t < 60]
    
    # Check rate limit
    if len(app._event_rate_limiter[ip]) >= 30:
        print(f"[LOG_EVENT] Rate limit exceeded for IP: {ip}")
        return '', 429  # Too Many Requests
    
    # Record this request
    app._event_rate_limiter[ip].append(now)
    
    ua = request.headers.get('User-Agent', 'Unknown')
    
    # Enhanced Referrer Logic for events (e.g. LinkedIn scroll)
    referrer = request.referrer or request.args.get('referrer')
    utm_source = request.args.get('utm_source')
    if utm_source and (not referrer or any(host in referrer for host in ['yourlifepathways.com', 'localhost', '127.0.0.1'])):
        referrer = f"social://{utm_source}"
    
    def save_event_task(app_context, ip, url, ua, referrer):
        from utils import get_ip_location
        location = get_ip_location(ip)
        with app_context:
            try:
                from models import SiteVisit, PostView, Post
                from datetime import datetime, timezone, timedelta
                
                # Use timezone-aware comparison for deduplication
                now = datetime.now(timezone.utc)
                recent = SiteVisit.query.filter_by(visitor_ip=ip, url=url).filter(SiteVisit.timestamp > now - timedelta(seconds=10)).first()
                if recent:
                    # Already logged very recently, skip duplicate
                    return

                # Save general visit
                visit = SiteVisit(url=url, visitor_ip=ip, visitor_location=location, user_agent=ua, referrer=referrer)
                db.session.add(visit)
                
                # Enhanced blog content detection
                # 1. Individual Post (matches /blog/slug)
                blog_post_match = re.search(r'/blog/([^/?#]+)', url)
                if blog_post_match:
                    slug = blog_post_match.group(1).strip('/')
                    if slug:
                        post = Post.query.filter_by(slug=slug).first()
                        if post:
                            p_view = PostView(post_id=post.id, visitor_ip=ip, visitor_location=location, user_agent=ua)
                            db.session.add(p_view)
                        else:
                            # It might be the main list at /blog/
                            if slug == 'blog':
                                # Main blog list - usually handled by SiteVisit, but we can tag it
                                pass
                # 2. Main Blog List page (multiple possible URLs)
                elif any(p in url for p in ['/blog', 'main_life_professional_business_leadership_executive_coaching_blog']):
                    # This captures the blog listing views
                    pass
                db.session.commit()
            except Exception as e:
                print(f"[log_event] Background error: {e}")
                db.session.rollback()
    
    executor.submit(save_event_task, app.app_context(), ip, target_url, ua, referrer)
    return '', 204



if __name__ == "__main__":
    app.run(debug=True)
