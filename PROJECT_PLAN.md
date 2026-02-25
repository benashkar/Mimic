# CR News Pipeline Automation — Project Plan

## Overview

**Project Name:** `cr-news-pipeline`
**Goal:** Replace a manual copy/paste editorial pipeline (Grok → Spreadsheet → Grok → Grok → Lumen CMS) with a React + Flask web app that automates the pipeline via the xAI Grok API.

**Current Workflow (Manual):**
1. User runs a Grok "Source List" prompt to discover newsworthy stories/sources.
2. User adds routing metadata in a spreadsheet: Issuer, Opportunity, State, Publication(s), Topic Summary, Context, Pitches per Week.
3. Second user pastes results into either **PAPA** (for announcements) or **PSST** (for statements/quotes) for story refinement.
4. Output is pasted into **Amy Bot** (editorial review agent) for validation.
5. Amy Bot returns `DECISION: APPROVE` or `DECISION: REJECT — with fixes`.
6. If approved → manually entered into Lumen CMS. If rejected → story is killed.

**Target Workflow (Automated):**
1. User browses **Prompt Library**, clicks a Source List config to run it.
2. Reviews results, selects a story/source.
3. Picks **PAPA** (if source is an announcement) or **PSST** (if source is a statement/quote).
4. Clicks "Run Pipeline" → backend auto-chains selected prompt → Amy Bot.
5. Amy Bot returns `DECISION: APPROVE` → push to CMS API.
6. Amy Bot returns `DECISION: REJECT` → **story is killed. Dead. No retry. Logged and done.**

---

## The 3 Prompt Types — What They Do

### Source List (Step 1 — Discovery)
**Purpose:** Searches X (Twitter) and the web for newsworthy stories matching a specific topic/region/narrative.
**Input:** The prompt text (typically 1,000–4,000 chars) which describes what to search for, credibility filters, and output format requirements.
**Output:** A list of 2–5 topics with associated X posts and web links from credible, verified sources.
**Count:** Currently 34 active configs across 8 Opportunities and 15 states.
**Config includes routing metadata:** Issuer, Opportunity, State, Publications, Topic Summary, Context, Pitches/Week.

### PAPA — Provided Announcement Pitch Assistant (Step 3 option A)
**Purpose:** Processes official organizational announcements (press releases, filings, reports) into newsroom-ready structured pitches.
**Use when:** The source material is an **announcement from an organization** (not a personal statement).
**Output structure:** Organization → What → Key Phrase → Announcement Summary → Headline → Lede → Factoids 1-4.
**Key rules:** Right-leaning framing default, no editorial language, 100-char headlines in present tense, ledes ≤250 chars, factoids 300-400 chars each with source URLs.

### PSST — Provided Statement Speech Tool (Step 3 option B)
**Purpose:** Processes individual statements and quotes (from X posts, speeches, interviews) into newsroom-ready structured pitches.
**Use when:** The source material is a **statement or quote from a person** (not an organizational announcement).
**Output structure:** Speaker Name → Speaker Title → Organization → Quotes → Key Phrase → Statement Summary → Headline → Lede → Factoids 1-5.
**Key rules:** Right-leaning framing default, no editorial language, quote attribution accuracy critical, 100-char headlines, ledes ≤220 chars, factoids 300-400 chars.

### Amy Bot — Editorial Review Agent (Step 4 — Validation Gate)
**Purpose:** Reviews PAPA/PSST output before it goes to editors. Checks for attribution errors, editorial language, factoid quality, source accuracy.
**Input:** The complete PAPA or PSST output.
**Output:** Either `DECISION: APPROVE` or `DECISION: REJECT — with fixes`.
**Pipeline behavior:**
- `APPROVE` → Story is valid → push to CMS API.
- `REJECT` → **Story is killed. Logged. No fixes applied. No retry. Done.**
**Key checks:** Quote attribution (#1 issue), headline clarity, lede context, factoid relevance, source currency.

---

## Source List Data Model (from Lead Pitcher Spreadsheet)

Each Source List prompt is a **full request configuration** with routing metadata baked in. 34 active configs across 8 Opportunities and 15 states.

| Column | Field             | Purpose                            | Example                                    |
|--------|-------------------|------------------------------------|--------------------------------------------|
| A      | Created Date      | When config was created            | 2026-01-12                                 |
| B      | Issuer            | Who created this request           | Max, Jay, Tor                              |
| C      | Opportunity       | Client/project assignment          | "Kin", "Illinois Local Government News"    |
| D      | State             | Geographic target                  | California, Illinois, Ohio                 |
| E      | Publication(s)    | Target outlets                     | "Chicago City Wire, DuPage Policy Journal" |
| F      | Topic Summary     | What the story should cover        | (1-2 paragraph description)               |
| G      | Context           | Background/narrative framing       | (1-2 paragraph context)                    |
| H      | Pitches per Week  | Volume target                      | 2, 3, 4, 25                               |
| I      | Search Prompt     | The Grok prompt text (1K-4K chars) | "Find the most recent information..."      |

### Current Routing Values
**Opportunities (8):** Illinois Local Government News, Kin, Reparations NewsSpheres, Somali NewsSpheres, Trial Lawyer + Insurance News, US Regional News Network(s) - Baseline
**States (15):** CA, CO, FL, GA, IL, MA, MI, MN, NJ, NY, OH, OR, VA, WA, DC
**Issuers (3):** Jay, Max, Tor

---

## Key Design Decisions

### Prompt Library
- 3 types: `source-list`, `papa`, `amy-bot` (PSST is a `papa`-type variant).
- Many instances per type. Full CRUD for admins. Browse/run for users.
- Source List configs include routing metadata. PAPA/PSST/Amy Bot are prompt-text only.

### PAPA vs PSST Selection
The user picks based on source material type:
- **Announcement** (press release, filing, report) → use **PAPA**
- **Statement/quote** (X post, speech, interview) → use **PSST**

### Amy Bot Validation Logic
```python
# Parse Amy Bot output for APPROVE or REJECT
def parse_amy_bot_result(output: str) -> bool:
    """
    Amy Bot returns structured output starting with either:
      'DECISION: APPROVE' → True (valid, push to CMS)
      'DECISION: REJECT'  → False (kill, do nothing)

    We parse the first occurrence of 'DECISION:' in the output.
    Anything after REJECT (the fixes) is logged but not used.
    """
    output_upper = output.upper()
    if "DECISION: APPROVE" in output_upper or "DECISION:APPROVE" in output_upper:
        return True
    return False  # Any non-APPROVE result = kill
```

### Pipeline: Reject = Kill
When Amy Bot rejects a story:
- Story is logged in the database with `is_valid=False`.
- Amy Bot's full output (including suggested fixes) is stored in `amy_bot_output`.
- **No fixes are applied. No retry. No user review. Story is dead.**
- The CMS API is NOT called.

### Roles
| Role  | Prompts                   | Pipeline | Stories  |
|-------|---------------------------|----------|----------|
| Admin | Create, Edit, Delete, Run | Run      | View all |
| User  | View and Run only         | Run      | View all |

---

## User Flow

```
PROMPT LIBRARY
  Source List Configs (34):
    [Kin - California]           4/wk  [Run]
    [IL Local Gov - Pritzker]    4/wk  [Run]
    ...
    [+ New] (admin)

  Refinement Prompts:
    [PAPA - Announcements]   [PSST - Statements]   [+ New] (admin)

  Validation Prompts:
    [Amy Bot v1]   [+ New] (admin)

USER CLICKS [Run] on a Source List config
  → Grok returns story/source candidates
  → User reviews and selects one

USER PICKS refinement type:
  ○ PAPA (this is an announcement)
  ○ PSST (this is a statement/quote)

USER CLICKS [Run Pipeline]
  → Backend: selected PAPA/PSST prompt + story + routing → Grok API
  → Backend: Amy Bot prompt + PAPA/PSST output → Grok API
  → Amy Bot returns DECISION

  APPROVE → Push to CMS API → Store → Done
  REJECT  → Log. Kill. Nothing else.
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  React Frontend                                          │
│  Login: Google @plmediaagency.com only                   │
│                                                          │
│  Prompt Library (CRUD/browse) │ Pipeline Runner          │
│  Source List configs (34+)    │ Pick config → Run        │
│  PAPA / PSST prompts          │ Pick PAPA or PSST        │
│  Amy Bot prompts              │ Auto-chain → Amy Bot     │
│  Admin: CRUD | User: browse   │ Approve→CMS | Reject→Kill│
│                               │                          │
│  Stories Log: all results     │ Dashboard: stats         │
└──────────────────────┬───────────────────────────────────┘
                       │ REST API — JWT auth
┌──────────────────────▼───────────────────────────────────┐
│  Flask Backend                                            │
│  /api/auth/*                  — Google OAuth              │
│  /api/prompts                 — CRUD (admin-gated writes) │
│  /api/pipeline/source-list    — Run Source List           │
│  /api/pipeline/run            — PAPA/PSST → Amy Bot       │
│  /api/stories                 — Browse results            │
│  Services: Auth, Grok, Pipeline, Story, CMS (stub)        │
└──────────────────────┬───────────────────────────────────┘
                       │
│  PostgreSQL (Render): users, prompts, stories, pipeline_runs │
└───────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer       | Technology           | Notes                              |
|-------------|----------------------|------------------------------------|
| Frontend    | React (Vite)         | Lightweight                        |
| Backend     | Python / Flask       | REST API + Grok calls              |
| LLM API     | xAI Grok API         | Replaces Grok web UI               |
| Database    | PostgreSQL (Render)  | Existing infra                     |
| Auth        | Google OAuth 2.0     | @plmediaagency.com + admin/user    |
| Deployment  | Docker + Render      | Free tier → custom domain          |
| CI/CD       | GitHub Actions       | Tests before merge to master       |
| Testing     | pytest + Jest        | Per CLAUDE.md                      |

---

## Database Schema

```sql
-- ============================================================
-- Table: users
-- @plmediaagency.com only. role = 'admin' or 'user'.
-- ============================================================
CREATE TABLE users (
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
-- The Prompt Library. Many per type. Full CRUD for admins.
--
-- prompt_type values:
--   'source-list' — Discovery prompts (carry routing metadata)
--   'papa'        — PAPA + PSST refinement prompts
--   'amy-bot'     — Editorial validation prompts
--
-- Note: PAPA and PSST are both prompt_type='papa'. They are
-- distinguished by their name/description. The user picks
-- between them based on source material type.
-- ============================================================
CREATE TABLE prompts (
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

CREATE INDEX idx_prompts_type ON prompts(prompt_type);
CREATE INDEX idx_prompts_opportunity ON prompts(opportunity);
CREATE INDEX idx_prompts_state ON prompts(state);

-- ============================================================
-- Table: stories
-- Every pipeline run — approved AND rejected.
-- Rejected stories are logged but no CMS push happens.
-- ============================================================
CREATE TABLE stories (
    id SERIAL PRIMARY KEY,

    -- Which prompts were used
    source_list_prompt_id INTEGER REFERENCES prompts(id),
    refinement_prompt_id INTEGER REFERENCES prompts(id),  -- PAPA or PSST
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
    amy_bot_output TEXT,                       -- Full Amy Bot response
    is_valid BOOLEAN DEFAULT FALSE,            -- TRUE = APPROVE, FALSE = REJECT
    validation_decision VARCHAR(20),           -- 'APPROVE' or 'REJECT' (parsed)

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
CREATE TABLE pipeline_runs (
    id SERIAL PRIMARY KEY,
    story_id INTEGER REFERENCES stories(id),
    prompt_id INTEGER REFERENCES prompts(id),
    step_type VARCHAR(50) NOT NULL,            -- 'source-list', 'refinement', 'amy-bot'
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    input_text TEXT,
    output_text TEXT,
    error_message TEXT,
    duration_ms INTEGER,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
```

---

## Project Structure

```
cr-news-pipeline/
├── CLAUDE.md
├── PROJECT_PLAN.md
├── README.md
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
├── .github/workflows/ci.yml
│
├── backend/
│   ├── requirements.txt
│   ├── app.py
│   ├── config.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── prompt.py
│   │   ├── story.py
│   │   └── pipeline_run.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── prompts.py
│   │   ├── pipeline.py
│   │   └── stories.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── grok_service.py
│   │   ├── pipeline_service.py    # Core: Source List → PAPA/PSST → Amy Bot → CMS/Kill
│   │   ├── validation_service.py  # Parses Amy Bot APPROVE/REJECT output
│   │   ├── story_service.py
│   │   └── cms_service.py         # Stub
│   ├── decorators/
│   │   ├── __init__.py
│   │   ├── login_required.py
│   │   └── admin_required.py
│   └── migrations/
│       ├── 001_initial_schema.sql
│       └── 002_seed_prompts.sql   # All 34 Source Lists + PAPA + PSST + Amy Bot
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── api/client.js
│   │   ├── context/AuthContext.jsx
│   │   ├── components/
│   │   │   ├── ProtectedRoute.jsx
│   │   │   ├── AdminOnly.jsx
│   │   │   ├── GoogleLoginBtn.jsx
│   │   │   ├── SourceListCard.jsx
│   │   │   ├── PromptCard.jsx
│   │   │   ├── SourceListForm.jsx     # Admin: create/edit source list config
│   │   │   ├── PromptForm.jsx         # Admin: create/edit PAPA/PSST/Amy Bot
│   │   │   ├── StoryCard.jsx
│   │   │   ├── RefinementSelector.jsx # Pick PAPA or PSST
│   │   │   ├── PipelineStatus.jsx
│   │   │   └── ValidationBadge.jsx    # APPROVE (green) / REJECT (red)
│   │   ├── pages/
│   │   │   ├── LoginPage.jsx
│   │   │   ├── DashboardPage.jsx
│   │   │   ├── PromptLibraryPage.jsx
│   │   │   ├── SourceListDetailPage.jsx
│   │   │   ├── PromptDetailPage.jsx
│   │   │   ├── SourceListRunPage.jsx
│   │   │   ├── PipelinePage.jsx       # Pick PAPA/PSST → run → result
│   │   │   └── StoriesPage.jsx
│   │   └── styles/index.css
│   └── tests/components/
│
└── tests/
    ├── conftest.py
    ├── test_auth_service.py
    ├── test_grok_service.py
    ├── test_pipeline_service.py
    ├── test_validation_service.py  # APPROVE/REJECT parsing
    ├── test_prompt_crud.py
    ├── test_story_service.py
    └── test_routes_*.py
```

---

## Implementation Phases

### Phase 1: Project Scaffolding & Database ✅
1. Init repo. Project-specific `CLAUDE.md`.
2. Flask factory + CORS. `config.py`.
3. SQLAlchemy models (4 tables).
4. Run migration on Render PostgreSQL.
5. `GET /api/health` → 200.
6. React + Vite + Router (placeholders).
7. `docker-compose.yml`.

**Tests:** health check, DB read/write. (9 tests passing)

---

### Phase 1.5: Authentication + Roles ✅
1. `auth_service.py`: Google token → check `@plmediaagency.com` → role.
2. `routes/auth.py`: login, me (returns role), logout.
3. `@login_required`, `@admin_required` decorators.
4. Frontend: LoginPage, ProtectedRoute, AuthContext, AdminOnly, GoogleLoginBtn.
5. JWT session tokens (PyJWT), Google OAuth token verification (google-auth).
6. First user = admin, subsequent users = user role.

**Tests:** valid/wrong domain, admin/user role enforcement, JWT roundtrip, decorator auth. (~15 new tests)

---

### Phase 2: Grok API Integration
1. `grok_service.py`: `call_grok(prompt, context)` → xAI API.
2. Error handling (rate limits, timeouts).
3. Extensively commented.

**Tests (fixtures):** success, timeout, rate limit.

---

### Phase 3: Prompt Library (CRUD + UI + Seed Data)
**Backend:**
- `GET /api/prompts?type=source-list` — filter by type, opportunity, state.
- `POST/PUT/DELETE /api/prompts` — admin only.

**Frontend:**
- `PromptLibraryPage.jsx`: 3 sections — Source Lists (with routing metadata visible), Refinement (PAPA/PSST), Amy Bot.
- `SourceListForm.jsx`: all routing fields + prompt text.
- `PromptForm.jsx`: name + prompt text + description.

**Seed data:** All 34 Source List configs + PAPA + PSST + Amy Bot with real prompt texts.

**Tests:** list, filter, create (admin), create (user → 403), update, delete.

---

### Phase 4: Source List Runner
1. `POST /api/pipeline/source-list` — `{ prompt_id }`.
2. `SourceListRunPage.jsx`: shows routing metadata, runs Grok, displays selectable results.

**Tests:** run success, wrong prompt type.

---

### Phase 5: Pipeline Execution (Main Feature)

**Core pipeline logic in `pipeline_service.py`:**
```python
def run_pipeline(selected_story, source_list_prompt_id, refinement_prompt_id, user_email):
    """
    1. Snapshot routing from Source List config
    2. Determine if refinement prompt is PAPA or PSST (by name/description)
    3. Call Grok: refinement prompt + selected story + routing context
    4. Call Grok: Amy Bot prompt + refinement output
    5. Parse Amy Bot decision:
       - 'DECISION: APPROVE' → push to CMS API, mark as valid
       - Anything else → kill. Log. Do nothing.
    """
    # Step 3: Refinement (PAPA or PSST — user already picked which one)
    refinement_prompt = Prompt.query.get(refinement_prompt_id)
    refinement_input = build_refinement_input(refinement_prompt, selected_story, routing)
    refinement_result = grok_service.call_grok(refinement_input)

    # Step 4: Amy Bot (auto-selects active amy-bot prompt)
    amy_prompt = Prompt.query.filter_by(prompt_type='amy-bot', is_active=True).first()
    amy_input = build_amy_input(amy_prompt, refinement_result.output)
    amy_result = grok_service.call_grok(amy_input)

    # Parse decision
    is_valid = validation_service.parse_decision(amy_result.output)
    # Returns True if 'DECISION: APPROVE' found, False otherwise

    if is_valid:
        cms_response = cms_service.push_to_cms(story)
        story.pushed_to_cms = True
        story.validation_decision = 'APPROVE'
    else:
        # Kill it. Log the full Amy Bot output (including fixes). Do nothing.
        story.validation_decision = 'REJECT'
        story.is_valid = False
        # Amy Bot's suggested fixes are stored in amy_bot_output for reference
        # but are NEVER applied. Story is dead.

    return story
```

**`validation_service.py`:**
```python
def parse_decision(amy_bot_output: str) -> bool:
    """
    Parse Amy Bot's structured output for APPROVE or REJECT.

    Amy Bot returns one of:
      'DECISION: APPROVE' followed by 'All fields meet editorial standards.'
      'DECISION: REJECT — with fixes' followed by field-by-field corrections.

    We only care about the DECISION line.
    APPROVE = True (push to CMS).
    Anything else = False (kill the story).
    """
    output_upper = (amy_bot_output or "").upper()
    if "DECISION: APPROVE" in output_upper or "DECISION:APPROVE" in output_upper:
        return True
    return False
```

**Frontend — `PipelinePage.jsx`:**
- Shows selected story + routing (pre-filled from Source List config).
- `RefinementSelector`: "Is this an announcement or a statement?"
  - Announcement → shows PAPA-type prompts.
  - Statement → shows PSST-type prompts.
- "Run Pipeline" button.
- `PipelineStatus` while running.
- Result: green `APPROVED — Pushed to CMS` or red `REJECTED — Story Killed`.

**Tests:**
- `test_pipeline_approve`: Mock PAPA + Amy Bot (APPROVE) → CMS called, pushed=True.
- `test_pipeline_reject`: Mock PAPA + Amy Bot (REJECT) → CMS NOT called, is_valid=False, story logged.
- `test_pipeline_refinement_fails`: Mock error → stops, no Amy Bot call.
- `test_validation_parse_approve`: Various APPROVE formats → True.
- `test_validation_parse_reject`: Various REJECT formats → False.
- `test_validation_parse_garbage`: Unexpected output → False (safe default = kill).

---

### Phase 6: Stories Log & Dashboard
1. Paginated story list: filter by valid/rejected, opportunity, state, refinement prompt used.
2. Story detail: all inputs/outputs, which prompts used, Amy Bot full response.
3. Dashboard: approval rate, stories today, per opportunity.

---

### Phase 7: Docker, CI/CD & Deployment
1. Dockerfiles (no `COPY ../`).
2. GitHub Actions CI on PRs to master.
3. Deploy to Render free tier. Manual deploy.

---

### Phase 8: CMS Integration (When Lumen API Provided)
Replace `cms_service.py` stub with real Lumen API calls.

---

## Prompt Texts (Seed Data)

The actual prompt texts for PAPA, PSST, and Amy Bot are stored in the companion file `PROMPT_SEED_DATA.md` (too large to inline here). The 34 Source List configs will be imported from the Lead Pitcher spreadsheet via migration script `002_seed_prompts.sql`.

**Summary of seed prompts:**

| Prompt | Type | Name | Chars |
|--------|------|------|-------|
| PAPA | papa | PAPA - Provided Announcement Pitch Assistant | ~4,800 |
| PSST | papa | PSST - Provided Statement Speech Tool | ~7,200 |
| Amy Bot | amy-bot | Amy Bot - Editorial Review Agent | ~5,500 |
| Source Lists (34) | source-list | Various (from spreadsheet) | 1,000-4,300 each |

---

## Authentication

```
Google Sign-In → verify token → check @plmediaagency.com
→ create/lookup user with role → session
→ wrong domain → 403
```
First user = admin. Admin promotes others via DB (admin panel later).

---

## Deployment — Free Tier → Custom Domain

**Stage 1:** Render free tier.
**Stage 2:** Custom domain — zero code changes (DNS + Render dashboard + Google OAuth + FRONTEND_URL env var).

```python
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
```
```javascript
const API_BASE = import.meta.env.VITE_API_URL || "/api";
```

---

## Environment Variables

| Variable              | Description                     | Where Set       |
|-----------------------|---------------------------------|-----------------|
| `DATABASE_URL`        | PostgreSQL connection string    | Render env      |
| `GROK_API_KEY`        | xAI API key                     | Render env      |
| `GROK_API_URL`        | xAI endpoint (default exists)   | Render env      |
| `LUMEN_API_URL`       | Lumen CMS endpoint (future)     | Render env      |
| `LUMEN_API_KEY`       | Lumen CMS key (future)          | Render env      |
| `RENDER_API_KEY`      | Render deploy key               | Shell / CI      |
| `FLASK_ENV`           | development / production        | Render env      |
| `SECRET_KEY`          | Flask sessions/JWT              | Render env      |
| `GOOGLE_CLIENT_ID`    | Google OAuth client ID          | Render env      |
| `GOOGLE_CLIENT_SECRET`| Google OAuth client secret      | Render env      |
| `FRONTEND_URL`        | CORS + OAuth redirects          | Render env      |

---

## Global Rules (from CLAUDE.md)

1. Every commit: `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`.
2. Commit messages explain "why."
3. No Unicode in logger output — `[OK]`, `[--]`, `[ERR]`.
4. `d.get("key") or ""` not `d.get("key", "")`.
5. Never `COPY ../` in Docker.
6. `python3 -m pip` not bare `pip`.
7. Testing mandatory. pytest. Happy-path + edge-case per function.
8. `.lower()` both sides for case-insensitive checks.
9. Render: always manual deploy after push.
10. `$RENDER_API_KEY` — never ask user.
11. Extensive comments. Every function docstring. Junior-dev friendly.

---

## Open Questions / TODOs

- [ ] **Lumen API docs** — Stubbed until Ben provides.
- [ ] **xAI API key** — Ben to provide.
- [ ] **Google OAuth credentials** — Ben to create Google Cloud project. (Code ready, drop GOOGLE_CLIENT_ID into env vars)
- [ ] **Custom domain** — When ready to migrate off Render free tier.
- [x] **Source List prompts** — 34 configs from Lead Pitcher spreadsheet.
- [x] **PAPA prompt** — Full text captured (~4,800 chars).
- [x] **PSST prompt** — Full text captured (~7,200 chars).
- [x] **Amy Bot prompt** — Full text captured (~5,500 chars). Validation logic: parse `DECISION: APPROVE` / `DECISION: REJECT`.

---

## How to Use This Plan with Claude Code

1. Copy `PROJECT_PLAN.md`, `CLAUDE.md`, and `PROMPT_SEED_DATA.md` into root of new repo.
2. Tell Claude Code: *"Read PROJECT_PLAN.md and CLAUDE.md. Start with Phase 1."*
3. After each phase: review, test, then *"Proceed to Phase 1.5"* (etc.).
4. Phase 3 will need the prompt seed data — Claude Code should read `PROMPT_SEED_DATA.md` and the Lead Pitcher spreadsheet to generate the migration SQL.
