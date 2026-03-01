-- Migration 010: Add scheduler queue infrastructure
-- Adds schedule_enabled flag to prompts and queue_items table for
-- the daily automated source list discovery pipeline.

ALTER TABLE prompts ADD COLUMN IF NOT EXISTS schedule_enabled BOOLEAN DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS queue_items (
    id SERIAL PRIMARY KEY,
    story_id INTEGER NOT NULL REFERENCES stories(id),
    prompt_id INTEGER NOT NULL REFERENCES prompts(id),
    label TEXT NOT NULL,
    body TEXT NOT NULL,
    agency VARCHAR(255),
    opportunity VARCHAR(255),
    state VARCHAR(255),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    claimed_by VARCHAR(255),
    claimed_at TIMESTAMP,
    refinement_prompt_id INTEGER REFERENCES prompts(id),
    pipeline_story_id INTEGER REFERENCES stories(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_queue_items_status ON queue_items(status);
CREATE INDEX IF NOT EXISTS idx_queue_items_opportunity ON queue_items(opportunity);
