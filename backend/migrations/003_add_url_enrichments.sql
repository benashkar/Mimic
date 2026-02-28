-- Add url_enrichments column to stories table.
-- Stores JSON-encoded enrichment data (tweet text, page titles) for URLs
-- found in source list output.
ALTER TABLE stories ADD COLUMN IF NOT EXISTS url_enrichments TEXT;
