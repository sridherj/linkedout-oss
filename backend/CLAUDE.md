# LinkedOut OSS — Backend

Open-source professional network intelligence tool. This is the backend (Python/FastAPI + PostgreSQL).

## Behavioral Guidelines

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Scaffold First, Fill Later

**When dealing with a large problem, always scaffold first and fill later.**

1. Think through various ways by which you can decompose the problem
2. Extract out logical components
3. Then, and only then, fill in the details.
4. Look for opportunities to generalize (inheritance, modularity etc)

Ask yourself: "Would a senior architect decompose the problem into these components? Why/why not?"

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" -> "Write tests for invalid inputs, then make them pass"
- "Fix the bug" -> "Write a test that reproduces it, then make it pass"
- "Refactor X" -> "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] -> verify: [check]
2. [Step] -> verify: [check]
3. [Step] -> verify: [check]
```

### 5. Verification Gate

`precommit-tests` (unit + integration + live_llm) must pass after any significant change. This is the non-negotiable proof that nothing is broken.

## Agents (in .claude/agents/)

| Agent | Purpose |
|-------|---------|
| crud-orchestrator-agent | Orchestrates complete CRUD implementations by delegating to specialized agents |
| entity-creation-agent | Creates SQLAlchemy entity classes with TenantBuMixin |
| schema-creation-agent | Creates Pydantic schemas (enums, core, API) |
| repository-agent | Creates repository classes extending BaseRepository |
| service-agent | Creates service classes extending BaseService |
| controller-agent | Creates FastAPI controllers using CRUDRouterFactory (default) |
| custom-controller-agent | Creates hand-written controllers for custom endpoints |
| repository-test-agent | Creates repository wiring tests |
| service-test-agent | Creates service wiring tests |
| controller-test-agent | Creates controller wiring tests |
| integration-test-creator-agent | Creates integration tests against real PostgreSQL |
| seed-db-creator-agent | Extends database seeding infrastructure (dev) |
| seed-test-db-creator-agent | Extends database seeding infrastructure (test) |
| crud-compliance-checker-agent | Audits CRUD implementations for compliance |

## Specs (Source of Truth)
Product specs live in `docs/specs/` — the registry is `docs/specs/_registry.md`.
- **When to consult:** Before modifying any feature, before asking "how does X work?", before planning changes
- **Priority:** Specs are the **first place** to look when you need to understand a feature's behavior, contracts, or design rationale. Check specs before reading code, before reading agents, before reading plans.
- **Format:** Each spec covers behavior, data contracts, edge cases, and cross-references to other specs

## Repo Structure

```
linkedout-oss/
├── backend/          # You are here — Python/FastAPI
│   ├── src/
│   ├── migrations/   # Alembic
│   ├── tests/
│   └── pyproject.toml
├── extension/        # Chrome extension (optional add-on)
├── skills/           # Cross-platform skill definitions
│   ├── claude-code/
│   ├── codex/
│   └── copilot/
├── seed-data/        # Seed data scripts
└── docs/             # User-facing documentation
```

## Architecture

### MVCS Stack
| Layer | Base Class | Provides |
|-------|-----------|----------|
| Entity | `BaseEntity` | Prefixed IDs, timestamps, soft delete, audit fields, active flag, version |
| Repository | `BaseRepository[TEntity, TSortEnum]` | CRUD, FilterSpec-based filtering, pagination, sorting |
| Service | `BaseService[TEntity, TSchema, TRepository]` | CRUD orchestration, schema conversion, bulk ops |
| Controller | `CRUDRouterFactory` | Reusable CRUD endpoint generation |

### Multi-Tenancy
Default mode: `TenantBu` (Tenant -> Business Unit). All scoped entities use `TenantBuMixin`.
URL pattern: `/tenants/{tenant_id}/bus/{bu_id}/...`

### Module Structure
```
src/
  common/          # Base classes (entities, repos, services, controllers, schemas)
  organization/    # Tenant, BU, AppUser entities
  linkedout/       # LinkedOut domain (connections, companies, search, intelligence)
  shared/          # Cross-cutting utilities (auth, infra, test_utils)
  utilities/       # LLM client, prompt manager
  dev_tools/       # CLI, DB reset/seed/validate
```

### Testing Layers
| Layer | What's Real | What's Mocked |
|-------|-------------|---------------|
| Repository | SQLite DB | Nothing |
| Service | Nothing | Repository |
| Controller | Nothing | Service |
| Integration | PostgreSQL + full stack | Nothing |

## Design System
`../extension/docs/linkedout-design-system.md` — font choices, colors, spacing, and aesthetic direction.
Always read before making any visual or UI decisions. Do not deviate without explicit user approval.
In QA mode, flag any code that doesn't match the design system.

## Learnings

Reusable engineering principles from past sessions are in `plan_and_progress/LEARNINGS.md` (if present).
- **When to consult:** Before debugging, before designing a new system, before making architectural choices

## Decision Records

Significant technical decisions are documented in `docs/decision/` as lightweight ADRs.
- **Format:** `YYYY-MM-DD-<short-slug>.md` with Question, Key Findings, Decision, Implications
- **When to create:** go/no-go calls, architecture picks, tool/data source selections, strategy changes

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
