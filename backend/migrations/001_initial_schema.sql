-- ============================================================
-- Mimic — Initial Schema (4 tables)
-- Run against Render PostgreSQL to set up the database.
-- Uses CREATE TABLE IF NOT EXISTS for idempotency.
-- ============================================================

-- ============================================================
-- Table: users
-- Google OAuth accounts. @plmediaagency.com only.
-- role = 'admin' or 'user'.
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    google_id VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255),
    avatar_url TEXT,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login_at TIMESTAMP
);

-- ============================================================
-- Table: prompts
-- The Prompt Library. prompt_type: 'source-list', 'papa', 'amy-bot'.
-- Source List prompts carry routing metadata (nullable columns).
-- PAPA and PSST are both prompt_type='papa', distinguished by name.
-- ============================================================
CREATE TABLE IF NOT EXISTS prompts (
    id SERIAL PRIMARY KEY,
    prompt_type VARCHAR(50) NOT NULL,

    -- Common fields (all types)
    name VARCHAR(255) NOT NULL,
    prompt_text TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_by VARCHAR(255),
    updated_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Source List routing metadata (nullable; only for source-list type)
    issuer VARCHAR(255),
    opportunity VARCHAR(255),
    state VARCHAR(255),
    publications TEXT,
    topic_summary TEXT,
    context TEXT,
    pitches_per_week INTEGER
);

CREATE INDEX IF NOT EXISTS idx_prompts_type ON prompts(prompt_type);
CREATE INDEX IF NOT EXISTS idx_prompts_opportunity ON prompts(opportunity);
CREATE INDEX IF NOT EXISTS idx_prompts_state ON prompts(state);

-- ============================================================
-- Table: stories
-- Every pipeline run — approved AND rejected.
-- Rejected stories are logged but no CMS push happens.
-- ============================================================
CREATE TABLE IF NOT EXISTS stories (
    id SERIAL PRIMARY KEY,

    -- Which prompts were used
    source_list_prompt_id INTEGER REFERENCES prompts(id),
    refinement_prompt_id INTEGER REFERENCES prompts(id),
    amy_bot_prompt_id INTEGER REFERENCES prompts(id),

    -- Step 1: Source List
    source_list_input TEXT,
    source_list_output TEXT,
    selected_story TEXT,

    -- Routing snapshot (copied from source list config at runtime)
    opportunity VARCHAR(255),
    state VARCHAR(255),
    publications TEXT,
    topic_summary TEXT,
    context TEXT,

    -- Step 3: PAPA or PSST output
    refinement_input TEXT,
    refinement_output TEXT,

    -- Step 4: Amy Bot output
    amy_bot_input TEXT,
    amy_bot_output TEXT,
    is_valid BOOLEAN DEFAULT FALSE,
    validation_decision VARCHAR(20),

    -- CMS push (only if APPROVE)
    pushed_to_cms BOOLEAN DEFAULT FALSE,
    cms_push_date TIMESTAMP,
    cms_response TEXT,

    -- Audit
    created_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- Table: pipeline_runs
-- Audit log — one row per Grok API call.
-- ============================================================
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id SERIAL PRIMARY KEY,
    story_id INTEGER REFERENCES stories(id),
    prompt_id INTEGER REFERENCES prompts(id),
    step_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    input_text TEXT,
    output_text TEXT,
    error_message TEXT,
    duration_ms INTEGER,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
