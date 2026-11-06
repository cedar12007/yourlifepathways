from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify, make_response, session
from datetime import timedelta
from models import Post, Comment, User, LoginHistory, db, SiteVisit, PostView, EmailOpen
from utils import slugify, parse_user_agent, send_comment_approval_email
from routes_blog import is_admin
from extensions import executor
from functools import wraps
from flask_login import login_user, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin():
            # If not logged in, silently redirect to home instead of showing the login page
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

# --- Hidden Authentication Routes ---

@admin_bp.route('/cedar_login', methods=['GET', 'POST'])
def cedar_login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        history = LoginHistory(
            username_attempted=username,
            ip_address=request.remote_addr,
            user_agent=str(request.user_agent)
        )
        
        if user and check_password_hash(user.password_hash, password):
            # Capture the last successful login timestamp before recording this new one
            last_successful = LoginHistory.query.filter_by(
                user_id=user.id,
                status='success'
            ).order_by(LoginHistory.timestamp.desc()).first()
            if last_successful and last_successful.timestamp:
                session['last_login_time'] = last_successful.timestamp.isoformat()
            else:
                session.pop('last_login_time', None)

            login_user(user)
            history.user_id = user.id
            history.status = 'success'
            db.session.add(history)
            db.session.commit()
            return redirect(url_for('admin.dashboard'))
        else:
            history.status = 'failed'
            db.session.add(history)
            db.session.commit()
            flash('Access Denied.', 'danger')
            
    return render_template('admin/login.html', noindex=True)

@admin_bp.route('/exit-pathway')
def logout():
    session.pop('last_login_time', None)
    logout_user()
    return redirect(url_for('main.index'))

@admin_bp.route('/security-logs')
@admin_required
def security_logs():
    logs = LoginHistory.query.order_by(LoginHistory.timestamp.desc()).all()
    return render_template('admin/logs.html', logs=logs, noindex=True)

@admin_bp.route('/tracking')
@admin_required
def tracking_stats():
    # Group visits by IP to see "Journeys"
    from sqlalchemy import func
    from datetime import datetime, date, timedelta
    
    # 1. Get Filter Parameters
    period = request.args.get('period', 'today')
    custom_date = request.args.get('custom_date', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    show_all = request.args.get('show_all') == 'true'
    has_referrer = request.args.get('has_referrer') == 'true'
    referrer_filter = request.args.get('referrer_filter', '')
    # Bots are always automatically hidden from traffic analytics unless explicitly requested otherwise
    hide_bots = request.args.get('hide_bots', 'true').lower() != 'false'
        
    sort_by = request.args.get('sort_by', 'recent') # 'recent' or 'views'
    
    # 2. Build Base Query
    # Build subquery to get first user_agent for each IP
    first_ua_subquery = db.session.query(
        SiteVisit.visitor_ip,
        SiteVisit.user_agent
    ).distinct(SiteVisit.visitor_ip).order_by(
        SiteVisit.visitor_ip,
        SiteVisit.timestamp.asc()
    ).subquery()
    
    query = db.session.query(
        SiteVisit.visitor_ip,
        func.max(SiteVisit.visitor_location).label('location'),
        func.min(SiteVisit.timestamp).label('first_visit'),
        func.max(SiteVisit.timestamp).label('last_visit'),
        func.count(SiteVisit.id).label('page_views'),
    )
    
    # 3. Apply Date Filters
    from sqlalchemy import and_
    date_filter = None
    
    if period == 'today':
        date_filter = func.date(SiteVisit.timestamp) == date.today()
    elif period == 'yesterday':
        date_filter = func.date(SiteVisit.timestamp) == date.today() - timedelta(days=1)
    elif period == 'custom' and (start_date or end_date):
        filters = []
        if start_date:
            try:
                s_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                filters.append(func.date(SiteVisit.timestamp) >= s_date)
            except ValueError: pass
        if end_date:
            try:
                e_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                filters.append(func.date(SiteVisit.timestamp) <= e_date)
            except ValueError: pass
        if filters:
            date_filter = and_(*filters)
    elif period == 'custom' and custom_date:
        try:
            target_date = datetime.strptime(custom_date, '%Y-%m-%d').date()
            date_filter = func.date(SiteVisit.timestamp) == target_date
        except ValueError:
            pass # Fallback to no date filter if invalid
            
    if date_filter is not None:
        query = query.filter(date_filter)
        
    if referrer_filter:
        refs_ip_query = db.session.query(SiteVisit.visitor_ip).filter(
            SiteVisit.referrer == referrer_filter
        )
        if date_filter is not None:
            refs_ip_query = refs_ip_query.filter(date_filter)
        query = query.filter(SiteVisit.visitor_ip.in_(refs_ip_query))
    elif has_referrer:
        refs_ip_query = db.session.query(SiteVisit.visitor_ip).filter(
            SiteVisit.referrer.isnot(None),
            ~SiteVisit.referrer.contains('yourlifepathways.com'),
            ~SiteVisit.referrer.contains('asifcoaching.com'),
            ~SiteVisit.referrer.contains('mylifepathways.com'),
            ~SiteVisit.referrer.contains('localhost'),
            ~SiteVisit.referrer.contains('127.0.0.1')
        )
        if date_filter is not None:
            refs_ip_query = refs_ip_query.filter(date_filter)
        query = query.filter(SiteVisit.visitor_ip.in_(refs_ip_query))
            
    query = query.group_by(SiteVisit.visitor_ip)
    
    # Count total before bounce filter
    total_count_query = query
    total_visitors = total_count_query.count()
    
    # 4. Apply Duration Filter (Hide 0s duration by default)
    if not show_all:
        query = query.having(func.max(SiteVisit.timestamp) > func.min(SiteVisit.timestamp))
    
    # Count after bounce filter, before limit
    filtered_count = query.count()
    
    valid_ips_subquery = query.with_entities(SiteVisit.visitor_ip).subquery()
    
    # Top Referrers for the time range (counting unique visitors rather than total hits)
    top_refs_query = db.session.query(
        SiteVisit.referrer,
        func.count(func.distinct(SiteVisit.visitor_ip)).label('count')
    ).filter(
        SiteVisit.visitor_ip.in_(valid_ips_subquery),
        SiteVisit.referrer.isnot(None),
        ~SiteVisit.referrer.contains('yourlifepathways.com'),
        ~SiteVisit.referrer.contains('asifcoaching.com'),
        ~SiteVisit.referrer.contains('mylifepathways.com'),
        ~SiteVisit.referrer.contains('localhost'),
        ~SiteVisit.referrer.contains('127.0.0.1')
    )
    if date_filter is not None:
        top_refs_query = top_refs_query.filter(date_filter)
        
    raw_top_refs = top_refs_query.group_by(SiteVisit.referrer).order_by(func.count(func.distinct(SiteVisit.visitor_ip)).desc()).limit(60).all()
    
    import re
    top_referrers = []
    for ref, cnt in raw_top_refs:
        if not ref:
            continue
        ref_l = ref.lower().strip()
        # Drop internal & redirect domains
        if any(d in ref_l for d in ('yourlifepathways.com', 'asifcoaching.com', 'mylifepathways.com', 'localhost', '127.0.0.1')):
            continue
        # Drop raw IP addresses in referrers
        if re.search(r'https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', ref_l):
            continue
        # Drop commercial scrapers, bots, link-farms, and exploit probes
        if any(bad in ref_l for bad in (
            'scraper', 'crawler', 'spider', 'proxy', 'diffbot', 'semrush', 'ahrefs',
            'backlink', 'linkbuilding', 'seochecker', 'dapachecker', 'rankchecker',
            ':443', ':8443', ':8880', ':2083', ':2087', ':2096',
            '/access/api/', 'wp-', '.php', '.env', '.git', 'graphql', 'dump.sql'
        )):
            continue
        top_referrers.append((ref, cnt))
        if len(top_referrers) >= 20:
            break
    
    # 5. Apply Sorting and Execute main query with limit
    if sort_by == 'views':
        query = query.order_by(func.count(SiteVisit.id).desc(), func.max(SiteVisit.timestamp).desc())
    elif sort_by in ('duration', 'session_length'):
        query = query.order_by((func.max(SiteVisit.timestamp) - func.min(SiteVisit.timestamp)).desc(), func.max(SiteVisit.timestamp).desc())
    else: # Default: recent
        query = query.order_by(func.max(SiteVisit.timestamp).desc())
        
    raw_journeys = query.limit(100).all()
    showing_count = len(raw_journeys)
    # Get list of IPs to fetch details for
    ip_list = [row[0] for row in raw_journeys]
    
    # Initialize optimization containers
    ip_to_ua = {}
    ip_to_referrers = {}
    
    if ip_list:
        # OPTIMIZATION: Fetch first user agents for all IPs in ONE query
        first_ua_query = db.session.query(
            SiteVisit.visitor_ip,
            SiteVisit.user_agent
        ).filter(
            SiteVisit.visitor_ip.in_(ip_list)
        ).distinct(SiteVisit.visitor_ip).order_by(
            SiteVisit.visitor_ip,
            SiteVisit.timestamp.asc()
        )
        
        ip_to_ua = {ip: ua for ip, ua in first_ua_query.all()}
        
        # OPTIMIZATION: Fetch all external referrers in ONE query
        external_refs_query = db.session.query(
            SiteVisit.visitor_ip,
            SiteVisit.referrer,
            SiteVisit.timestamp
        ).filter(
            SiteVisit.visitor_ip.in_(ip_list),
            SiteVisit.referrer.isnot(None),
            # Exclude internal referrers specifically, but allowed external ones containing our name
            ~SiteVisit.referrer.contains('://yourlifepathways.com'),
            ~SiteVisit.referrer.contains('://www.yourlifepathways.com'),
            ~SiteVisit.referrer.contains('://localhost'),
            ~SiteVisit.referrer.contains('://127.0.0.1')
        ).order_by(
            SiteVisit.visitor_ip,
            SiteVisit.timestamp.asc()
        ).all()
        
        # Group referrers by IP and deduplicate
        from collections import defaultdict
        ip_to_referrers = defaultdict(list)
        seen_refs = defaultdict(set)
        
        for ip, ref, _ in external_refs_query:
            if ref not in seen_refs[ip]:
                seen_refs[ip].add(ref)
                ip_to_referrers[ip].append(ref)
                
        # OPTIMIZATION: Fetch Lifetime stats for all IPs in ONE query
        lifetime_stats_query = db.session.query(
            SiteVisit.visitor_ip,
            func.count(SiteVisit.id).label('total_lifetime_views'),
            func.count(func.distinct(func.date(SiteVisit.timestamp))).label('total_days'),
            func.min(SiteVisit.timestamp).label('earliest_visit')
        ).filter(SiteVisit.visitor_ip.in_(ip_list)).group_by(SiteVisit.visitor_ip).all()
        
        ip_to_lifetime = {row.visitor_ip: {
            'views': row.total_lifetime_views,
            'days': row.total_days,
            'first': row.earliest_visit
        } for row in lifetime_stats_query}

        # OPTIMIZATION: Fetch true active session time and detect 404 scanners in ONE query
        ip_active_seconds = defaultdict(int)
        ip_dead_routes = defaultdict(int)
        ts_query = db.session.query(
            SiteVisit.visitor_ip,
            SiteVisit.timestamp,
            SiteVisit.url
        ).filter(SiteVisit.visitor_ip.in_(ip_list))
        if date_filter is not None:
            ts_query = ts_query.filter(date_filter)
        ts_rows = ts_query.order_by(SiteVisit.visitor_ip, SiteVisit.timestamp.asc()).all()
        
        from urllib.parse import urlparse
        valid_blog_slugs = {p.slug for p in Post.query.with_entities(Post.slug).all()}

        VALID_STATIC_PATHS = {
            '/',
            '/index.html',
            '/connect',
            '/discovery-call',
            '/overview',
            '/about',
            '/community-involvement-and-mentorship',
            '/educational-institutions',
            '/non-profits-and-mission-driven-organizations',
            '/blog',
            '/main_life_professional_business_leadership_executive_coaching_blog',
            '/cedar_login',
            '/validate-captcha'
        }

        def is_valid_site_path(path, valid_slugs):
            if not path or path == '/':
                return True
            if path in VALID_STATIC_PATHS:
                return True
            if path.startswith('/blog/'):
                slug = path[len('/blog/'):].strip('/')
                return slug in valid_slugs
            if any(path.startswith(prefix) for prefix in ('/r=', '/r/', '/i=', '/i/', '/ref=', '/ref/')):
                return True
            if path == '/log_telemetry' or '/signature/' in path or path.startswith('/static/'):
                return True
            return False

        ip_ts_map = defaultdict(list)
        for r_ip, r_ts, r_url in ts_rows:
            ip_ts_map[r_ip].append(r_ts)
            r_path = urlparse(r_url or '').path.rstrip('/') or '/'
            if not is_valid_site_path(r_path, valid_blog_slugs):
                ip_dead_routes[r_ip] += 1
            
        for r_ip, t_list in ip_ts_map.items():
            if not t_list:
                continue
            sessions = []
            curr = [t_list[0]]
            for t in t_list[1:]:
                if (t - curr[-1]).total_seconds() > 1800:
                    sessions.append(curr)
                    curr = [t]
                else:
                    curr.append(t)
            sessions.append(curr)
            ip_active_seconds[r_ip] = sum(int((s[-1] - s[0]).total_seconds()) for s in sessions)

    def format_secs_short(s):
        if s < 1:
            return "< 1s"
        elif s < 60:
            return f"{s}s"
        elif s < 3600:
            return f"{s // 60}m {s % 60}s"
        else:
            return f"{s // 3600}h {(s % 3600) // 60}m"
    
    from utils import is_bot, parse_user_agent, parse_referrer_query
    
    journeys = []
    
    for row in raw_journeys:
        # Tuple unpacking: ip, location, first, last, views
        ip, loc, first, last, views = row
        ua = ip_to_ua.get(ip, 'Unknown')
        referrers = ip_to_referrers.get(ip, []) if ip_list else []
        clean_ua = parse_user_agent(ua)
        
        dead_cnt = ip_dead_routes.get(ip, 0)
        is_scanner_bot = dead_cnt >= 2
        is_auto_bot = is_bot(ua) or is_scanner_bot
        bot_status = 'auto' if is_auto_bot else None

        if hide_bots and bot_status:
            continue
            
        first_ref = referrers[0] if referrers else None
        search_term = parse_referrer_query(first_ref)
        
        lifetime = ip_to_lifetime.get(ip, {'views': views, 'days': 1, 'first': first})
        active_sec = ip_active_seconds.get(ip, 0)
        lifetime['active_seconds'] = active_sec
        lifetime['formatted_active'] = format_secs_short(active_sec)
        lifetime['dead_routes'] = dead_cnt
        lifetime['valid_views'] = max(0, views - dead_cnt)
        lifetime['is_scanner_bot'] = is_scanner_bot
        
        journeys.append((ip, loc, first, last, views, referrers, clean_ua, search_term, bot_status, lifetime))
    
    if sort_by == 'views':
        journeys.sort(key=lambda j: j[9].get('valid_views', 0), reverse=True)
    elif sort_by in ('duration', 'session_length'):
        journeys.sort(key=lambda j: j[9].get('active_seconds', 0), reverse=True)
    
    import os
    logging_enabled = os.getenv('TRAFFIC_LOGGING', 'no').lower() == 'yes'
    
    return render_template('admin/tracking.html', 
                          journeys=journeys,
                          title='Traffic Analytics',
                          logging_enabled=logging_enabled, 
                          period=period,
                          custom_date=custom_date,
                          start_date=start_date,
                          end_date=end_date,
                          has_referrer=has_referrer,
                          referrer_filter=referrer_filter,
                          show_all=show_all,
                          hide_bots=hide_bots,
                          sort_by=sort_by,
                          showing_count=len(journeys),
                          filtered_count=filtered_count,
                          total_visitors=total_visitors,
                          top_referrers=top_referrers,
                          noindex=True)

@admin_bp.route('/tracking/journey/<string:ip>')
@admin_required
def view_journey(ip):
    from sqlalchemy import func
    from datetime import datetime, date, timedelta
    from utils import is_bot, parse_user_agent, parse_referrer_query
    
    # 1. Get same filter parameters as tracking page to provide context
    period = request.args.get('period', 'today')
    custom_date = request.args.get('custom_date', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    show_all = request.args.get('show_all') == 'true'
    hide_bots = request.args.get('hide_bots', 'true').lower() != 'false'
    has_referrer = request.args.get('has_referrer') == 'true'
    referrer_filter = request.args.get('referrer_filter', '')
    sort_by = request.args.get('sort_by', 'recent')
    
    # 2. Get the current list of IPs to find next/prev
    query = db.session.query(
        SiteVisit.visitor_ip,
        func.min(SiteVisit.timestamp).label('first_visit'),
        func.max(SiteVisit.timestamp).label('last_visit'),
    )
    
    from sqlalchemy import and_
    date_filter = None
    
    if period == 'today':
        date_filter = func.date(SiteVisit.timestamp) == date.today()
    elif period == 'yesterday':
        date_filter = func.date(SiteVisit.timestamp) == date.today() - timedelta(days=1)
    elif period == 'custom' and (start_date or end_date):
        filters = []
        if start_date:
            try:
                s_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                filters.append(func.date(SiteVisit.timestamp) >= s_date)
            except ValueError: pass
        if end_date:
            try:
                e_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                filters.append(func.date(SiteVisit.timestamp) <= e_date)
            except ValueError: pass
        if filters:
            date_filter = and_(*filters)
    elif period == 'custom' and custom_date:
        try:
            target_date = datetime.strptime(custom_date, '%Y-%m-%d').date()
            date_filter = func.date(SiteVisit.timestamp) == target_date
        except ValueError:
            pass
            
    if date_filter is not None:
        query = query.filter(date_filter)
        
    if referrer_filter:
        refs_ip_query = db.session.query(SiteVisit.visitor_ip).filter(
            SiteVisit.referrer == referrer_filter
        )
        if date_filter is not None:
            refs_ip_query = refs_ip_query.filter(date_filter)
        query = query.filter(SiteVisit.visitor_ip.in_(refs_ip_query))
    elif has_referrer:
        refs_ip_query = db.session.query(SiteVisit.visitor_ip).filter(
            SiteVisit.referrer.isnot(None),
            ~SiteVisit.referrer.contains('://yourlifepathways.com'),
            ~SiteVisit.referrer.contains('://www.yourlifepathways.com'),
            ~SiteVisit.referrer.contains('://localhost'),
            ~SiteVisit.referrer.contains('://127.0.0.1')
        )
        if date_filter is not None:
            refs_ip_query = refs_ip_query.filter(date_filter)
        query = query.filter(SiteVisit.visitor_ip.in_(refs_ip_query))
            
    query = query.group_by(SiteVisit.visitor_ip)
    
    if not show_all:
        query = query.having(func.max(SiteVisit.timestamp) > func.min(SiteVisit.timestamp))
    
    if sort_by == 'views':
        query = query.order_by(func.count(SiteVisit.id).desc(), func.max(SiteVisit.timestamp).desc())
    elif sort_by in ('duration', 'session_length'):
        query = query.order_by((func.max(SiteVisit.timestamp) - func.min(SiteVisit.timestamp)).desc(), func.max(SiteVisit.timestamp).desc())
    else: # Default: recent
        query = query.order_by(func.max(SiteVisit.timestamp).desc())
        
    raw_ip_list = query.all()
    
    # Fetch first user agents to filter bots if needed
    all_ips = [r[0] for r in raw_ip_list]
    ip_to_ua = {}
    if all_ips:
        ua_query = db.session.query(
            SiteVisit.visitor_ip,
            SiteVisit.user_agent
        ).filter(SiteVisit.visitor_ip.in_(all_ips)).distinct(SiteVisit.visitor_ip).order_by(SiteVisit.visitor_ip, SiteVisit.timestamp.asc())
        ip_to_ua = {r[0]: r[1] for r in ua_query.all()}

    # Final list of IPs according to filters
    filtered_ips = []
    for row in raw_ip_list:
        ip_addr = row[0]
        is_auto = is_bot(ip_to_ua.get(ip_addr, ''))
        
        if hide_bots and is_auto:
            continue
        filtered_ips.append(ip_addr)

    if sort_by in ('duration', 'session_length') and filtered_ips:
        from collections import defaultdict
        ip_ts_map = defaultdict(list)
        all_ts_q = db.session.query(SiteVisit.visitor_ip, SiteVisit.timestamp)\
            .filter(SiteVisit.visitor_ip.in_(filtered_ips))
        if date_filter is not None:
            all_ts_q = all_ts_q.filter(date_filter)
        for f_ip, f_ts in all_ts_q.order_by(SiteVisit.visitor_ip, SiteVisit.timestamp.asc()).all():
            ip_ts_map[f_ip].append(f_ts)
        
        def calc_active(ip_addr):
            t_list = ip_ts_map.get(ip_addr, [])
            if len(t_list) < 2:
                return 0
            sessions = []
            curr = [t_list[0]]
            for t in t_list[1:]:
                if (t - curr[-1]).total_seconds() > 1800:
                    sessions.append(curr)
                    curr = [t]
                else:
                    curr.append(t)
            sessions.append(curr)
            return sum(int((s[-1] - s[0]).total_seconds()) for s in sessions)
            
        filtered_ips.sort(key=calc_active, reverse=True)
        
    # Find next and previous
    prev_ip = None
    next_ip = None
    try:
        idx = filtered_ips.index(ip)
        if idx > 0:
            prev_ip = filtered_ips[idx-1]
        if idx < len(filtered_ips) - 1:
            next_ip = filtered_ips[idx+1]
    except ValueError:
        pass # Current IP not in current filtered list
        
    # Lifetime Statistics for this IP
    lifetime_stats = db.session.query(
        func.count(SiteVisit.id).label('total_views'),
        func.count(func.distinct(func.date(SiteVisit.timestamp))).label('total_days'),
        func.min(SiteVisit.timestamp).label('first_ever'),
        func.max(SiteVisit.timestamp).label('last_ever')
    ).filter_by(visitor_ip=ip).first()
    
    lifetime = {
        'views': lifetime_stats.total_views,
        'days': lifetime_stats.total_days,
        'first': lifetime_stats.first_ever,
        'last': lifetime_stats.last_ever,
        'duration': lifetime_stats.last_ever - lifetime_stats.first_ever
    }
        
    # Detailed sequence of pages for a specific IP, limited to the filtered period
    visits_query = SiteVisit.query.filter_by(visitor_ip=ip)
    
    if date_filter is not None:
        visits_query = visits_query.filter(date_filter)
            
    visits = visits_query.order_by(SiteVisit.timestamp.asc()).all()
    
    # Extract referrers natively from the visits to show on the journey page
    referrers = []
    seen = set()
    for v in visits:
        r = v.referrer
        if r and r not in seen and not ('://yourlifepathways.com' in r or '://www.yourlifepathways.com' in r or '://localhost' in r or '://127.0.0.1' in r):
            seen.add(r)
            referrers.append(r)
            
    first_ref = referrers[0] if referrers else None
    search_term = parse_referrer_query(first_ref)
    
    # Identify if bot (check all visits in this journey)
    is_auto_bot_journey = any(is_bot(v.user_agent) for v in visits)
    bot_status = 'auto' if is_auto_bot_journey else None

    # Helper to synthesize raw visits into an Executive Story Analysis and clean human-readable steps
    valid_blog_slugs = {p.slug for p in Post.query.with_entities(Post.slug).all()}

    VALID_STATIC_PATHS = {
        '/',
        '/index.html',
        '/connect',
        '/discovery-call',
        '/overview',
        '/about',
        '/community-involvement-and-mentorship',
        '/educational-institutions',
        '/non-profits-and-mission-driven-organizations',
        '/blog',
        '/main_life_professional_business_leadership_executive_coaching_blog',
        '/cedar_login',
        '/validate-captcha'
    }

    def is_valid_site_path(path):
        if not path or path == '/':
            return True
        if path in VALID_STATIC_PATHS:
            return True
        if path.startswith('/blog/'):
            slug = path[len('/blog/'):].strip('/')
            return slug in valid_blog_slugs
        if any(path.startswith(prefix) for prefix in ('/r=', '/r/', '/i=', '/i/', '/ref=', '/ref/')):
            return True
        if path == '/log_telemetry' or '/signature/' in path or path.startswith('/static/'):
            return True
        return False

    SECTION_NAMES = {
        'intro': 'Introduction & Overview',
        'spotlight': 'Executive Spotlight (Donna Hurley Quote)',
        'pathways': 'Career Pathways & Programs',
        'about_me': 'About Me & Credentials',
        'community': 'Community & Giving Back',
        'cost': 'Pricing & Investment',
        'testimonials': 'Client Testimonials',
        'contact': 'Contact Form & Discovery Call',
        'latest-blog-posts': 'Latest Articles',
        'comments': 'Comments & Discussion',
        'post-content': 'Article Content',
        'ericksonCertModal': 'Erickson Coaching Certification Modal',
        'sapGlobalCoachModal': 'SAP Global Coach Modal',
        'soccerCoachingModal': 'US Soccer Coaching Modal',
        'volleyballCoachingModal': 'Volleyball Coaching Modal',
        'jvVolleyballModal': 'JV Volleyball Coaching Modal',
        'soccerLicenseModal': 'USSF National C License Modal'
    }

    def format_secs(s):
        if s < 60:
            return f"{s}s"
        elif s < 3600:
            return f"{s // 60}m {s % 60}s"
        else:
            return f"{s // 3600}h {(s % 3600) // 60}m"

    def build_session_object(v_list, num):
        from urllib.parse import urlparse, parse_qs
        from models import Post

        s_start = v_list[0].timestamp
        s_end = v_list[-1].timestamp
        s_dur = int((s_end - s_start).total_seconds())

        steps = []
        raw_steps = []
        distinct_pages = set()
        section_dwell = {}
        total_dwell_seconds = 0
        max_overall_depth = 0
        dead_probes_count = 0

        for v in v_list:
            ts = v.timestamp
            url = v.url or ''
            depth = getattr(v, 'scroll_depth', 0) or 0
            s_views = getattr(v, 'section_views', None) or ''

            raw_steps.append({
                'url': url,
                'timestamp': ts,
                'scroll_depth': depth,
                'section_views': s_views
            })

            parsed = urlparse(url)
            path = parsed.path.rstrip('/') or '/'
            frag = parsed.fragment

            # Accumulate dwell from section_views field
            if s_views:
                for part in s_views.split(','):
                    if ':' in part:
                        k, val = part.split(':', 1)
                        try:
                            clean_sec = int(val.rstrip('s'))
                            section_dwell[k] = section_dwell.get(k, 0) + clean_sec
                            total_dwell_seconds += clean_sec
                        except ValueError:
                            pass

            # Handle /log_telemetry queries (fold into previous steps)
            if path == '/log_telemetry':
                qs = parse_qs(parsed.query)
                if 'sections' in qs:
                    for item in qs['sections'][0].split(','):
                        if ':' in item:
                            k, val = item.split(':', 1)
                            try:
                                clean_sec = int(val.rstrip('s'))
                                section_dwell[k] = section_dwell.get(k, 0) + clean_sec
                                total_dwell_seconds += clean_sec
                                if steps and steps[-1].get('item_key') == k:
                                    steps[-1]['active_reading_seconds'] = steps[-1].get('active_reading_seconds', 0) + clean_sec
                            except ValueError:
                                pass
                if 'depth' in qs:
                    try:
                        d_val = int(qs['depth'][0])
                        if d_val > max_overall_depth:
                            max_overall_depth = d_val
                        if steps and d_val > steps[-1]['depth']:
                            steps[-1]['depth'] = d_val
                    except ValueError:
                        pass
                if steps and ts > steps[-1]['end_time']:
                    steps[-1]['end_time'] = ts
                continue

            # Skip standalone email signature fetches from website journey
            if '/signature/' in path:
                continue

            if depth > max_overall_depth:
                max_overall_depth = depth

            is_page_valid = is_valid_site_path(path)

            # Human-friendly action title, name & icon
            if not is_page_valid:
                dead_probes_count += 1
                friendly_name = f"404 Dead Path: {path}"
                friendly_title = f'404 Probe: "{path}" (Non-Existing Page)'
                icon = "fa-solid fa-ban"
                badge_color = "#e53e3e"
                step_type = "probe_404"
                item_key = "404_probes"
                # Do NOT add to distinct_pages!
            elif frag and frag in SECTION_NAMES:
                distinct_pages.add(path)
                friendly_name = SECTION_NAMES[frag]
                friendly_title = f"Explored Section: {friendly_name}"
                icon = "fa-solid fa-compass"
                badge_color = "#3182ce"
                step_type = "section"
                item_key = frag
            elif path == '/':
                distinct_pages.add(path)
                friendly_name = "Homepage"
                friendly_title = "Landed on Homepage" if not steps else "Returned to Homepage"
                icon = "fa-solid fa-house"
                badge_color = "#2e7d32"
                step_type = "page"
                item_key = "homepage"
            elif path.startswith('/blog/'):
                distinct_pages.add(path)
                slug = path.replace('/blog/', '')
                try:
                    post = Post.query.filter_by(slug=slug).first()
                    p_title = post.title if post else slug.replace('-', ' ').title()
                except Exception:
                    p_title = slug.replace('-', ' ').title()
                friendly_name = f'Blog: "{p_title}"'
                friendly_title = f'Read Blog: "{p_title}"'
                icon = "fa-solid fa-newspaper"
                badge_color = "#805ad5"
                step_type = "blog"
                item_key = path
            elif path == '/non-profits-and-mission-driven-organizations':
                distinct_pages.add(path)
                friendly_name = "Non-Profits & Mission-Driven Organizations"
                friendly_title = "Viewed: Non-Profits & Mission-Driven Organizations"
                icon = "fa-solid fa-handshake-angle"
                badge_color = "#319795"
                step_type = "page"
                item_key = path
            elif path == '/connect' or path == '/discovery-call':
                distinct_pages.add(path)
                friendly_name = "Connect & Discovery Booking"
                friendly_title = "Viewed: Connect & Discovery Booking"
                icon = "fa-solid fa-calendar-check"
                badge_color = "#dd6b20"
                step_type = "page"
                item_key = path
            elif path == '/overview' or path == '/about':
                distinct_pages.add(path)
                clean_name = path.strip('/').replace('-', ' ').title()
                friendly_name = clean_name
                friendly_title = f"Viewed Page: {clean_name}"
                icon = "fa-solid fa-circle-info"
                badge_color = "#3182ce"
                step_type = "page"
                item_key = path
            else:
                distinct_pages.add(path)
                clean_name = path.strip('/').replace('-', ' ').title()
                friendly_name = clean_name
                friendly_title = f"Viewed Page: {clean_name}"
                icon = "fa-solid fa-globe"
                badge_color = "#4a5568"
                step_type = "page"
                item_key = path

            # Consolidate consecutive identical actions
            if steps and steps[-1]['title'] == friendly_title:
                steps[-1]['count'] += 1
                steps[-1]['end_time'] = ts
                if depth > steps[-1]['depth']:
                    steps[-1]['depth'] = depth
            else:
                steps.append({
                    'title': friendly_title,
                    'item_name': friendly_name,
                    'item_key': item_key,
                    'icon': icon,
                    'badge_color': badge_color,
                    'step_type': step_type,
                    'is_404': not is_page_valid,
                    'url': url,
                    'timestamp': ts,
                    'end_time': ts,
                    'depth': depth,
                    'count': 1,
                    'duration_seconds': 0,
                    'formatted_duration': '',
                    'active_reading_seconds': 0,
                    'section_views': s_views
                })

        # Calculate time spent on each step
        session_end = v_list[-1].timestamp
        for i, step in enumerate(steps):
            if i < len(steps) - 1:
                next_ts = steps[i+1]['timestamp']
                dur = max(0, int((next_ts - step['timestamp']).total_seconds()))
            else:
                dur = max(0, int((session_end - step['timestamp']).total_seconds()))

            if step['end_time'] > step['timestamp']:
                end_diff = int((step['end_time'] - step['timestamp']).total_seconds())
                if end_diff > dur:
                    dur = end_diff

            if step.get('active_reading_seconds', 0) > dur:
                dur = step['active_reading_seconds']

            step['duration_seconds'] = dur
            step['formatted_duration'] = format_secs(dur) if dur > 0 else "< 1s"

        # Calculate aggregated time spent per section and page across the session
        content_breakdown = {}
        for step in steps:
            k = step.get('item_key') or 'other'
            if k not in content_breakdown:
                content_breakdown[k] = {
                    'key': k,
                    'name': step.get('item_name') or step['title'],
                    'icon': step['icon'],
                    'type': step['step_type'],
                    'elapsed_seconds': 0,
                    'active_reading_seconds': 0,
                    'views_count': 0
                }
            content_breakdown[k]['elapsed_seconds'] += step['duration_seconds']
            content_breakdown[k]['active_reading_seconds'] += step.get('active_reading_seconds', 0)
            content_breakdown[k]['views_count'] += step.get('count', 1)

        # Consolidate 404 dead routes in breakdown
        if '404_probes' in content_breakdown:
            content_breakdown['404_probes']['name'] = f"Dead Routes Probed (404s: {dead_probes_count} attempts)"
            content_breakdown['404_probes']['icon'] = "fa-solid fa-triangle-exclamation"

        # Merge telemetry dwell times into content_breakdown
        for sec_k, d_sec in section_dwell.items():
            if sec_k in content_breakdown:
                if d_sec > content_breakdown[sec_k]['active_reading_seconds']:
                    content_breakdown[sec_k]['active_reading_seconds'] = d_sec
            else:
                content_breakdown[sec_k] = {
                    'key': sec_k,
                    'name': SECTION_NAMES.get(sec_k, sec_k.title()),
                    'icon': 'fa-solid fa-compass',
                    'type': 'section',
                    'elapsed_seconds': d_sec,
                    'active_reading_seconds': d_sec,
                    'views_count': 1
                }

        section_breakdown = []
        for item in content_breakdown.values():
            eff_secs = max(item['elapsed_seconds'], item['active_reading_seconds'])
            if eff_secs > 0:
                item['total_seconds'] = eff_secs
                item['formatted_total'] = format_secs(eff_secs)
                item['formatted_active'] = format_secs(item['active_reading_seconds'])
                section_breakdown.append(item)

        # Sort by highest time spent first
        section_breakdown.sort(key=lambda x: x['total_seconds'], reverse=True)

        # Top attention sections (sorted by dwell time)
        top_sections = []
        for sec_id, secs in sorted(section_dwell.items(), key=lambda x: x[1], reverse=True)[:5]:
            top_sections.append({
                'id': sec_id,
                'name': SECTION_NAMES.get(sec_id, sec_id.title()),
                'seconds': secs,
                'formatted': format_secs(secs)
            })

        # Engagement level badge
        if dead_probes_count >= 2 and (dead_probes_count / max(1, len(steps))) >= 0.3:
            engagement = {'label': 'Automated 404 Scanner (Bot)', 'color': '#c53030', 'bg': '#fff5f5', 'icon': 'fa-solid fa-shield-virus'}
        elif max_overall_depth >= 85 or total_dwell_seconds >= 120:
            engagement = {'label': 'High Engagement (Deep Read)', 'color': '#2e7d32', 'bg': '#e8f5e9', 'icon': 'fa-solid fa-fire'}
        elif max_overall_depth >= 45 or total_dwell_seconds >= 30:
            engagement = {'label': 'Moderate Engagement', 'color': '#1976d2', 'bg': '#e3f2fd', 'icon': 'fa-solid fa-chart-line'}
        else:
            engagement = {'label': 'Quick Skim', 'color': '#f57c00', 'bg': '#fff3e0', 'icon': 'fa-solid fa-eye'}

        analysis = {
            'unique_pages_count': max(1 if distinct_pages else 0, len(distinct_pages)),
            'distinct_pages': list(distinct_pages),
            'dead_probes_count': dead_probes_count,
            'top_sections': top_sections,
            'section_breakdown': section_breakdown,
            'total_dwell_seconds': total_dwell_seconds,
            'formatted_dwell': format_secs(total_dwell_seconds),
            'max_depth': max_overall_depth,
            'engagement': engagement
        }

        return {
            'num': num,
            'start': s_start,
            'end': s_end,
            'duration_seconds': s_dur,
            'visits': v_list,
            'steps': steps,
            'raw_steps': raw_steps,
            'raw_count': len(v_list),
            'analysis': analysis
        }

    # Group visits into distinct sessions using standard 30-minute inactivity threshold
    sessions = []
    current_session_visits = []
    
    for v in visits:
        if not current_session_visits:
            current_session_visits.append(v)
        else:
            prev_v = current_session_visits[-1]
            time_diff = (v.timestamp - prev_v.timestamp).total_seconds()
            if time_diff > 1800: # > 30 min gap -> new session
                sessions.append(build_session_object(current_session_visits, len(sessions) + 1))
                current_session_visits = [v]
            else:
                current_session_visits.append(v)
                
    if current_session_visits:
        sessions.append(build_session_object(current_session_visits, len(sessions) + 1))
        
    total_active_seconds = sum(s['duration_seconds'] for s in sessions)
    
    # Auto-flag as bot if multiple dead 404 paths were scanned
    has_scanner_behavior = any(s['analysis'].get('dead_probes_count', 0) >= 2 for s in sessions)
    if has_scanner_behavior:
        is_auto_bot_journey = True
        bot_status = 'auto'

    return render_template('admin/journey_details.html', 
                          ip=ip, 
                          visits=visits, 
                          sessions=sessions,
                          total_active_seconds=total_active_seconds,
                          prev_ip=prev_ip,
                          next_ip=next_ip,
                          bot_status=bot_status,
                          lifetime=lifetime,
                          period=period,
                          custom_date=custom_date,
                          start_date=start_date,
                          end_date=end_date,
                          has_referrer=has_referrer,
                          referrer_filter=referrer_filter,
                          show_all=show_all,
                          hide_bots=hide_bots,
                          sort_by=sort_by,
                          referrers=referrers,
                          search_term=search_term,
                          noindex=True)

@admin_bp.route('/tracking/cleanup', methods=['POST'])
@admin_required
def cleanup_tracking_data():
    """Delete old tracking data to manage database size"""
    from datetime import datetime, timedelta, timezone
    
    months = int(request.form.get('months', 12))
    execute = request.form.get('execute') == 'true'
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=30 * months)
    
    # Count rows to be deleted
    old_site_visits = SiteVisit.query.filter(SiteVisit.timestamp < cutoff_date).count()
    old_post_views = PostView.query.filter(PostView.timestamp < cutoff_date).count()
    total_to_delete = old_site_visits + old_post_views
    
    if not execute:
        # Preview mode - just return counts
        estimated_mb = ((old_site_visits * 500) + (old_post_views * 200)) / (1024 * 1024)
        return jsonify({
            'success': True,
            'preview': True,
            'months': months,
            'cutoff_date': cutoff_date.strftime('%Y-%m-%d'),
            'site_visits': old_site_visits,
            'post_views': old_post_views,
            'total': total_to_delete,
            'estimated_mb': round(estimated_mb, 2)
        })
    
    # Execute mode - actually delete
    try:
        SiteVisit.query.filter(SiteVisit.timestamp < cutoff_date).delete()
        PostView.query.filter(PostView.timestamp < cutoff_date).delete()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'preview': False,
            'deleted': total_to_delete,
            'message': f'Successfully deleted {total_to_delete:,} rows older than {months} months'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_bp.route('/update-ip-location', methods=['POST'])
@admin_required
def update_ip_location():
    data = request.json
    ip = data.get('ip')
    location = data.get('location')
    
    if ip and location:
        # Update both tables for this IP
        SiteVisit.query.filter_by(visitor_ip=ip).update({SiteVisit.visitor_location: location})
        PostView.query.filter_by(visitor_ip=ip).update({PostView.visitor_location: location})
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False}), 400

@admin_bp.route('/security/change-password', methods=['GET', 'POST'])
@admin_required
def change_password():
    if request.method == 'POST':
        current_pw = request.form.get('current_password')
        new_pw = request.form.get('new_password')
        confirm_pw = request.form.get('confirm_password')
        
        if not check_password_hash(current_user.password_hash, current_pw):
            flash('Current password incorrect.', 'danger')
        elif new_pw != confirm_pw:
            flash('New passwords do not match.', 'danger')
        elif len(new_pw) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
        else:
            current_user.password_hash = generate_password_hash(new_pw)
            db.session.commit()
            flash('Password updated successfully!', 'success')
            return redirect(url_for('admin.dashboard'))
            
    return render_template('admin/change_password.html', noindex=True)

@admin_bp.route('/settings/resilience')
@admin_required
def database_resilience():
    # Calculate database stats for display
    total_site_visits = SiteVisit.query.count()
    total_post_views = PostView.query.count()
    
    # Estimate database size (rough calculation)
    estimated_mb = ((total_site_visits * 500) + (total_post_views * 200)) / (1024 * 1024)
    
    # Calculate data by age
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    
    older_than_12m = SiteVisit.query.filter(SiteVisit.timestamp < now - timedelta(days=365)).count()
    older_than_6m = SiteVisit.query.filter(SiteVisit.timestamp < now - timedelta(days=182)).count()
    older_than_3m = SiteVisit.query.filter(SiteVisit.timestamp < now - timedelta(days=91)).count()
    
    db_stats = {
        'total_visits': total_site_visits,
        'total_post_views': total_post_views,
        'estimated_mb': round(estimated_mb, 2),
        'older_than_12m': older_than_12m,
        'older_than_6m': older_than_6m,
        'older_than_3m': older_than_3m
    }
    
    return render_template('admin/resilience.html', db_stats=db_stats, noindex=True)

@admin_bp.route('/security/export-backup')
@admin_required
def export_data():
    from models import User, Post, Comment, PostLike, PostShare, PostView, LoginHistory
    import json
    from datetime import datetime

    def dump_table(model):
        return [
            {column.name: getattr(row, column.name).isoformat() if isinstance(getattr(row, column.name), datetime) else getattr(row, column.name) 
             for column in model.__table__.columns}
            for row in model.query.all()
        ]

    backup = {
        "users": dump_table(User),
        "posts": dump_table(Post),
        "comments": dump_table(Comment),
        "likes": dump_table(PostLike),
        "shares": dump_table(PostShare),
        "views": dump_table(PostView),
        "login_history": dump_table(LoginHistory),
        "exported_at": datetime.utcnow().isoformat()
    }

    response = make_response(jsonify(backup))
    filename = f"yourlifepathways_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response

@admin_bp.route('/security/import-backup', methods=['POST'])
@admin_required
def import_data():
    if 'backup_file' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('admin.change_password'))
    
    file = request.files['backup_file']
    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(url_for('admin.change_password'))

    if file:
        import json
        from datetime import datetime
        from models import User, Post, Comment, PostLike, PostShare, PostView, LoginHistory

        try:
            data = json.load(file)
            
            # Wiping old data (careful order)
            LoginHistory.query.delete()
            PostLike.query.delete()
            PostShare.query.delete()
            PostView.query.delete()
            Comment.query.delete()
            Post.query.delete()
            User.query.delete()
            db.session.commit()

            # 1. Users
            for u_data in data.get('users', []):
                db.session.add(User(**u_data))
            
            # 2. Posts
            for p_data in data.get('posts', []):
                p_data['date_created'] = datetime.fromisoformat(p_data['date_created'])
                p_data['updated_date'] = datetime.fromisoformat(p_data['updated_date'])
                db.session.add(Post(**p_data))
            
            db.session.commit()

            # 3. Comments & Engagement
            for c_data in data.get('comments', []):
                c_data['date_created'] = datetime.fromisoformat(c_data['date_created'])
                db.session.add(Comment(**c_data))

            for l_data in data.get('likes', []):
                if l_data.get('timestamp'): l_data['timestamp'] = datetime.fromisoformat(l_data['timestamp'])
                db.session.add(PostLike(**l_data))

            for s_data in data.get('shares', []):
                if s_data.get('timestamp'): s_data['timestamp'] = datetime.fromisoformat(s_data['timestamp'])
                db.session.add(PostShare(**s_data))

            for v_data in data.get('views', []):
                if v_data.get('timestamp'): v_data['timestamp'] = datetime.fromisoformat(v_data['timestamp'])
                db.session.add(PostView(**v_data))

            for h_data in data.get('login_history', []):
                if h_data.get('timestamp'): h_data['timestamp'] = datetime.fromisoformat(h_data['timestamp'])
                db.session.add(LoginHistory(**h_data))

            db.session.commit()
            flash('Database successfully restored from backup!', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Restoration failed: {str(e)}', 'danger')
            
    return redirect(url_for('admin.change_password'))

# --- One-time setup: Create admin ---
# You can delete this after using it or use a script
@admin_bp.route('/initialize-gateway-erez', methods=['GET'])
def create_initial_admin():
    if User.query.filter_by(username='admin').first():
        return "Gateway already initialized."
    
    # Ideally, pull this from .env or a secure place
    hashed_pw = generate_password_hash('ChangeMe123!') # Temp password
    new_user = User(username='admin', password_hash=hashed_pw)
    db.session.add(new_user)
    db.session.commit()
    return "Gateway initialized. Username: admin, Password: ChangeMe123! - PLEASE CHANGE PASSWORD IMMEDIATELY."

@admin_bp.route('/')
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    from sqlalchemy import func
    from datetime import datetime
    posts = Post.query.order_by(Post.date_created.desc()).all()
    view_counts = dict(
        db.session.query(PostView.post_id, func.count(PostView.id))
        .group_by(PostView.post_id)
        .all()
    )

    # Determine last login timestamp to calculate new views
    last_login_time = None
    last_login_iso = session.get('last_login_time')
    if last_login_iso:
        try:
            last_login_time = datetime.fromisoformat(last_login_iso)
        except Exception:
            last_login_time = None

    # Fallback to LoginHistory if not present in session (e.g. session active before this update)
    if not last_login_time and current_user.is_authenticated:
        recent_logins = LoginHistory.query.filter_by(
            user_id=current_user.id,
            status='success'
        ).order_by(LoginHistory.timestamp.desc()).limit(2).all()

        if len(recent_logins) >= 2:
            last_login_time = recent_logins[1].timestamp
        elif len(recent_logins) == 1:
            last_login_time = recent_logins[0].timestamp

        if last_login_time:
            session['last_login_time'] = last_login_time.isoformat()

    new_view_counts = {}
    if last_login_time:
        try:
            new_views_query = (
                db.session.query(PostView.post_id, func.count(PostView.id))
                .filter(PostView.timestamp >= last_login_time)
                .group_by(PostView.post_id)
                .all()
            )
            new_view_counts = dict(new_views_query)
        except Exception as e:
            print(f"Error querying new views since last login: {e}")
            new_view_counts = {}

    for post in posts:
        post.view_count = view_counts.get(post.id, 0)
        post.new_views = new_view_counts.get(post.id, 0)

    return render_template(
        'admin/dashboard.html',
        posts=posts,
        last_login_time=last_login_time,
        noindex=True
    )

@admin_bp.route('/post/new', methods=['GET', 'POST'])
@admin_required
def new_post():
    if request.method == 'POST':
        title = request.form.get('title')
        slug = request.form.get('slug')
        summary = request.form.get('summary')
        content = request.form.get('content')
        image_file = request.form.get('image_file', 'default.jpg')
        category = request.form.get('category')
        canonical_url = request.form.get('canonical_url', '').strip() or None
        
        # Ensure we have a valid slug
        final_slug = slugify(slug if slug else title)
        
        post = Post(
            title=title,
            slug=final_slug,
            summary=summary,
            content=content,
            image_file=image_file,
            category=category,
            canonical_url=canonical_url
        )
        db.session.add(post)
        db.session.commit()
        flash('Post created successfully!', 'success')
        return redirect(url_for('admin.dashboard'))
    
    return render_template('admin/edit_post.html', post=None, noindex=True)

@admin_bp.route('/post/<int:post_id>/views-analytics')
@admin_required
def post_views_analytics(post_id):
    from sqlalchemy import func
    from datetime import datetime
    from utils import parse_user_agent

    post = Post.query.get_or_404(post_id)

    # 1. Determine last login timestamp
    last_login_time = None
    last_login_iso = session.get('last_login_time')
    if last_login_iso:
        try:
            last_login_time = datetime.fromisoformat(last_login_iso)
        except Exception:
            last_login_time = None

    if not last_login_time and current_user.is_authenticated:
        recent_logins = LoginHistory.query.filter_by(
            user_id=current_user.id,
            status='success'
        ).order_by(LoginHistory.timestamp.desc()).limit(2).all()

        if len(recent_logins) >= 2:
            last_login_time = recent_logins[1].timestamp
        elif len(recent_logins) == 1:
            last_login_time = recent_logins[0].timestamp

    # 2. Total & new counts
    total_views_count = PostView.query.filter_by(post_id=post.id).count()
    new_views_count = 0
    if last_login_time:
        new_views_count = PostView.query.filter_by(post_id=post.id).filter(PostView.timestamp >= last_login_time).count()

    # 3. Filter mode
    filter_mode = request.args.get('filter', '')
    if not filter_mode:
        if request.args.get('since_login') == 'true' or new_views_count > 0:
            filter_mode = 'new'
        else:
            filter_mode = 'all'

    # 4. Fetch PostViews according to filter
    pv_query = PostView.query.filter_by(post_id=post.id)
    if filter_mode == 'new' and last_login_time:
        pv_query = pv_query.filter(PostView.timestamp >= last_login_time)
    views_records = pv_query.order_by(PostView.timestamp.desc()).limit(300).all()

    # 5. Enrich with SiteVisit telemetry (scroll depth, section dwell time, referrer)
    ips = list({v.visitor_ip for v in views_records if v.visitor_ip})
    site_visits_by_ip = {}
    if ips:
        matching_visits = SiteVisit.query.filter(
            SiteVisit.visitor_ip.in_(ips),
            SiteVisit.url.contains(post.slug)
        ).order_by(SiteVisit.timestamp.desc()).all()
        for sv in matching_visits:
            if sv.visitor_ip not in site_visits_by_ip:
                site_visits_by_ip[sv.visitor_ip] = []
            site_visits_by_ip[sv.visitor_ip].append(sv)

    view_items = []
    unique_locations = set()

    for pv in views_records:
        sv_candidates = site_visits_by_ip.get(pv.visitor_ip, [])
        best_sv = None
        min_diff = None
        for sv in sv_candidates:
            diff = abs((sv.timestamp - pv.timestamp).total_seconds()) if (sv.timestamp and pv.timestamp) else 999999
            if min_diff is None or diff < min_diff:
                min_diff = diff
                best_sv = sv

        loc = pv.visitor_location or (best_sv.visitor_location if best_sv else 'Unknown')
        if loc and loc != 'Unknown':
            unique_locations.add(loc)

        depth = getattr(best_sv, 'scroll_depth', 0) if best_sv else 0
        sections = getattr(best_sv, 'section_views', None) if best_sv else None
        referrer = best_sv.referrer if best_sv else None
        is_new = bool(last_login_time and pv.timestamp and pv.timestamp >= last_login_time)

        view_items.append({
            'id': pv.id,
            'timestamp': pv.timestamp,
            'ip': pv.visitor_ip,
            'location': loc or 'Unknown Location',
            'device': parse_user_agent(pv.user_agent),
            'scroll_depth': depth or 0,
            'section_views': sections or '',
            'referrer': referrer,
            'is_new': is_new
        })

    return render_template(
        'admin/post_views_analytics.html',
        post=post,
        views=view_items,
        total_views_count=total_views_count,
        new_views_count=new_views_count,
        filter_mode=filter_mode,
        last_login_time=last_login_time,
        unique_locations_count=len(unique_locations),
        noindex=True
    )

@admin_bp.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    if request.method == 'POST':
        post.title = request.form.get('title')
        slug = request.form.get('slug')
        post.summary = request.form.get('summary')
        post.content = request.form.get('content')
        post.image_file = request.form.get('image_file')
        post.category = request.form.get('category')
        post.canonical_url = request.form.get('canonical_url', '').strip() or None
        post.slug = slugify(slug if slug else post.title)
        
        db.session.commit()
        flash('Post updated successfully!', 'success')
        return redirect(url_for('admin.dashboard'))
    
    return render_template('admin/edit_post.html', post=post, noindex=True)

@admin_bp.route('/post/<int:post_id>/toggle-delete', methods=['POST'])
@admin_required
def toggle_delete(post_id):
    post = Post.query.get_or_404(post_id)
    post.is_deleted = not post.is_deleted
    db.session.commit()
    status = 'archived' if post.is_deleted else 'restored'
    message = f'Post {status} successfully!'
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"success": True, "message": message})
        
    flash(message, 'success')
    return redirect(url_for('admin.dashboard', admin='true'))

@admin_bp.route('/comments')
@admin_required
def manage_comments():
    comments = Comment.query.order_by(Comment.is_approved.asc(), Comment.date_created.desc()).all()
    return render_template('admin/comments.html', comments=comments, noindex=True)

@admin_bp.route('/comment/<int:comment_id>/toggle-approve', methods=['POST'])
@admin_required
def toggle_approve_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    was_approved = comment.is_approved
    comment.is_approved = not comment.is_approved
    db.session.commit()
    status = 'approved' if comment.is_approved else 'unapproved'
    message = f'Comment {status}!'

    if comment.is_approved and not was_approved and comment.email:
        post = Post.query.get(comment.post_id)
        if post:
            executor.submit(send_comment_approval_email, comment.name, comment.email, post.title, post.slug)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"success": True, "message": message})

    flash(message, 'success')
    return redirect(url_for('admin.manage_comments', admin='true'))

@admin_bp.route('/comment/<int:comment_id>/toggle-delete', methods=['POST'])
@admin_required
def toggle_delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    comment.is_deleted = not comment.is_deleted
    db.session.commit()
    status = 'archived' if comment.is_deleted else 'restored'
    message = f'Comment {status}!'

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"success": True, "message": message})

    flash(message, 'success')
    return redirect(url_for('admin.manage_comments'))

@admin_bp.route('/comment/<int:comment_id>/reply', methods=['POST'])
@admin_required
def reply_to_comment(comment_id):
    parent_comment = Comment.query.get_or_404(comment_id)
    content = request.form.get('reply_content')
    
    if content:
        new_reply = Comment(
            name="Erez Asif",  # Official identity
            content=content,
            post_id=parent_comment.post_id,
            parent_id=parent_comment.id,
            is_approved=True # Admin responses are auto-approved
        )
        db.session.add(new_reply)
        # Auto-approve the parent comment if an admin is responding to it
        parent_comment.is_approved = True
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": True, "message": "Reply posted successfully!"})
            
        flash('Reply posted!', 'success')
        
    return redirect(url_for('admin.manage_comments'))

@admin_bp.route('/likes')
@admin_required
def manage_likes():
    from models import PostLike, SiteVisit
    from sqlalchemy import func
    from utils import get_ip_location

    likes_raw = db.session.query(PostLike, Post.title, Post.slug)\
        .join(Post, PostLike.post_id == Post.id)\
        .order_by(PostLike.timestamp.desc())\
        .all()

    # Pre-fetch known locations from SiteVisit
    ip_list = [like.visitor_ip for like, _, _ in likes_raw if like.visitor_ip]
    ip_locations = {}
    if ip_list:
        loc_rows = db.session.query(SiteVisit.visitor_ip, func.max(SiteVisit.visitor_location))\
            .filter(SiteVisit.visitor_ip.in_(ip_list), SiteVisit.visitor_location.isnot(None))\
            .group_by(SiteVisit.visitor_ip)\
            .all()
        ip_locations = {ip: loc for ip, loc in loc_rows if loc}

    likes_data = []
    for like, post_title, post_slug in likes_raw:
        loc = ip_locations.get(like.visitor_ip)
        if not loc and like.visitor_ip:
            loc = get_ip_location(like.visitor_ip)
            if loc and loc != "Location unavailable":
                ip_locations[like.visitor_ip] = loc
        likes_data.append({
            'timestamp': like.timestamp,
            'post_title': post_title,
            'post_slug': post_slug,
            'visitor_ip': like.visitor_ip,
            'location': loc or 'Location unavailable',
            'is_deleted': like.is_deleted
        })

    return render_template('admin/likes.html', likes=likes_data, noindex=True)


@admin_bp.route('/email-tracking')
@admin_required
def email_tracking():
    from urllib.parse import unquote
    opens = EmailOpen.query.order_by(EmailOpen.timestamp.desc()).limit(150).all()
    for o in opens:
        if o.location:
            o.location = unquote(o.location)
    return render_template('admin/email_tracking.html', opens=opens, noindex=True)


@admin_bp.route('/email-tracking/<int:entry_id>/delete', methods=['POST'])
@admin_required
def delete_email_open(entry_id):
    entry = EmailOpen.query.get_or_404(entry_id)
    db.session.delete(entry)
    db.session.commit()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({'status': 'success', 'message': 'Entry deleted'})
    flash('Email read entry deleted.', 'success')
    return redirect(url_for('admin.email_tracking'))


@admin_bp.route('/email-tracking/clear-all', methods=['POST'])
@admin_required
def clear_all_email_opens():
    EmailOpen.query.delete()
    db.session.commit()
    flash('All email read entries cleared.', 'success')
    return redirect(url_for('admin.email_tracking'))
