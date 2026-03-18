from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify, make_response
from datetime import timedelta
from models import Post, Comment, User, LoginHistory, db, SiteVisit, PostView
from utils import slugify, parse_user_agent
from routes_blog import is_admin
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
    
    # If any query parameters exist, we respect the checkbox state (missing = unchecked)
    # If no parameters exist (first load), we default to True
    if request.args:
        hide_bots = request.args.get('hide_bots') == 'true'
    else:
        hide_bots = True
        
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
            ~SiteVisit.referrer.contains('://yourlifepathways.com'),
            ~SiteVisit.referrer.contains('://www.yourlifepathways.com'),
            ~SiteVisit.referrer.contains('://localhost'),
            ~SiteVisit.referrer.contains('://127.0.0.1')
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
        ~SiteVisit.referrer.contains('://yourlifepathways.com'),
        ~SiteVisit.referrer.contains('://www.yourlifepathways.com'),
        ~SiteVisit.referrer.contains('://localhost'),
        ~SiteVisit.referrer.contains('://127.0.0.1')
    )
    if date_filter is not None:
        top_refs_query = top_refs_query.filter(date_filter)
        
    top_referrers = top_refs_query.group_by(SiteVisit.referrer).order_by(func.count(func.distinct(SiteVisit.visitor_ip)).desc()).limit(20).all()
    
    # 5. Apply Sorting and Execute main query with limit
    if sort_by == 'views':
        query = query.order_by(func.count(SiteVisit.id).desc(), func.max(SiteVisit.timestamp).desc())
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
    
    from utils import is_bot, parse_user_agent, parse_referrer_query
    from models import ManualBot
    
    manual_bot_ips = {b.ip_address for b in ManualBot.query.all()}
    journeys = []
    
    for row in raw_journeys:
        # Tuple unpacking: ip, location, first, last, views
        ip, loc, first, last, views = row
        ua = ip_to_ua.get(ip, 'Unknown')
        referrers = ip_to_referrers.get(ip, []) if ip_list else []
        clean_ua = parse_user_agent(ua)
        
        is_auto_bot = is_bot(ua)
        is_manual_bot = ip in manual_bot_ips
        
        bot_status = None
        if is_manual_bot:
            bot_status = 'manual'
        elif is_auto_bot:
            bot_status = 'auto'

        if hide_bots and bot_status:
            continue
            
        first_ref = referrers[0] if referrers else None
        search_term = parse_referrer_query(first_ref)
        
        lifetime = ip_to_lifetime.get(ip, {'views': views, 'days': 1, 'first': first})
        
        journeys.append((ip, loc, first, last, views, referrers, clean_ua, search_term, bot_status, lifetime))
    
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
    hide_bots = request.args.get('hide_bots', 'true') == 'true'
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

    from models import ManualBot
    manual_bot_ips = {b.ip_address for b in ManualBot.query.all()}

    # Final list of IPs according to filters
    filtered_ips = []
    for row in raw_ip_list:
        ip_addr = row[0]
        is_auto = is_bot(ip_to_ua.get(ip_addr, ''))
        is_manual = ip_addr in manual_bot_ips
        
        if hide_bots and (is_auto or is_manual):
            continue
        filtered_ips.append(ip_addr)
        
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
    is_manual_bot_journey = ip in manual_bot_ips
    
    bot_status = 'manual' if is_manual_bot_journey else ('auto' if is_auto_bot_journey else None)

    return render_template('admin/journey_details.html', 
                          ip=ip, 
                          visits=visits, 
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
@admin_required
def dashboard():
    posts = Post.query.order_by(Post.date_created.desc()).all()
    return render_template('admin/dashboard.html', posts=posts, noindex=True)

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
    comment.is_approved = not comment.is_approved
    db.session.commit()
    status = 'approved' if comment.is_approved else 'unapproved'
    message = f'Comment {status}!'

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
    from models import PostLike
    likes = db.session.query(PostLike, Post.title, Post.slug).join(Post, PostLike.post_id == Post.id).order_by(PostLike.timestamp.desc()).all()
    return render_template('admin/likes.html', likes=likes, noindex=True)

@admin_bp.route('/tracking/bot/toggle/<string:ip>', methods=['POST'])
@admin_required
def toggle_manual_bot(ip):
    from models import ManualBot
    bot = ManualBot.query.filter_by(ip_address=ip).first()
    if bot:
        db.session.delete(bot)
        db.session.commit()
        return jsonify({'status': 'success', 'bot_status': None})
    else:
        new_bot = ManualBot(ip_address=ip)
        db.session.add(new_bot)
        db.session.commit()
        return jsonify({'status': 'success', 'bot_status': 'manual'})
