-- Allow google_id to be NULL for pre-invited users
ALTER TABLE users ALTER COLUMN google_id DROP NOT NULL;
