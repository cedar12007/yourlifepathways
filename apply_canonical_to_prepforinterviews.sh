#!/bin/bash

# Automated script to apply canonical URL implementation to prepforinterviews
# Run this from the yourlifepathways directory

set -e  # Exit on error

PREP_DIR="/Users/I845387/Documents/python/prepforinterviews"

echo "=============================================="
echo "Canonical URL Implementation"
echo "Target: prepforinterviews"
echo "=============================================="
echo ""

# Check if prepforinterviews directory exists
if [ ! -d "$PREP_DIR" ]; then
    echo "❌ Error: prepforinterviews directory not found at $PREP_DIR"
    exit 1
fi

echo "✓ Found prepforinterviews directory"
echo ""

# Step 1: Copy migration script
echo "Step 1: Creating migration script..."
cat > "$PREP_DIR/run_canonical_migration.py" << 'MIGRATION_EOF'
#!/usr/bin/env python3
"""
Migration script to add canonical_url column to posts table.
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

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
            trans = conn.begin()
            
            try:
                print("Adding canonical_url column to posts table...")
                conn.execute(text("""
                    ALTER TABLE posts
                    ADD COLUMN IF NOT EXISTS canonical_url VARCHAR(500);
                """))
                
                print("✓ Column added successfully")
                
                try:
                    conn.execute(text("""
                        COMMENT ON COLUMN posts.canonical_url IS 
                        'External canonical URL for syndicated content. NULL means use the site URL.';
                    """))
                    print("✓ Column comment added")
                except Exception as e:
                    print(f"Note: Could not add column comment (non-critical): {e}")
                
                trans.commit()
                print("\n✅ Migration completed successfully!")
                
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
    print("PrepForInterviews - Canonical URL Migration")
    print("="*60)
    print()
    run_migration()
MIGRATION_EOF

chmod +x "$PREP_DIR/run_canonical_migration.py"
echo "✓ Migration script created"
echo ""

# Step 2: Copy helper script
echo "Step 2: Creating helper script to list posts..."
cat > "$PREP_DIR/list_posts_canonical.py" << 'HELPER_EOF'
#!/usr/bin/env python3
"""List all blog posts and their canonical URLs"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def list_posts():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not found")
        sys.exit(1)
    
    engine = create_engine(database_url)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, title, slug, canonical_url, created_at 
                FROM posts 
                WHERE is_deleted = false 
                ORDER BY created_at DESC
            """))
            posts = result.fetchall()
            
            if not posts:
                print("\n📝 No posts found.")
                return
            
            print(f"\n📚 Found {len(posts)} post(s):\n")
            print("-" * 80)
            
            for post in posts:
                post_id, title, slug, canonical_url, created = post
                print(f"ID: {post_id}")
                print(f"Title: {title}")
                print(f"Slug: {slug}")
                print(f"Canonical: {canonical_url or '(using site URL)'}")
                print(f"Created: {created}")
                print("-" * 80)
                
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    finally:
        engine.dispose()

if __name__ == "__main__":
    print("="*80)
    print("PrepForInterviews - Blog Posts List")
    print("="*80)
    list_posts()
HELPER_EOF

chmod +x "$PREP_DIR/list_posts_canonical.py"
echo "✓ Helper script created"
echo ""

# Step 3: Run the migration
echo "Step 3: Running database migration..."
echo "Press Enter to continue or Ctrl+C to cancel..."
read

cd "$PREP_DIR"
python3 run_canonical_migration.py

echo ""
echo "=============================================="
echo "Migration Complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo "1. Update models.py - add: canonical_url = db.Column(db.String(500), nullable=True)"
echo "2. Update blog routes - change canonical URL logic"
echo "3. Update templates/admin/edit_post.html - add canonical URL field"
echo "4. Update admin routes - handle canonical_url in new_post and edit_post"
echo ""
echo "See CANONICAL_URL_IMPLEMENTATION_FOR_PREPFORINTERVIEWS.md for detailed instructions"
echo ""