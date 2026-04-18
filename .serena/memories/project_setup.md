# Project: Work Maturation Platform (Tuio)

## Stack
- Backend: Python 3.12+, FastAPI, SQLAlchemy async, Alembic, Celery (Postgres broker)
- Frontend: Next.js 14, TypeScript strict, Tailwind
- DB: Postgres 16
- External: Dundun (AI), Puppet (RAG), Jira (fakeable in dev)

## Testing
```bash
cd backend && pytest
cd frontend && npm test
```

## Code Conventions
- All code/commits/docs: **English**
- TDD mandatory: RED → GREEN → REFACTOR
- Naming: Python snake_case files/funcs, PascalCase classes; TS camelCase files/vars, PascalCase classes
- Strict type checking: mypy, TypeScript strict mode
- DDD layered: domain → application → infrastructure → presentation

## Dev Ports
- Postgres: 17000
- Backend: 17004
- Frontend: 17005

## Run Tests
```bash
cd backend && pytest  # Uses testcontainers for Postgres
```
