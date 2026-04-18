# M0 — Repo Bootstrap

Source of truth: `tasks/implementation_plan.md` §2.

**Goal:** `docker-compose up` brings full stack; `pytest` green; `npm test` green; CI green; new dev runs in <15 min.

**Status: COMPLETED** (2026-04-15) — CI/CD + pre-commit descoped by user decision; all remaining exit criteria met.

## Deliverables

### Monorepo skeleton
- [x] `backend/` tree per implementation_plan.md §2 (domain/application/infrastructure/presentation/config + migrations + tests) — 2026-04-15
- [x] `frontend/` tree (Next.js App Router + components + lib + hooks + styles + locales + __tests__) — 2026-04-15
- [x] Root `.gitignore` extensions (venv, node_modules, .env, coverage, dist, build, .pytest_cache, __pycache__) — 2026-04-15
- [x] Root `README.md` with 15-min onboarding — 2026-04-15
- [x] Root `.env.example` with every var documented — 2026-04-15 (ports ≥17000)

### Infra
- [x] `docker-compose.dev.yml` — Postgres 16, Backend, Frontend — 2026-04-15 (Redis and MinIO removed 2026-04-15 per user decision; cache/broker → Postgres; attachments deferred to EP-16)
- [x] `backend/Dockerfile` (dev target) — 2026-04-15
- [x] `frontend/Dockerfile` (dev target) — 2026-04-15

### Backend skeleton
- [x] FastAPI app with `/api/v1/health` endpoint — 2026-04-15
- [x] `CorrelationIDMiddleware` — 2026-04-15
- [x] stdlib `logging` config (JSON format + correlation_id) — 2026-04-15
- [x] `pydantic-settings` config classes: `AppSettings`, `DatabaseSettings`, `CelerySettings`, `AuthSettings`, `DundunSettings`, `PuppetSettings`, `JiraSettings` — 2026-04-15 (RedisSettings + StorageSettings removed 2026-04-15)
- [x] SQLAlchemy async engine wiring — 2026-04-15
- [x] Alembic initialized with empty baseline — 2026-04-15
- [x] Celery app with `default`, `dundun`, `puppet_sync` queues — 2026-04-15 (broker switched to Postgres via `celery[sqlalchemy]`; `TASK_ALWAYS_EAGER=true` default until M2 confirms broker)
- [x] DI container pattern established (constructor injection; settings via get_settings()) — 2026-04-15
- [x] `FakeDundunClient` + `FakePuppetClient` skeletons in `tests/fakes/` — 2026-04-15
- [x] `pyproject.toml` with: fastapi, sqlalchemy[asyncio], alembic, pydantic-settings, celery, redis, httpx, pytest, pytest-asyncio, pytest-cov, mypy, ruff, black, bandit — 2026-04-15
- [x] `tests/conftest.py` with Postgres testcontainer + Celery eager mode — 2026-04-15 (Redis fixture removed)
- [x] One passing smoke test: `GET /api/v1/health` returns 200 with DB check — RED confirmed, GREEN 3/3 2026-04-15 (Redis check removed 2026-04-15)

### Frontend skeleton
- [x] Next.js 14 App Router + TypeScript strict — 2026-04-15
- [x] Tailwind configured — 2026-04-15
- [x] Dark-mode toggle — 2026-04-15
- [x] i18n setup with ES primary locale, stub EN — 2026-04-15
- [x] Dev proxy to backend `/api/v1/*` — 2026-04-15
- [x] Vitest + React Testing Library configured — 2026-04-15
- [x] Playwright configured (e2e skeleton) — 2026-04-15
- [x] One passing smoke test: renders home page — RED confirmed, GREEN 3/3 2026-04-15
- [x] `package.json` with scripts: dev, build, start, test, test:e2e, lint, typecheck, format — 2026-04-15

### Quality gates
- [~] `.pre-commit-config.yaml` — DESCOPED by user (no CI/CD in M0)
- [~] `.github/workflows/ci.yml` — DESCOPED by user (no CI/CD in M0)
- [~] `bandit` in CI — DESCOPED (bandit remains available via `pyproject.toml` dev deps; run manually)
- [x] `eslint-plugin-security` for TS — already in `frontend/package.json` devDependencies

## Exit Criteria

- [x] `docker-compose -f docker-compose.dev.yml up` → full stack up, Postgres healthy, backend `/api/v1/health` → 200 `{status:ok, db:ok}`, frontend `/` → 200 rendered — 2026-04-15
- [x] `cd backend && pytest` → green (3/3 tests passing, 82% coverage) — 2026-04-15
- [x] `cd frontend && npm test` → green (3/3 smoke tests passing) — 2026-04-15
- [~] `pre-commit run --all-files` — DESCOPED
- [~] CI green on main — DESCOPED
- [x] README onboarding verified (compose-up path + hybrid path) — 2026-04-15

## M0 Closeout Fixes (2026-04-15)

Bugs surfaced when the full stack first booted end-to-end:

- `backend/app/config/settings.py`: list fields (`cors_allowed_origins`, `allowed_domains`, `seed_superadmin_emails`) failed pydantic-settings JSON decode for CSV env values. Fixed by annotating with `NoDecode` + `field_validator(mode="before")` CSV splitter.
- `.env` / `.env.example`: `SEED_SUPERADMIN_EMAILS` → `AUTH_SEED_SUPERADMIN_EMAILS`; `CORS_ALLOWED_ORIGINS` → `APP_CORS_ALLOWED_ORIGINS`. The `.env` also had stale `REDIS_*` and `STORAGE_*` lines from before the Redis/MinIO descope — rewritten to match `.env.example`.
- `frontend/app/page.tsx`: `useTranslations` requires a client context — added `'use client'`.
- `frontend/app/layout.tsx`: dynamic JSON import returned a module namespace, failing RSC serialization — take `.default`.
- `frontend/app/providers.tsx`: added `timeZone="UTC"` to `NextIntlClientProvider` to silence `ENVIRONMENT_FALLBACK` warning.

## Known Non-blocking Debt (flag for later)

- `next@14.2.29` has a CVE (surfaced by `npm ci`). Bump when EP-19 starts.
- Backend tests require Docker on host (testcontainers) — cannot run inside the `wmp-backend` container.
