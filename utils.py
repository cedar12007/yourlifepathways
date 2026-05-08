import re
import time
import os
import ssl
import certifi
import requests
import smtplib
from redis import Redis
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import request

# Redis Setup
REDIS_ENABLED = os.getenv("redis_enabled", "false").lower() == "true"
redis_client = None
if REDIS_ENABLED:
    redis_client = Redis(
        url=os.getenv("redis_url"),
        token=os.getenv("redis_token")
    )

RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")
GMAIL_USER = os.getenv("doar_ktovet")
GMAIL_PASSWORD = os.getenv("doar_sisma")

from functools import wraps
from flask import make_response

def vercel_edge_cache(s_maxage=1, swr=86400):
    """
    Decorator to apply Vercel Edge Caching headers.
    Bypasses for authenticated admins.
    
    s-maxage=1: Stays fresh for 1s.
    stale-while-revalidate=86400: Serves stale while revalidating for up to 24h.
    This effectively makes pages instant while ensuring they stay reasonably fresh.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # We import here to avoid circular dependencies
            from flask_login import current_user
            
            # Execute the route
            result = f(*args, **kwargs)
            
            # Handle list/tuple returns (e.g. render_template(), 404)
            if isinstance(result, tuple):
                response = make_response(result[0])
                status_code = result[1]
            else:
                response = make_response(result)
                status_code = response.status_code

            # If it's a redirect (301, 302, 307, 308), we should typically not cache it 
            # or cache it differently. For now, let's just ensure the status code is preserved.
            
            # If user is admin (logged in), NEVER cache
            if current_user.is_authenticated:
                response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
                return response, status_code
                
            # Apply Vercel Edge caching headers for successful responses
            if 200 <= status_code < 300:
                response.headers['Cache-Control'] = f'public, s-maxage={s_maxage}, stale-while-revalidate={swr}'
            
            return response, status_code
        return decorated_function
    return decorator

def get_client_ip():
    """Returns the real client IP, considering proxies."""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr

def get_ip_location(ip_address):
    """Fetches geolocation for a given IP address using ip-api.com."""
    if not ip_address or ip_address in ['127.0.0.1', '::1']:
        return "Localhost"
    
    # In case a list was passed
    ip_address = ip_address.split(',')[0].strip()
    
    try:
        # Using http because some environments block https for this API or it's free tier
        response = requests.get(f"http://ip-api.com/json/{ip_address}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                return f"{data.get('city')}, {data.get('regionName')}, {data.get('country')} (ISP: {data.get('isp')})"
            return f"Unknown Location ({data.get('message', 'API Error')})"
    except Exception as e:
        print(f"Geolocation error for IP {ip_address}: {e}")
    return "Location unavailable"

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

def verify_recaptcha(token):
    if not token:
        return {"success": False, "message": "No token provided."}

    print("verify_recaptcha")
    verify_response = requests.post(
        "https://www.google.com/recaptcha/api/siteverify",
        data={
            "secret": RECAPTCHA_SECRET_KEY,
            "response": token,
        },
    )
    return verify_response.json()

def check_rate_limit(ip_address, max_submissions=3, time_window=60*5):
    """Checks if the IP has exceeded the submission limit using Redis."""
    if not REDIS_ENABLED or not redis_client:
        return True # Fail open if Redis is not enabled
        
    current_time = time.time()
    ip_record = redis_client.get(ip_address)

    if ip_record is None:
        redis_client.set(ip_address, f"1-{current_time}")
        return True
    
    # Redis returns bytes, need to decode
    if isinstance(ip_record, bytes):
        ip_record = ip_record.decode('utf-8')

    parts = ip_record.split("-")
    try:
        attempt_count = int(parts[0])
        first_attempt = float(parts[1])
    except (IndexError, ValueError):
        # Reset if malformed
        redis_client.set(ip_address, f"1-{current_time}")
        return True

    if (current_time - first_attempt) > time_window:
        redis_client.set(ip_address, f"1-{current_time}")
        return True
    elif attempt_count < max_submissions:
        # Update record with incremented count
        new_record = f"{attempt_count + 1}-" + "-".join(parts[1:]) + f"-{current_time}"
        redis_client.set(ip_address, new_record)
        return True

    return False

def send_email_notification(name, email, message, recaptcha_result, subject="New YourLifePathways Contact Form", ip_address=None):
    """Helper to handle SMTP logic."""
    if not GMAIL_USER or not GMAIL_PASSWORD:
        print("Email credentials not set. Skipping email.")
        return

    # If ip_address wasn't passed, try to get it from the request context
    if not ip_address:
        try:
            ip_address = get_client_ip()
        except:
            ip_address = "Not available"

    location = get_ip_location(ip_address) if ip_address != "Not available" else "Location unavailable"
    
    body = f"Name: {name}\nEmail: {email}\nIP: {ip_address}\nLocation: {location}\n\nMessage:\n{message}\n\nReCaptcha: {recaptcha_result}"

    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(cafile=certifi.where()), timeout=10) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())
        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")

def send_comment_approval_email(name, email, post_title, post_slug):
    if not GMAIL_USER or not GMAIL_PASSWORD or not email:
        return
    post_url = f"https://www.yourlifepathways.com/blog/{post_slug}"
    subject = f"Your comment on \"{post_title}\" has been approved!"
    body = f"""Hi {name},

Thank you for your engagement! Your comment on "{post_title}" has been approved and is now visible on the blog.

You can view it here: {post_url}

Best,

Erez
"""
    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(cafile=certifi.where()), timeout=10) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, email, msg.as_string())
    except Exception as e:
        print(f"Error sending approval email: {e}")

def send_comment_like_notification(name, email, post_title, post_slug):
    if not GMAIL_USER or not GMAIL_PASSWORD or not email:
        return
    post_url = f"https://www.yourlifepathways.com/blog/{post_slug}"
    subject = f"Someone liked your comment on \"{post_title}\"!"
    body = f"""Hi {name},

Someone just liked your comment on "{post_title}" — nice contribution!

Read the post here: {post_url}

Best,

Erez
"""
    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(cafile=certifi.where()), timeout=10) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, email, msg.as_string())
    except Exception as e:
        print(f"Error sending comment like notification: {e}")

def is_bot(ua_string):
    """
    Returns True if the user agent matches common bots/crawlers.
    """
    if not ua_string or ua_string == 'Unknown':
        return False
        
    ua = ua_string.lower()
    bot_keywords = [
        'bot', 'spider', 'crawler', 'lighthouse', 'google', 'bing', 'yandex', 
        'headless', 'monitoring', 'slurp', 'baiduspider', 'facebookexternalhit',
        'python-requests', 'go-http-client', 'node-fetch', 'axios', 'curl', 'wget',
        'pingdom', 'statuscake', 'uptime', 'preview'
    ]
    
    return any(keyword in ua for keyword in bot_keywords)

def parse_user_agent(ua_string):
    """
    Simulated UA Parser. 
    Returns a human-readable device/browser string from a raw User-Agent.
    """
    if not ua_string or ua_string == 'Unknown':
        return 'Unknown Device'
    
    if is_bot(ua_string):
        # Identify specific bots if possible
        ua = ua_string.lower()
        if 'googlebot' in ua: return 'Bot / Googlebot'
        if 'bingbot' in ua: return 'Bot / Bingbot'
        if 'yandex' in ua: return 'Bot / Yandex'
        if 'lighthouse' in ua: return 'Bot / Lighthouse'
        return 'Bot / Automated'
        
    ua = ua_string.lower()
    
    device = "Desktop"
    if "iphone" in ua:
        device = "iPhone"
    elif "ipad" in ua:
        device = "iPad"
    elif "android" in ua:
        device = "Android"
    elif "mobile" in ua:
        device = "Mobile"
        
    browser = "Browser"
    if "chrome" in ua and "safari" in ua and "edg" in ua:
         browser = "Edge"
    elif "chrome" in ua and "safari" in ua and "opr" in ua:
         browser = "Opera"
    elif "chrome" in ua and "safari" in ua:
         browser = "Chrome"
    elif "safari" in ua and "chrome" not in ua:
         browser = "Safari"
    elif "firefox" in ua:
         browser = "Firefox"
    elif "msie" in ua or "trident" in ua:
         browser = "IE"
         
    os_name = ""
    if "windows" in ua:
        os_name = "Windows"
    elif "mac os" in ua:
        os_name = "macOS"
    elif "linux" in ua:
        os_name = "Linux"
        
    return f"{device} / {browser} {os_name}".strip()

def parse_referrer_query(referrer_url):
    """
    Extracts search query from common search engine referrers.
    Returns the search term or None.
    """
    if not referrer_url:
        return None
        
    try:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(referrer_url)
        params = parse_qs(parsed.query)
        
        # Google, Bing usually use 'q'
        if 'q' in params:
            return params['q'][0]
        # Yahoo uses 'p'
        if 'p' in params:
            return params['p'][0]
        # Baidu uses 'wd'
        if 'wd' in params:
            return params['wd'][0]
        # Some others use 'query' or 'k'
        if 'query' in params:
            return params['query'][0]
            
        return None
    except:
        return None
