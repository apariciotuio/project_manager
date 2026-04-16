# Work Maturation Platform

Internal Tuio platform for maturing user stories/work items into Ready-to-develop specs, with AI assistance (Dundun) and semantic search (Puppet). VPN-only, Google SSO.

**Status:** M0 (bootstrap). No feature code yet. See `tasks/implementation_plan.md`.

---

## Stack

- **Backend:** Python 3.12+, FastAPI, SQLAlchemy (async), Celery (Postgres broker), Alembic
- **Frontend:** Next.js 14 (App Router), TypeScript strict, Tailwind, next-intl
- **Data:** Postgres 16 (+ RLS) — also used as Celery broker/backend (no Redis)
- **External:** Dundun (AI), Puppet (RAG), Jira — all fakeable in dev
- **Object storage (attachments, EP-16):** deferred

---

## Port map (host, ≥17000)

| Port | Service |
|------|---------|
| 17000 | Postgres |
| 17004 | Backend (FastAPI) |
| 17005 | Frontend (Next.js) |
| 17006 | Dundun fake (reserved) |
| 17007 | Puppet fake (reserved) |

---

## 15-minute onboarding

### 0. Prereqs

- Docker + docker compose v2
- Python 3.12+ and `pip` (for local backend dev)
- Node.js 20+ and `npm` (for local frontend dev)

### 1. Clone + env

```bash
cp .env.example .env
# Fill secrets later; defaults work for local dev.
```

### 2. Bring the stack up (full — Docker)

```bash
docker compose -f docker-compose.dev.yml up --build
```

- Backend:  http://localhost:17004/api/v1/health
- Frontend: http://localhost:17005

Stop: `docker compose -f docker-compose.dev.yml down` (add `-v` to wipe volumes).

### 3. Hybrid (Postgres in Docker, apps local)

Faster iteration. Run only Postgres in Docker:

```bash
docker compose -f docker-compose.dev.yml up -d postgres
```

Then, in two terminals:

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 17004
```

```bash
# Frontend
cd frontend
npm ci
npm run dev              # listens on 17005 (next dev -p 17005)
```

---

## Test

```bash
# Backend (requires Docker running — uses testcontainers for Postgres)
cd backend
pytest

# Frontend
cd frontend
npm run typecheck
npm test
npm run test:e2e        # Playwright; needs backend + frontend running
```

---

## Repo layout

```
backend/     FastAPI app (DDD: domain / application / infrastructure / presentation)
frontend/    Next.js App Router
tasks/       Plans, specs, designs per epic (EP-00 … EP-19, M0)
docs/        Functional + UX docs
docker-compose.dev.yml
.env.example
```

---

## Next steps

M0 is the skeleton. Implementation starts at M1 (EP-00: auth + workspaces). See `tasks/implementation_plan.md` for the full roadmap and `tasks/<EP-XX>/` for per-epic plans.

## Conventions

- All code, commits, docs: **English**. UI copy: **Spanish** (i18n).
- TDD mandatory: RED → GREEN → REFACTOR.
- One commit per logical step, conventional format: `Refs: <EP-ID>`.
- Never push without running tests + type checks locally.
