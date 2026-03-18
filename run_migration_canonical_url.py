#!/usr/bin/env python3
"""
Migration script to add canonical_url column to ylp_posts table.
This allows setting external canonical URLs for syndicated content.
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_migration():
    """Execute the canonical_url migration"""
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("ERROR: DATABASE_URL not found in environment variables")
        sys.exit(1)
    
    print("Connecting to database...")
    engine = create_engine(database_url)
    
    try:
        with engine.connect() as conn:
            # Start a transaction
            trans = conn.begin()
            
            try:
                print("Adding canonical_url column to ylp_posts table...")
                
                # Add the column
                conn.execute(text("""
                    ALTER TABLE ylp_posts
                    ADD COLUMN IF NOT EXISTS canonical_url VARCHAR(500);
                """))
                
                print("✓ Column added successfully")
                
                # Add comment (optional, may not work on all PostgreSQL versions)
                try:
                    conn.execute(text("""
                        COMMENT ON COLUMN ylp_posts.canonical_url IS 
                        'External canonical URL for syndicated content (e.g., original Substack URL). NULL means use the site URL.';
                    """))
                    print("✓ Column comment added")
                except Exception as e:
                    print(f"Note: Could not add column comment (non-critical): {e}")
                
                # Commit the transaction
                trans.commit()
                print("\n✅ Migration completed successfully!")
                print("\nNext steps:")
                print("1. Restart your Flask application")
                print("2. To set canonical URL for the Substack post, run:")
                print("   UPDATE ylp_posts SET canonical_url = 'https://notaicoach.substack.com/p/im-not-your-ai-coach'")
                print("   WHERE slug = 'im-not-your-ai-coach';")
                
            except Exception as e:
                trans.rollback()
                print(f"\n❌ Migration failed: {e}")
                sys.exit(1)
                
    except Exception as e:
        print(f"\n❌ Database connection failed: {e}")
        sys.exit(1)
    
    finally:
        engine.dispose()

if __name__ == "__main__":
    print("="*60)
    print("YourLifePathways - Canonical URL Migration")
    print("="*60)
    print()
    run_migration()