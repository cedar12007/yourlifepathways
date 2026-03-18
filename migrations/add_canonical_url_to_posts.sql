-- Migration: Add canonical_url column to ylp_posts table
-- Date: 2026-03-18
-- Description: Adds support for external canonical URLs for syndicated content

-- Add the canonical_url column
ALTER TABLE ylp_posts
ADD COLUMN IF NOT EXISTS canonical_url VARCHAR(500);

-- Add a comment explaining the column
COMMENT ON COLUMN ylp_posts.canonical_url IS 'External canonical URL for syndicated content (e.g., original Substack URL). NULL means use the site URL.';

-- Optional: Update specific post with Substack canonical URL
-- Uncomment and adjust the slug if you want to set it immediately
-- UPDATE ylp_posts 
-- SET canonical_url = 'https://notaicoach.substack.com/p/im-not-your-ai-coach'
-- WHERE slug = 'im-not-your-ai-coach';