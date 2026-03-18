#!/usr/bin/env python3
"""
Script to set the canonical URL for the "I'm Not Your AI Coach" post
to point to the original Substack publication.
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def set_canonical_url():
    """Set the canonical URL for the Substack post"""
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("ERROR: DATABASE_URL not found in environment variables")
        sys.exit(1)
    
    # Configuration
    post_slug = 'i-am-not-your-ai-coach'
    canonical_url = 'https://notaicoach.substack.com/p/im-not-your-ai-coach'
    
    print("Connecting to database...")
    engine = create_engine(database_url)
    
    try:
        with engine.connect() as conn:
            trans = conn.begin()
            
            try:
                # Check if post exists
                result = conn.execute(
                    text("SELECT id, title FROM ylp_posts WHERE slug = :slug AND is_deleted = false"),
                    {"slug": post_slug}
                )
                post = result.fetchone()
                
                if not post:
                    print(f"❌ Post with slug '{post_slug}' not found or is deleted")
                    sys.exit(1)
                
                print(f"Found post: {post[1]} (ID: {post[0]})")
                
                # Update the canonical URL
                conn.execute(
                    text("UPDATE ylp_posts SET canonical_url = :url WHERE slug = :slug"),
                    {"url": canonical_url, "slug": post_slug}
                )
                
                trans.commit()
                print(f"\n✅ Successfully set canonical URL to:")
                print(f"   {canonical_url}")
                print("\nThe blog post now points to the original Substack article as the canonical source.")
                print("This tells search engines that Substack is the authoritative version.")
                
            except Exception as e:
                trans.rollback()
                print(f"\n❌ Update failed: {e}")
                sys.exit(1)
                
    except Exception as e:
        print(f"\n❌ Database connection failed: {e}")
        sys.exit(1)
    
    finally:
        engine.dispose()

if __name__ == "__main__":
    print("="*60)
    print("Set Substack Canonical URL")
    print("="*60)
    print()
    set_canonical_url()