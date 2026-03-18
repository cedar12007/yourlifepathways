# Canonical URL Implementation Guide for prepforinterviews

This guide provides complete code snippets to implement canonical URL support in the prepforinterviews project.

## Overview
This implementation allows you to set external canonical URLs for blog posts that were originally published elsewhere (e.g., Substack, Medium), preventing duplicate content SEO penalties.

---

## Step 1: Update models.py

Add the canonical_url field to your Post model:

```python
# In models.py, add to the Post class:
canonical_url = db.Column(db.String(500), nullable=True)
```

**Complete Post model snippet:**
```python
class Post(db.Model):
    __tablename__ = 'posts'  # or your table name
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), unique=True, nullable=False)
    summary = db.Column(db.Text, nullable=False)
    content = db.Column(db.Text, nullable=True)
    image_file = db.Column(db.String(100), nullable=False, default='default.jpg')
    category = db.Column(db.String(100))
    canonical_url = db.Column(db.String(500), nullable=True)  # ADD THIS LINE
    # ... rest of your fields
```

---

## Step 2: Create Database Migration Script

Save this as `run_canonical_migration.py` in your prepforinterviews project root:

```python
#!/usr/bin/env python3
"""
Migration script to add canonical_url column to posts table.
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
            trans = conn.begin()
            
            try:
                print("Adding canonical_url column to posts table...")
                
                # Adjust table name if different (e.g., 'pfi_posts')
                conn.execute(text("""
                    ALTER TABLE posts
                    ADD COLUMN IF NOT EXISTS canonical_url VARCHAR(500);
                """))
                
                print("✓ Column added successfully")
                
                try:
                    conn.execute(text("""
                        COMMENT ON COLUMN posts.canonical_url IS 
                        'External canonical URL for syndicated content (e.g., original Substack URL). NULL means use the site URL.';
                    """))
                    print("✓ Column comment added")
                except Exception as e:
                    print(f"Note: Could not add column comment (non-critical): {e}")
                
                trans.commit()
                print("\n✅ Migration completed successfully!")
                print("\nNext steps:")
                print("1. Restart your Flask application")
                print("2. The canonical URL field is now available in the admin interface")
                
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
```

**Run the migration:**
```bash
cd /Users/I845387/Documents/python/prepforinterviews
python3 run_canonical_migration.py
```

---

## Step 3: Update Blog Routes

In your blog routes file (e.g., `routes.py` or `routes_blog.py`), find the view_post function and update the canonical URL logic:

**BEFORE:**
```python
canonical_url = f"https://prepforinterviews.com/blog/{post.slug}"
```

**AFTER:**
```python
# Use post's canonical_url if set (for syndicated content), otherwise use our site's URL
canonical_url = post.canonical_url or f"https://prepforinterviews.com/blog/{post.slug}"
```

**Complete snippet for context:**
```python
@blog.route('/blog/<string:slug>')
def view_post(slug):
    post = Post.query.filter_by(slug=slug, is_deleted=False).first_or_404()
    
    # ... your existing code ...
    
    # Canonical URL logic
    canonical_url = post.canonical_url or f"https://prepforinterviews.com/blog/{post.slug}"
    
    return render_template('blog_detail.html', 
                         post=post, 
                         canonical_url=canonical_url,
                         # ... other variables ...
                         )
```

---

## Step 4: Update Admin Edit Post Template

In `templates/admin/edit_post.html`, add this field between your image and summary fields:

```html
<div class="form-group">
    <label for="canonical_url">Canonical URL (Optional - for syndicated content)</label>
    <input type="url" id="canonical_url" name="canonical_url" 
        value="{{ post.canonical_url if post and post.canonical_url else '' }}"
        placeholder="https://example.com/original-article">
    <small style="color: #666;">Leave empty to use this site's URL. Set this if the post was originally published elsewhere (e.g., Substack, Medium)</small>
</div>
```

**Complete form snippet for context:**
```html
<div class="form-group">
    <label for="image_file">Image Filename</label>
    <input type="text" id="image_file" name="image_file" 
        value="{{ post.image_file if post else 'default.jpg' }}" required>
</div>

<!-- ADD THIS SECTION -->
<div class="form-group">
    <label for="canonical_url">Canonical URL (Optional - for syndicated content)</label>
    <input type="url" id="canonical_url" name="canonical_url" 
        value="{{ post.canonical_url if post and post.canonical_url else '' }}"
        placeholder="https://example.com/original-article">
    <small style="color: #666;">Leave empty to use this site's URL. Set this if the post was originally published elsewhere (e.g., Substack, Medium)</small>
</div>

<div class="form-group">
    <label for="summary">Summary</label>
    <textarea id="summary" name="summary" required>{{ post.summary if post else '' }}</textarea>
</div>
```

---

## Step 5: Update Admin Routes

In your admin routes file (e.g., `routes_admin.py`), update both the `new_post` and `edit_post` functions:

### new_post function:

**BEFORE:**
```python
post = Post(
    title=title,
    slug=final_slug,
    summary=summary,
    content=content,
    image_file=image_file,
    category=category
)
```

**AFTER:**
```python
canonical_url = request.form.get('canonical_url', '').strip() or None

post = Post(
    title=title,
    slug=final_slug,
    summary=summary,
    content=content,
    image_file=image_file,
    category=category,
    canonical_url=canonical_url  # ADD THIS LINE
)
```

### edit_post function:

**BEFORE:**
```python
post.title = request.form.get('title')
post.summary = request.form.get('summary')
post.content = request.form.get('content')
post.image_file = request.form.get('image_file')
post.category = request.form.get('category')
```

**AFTER:**
```python
post.title = request.form.get('title')
post.summary = request.form.get('summary')
post.content = request.form.get('content')
post.image_file = request.form.get('image_file')
post.category = request.form.get('category')
post.canonical_url = request.form.get('canonical_url', '').strip() or None  # ADD THIS LINE
```

---

## Step 6: Verify base.html Template

Make sure your `base.html` template has the canonical URL meta tag:

```html
<head>
    <!-- ... other meta tags ... -->
    
    {% if canonical_url %}
    <link rel="canonical" href="{{ canonical_url }}">
    {% else %}
    <link rel="canonical" href="https://prepforinterviews.com{{ request.path }}">
    {% endif %}
    
    <!-- ... rest of head ... -->
</head>
```

---

## Testing Checklist

After implementation:

1. ✅ Run the migration script: `python3 run_canonical_migration.py`
2. ✅ Restart your Flask application
3. ✅ Create a new blog post - check that canonical URL field appears
4. ✅ Edit an existing post - check that canonical URL field appears
5. ✅ Leave canonical URL empty - verify it uses your site's URL
6. ✅ Set a canonical URL (e.g., Substack) - verify it appears in page source
7. ✅ Check page source of blog post: look for `<link rel="canonical" href="...">` tag

---

## Helper Script: List Posts with Canonical URLs

Save this as `list_posts.py`:

```python
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
```

---

## Common Use Cases

### 1. Original Content (Default)
- Leave canonical URL field **empty**
- System automatically uses: `https://prepforinterviews.com/blog/your-post-slug`

### 2. Syndicated from Substack
- Set canonical URL to: `https://yourname.substack.com/p/article-slug`
- Tells Google the Substack version is the authoritative source

### 3. Syndicated from Medium
- Set canonical URL to: `https://medium.com/@username/article-slug`
- Prevents duplicate content penalties

---

## SEO Benefits

✅ **Proper Attribution** - Credit to original source  
✅ **No Penalties** - Avoid duplicate content issues  
✅ **Flexibility** - Syndicate content freely  
✅ **Easy Management** - Simple admin interface  

---

## Troubleshooting

### Migration fails with "column already exists"
- Safe to ignore - column was already added
- Or use `ALTER TABLE posts ADD COLUMN IF NOT EXISTS ...`

### Canonical URL not appearing in HTML
- Check that you're passing `canonical_url` to the template
- Verify `base.html` has the canonical link tag
- Restart Flask application after code changes

### Field not saving
- Verify admin route includes: `post.canonical_url = request.form.get('canonical_url', '').strip() or None`
- Check browser console for JavaScript errors
- Verify form has `name="canonical_url"` attribute

---

## Implementation Complete! 🎉

After following these steps, your prepforinterviews project will have full canonical URL support.