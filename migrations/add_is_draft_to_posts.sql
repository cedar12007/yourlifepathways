-- Migration: Add is_draft column to ylp_posts table
-- Date: 2026-11-15
-- Description: Adds draft state support for blog posts, keeping unpublished posts hidden from the public

ALTER TABLE ylp_posts
ADD COLUMN IF NOT EXISTS is_draft BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_ylp_posts_is_draft ON ylp_posts(is_draft);

COMMENT ON COLUMN ylp_posts.is_draft IS 'Flag indicating whether the post is an unpublished draft (TRUE) or publicly published (FALSE).';
