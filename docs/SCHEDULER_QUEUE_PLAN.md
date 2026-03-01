# Scheduled Daily Pipeline + Shared Queue — Implementation Plan

## Status: DEPLOYED TO STAGING — Testing in progress

## Overview

Automates daily source list discovery via a cron job so users log in to a pre-populated
queue and only do the human part: review sources, select PAPA/PSST, execute refinement.

**Architecture:**
```
Render Cron Job (daily 10:00 UTC)
  → POST /api/scheduler/run (secret auth)
    → For each schedule-enabled source-list prompt:
      → Call Grok with search (same as manual run)
      → Parse sources server-side (Python port of parseSources)
      → Create QueueItem rows (pending)

Users log in → /queue page
  → See pending items filtered by UserAgency permissions
  → Select PAPA/PSST per source → Run → Poll → Results
```

## Branch Strategy

All phases on `staging` branch. Feature branches preserved for rollback:
- `feature/scheduler-phase1` — Backend foundation (migration, models, source parser)
- `feature/scheduler-phase2` — Scheduler service + cron endpoint
- `feature/scheduler-phase3` — Queue API routes
- `feature/scheduler-phase4` — Frontend (QueuePage, prompt changes, dashboard)

## Commits on staging (5 total, 225 tests)

1. `76b6e32` Phase 1: migration, QueueItem model, source parser, 20 tests
2. `f1c192a` Phase 2: scheduler service, cron endpoint, 11 tests
3. `e52e375` Phase 3: queue API routes, prompt changes, 17 tests
4. `af88c1b` Phase 4: QueuePage, App nav, PromptLibrary schedule, Dashboard stats
5. `4a149ed` Hotfix: split multi-statement SQL migrations for SQLAlchemy 2.0

## Files Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| `backend/migrations/010_add_scheduler_queue.sql` | New | queue_items table, schedule_enabled column |
| `backend/models/queue_item.py` | New | QueueItem model |
| `backend/models/__init__.py` | Edit | Import QueueItem |
| `backend/models/prompt.py` | Edit | Add schedule_enabled column + to_dict |
| `backend/services/source_parser.py` | New | Python port of parseSources |
| `backend/services/scheduler_service.py` | New | Daily run orchestrator |
| `backend/routes/scheduler.py` | New | Cron endpoint |
| `backend/routes/queue.py` | New | Queue CRUD + execute |
| `backend/routes/__init__.py` | Edit | Register scheduler + queue blueprints |
| `backend/routes/prompts.py` | Edit | Handle schedule_enabled in create/update |
| `backend/config.py` | Edit | Add SCHEDULER_SECRET |
| `backend/app.py` | Edit | Fix migration runner for SQLAlchemy 2.0 |
| `frontend/src/pages/QueuePage.jsx` | New | Shared review queue UI |
| `frontend/src/App.jsx` | Edit | Import QueuePage, add route + nav link |
| `frontend/src/pages/PromptLibraryPage.jsx` | Edit | Schedule checkbox + badge |
| `frontend/src/pages/DashboardPage.jsx` | Edit | Queue stats section |
| `tests/test_source_parser.py` | New | 20 parser parity tests |
| `tests/test_scheduler_service.py` | New | 6 scheduler service tests |
| `tests/test_routes_scheduler.py` | New | 5 cron auth tests |
| `tests/test_routes_queue.py` | New | 17 queue route tests |

## Staging Testing Checklist

- [ ] Schedule checkbox — edit source-list prompt, check "Enable daily scheduled runs", save
- [ ] Schedule badge — green "Scheduled" badge appears on prompt card after save
- [ ] Queue page empty state — /queue shows "No pending sources" when empty
- [ ] Nav link — "Queue" link in nav bar between Prompts and Stories
- [ ] Set SCHEDULER_SECRET env var on staging backend
- [ ] Scheduler endpoint — POST /api/scheduler/run with X-Scheduler-Secret
- [ ] Queue populates — items appear on /queue grouped by opportunity
- [ ] Permission filtering — non-admin only sees assigned agency items
- [ ] PAPA/PSST execute — select, Run All, poll, auto-navigate to results
- [ ] Discard flow — discard items, confirm, removed from queue
- [ ] Dashboard banner — yellow "X sources pending review" when queue has items
- [ ] Existing manual flow — Prompts → Run Selected → Batch Review still works

## Phase 5: Render Production Setup (after testing)

1. Set `SCHEDULER_SECRET` env var on prod backend
2. Merge staging → master
3. Create Render Cron Job: `0 10 * * *` (10:00 UTC daily)
4. Command: `curl -s -X POST -H "X-Scheduler-Secret: $SCHEDULER_SECRET" https://tor-bot-api-19yx.onrender.com/api/scheduler/run`

## Known Fix Applied

- **Migration runner**: SQLAlchemy 2.0 can't execute multi-statement SQL in one `text()` call
- **Fix**: split on semicolons, execute each statement individually in `app.py _auto_migrate()`

---

## Phase 6: Speed-Up Optimizations

Six independent features to reduce pipeline latency, eliminate waste, and improve UX.
Each ships as its own feature branch → PR to staging for independent testing.

### PR 1: `feature/parallel-refinement` — Parallel Refinement Execution
- **Problem:** Queue "Run All" fires pipelines sequentially — 10 sources × 30s = 5 min
- **Solution:** `POST /api/queue/execute-batch` uses `ThreadPoolExecutor(max_workers=5)` for concurrent runs
- **Files:** `backend/routes/queue.py`, `frontend/src/pages/QueuePage.jsx`, `tests/test_routes_queue.py`

### PR 2: `feature/source-dedup` — Source Deduplication
- **Problem:** Same tweet/URL appears in consecutive daily scheduler runs, wasting Grok calls
- **Solution:** Hash source URLs, skip items already seen in last N days (configurable via `DEDUP_WINDOW_DAYS`)
- **Files:** `backend/migrations/011_add_seen_sources.sql`, `backend/models/seen_source.py`, `backend/services/scheduler_service.py`, `backend/config.py`, `tests/test_source_dedup.py`

### PR 3: `feature/prefetch-enrichment` — Pre-fetch URL Enrichment on Queue Items
- **Problem:** QueuePage re-fetches enrichments via `/pipeline/status/{story_id}` per story on load
- **Solution:** Store enrichment JSON on QueueItem during scheduler run, serve directly in API
- **Files:** `backend/migrations/012_add_queue_enrichment.sql`, `backend/models/queue_item.py`, `backend/services/scheduler_service.py`, `frontend/src/pages/QueuePage.jsx`, `tests/test_scheduler_service.py`

### PR 4: `feature/smart-scheduling` — Smart Schedule Frequency
- **Problem:** All scheduled prompts run daily at the same time
- **Solution:** `schedule_frequency` (daily/weekdays/mwf/weekly) and `schedule_time` fields on prompts
- **Files:** `backend/migrations/013_add_schedule_fields.sql`, `backend/models/prompt.py`, `backend/routes/prompts.py`, `backend/services/scheduler_service.py`, `frontend/src/pages/PromptLibraryPage.jsx`, `tests/test_scheduler_service.py`

### PR 5: `feature/batch-refinement` — Batch Refinement Prompt (Experimental)
- **Problem:** Running PAPA/PSST on each source individually = N API calls
- **Solution:** Optionally batch up to N sources into a single Grok call, parse multi-source output back
- **Files:** `backend/routes/queue.py`, `backend/services/pipeline_service.py`, `frontend/src/pages/QueuePage.jsx`, `tests/test_batch_refinement.py`

### PR 6: `feature/sse-push` — SSE Push Events (Replace Polling)
- **Problem:** Frontend polls `/pipeline/status/{story_id}` every 2s — wasteful and laggy
- **Solution:** Server-Sent Events endpoint with internal pub/sub event bus
- **Files:** `backend/routes/events.py`, `backend/routes/__init__.py`, `backend/services/pipeline_service.py`, `backend/routes/queue.py`, `frontend/src/utils/pipelineEvents.js`, `frontend/src/pages/QueuePage.jsx`, `frontend/src/pages/BatchReviewPage.jsx`, `tests/test_routes_events.py`

### Execution Order
1. PR 1: Parallel refinement (biggest user-facing impact)
2. PR 2: Source dedup (reduces daily noise)
3. PR 3: Pre-fetch enrichment (quick win, less API calls on page load)
4. PR 4: Smart scheduling (small schema + UI)
5. PR 5: Batch refinement (experimental, test quality)
6. PR 6: SSE push (replaces polling everywhere)
