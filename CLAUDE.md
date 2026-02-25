# Mimic — CR News Pipeline Automation

## Overview
Mimic automates the CR News editorial pipeline (Source List → PAPA/PSST → Amy Bot → CMS) via a React + Flask web app. It replaces a manual copy/paste workflow with automated Grok API calls and editorial validation.

## Tech Stack
| Layer | Technology |
|-------|-----------|
| Frontend | React (Vite) + React Router |
| Backend | Python 3.14 / Flask |
| LLM API | xAI Grok API |
| Database | PostgreSQL 16 (Render) |
| Auth | Google OAuth 2.0 (@plmediaagency.com) |
| Deployment | Docker + Render |
| Testing | pytest (backend), Jest (frontend) |

## Local Development

### Backend
```bash
cd backend
python3 -m pip install -r requirements.txt
python3 -m flask run  # http://localhost:5000
```

### Frontend
```bash
cd frontend
npm install
npm run dev  # http://localhost:5173 (proxies /api to :5000)
```

### Docker (full stack)
```bash
docker-compose up --build  # http://localhost:3000
```

### Tests
```bash
python3 -m pytest tests/ -v
```

## Environment Variables
| Variable | Description | Where Set |
|----------|-------------|-----------|
| `DATABASE_URL` | PostgreSQL connection string | Render env / .env |
| `SECRET_KEY` | Flask sessions/JWT | Render env / .env |
| `FLASK_ENV` | development / production | Render env / .env |
| `FRONTEND_URL` | CORS + OAuth redirects | Render env / .env |
| `GROK_API_KEY` | xAI API key | Render env / .env |
| `GROK_API_URL` | xAI endpoint | Render env / .env |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | Render env / .env |
| `GOOGLE_CLIENT_SECRET` | Google OAuth secret | Render env / .env |
| `LUMEN_API_URL` | Lumen CMS endpoint (future) | Render env / .env |
| `LUMEN_API_KEY` | Lumen CMS key (future) | Render env / .env |
| `RENDER_API_KEY` | Render deploy key | Shell / CI |

## Project Structure
```
Mimic/
├── CLAUDE.md
├── PROJECT_PLAN.md
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
├── backend/
│   ├── app.py            # Flask factory + health check
│   ├── config.py         # Config + TestConfig
│   ├── requirements.txt
│   ├── models/           # SQLAlchemy models (4 tables)
│   ├── routes/           # API blueprints
│   ├── services/         # Business logic
│   └── migrations/       # SQL migration files
├── frontend/             # React + Vite
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── pages/
│   └── vite.config.js
└── tests/                # pytest
```

## Database Tables
- **users** — Google OAuth accounts, roles (admin/user)
- **prompts** — Prompt Library (source-list, papa, amy-bot types)
- **stories** — Pipeline results (approved + rejected)
- **pipeline_runs** — Audit log per Grok API call

## Global Rules
1. Every commit: `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`
2. Commit messages explain "why" not just "what"
3. No Unicode symbols in logger output — use `[OK]`, `[--]`, `[ERR]`
4. `d.get("key") or ""` not `d.get("key", "")` to handle None values
5. Never `COPY ../` in Dockerfiles
6. `python3 -m pip` not bare `pip`
7. Testing mandatory: pytest, happy-path + edge-case per function
8. `.lower()` both sides for case-insensitive checks
9. Render: always trigger manual deploy after push
10. `$RENDER_API_KEY` from env — never ask user
11. Extensive comments, every function gets a docstring, junior-dev friendly
