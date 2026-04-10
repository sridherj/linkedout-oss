# Shared Context — All Phases

This document contains shared context that every phase-runner agent needs. Each phase file references this document but is otherwise self-contained.

---

## Project Overview

**reference_code_v2** is a reference repository demonstrating a production-grade Python/FastAPI application with:
- Multi-tenant MVCS (Model-View-Controller-Service) architecture
- TenantBu (Tenant + Business Unit) scoping at every layer
- AI agent infrastructure with lifecycle management
- 4-layer test infrastructure (repo, service, controller, integration)

## Architecture Layers

### Base Classes (`src/common/`)
- **BaseEntity** — nanoid-prefixed IDs, timestamps, soft delete, audit fields, version
- **TenantBuMixin** — tenant_id + bu_id FK columns with `backref` (auto-creates reverse relationships)
- **SoftDeleteMixin** — soft_delete(), restore(), is_deleted
- **BaseRepository[TEntity, TSortEnum]** — CRUD, FilterSpec-based filtering, pagination, tenant+BU scoping
- **BaseService[TEntity, TSchema, TRepository]** — CRUD orchestration, schema conversion, bulk ops
- **CRUDRouterFactory** — reusable FastAPI endpoint generation via CRUDRouterConfig

### Organization (`src/organization/`)
- **TenantEntity** — top-level org unit, NOT using BaseRepository (sits above scoping)
- **BuEntity** — child of Tenant, scoped by tenant_id only
- Custom repos/services/controllers (not generic base classes)

### Shared Infrastructure (`src/shared/`)
- Config (pydantic-settings, env-file-per-environment)
- DB session manager (read/write session types)
- Nanoid generation
- Logger

### Utilities (`src/utilities/`)
- LLM client (provider-agnostic, structured output)
- Prompt manager (local file + Langfuse, configurable)

## Key Conventions

| Convention | Value |
|-----------|-------|
| Module name | `project_mgmt` (NOT `project_management`) |
| Router naming | Plural: `labels_router`, `priorities_router` |
| ID prefix format | `{prefix}_{nanoid}` e.g. `label_abc123` |
| AgentRun ID prefix | `arn` |
| URL pattern | `/tenants/{tenant_id}/bus/{bu_id}/{entity_path}` |
| TenantBuMixin | Uses `backref` (NOT `back_populates`) for reverse relationships |
| Phase 3/4 data | Source of truth for all downstream phases |
| TaskStatus values | BACKLOG, TODO, IN_PROGRESS, IN_REVIEW, DONE, CANCELLED |
| ProjectStatus values | PLANNING, ACTIVE, ON_HOLD, COMPLETED, ARCHIVED |
| Principal field | `auth_provider_id` (NOT `id`) |

## Verification Gate

Every phase MUST end with `precommit-tests` passing:
```bash
# Unit tests (SQLite)
pytest tests/ -k "not integration and not live_llm" -x --tb=short

# Integration tests (PostgreSQL)
pytest tests/integration/ -x --tb=short

# Full suite
precommit-tests
```

## Phase Dependency Graph

```
Phase 2 (MVCS generalization) — MUST be first
  -> Phase 3 (Example domain + AppUser + CRUDRouterFactory)
       |-> Phase 4 (Auth) ─────────────────────────┐
       |-> Phase 5a (Basic test infra) ─────────────┤
       |-> Phase 6a (Agent infra: LLM, BaseAgent)   │
       |                                             │
       Phase 4 + 6a done -> Phase 5b (Auth mock + agent tests)
       Phase 6a done -> Phase 6b (TaskTriageAgent + tests)
       All done -> Phase 7 (Ops, CLI, config, reliability)
                     -> Phase 8 (Packhouse/linkedout cleanup)
```

## Packhouse Strategy

Packhouse/linkedout code stays as a living reference through Phases 2-7. It is ONLY removed in Phase 8. This means:
- New code coexists with rcm code
- `main.py` includes both old and new routers (until Phase 8)
- `conftest.py` imports both old and new entities (until Phase 8)
- Tests for both domains run in parallel (until Phase 8)

## Config Approach (Reconciliation Decision I6)

Composed config via multiple inheritance:
```python
class AuthConfig(BaseSettings): ...
class LLMConfig(BaseSettings): ...
class ReliabilityConfig(BaseSettings): ...
class AppConfig(AuthConfig, LLMConfig, ReliabilityConfig, BaseSettings): ...
```
NOT a flat 32-field BaseConfig class.
