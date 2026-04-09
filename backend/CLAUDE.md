# LinkedOut OSS — Backend

Python/FastAPI + PostgreSQL backend. See root `CLAUDE.md` for project-wide guidelines and specs.

## Verification Gate

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

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
