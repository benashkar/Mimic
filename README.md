# Mimic — CR News Pipeline Automation

Mimic automates a manual editorial pipeline that previously required copy-pasting between Grok, spreadsheets, and a CMS. It replaces that workflow with a React + Flask web app that orchestrates the xAI Grok API to discover, refine, validate, and publish newsroom-ready pitches.

## How It Works

```
Source List (discovery)  →  PAPA or PSST (refinement)  →  Amy Bot (validation)  →  CMS
     Grok searches              Structures pitch             Editorial review         Publish
     for stories                from source material         APPROVE or REJECT        or kill
```

1. **Source List** — User picks a pre-configured discovery prompt. Grok searches X/Twitter and the web for newsworthy stories matching a topic, region, and editorial angle.
2. **PAPA or PSST** — User selects an individual source from results, then picks a refinement type:
   - **PAPA** (Provided Announcement Pitch Assistant) — for organizational announcements
   - **PSST** (Provided Statement Speech Tool) — for individual statements/quotes
3. **Amy Bot** — Editorial review agent validates the refined pitch. Returns `APPROVE` or `REJECT`.
4. **Result** — Approved stories push to CMS. Rejected stories are killed (logged, never retried).

## Architecture

```
React (Vite) Frontend
  Google OAuth login (@plmediaagency.com)
  Prompt Library  |  Source List Runner  |  Pipeline  |  Stories Log
         │
         │  REST API — JWT auth
         ▼
Flask Backend
  /api/auth/*          — Google OAuth + JWT
  /api/prompts         — CRUD (admin-gated writes)
  /api/pipeline/*      — Source List + full pipeline (async)
  /api/stories         — Browse results + dashboard stats
         │
         ▼
PostgreSQL (Render)
  users, prompts, stories, pipeline_runs
```

## Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Frontend | React 19 + Vite 7 | SPA with React Router |
| Backend | Python 3.14 / Flask 3.1 | REST API + background threads |
| LLM API | xAI Grok API | grok-3-fast model |
| Database | PostgreSQL 16 | Render managed |
| Auth | Google OAuth 2.0 + JWT | Domain-restricted login |
| Deployment | Render | Static site + web service + managed DB |
| CI | GitHub Actions | pytest + frontend build on push |
| Containers | Docker Compose | Local dev with PostgreSQL |

## Features

- **Prompt Library** — CRUD for 3 prompt types (Source List, PAPA/PSST, Amy Bot) with routing metadata
- **Source List Runner** — Run discovery prompts, view individual sources, pick one to refine
- **Pipeline Execution** — Async refinement + validation with real-time polling (avoids Render 30s timeout)
- **Amy Bot Validation** — Automated editorial review with configurable rules
- **Stories Log** — Browse all pipeline runs with filters (approved/rejected/opportunity/state)
- **Dashboard** — Approval rate, total counts, per-opportunity breakdown
- **Role-Based Access** — Admin (full CRUD) and User (browse + run) roles
- **Audit Trail** — Every Grok API call logged with input, output, duration, and status

## Local Development

### Prerequisites

- Python 3.14+
- Node.js 24+
- Docker (optional, for PostgreSQL)

### Quick Start (Docker)

```bash
docker-compose up --build
```

This starts PostgreSQL, Flask backend (port 5000), and React frontend (port 3000).

### Manual Setup

**Backend:**

```bash
cd backend
python3 -m pip install -r requirements.txt
cp ../.env.example ../.env  # Edit with your values
flask run --port 5000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

Frontend dev server runs on http://localhost:5173 with API proxy to backend.

### Running Tests

```bash
# All backend tests
python3 -m pytest tests/ -v

# With coverage report
python3 -m pytest tests/ -v --cov=backend --cov-report=term-missing

# Frontend build check
cd frontend && npm run build
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `SECRET_KEY` | Yes | Flask sessions + JWT signing |
| `GROK_API_KEY` | Yes | xAI API key for Grok |
| `GOOGLE_CLIENT_ID` | Yes | Google OAuth client ID |
| `FRONTEND_URL` | Yes | Frontend URL for CORS |
| `GROK_API_URL` | No | xAI endpoint (default: `https://api.x.ai/v1/chat/completions`) |
| `GROK_MODEL` | No | Model name (default: `grok-3-fast`) |
| `GROK_TIMEOUT_SECONDS` | No | API timeout (default: `60`) |
| `JWT_EXPIRY_HOURS` | No | Token TTL (default: `24`) |
| `FLASK_ENV` | No | `development` or `production` |

See `.env.example` for a complete template.

## Deployment (Render)

The app runs on Render with 3 services:

| Service | Type | URL |
|---------|------|-----|
| Frontend | Static Site | `tor-bot-frontend.onrender.com` |
| Backend API | Web Service | `tor-bot-api-19yx.onrender.com` |
| Database | PostgreSQL 16 | Managed (Oregon) |

Auto-deploy is enabled on push to `master`. The frontend requires a SPA rewrite rule (`/* → /index.html`) configured in the Render dashboard.

## Database Schema

4 tables: `users`, `prompts`, `stories`, `pipeline_runs`.

- **users** — Google OAuth accounts with admin/user roles
- **prompts** — Prompt library (source-list, papa, amy-bot types) with routing metadata
- **stories** — Full pipeline journey: source list → refinement → validation → CMS
- **pipeline_runs** — Audit log per Grok API call (input, output, duration, status)

Schema defined in `backend/migrations/001_initial_schema.sql`.

## Project Structure

```
Mimic/
├── README.md
├── PROJECT_PLAN.md          # Detailed project specification
├── CLAUDE.md                # AI assistant guidelines
├── .env.example             # Environment variable template
├── docker-compose.yml       # Local dev (PostgreSQL + Flask + React)
├── Dockerfile.backend       # Python 3.14 + gunicorn
├── Dockerfile.frontend      # Node build + Nginx serve
├── .github/workflows/ci.yml # GitHub Actions (pytest + build)
│
├── backend/
│   ├── app.py               # Flask factory
│   ├── config.py            # Config classes
│   ├── requirements.txt
│   ├── models/              # SQLAlchemy ORM (User, Prompt, Story, PipelineRun)
│   ├── routes/              # Blueprints (auth, prompts, pipeline, stories)
│   ├── services/            # Business logic (auth, grok, pipeline, validation, cms)
│   ├── decorators/          # @login_required, @admin_required
│   └── migrations/          # SQL schema + seed data
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx          # Routes + nav + auth wrapper
│       ├── api/client.js    # Authenticated fetch wrapper
│       ├── context/         # AuthContext (JWT + Google OAuth)
│       ├── components/      # ProtectedRoute, AdminOnly, GoogleLoginBtn
│       └── pages/           # Login, Dashboard, PromptLibrary, SourceListRun,
│                            # Pipeline, Stories
│
└── tests/                   # pytest (71+ tests)
    ├── conftest.py          # Fixtures (app, client, auth_headers, make_user)
    ├── test_auth_service.py
    ├── test_decorators.py
    ├── test_grok_service.py
    ├── test_health.py
    ├── test_models.py
    ├── test_pipeline_service.py
    ├── test_routes_auth.py
    ├── test_routes_prompts.py
    ├── test_routes_stories.py
    └── test_validation_service.py
```

## Project Status

| Phase | Status |
|-------|--------|
| 1. Scaffolding & Database | Done |
| 1.5. Authentication & Roles | Done |
| 2. Grok API Integration | Done |
| 3. Prompt Library (CRUD + UI) | Done |
| 4. Source List Runner | Done |
| 5. Pipeline Execution | Done |
| 6. Stories Log & Dashboard | Done |
| 7. Docker, CI/CD & Deployment | Done |
| 8. CMS Integration (Lumen API) | Pending — awaiting API docs |

## License

Private repository. All rights reserved.
