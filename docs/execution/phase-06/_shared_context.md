# Shared Context: Phase 06 — Code Cleanup for OSS

## Goal
Strip private-repo artifacts, remove dead code, apply Phase 0 decisions. Verify existing auth/multi-tenancy works as-is. The codebase should emerge clean — no dead code, no private-repo baggage, no retired CLI surface. Backend boots cleanly, tests pass.

## Key Artifacts
- **Phase plan (source of truth):** `docs/plan/phase-06-code-cleanup.md`
- **CLI surface decision:** `docs/decision/cli-surface.md`
- **Queue strategy decision:** `docs/decision/queue-strategy.md`
- **Config design decision:** `docs/decision/env-config-design.md`
- **Logging strategy decision:** `docs/decision/logging-observability-strategy.md`
- **Embedding model decision:** `docs/decision/2026-04-07-embedding-model-selection.md`
- **Data directory decision:** `docs/decision/2026-04-07-data-directory-convention.md`

## Architecture Overview

### What This Phase Removes
1. **`project_mgmt` domain** — template scaffolding with no place in LinkedOut (Phase 0E decision). ~20+ files.
2. **Procrastinate task queue** — replaced by synchronous enrichment with simple retry (Phase 0F, `docs/decision/queue-strategy.md`).
3. **`rcv2` CLI and legacy entry points** — replaced by flat `linkedout` namespace (Phase 0A, `docs/decision/cli-surface.md`).
4. **Hardcoded dev paths** — `.` references, private-repo artifacts.
5. **`shared/test_endpoints/sse_router.py`** — spike artifact (Phase 6 decision Q4).

### What This Phase Keeps (Explicitly)
1. **Auth/multi-tenancy** — system tenant/BU/user model. No code changes, only documentation (Phase 0B/0D).
2. **`organization/` module** — load-bearing tenant/BU/enrichment_config infrastructure. NOT template scaffolding (Phase 6 decision Q7).
3. **`utilities/prompt_manager/`** — SJ decision: keep (Phase 6 decision Q2).
4. **Firebase auth provider code** — kept with comment: `# Firebase auth preserved for potential multi-user support — see Phase 0B decision.`

### What This Phase Creates
1. **`docs/architecture/auth-model.md`** — auth model documentation
2. **`shared/utilities/langfuse_guard.py`** — no-op stubs when Langfuse is disabled
3. **`linkedout/cli.py` + `linkedout/commands/`** — new flat CLI namespace with 13+1 commands
4. **Fresh baseline migration** — single Alembic migration replacing entire history
5. **`requirements-dev.txt`** — dev/test dependencies split out

## Codebase Conventions
- **Build system:** `uv run` for Python commands. Dependencies in `backend/requirements.txt`.
- **ORM:** SQLAlchemy 2.0 with `Mapped[]` type annotations. Alembic for migrations.
- **Entities:** Domain entities in `backend/src/linkedout/<domain>/entities/`. Base class: `BaseEntity` from `common.entities.base_entity`.
- **Services:** Business logic in `backend/src/linkedout/<domain>/services/`.
- **CLI:** Click commands currently in `backend/src/dev_tools/`. Moving to `backend/src/linkedout/commands/`.
- **Logging:** loguru via `get_logger()` from `shared.utilities.logger`. Bind `component` and `operation` fields.
- **Config:** pydantic-settings via `backend/src/shared/config/config.py`. Env vars override YAML. Prefix: `LINKEDOUT_`.
- **DB sessions:** `db_session_manager.get_session(DbSessionType.READ|WRITE, app_user_id=...)` context manager.
- **Tests:** pytest in `backend/tests/`. Unit tests mock external APIs.
- **System user:** `SYSTEM_USER_ID` from `dev_tools.db.fixed_data` for CLI operations.

## Key File Paths

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app — imports routers, Procrastinate lifecycle |
| `backend/src/project_mgmt/` | Domain to delete entirely |
| `backend/src/shared/queue/` | Queue module to delete entirely |
| `backend/src/shared/test_endpoints/sse_router.py` | SSE spike artifact to delete |
| `backend/src/shared/auth/` | Auth module — read, document, don't change |
| `backend/src/shared/config/config.py` | Config singleton — Langfuse flag lives here |
| `backend/src/linkedout/enrichment_pipeline/` | Enrichment — queue tasks become sync calls |
| `backend/src/linkedout/intelligence/tools/` | 9 files with `@observe` decorator to guard |
| `backend/src/linkedout/intelligence/controllers/` | 2 files with Langfuse `get_client` to guard |
| `backend/src/linkedout/intelligence/agents/search_agent.py` | Langfuse agent usage to guard |
| `backend/src/linkedout/intelligence/explainer/why_this_person.py` | Langfuse usage to guard |
| `backend/src/dev_tools/` | Legacy CLI — implementations move to `linkedout/commands/` |
| `backend/pyproject.toml` | Entry points to clean up |
| `backend/requirements.txt` | Dependencies to audit |
| `backend/migrations/` | Old migrations — replaced by fresh baseline |
| `backend/migrations/env.py` | Alembic config — remove Procrastinate exclusions |

## Resolved Decisions (Phase 6 — SJ, 2026-04-07)

1. **`common/` module scope:** Investigate during implementation. Grep `from common` / `import common` before deciding. Don't delete blind.
2. **`utilities/prompt_manager/`:** Keep. SJ decision.
3. **Alembic migrations:** Replace entire migration history with a single fresh baseline migration. One-way only (no down-migrations). Baseline includes all current tables minus `project_mgmt` and `procrastinate_*`, all indexes (HNSW, GIN, B-tree), extensions. Old migration files deleted.
4. **`shared/test_endpoints/sse_router.py`:** Remove. Spike artifact.
5. **Firebase auth provider code:** Keep as-is, add comment.
6. **`dev_tools/` directory:** Move implementation files to `linkedout/commands/`, delete `dev_tools/cli.py` and `rcv2` entry point. Clean break.
7. **`organization/` module:** DO NOT REMOVE. Actively used.

## Cross-Phase Decisions Affecting Phase 6

- **Phase 5 (embedding schema):** Dual-column pgvector schema goes into the fresh baseline migration.
- **`start-backend` idempotency:** Must detect existing process on port, kill it, then start fresh.
- **Tooling:** Use `uv` and `requirements.txt` everywhere.

## Build Order

```
sp1 (Auth Verification & Docs)
  ↓
sp2 (project_mgmt Removal) ──┐
sp3 (Procrastinate Removal) ──┤── can run in parallel (independent removals)
sp4 (Langfuse Guard) ─────────┘
  ↓
sp5 (Small Cleanups: paths + SSE router)
  ↓
sp6 (CLI Surface Refactor) ←── depends on sp2-sp4 (needs clean import tree)
  ↓
sp7 (Fresh Baseline Migration) ←── depends on sp2-sp3 (knows which tables are gone)
  ↓
sp8 (Dependency Cleanup) ←── depends on sp2-sp4 (knows which deps are removed)
  ↓
sp9 (Test Suite Green) ←── runs last, validates everything
```

## Phase Dependency Summary

| Sub-Phase | Depends On | Blocks | Can Parallel With |
|-----------|-----------|--------|-------------------|
| sp1 | None | sp2, sp3, sp4 | None |
| sp2 | sp1 | sp5, sp6, sp7, sp8 | sp3, sp4 |
| sp3 | sp1 | sp5, sp6, sp7, sp8 | sp2, sp4 |
| sp4 | sp1 | sp5, sp6, sp8 | sp2, sp3 |
| sp5 | sp2, sp3, sp4 | sp6 | None |
| sp6 | sp5 | sp9 | sp7, sp8 |
| sp7 | sp2, sp3 | sp9 | sp6, sp8 |
| sp8 | sp2, sp3, sp4 | sp9 | sp6, sp7 |
| sp9 | sp6, sp7, sp8 | None | None |

---

## Agents & Skills to Leverage

The following `.claude/agents/` and `.claude/skills/` are available and SHOULD be invoked during sub-phase execution where applicable:

### Skills (apply to ALL sub-phases)
| Skill | When to Invoke |
|-------|---------------|
| `.claude/skills/python-best-practices/SKILL.md` | When refactoring CLI surface, creating `linkedout/commands/` modules |
| `.claude/skills/pytest-best-practices/SKILL.md` | When updating tests after removals (sp9) |
| `.claude/skills/docstring-best-practices/SKILL.md` | When creating new CLI command modules, `langfuse_guard.py` |
| `.claude/skills/mvcs-compliance/SKILL.md` | When verifying service/repo/controller layers are intact after `project_mgmt` removal, Procrastinate removal, and CLI refactor |

### Agents (sub-phase specific)
| Agent | Sub-Phase | When to Invoke |
|-------|-----------|---------------|
| `.claude/agents/crud-compliance-checker-agent.md` | sp9 (Test Suite Green) | After all removals, run compliance checks on remaining CRUD stacks (organization, crawled_profile, etc.) to verify nothing was broken by the cleanup |
| `.claude/agents/review-ai-agent.md` | sp9 (Test Suite Green) | Verify AI agent implementations still work after Langfuse guard changes and import path changes |
| `.claude/agents/integration-test-creator-agent.md` | sp9 (Test Suite Green) | Reference for ensuring integration tests pass — test fixture patterns, seeded data |

### Notes
- This phase is primarily about removal and refactoring, not creation — CRUD creation agents don't apply
- The compliance checker is valuable post-removal to verify surviving CRUD stacks are still compliant
- `mvcs-compliance` skill is critical during sp6 (CLI refactor) — the new `linkedout/commands/` should call services, not repositories directly
