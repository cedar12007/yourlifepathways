#!/usr/bin/env python3
"""
Database Cleanup Script for Tracking Data

Run this periodically (e.g., monthly via cron) to keep database size manageable.
Keeps last 12 months of tracking data by default.
"""

import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

from flask import Flask
from extensions import db
from models import SiteVisit, PostView

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def cleanup_old_data(months_to_keep=12, dry_run=True):
    """
    Delete tracking data older than specified months.
    
    Args:
        months_to_keep: Number of months of data to retain (default: 12)
        dry_run: If True, only count rows without deleting (default: True)
    """
    with app.app_context():
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=30 * months_to_keep)
        
        # Count rows to be deleted
        old_site_visits = SiteVisit.query.filter(SiteVisit.timestamp < cutoff_date).count()
        old_post_views = PostView.query.filter(PostView.timestamp < cutoff_date).count()
        
        print(f"\n{'=' * 60}")
        print(f"Cleanup Analysis (keeping last {months_to_keep} months)")
        print(f"{'=' * 60}")
        print(f"Cutoff date: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\nRows to delete:")
        print(f"  - SiteVisit: {old_site_visits:,}")
        print(f"  - PostView: {old_post_views:,}")
        print(f"  - Total: {old_site_visits + old_post_views:,}")
        
        # Estimate space savings (rough estimate)
        estimated_mb = ((old_site_visits * 500) + (old_post_views * 200)) / (1024 * 1024)
        print(f"\nEstimated space to reclaim: ~{estimated_mb:.2f} MB")
        
        if dry_run:
            print(f"\n⚠️  DRY RUN MODE - No data will be deleted")
            print(f"To actually delete, run: python cleanup_old_tracking.py --execute")
        else:
            print(f"\n⚠️  EXECUTING DELETION...")
            try:
                # Delete old data
                SiteVisit.query.filter(SiteVisit.timestamp < cutoff_date).delete()
                PostView.query.filter(PostView.timestamp < cutoff_date).delete()
                db.session.commit()
                print(f"✅ Successfully deleted {old_site_visits + old_post_views:,} rows")
                
                # Recommend VACUUM for PostgreSQL
                print(f"\n💡 Tip: Run 'VACUUM FULL;' on your Supabase database to reclaim disk space")
                
            except Exception as e:
                db.session.rollback()
                print(f"❌ Error during cleanup: {e}")
                raise
        
        print(f"{'=' * 60}\n")

def cleanup_noise_data(days=7, include_bots=True, dry_run=True):
    """
    Delete sub-second drive-by visits (< 1s) with no telemetry and detected bots.
    """
    with app.app_context():
        from routes_admin import purge_noise_visits
        print(f"\n{'=' * 60}")
        print(f"Noise Traffic Cleanup Analysis (older than {days} days, include bots: {include_bots})")
        print(f"{'=' * 60}")
        result = purge_noise_visits(older_than_days=days, include_bots=include_bots, dry_run=dry_run)
        print(f"Noise visits identified: {result['total_visits']:,} across {result['unique_ips']:,} IPs")
        print(f"Estimated space to reclaim: ~{result['estimated_kb']:.1f} KB")
        if dry_run:
            print("\n⚠️  DRY RUN MODE - No data deleted.")
            print(f"To actually delete, run: python cleanup_old_tracking.py --clean-noise --days={days} --execute")
        else:
            print(f"\n✅ Successfully deleted {result['total_visits']:,} noise visits!")
        print(f"{'=' * 60}\n")

if __name__ == '__main__':
    import sys
    
    execute = '--execute' in sys.argv
    clean_noise = '--clean-noise' in sys.argv
    no_bots = '--no-bots' in sys.argv

    if clean_noise:
        days = 7
        for arg in sys.argv:
            if arg.startswith('--days='):
                days = int(arg.split('=')[1])
        cleanup_noise_data(days=days, include_bots=not no_bots, dry_run=not execute)
    else:
        months = 12
        for arg in sys.argv:
            if arg.startswith('--months='):
                months = int(arg.split('=')[1])
        cleanup_old_data(months_to_keep=months, dry_run=not execute)
