#!/usr/bin/env python3
"""
Script to list all blog posts and their slugs.
Useful for identifying which posts need canonical URLs set.
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def list_posts():
    """List all active blog posts"""
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("ERROR: DATABASE_URL not found in environment variables")
        sys.exit(1)
    
    print("Connecting to database...")
    engine = create_engine(database_url)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT id, title, slug, canonical_url, date_created 
                    FROM ylp_posts 
                    WHERE is_deleted = false 
                    ORDER BY date_created DESC
                """)
            )
            posts = result.fetchall()
            
            if not posts:
                print("\n📝 No active blog posts found in the database.")
                return
            
            print(f"\n📚 Found {len(posts)} active blog post(s):\n")
            print("-" * 80)
            
            for post in posts:
                post_id, title, slug, canonical_url, date_created = post
                print(f"ID: {post_id}")
                print(f"Title: {title}")
                print(f"Slug: {slug}")
                print(f"Canonical URL: {canonical_url or '(not set - will use site URL)'}")
                print(f"Created: {date_created}")
                print("-" * 80)
                
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    
    finally:
        engine.dispose()

if __name__ == "__main__":
    print("="*80)
    print("Blog Posts List")
    print("="*80)
    print()
    list_posts()