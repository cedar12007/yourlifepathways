#!/usr/bin/env python3
"""
Migration script to add highlight_summary column to ylp_posts table.
This allows separate rich HTML highlight summaries unconstrained by character limits.
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_migration():
    """Execute the highlight_summary migration"""
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("ERROR: DATABASE_URL not found in environment variables")
        sys.exit(1)
    
    print("Connecting to database...")
    engine = create_engine(database_url)
    
    try:
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                print("Adding highlight_summary column to ylp_posts table...")
                conn.execute(text("""
                    ALTER TABLE ylp_posts
                    ADD COLUMN IF NOT EXISTS highlight_summary TEXT;
                """))
                print("✓ Column highlight_summary added successfully")
                
                try:
                    conn.execute(text("""
                        COMMENT ON COLUMN ylp_posts.highlight_summary IS 
                        'Unconstrained rich HTML highlight summary displayed in callout box on article page.';
                    """))
                    print("✓ Column comment added")
                except Exception as e:
                    print(f"Note: Could not add column comment (non-critical): {e}")
                
                trans.commit()
                print("\nMigration completed successfully!")
            except Exception as e:
                trans.rollback()
                print(f"ERROR: Migration failed, rolled back: {e}")
                sys.exit(1)
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)

if __name__ == '__main__':
    run_migration()
