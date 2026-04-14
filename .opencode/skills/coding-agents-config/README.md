# tuio-dev-agent

Core development agent for Tuio projects. Enforces TDD, Security by Design, structured development pipelines (plan > implement > review > push), and code review gates.

Domain-specific standards are available as **composable packages** — each project imports only what it needs.

## Install

### Full install (everything)

```yaml
# apm.yml
dependencies:
  apm:
    - somostuio/coding-agents-config#apm                              # core
    - somostuio/coding-agents-config/packages/backend#apm
    - somostuio/coding-agents-config/packages/frontend#apm
    - somostuio/coding-agents-config/packages/temporal#apm
    - somostuio/coding-agents-config/packages/testing#apm
    - somostuio/coding-agents-config/packages/security#apm
    - somostuio/coding-agents-config/packages/documentation#apm
    - somostuio/coding-agents-config/packages/qa-playwright#apm
    - somostuio/coding-agents-config/packages/data-engineering#apm
    - somostuio/coding-agents-config/packages/ml-engineering#apm
    - somostuio/coding-agents-config/packages/swarm#apm
```

### Selective install (recommended)

Pick only the packages your project needs:

```yaml
# apm.yml — example for a Python + Temporal backend
dependencies:
  apm:
    - somostuio/coding-agents-config#apm                              # core (always)
    - somostuio/coding-agents-config/packages/backend#apm
    - somostuio/coding-agents-config/packages/temporal#apm
    - somostuio/coding-agents-config/packages/testing#apm
    - somostuio/coding-agents-config/packages/security#apm
```

Then run `apm install`.

## Packages

### Core (root)

Always required. Provides the development pipeline, agent routing, base standards, and core agents.

Skill: `core` (`SKILL.md` at repository root).

| What | Contents |
|------|----------|
| Instructions | soul, rules, agent-routing, agent-behavior, base-standards, task-management, insurance-domain |
| Agents | code-reviewer, sw-architect, product-analyst, poc-developer, quick-fix-developer |
| Prompts | plan-task, enrich-us, code-review, review-before-push, develop-poc, develop-quick-fix, plan-poc, meta-prompt |

### Domain Packages

| Package | Type | Skill | Instructions | Agents | Prompts |
|---------|------|-------|-------------|--------|---------|
| **backend** | hybrid | `backend` | DDD, SOLID, API design | backend-developer, db-reviewer | develop-backend, plan-backend-task, develop-backend-data-modeling |
| **frontend** | hybrid | `frontend` | *(none — uses core)* | frontend-developer | develop-frontend, plan-frontend-task |
| **temporal** | instructions | *(none)* | Workflow determinism, activities, workers | *(none)* | *(none)* |
| **testing** | hybrid | `testing` | TDD, fakes over mocks, triangulation | test-engineer | develop-backend-tests, develop-frontend-tests, test |
| **security** | instructions | *(none)* | OWASP, input validation, secrets | *(none)* | *(none)* |
| **documentation** | hybrid | `documentation` | READMEs, changelogs, API specs, ADRs | *(none)* | update-docs |
| **qa-playwright** | hybrid | `qa-playwright` | Playwright, page objects, test data | qa-automation-engineer (x2) | develop-qa-tests, plan-qa-tests |
| **data-engineering** | hybrid | `data-engineering` | Databricks, medallion, DLT, Unity Catalog | data-engineer | develop-data-pipeline, plan-data-pipeline, aidata-tasks |
| **ml-engineering** | hybrid | `ml-engineering` | MLflow, experiment tracking, model registry | ml-engineer | develop-ml-model, plan-ml-model |
| **swarm** | instructions | *(none)* | Multi-agent parallel coordination | *(none)* | *(none)* |

Rule: packages with `type: hybrid` must include a package-level `SKILL.md`.

## Development Pipelines

- **Feature**: enrich-us → plan-task → plan-backend/frontend-task → develop-backend/frontend (TDD) → code-review → review-before-push
- **PoC**: plan-poc → develop-poc (no TDD, track shortcuts)
- **QA**: plan-qa-tests → develop-qa-tests
- **Data**: plan-data-pipeline → develop-data-pipeline (medallion)
- **ML**: plan-ml-model → develop-ml-model (MLflow)

## Project Structure

```
coding-agents-config/
├── apm.yml                              # Core package manifest
├── .apm/
│   ├── instructions/                    # Core instructions (7)
│   ├── agents/                          # Core agents (5)
│   └── prompts/                         # Core prompts (8)
└── packages/
    ├── backend/                         # DDD, SOLID, API
    ├── frontend/                        # Component architecture
    ├── temporal/                        # Temporal workflows
    ├── testing/                         # TDD, test design
    ├── security/                        # OWASP, auth, secrets
    ├── documentation/                   # Docs standards
    ├── qa-playwright/                   # E2E testing
    ├── data-engineering/                # Databricks pipelines
    ├── ml-engineering/                  # MLflow models
    └── swarm/                           # Multi-agent coordination
```

Each package has its own `apm.yml` and `.apm/` directory with instructions, agents, and/or prompts.

## Primitive Types (What each file does)

APM packages are built from a small set of primitive files inside `.apm/`:

| Primitive | Source file | Required frontmatter | Purpose |
|-----------|-------------|----------------------|---------|
| **Instruction** | `.apm/instructions/*.instructions.md` | `description`, `applyTo` | Cross-cutting standards and guardrails applied by file pattern |
| **Agent** | `.apm/agents/*.agent.md` | `name`, `description` *(optional: `model`, `model_fallback`)* | Specialized AI persona/sub-agent |
| **Prompt** | `.apm/prompts/*.prompt.md` | `description` *(optional: `mode`, `input`)* | Reusable workflow command |
| **Sub-skill** | `.apm/skills/*/SKILL.md` | `name`, `description` | Promoted as top-level installable skill entry |
| **Skill** | `SKILL.md` (and optional extra files) | Skill metadata block | Reusable capability package |
| **Package manifest** | `apm.yml` | `name`, `version` | Declares package metadata, target/type, and dependencies |

## How APM resolves packages and conflicts

APM resolves primitives from your local package and dependencies deterministically:

- **Local-first precedence**: primitives in local `.apm/` override dependencies with the same primitive name.
- **Dependency order matters**: if two dependencies provide the same primitive, the one declared first in `dependencies.apm` wins.
- **Reproducibility**: resolved versions and deployed files are tracked in `apm.lock.yaml`.

This lets teams compose many packages while keeping behavior predictable across machines and CI.

## How this maps to Claude Code

`apm install` is the native deployment step for Claude. `apm compile` is optional.

| APM source | Claude destination | Result in Claude |
|------------|--------------------|------------------|
| `.apm/instructions/*.instructions.md` | `.claude/rules/*.md` | Rules loaded natively by Claude |
| `.apm/agents/*.agent.md` | `.claude/agents/*.md` | Sub-agents available in Claude |
| `.apm/prompts/*.prompt.md` | `.claude/commands/*.md` | Slash commands (e.g. `/code-review`) |
| `SKILL.md` (+ skill files) | `.claude/skills/{skill}/...` | Skills available to Claude agents |
| Hook JSON (if present) | `.claude/settings.json` (`hooks`) | Lifecycle hooks merged into Claude settings |

### Install vs compile (Claude)

- `apm install`: deploys primitives in Claude-native folders (`.claude/rules`, `.claude/agents`, `.claude/commands`, `.claude/skills`).
- `apm compile --target claude`: generates `CLAUDE.md` (instructions-only merged output). Useful when you want a single instruction file.

### Verify Claude integration

```bash
apm install
ls .claude/rules
ls .claude/agents
ls .claude/commands
ls .claude/skills
```

## How this maps to OpenCode

OpenCode support is split between native deployment and compiled instructions.

| APM source | OpenCode destination | Notes |
|------------|----------------------|-------|
| `.apm/agents/*.agent.md` | `.opencode/agents/*.md` | Native OpenCode agents |
| `.apm/prompts/*.prompt.md` | `.opencode/commands/*.md` | Native OpenCode commands |
| `SKILL.md` (+ skill files) | `.opencode/skills/{skill}/SKILL.md` | Native OpenCode skills |
| Instructions (`*.instructions.md`) | `AGENTS.md` via `apm compile` | OpenCode reads instructions from `AGENTS.md` |

### Install vs compile (OpenCode)

- `apm install`: deploys agents, commands, skills, and MCP config to OpenCode native files.
- `apm compile` (or `apm compile --target copilot`): required to generate `AGENTS.md` for instruction loading in OpenCode.

### Verify OpenCode integration

```bash
apm install
apm compile
ls .opencode/agents
ls .opencode/commands
ls .opencode/skills
ls AGENTS.md
```

## Built with

[APM](https://microsoft.github.io/apm/) — the Agent Package Manager.
