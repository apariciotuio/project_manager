---
name: core
description: Core development agent for Tuio projects — composable packages for TDD, Security by Design, structured pipelines, and code review gates
---

# Tuio Development Agent

Core development agent package for Tuio projects. Domain-specific standards are available as **composable packages** — each project imports only what it needs.

## Packages

| Package | What it adds |
|---------|-------------|
| **core** (root) | Pipeline enforcement, agent routing, base standards, TDD rules, 5 core agents, 8 core prompts |
| **backend** | DDD, SOLID, API design + backend-developer, db-reviewer agents |
| **frontend** | frontend-developer agent + plan/develop prompts |
| **temporal** | Workflow determinism, activity/worker patterns |
| **testing** | TDD methodology, fakes > mocks + test-engineer agent |
| **security** | OWASP, input validation, secrets management |
| **documentation** | READMEs, changelogs, API specs, ADRs |
| **qa-playwright** | Playwright E2E, page objects + qa-automation-engineer agent |
| **data-engineering** | Databricks medallion, DLT, Unity Catalog + data-engineer agent |
| **ml-engineering** | MLflow, experiment tracking + ml-engineer agent |
| **swarm** | Multi-agent parallel coordination |

## Development Pipelines

| Pipeline | Flow | When to use |
|----------|------|-------------|
| **Feature** | `enrich-us` → `plan-task` → `plan-backend-task` / `plan-frontend-task` → `develop-backend` / `develop-frontend` → `code-review` → `review-before-push` | New features, significant changes |
| **PoC** | `plan-poc` → `develop-poc` | Fast validation, no TDD ceremony |
| **QA** | `plan-qa-tests` → `develop-qa-tests` | E2E / acceptance tests |
| **Data** | `plan-data-pipeline` → `develop-data-pipeline` | Databricks medallion pipelines |
| **ML** | `plan-ml-model` → `develop-ml-model` | MLflow model development |
| **Quick Fix** | `develop-quick-fix` | Trivial changes (<=3 files) |

## Non-Negotiable Rules

- **TDD**: RED → GREEN → REFACTOR. No exceptions.
- **Security by Design**: "How can this be exploited?" before every feature.
- **Two reviews before push**: `code-review` then `review-before-push`.
- **Plan before implement**: Features require plans. No plan → refuse.
- **Delegation is directional**: Thinking → Execution → Trivial. Never upward.
- **English only**: All code, comments, commits, docs.
