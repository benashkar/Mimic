-- Migration 004: Add agency column to prompts and user_agencies table.
--
-- prompts.agency groups prompts by client/agency for permission scoping.
-- user_agencies maps users to the agencies (and optionally opportunities)
-- they are allowed to see. Admins bypass all permission checks.

ALTER TABLE prompts ADD COLUMN IF NOT EXISTS agency VARCHAR(255);

CREATE TABLE IF NOT EXISTS user_agencies (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    agency VARCHAR(255) NOT NULL,
    opportunity VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_agencies_user ON user_agencies(user_id);
CREATE INDEX IF NOT EXISTS idx_prompts_agency ON prompts(agency);
