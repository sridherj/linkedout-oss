# Phase 6: Code Cleanup for OSS — Detailed Execution Plan

**Version:** 1.0
**Date:** 2026-04-07
**Status:** Draft — pending SJ review
**Phase Goal:** Strip private-repo artifacts, remove dead code, apply Phase 0 decisions. Verify existing auth/multi-tenancy works as-is.
**Dependencies:** Phase 0 (all spikes resolved), Phases 2-5 (env/config, logging, constants, embedding abstraction)
**Delivers:** A clean codebase that reflects OSS decisions — no dead code, no private-repo baggage, no retired CLI surface. Backend boots cleanly, tests pass.

---

## Phase Overview

Phase 6 takes the codebase that has been incrementally improved through Phases 2-5 (config, logging, constants, embeddings) and applies the "surgical cleanup" decisions from Phase 0. This phase is about **removal and verification**, not new features:

1. Verify auth/multi-tenancy works unchanged (Phase 0B/0D decisions)
2. Strip `project_mgmt` domain entirely (Phase 0E decision)
3. Remove Procrastinate queue, inline enrichment (Phase 0F decision — `docs/decision/queue-strategy.md`)
4. Guard Langfuse behind `LANGFUSE_ENABLED` (default off)
5. Refactor CLI from `rcv2` to `linkedout` flat namespace (Phase 0A — `docs/decision/cli-surface.md`)
6. Strip hardcoded dev paths
7. Clean up dependencies
8. Get test suite green

---

## Task Breakdown

### 6A. Auth & Multi-Tenancy Verification

**Goal:** Confirm the existing single-user setup (system tenant/BU/user) works in the OSS repo without any code changes. Document it.

**Acceptance criteria:**
- Backend starts and serves API requests using the system tenant/BU/user
- Extension connects and can crawl/save profiles
- RLS policies function correctly with the system tenant context
- A short doc at `docs/architecture/auth-model.md` describes the auth model (system tenant, BU, user IDs, how they're set, where they come from)
- No auth code is changed — only documented

**Files to inspect (read, not modify):**
- `backend/src/shared/auth/config.py` — `AuthConfig` class, `AUTH_ENABLED`, Firebase toggle
- `backend/src/shared/auth/dependencies/` — FastAPI dependency injection for auth
- `backend/src/shared/auth/providers/` — Firebase provider (will stay but be disabled by default)
- `backend/migrations/versions/d1e2f3a4b5c6_enable_rls_policies.py` — RLS migration
- `backend/src/shared/config/config.py` — tenant/BU/user defaults

**Files to create:**
- `docs/architecture/auth-model.md` — auth model documentation

**Integration points:**
- `docs/decision/env-config-design.md` — `agent-context.env` contains tenant/BU/user IDs
- Phase 0B (auth strategy) — SJ decided: keep as-is, no changes
- Phase 0D (multi-tenancy simplification) — SJ decided: current state is clean, no changes

**Testing:**
- Manual: Start backend, hit `/api/v1/connections?page=1&per_page=10` with system tenant headers → should return data
- Integration test: Existing integration tests should pass without changes

**Complexity:** S

**CRITICAL CONSTRAINT:** DO NOT make any auth/multi-tenancy code changes without consulting SJ — the existing implementation is intentional.

---

### 6B. `project_mgmt` Domain Removal

**Goal:** Completely remove the `project_mgmt` domain. This was from the original template and has no place in LinkedOut OSS (Phase 0E decision).

**Acceptance criteria:**
- All `project_mgmt` source code deleted
- All `project_mgmt` references removed from `main.py`, routers, imports
- All `project_mgmt` tests deleted
- All `project_mgmt` database tables addressed via migration (drop tables)
- `common/controllers/agent_run_controller.py` evaluated — keep if used by other domains, remove if only `project_mgmt` used it
- No import errors on backend startup

**Files to delete:**
- `backend/src/project_mgmt/` — entire directory (~20+ files: label, priority, project, task, project_summary, agents)
- `backend/tests/project_mgmt/` — entire test directory

**Files to modify:**
- `backend/main.py` — remove lines 34, 37-41 (project_mgmt imports), remove router includes for `labels_router`, `priorities_router`, `projects_router`, `tasks_router`, `project_summaries_router`
- `backend/main.py` — evaluate `agent_run_router` (line 31-32) — if only used by project_mgmt agents, remove it too

**Files to evaluate:**
- `backend/src/common/` — check if `common/controllers/agent_run_controller.py` has callers outside project_mgmt. If not, delete `common/` entirely.
- `backend/src/project_mgmt/enums.py` — check if imported anywhere else

**Migration to create:**
- New Alembic migration that drops project_mgmt tables: `project`, `task`, `label`, `priority`, `project_summary`, and any join tables. Also drop `agent_run` table if only project_mgmt used it.

**Testing:**
- Backend starts without errors after removal
- `ruff check` clean (no unused imports)
- `pytest` passes (project_mgmt tests deleted, no other tests depend on them)

**Complexity:** M

---

### 6C. Procrastinate Queue Removal

**Goal:** Remove the Procrastinate task queue and inline enrichment synchronously. This is per `docs/decision/queue-strategy.md` (Phase 0F).

**Acceptance criteria:**
- `shared/queue/` directory deleted entirely
- `procrastinate`, `psycopg`, `psycopg_pool` removed from `requirements.txt`
- Worker lifecycle removed from `main.py` lifespan (lines 93-105 startup, 119-126 shutdown)
- Enrichment runs synchronously with simple retry (3 attempts, exponential backoff)
- `procrastinate_*` table exclusion removed from `migrations/env.py`
- Alembic migration to drop `procrastinate_*` tables
- No import errors on backend startup

**Files to delete:**
- `backend/src/shared/queue/__init__.py`
- `backend/src/shared/queue/config.py`
- `backend/src/shared/queue/tasks.py` — 3 POC tasks (dummy_task, failing_task, concurrency_task)
- `backend/src/shared/queue/poc_test.py`

**Files to modify:**
- `backend/main.py`:
  - Remove Procrastinate startup block (lines ~93-105)
  - Remove Procrastinate shutdown block (lines ~119-126)
  - Remove `asyncio` import if no longer needed elsewhere
- `backend/src/linkedout/enrichment_pipeline/controller.py`:
  - Replace `_defer_enrichment_task()` (line 173 imports `sync_app`) with direct inline call to enrichment logic
  - Add simple retry: 3 attempts, exponential backoff (use `tenacity` if already in deps, else manual)
- `backend/src/linkedout/enrichment_pipeline/tasks.py`:
  - Extract core enrichment logic (Apify call → PostEnrichmentService) into a plain function
  - Move to `enrichment_pipeline/service.py` or inline in controller
  - Delete `tasks.py` after extraction
- `backend/migrations/env.py`:
  - Remove `procrastinate_*` table exclusion from autogenerate filtering
- `backend/requirements.txt`:
  - Remove `procrastinate`
  - Keep `psycopg2-binary` (used by SQLAlchemy)
  - Remove `psycopg` and `psycopg_pool` if they were only for Procrastinate (verify first)

**Migration to create:**
- Alembic migration to drop: `procrastinate_jobs`, `procrastinate_events`, `procrastinate_periodic_defers`, `procrastinate_workers` (CASCADE)

**Integration points:**
- `docs/decision/queue-strategy.md` — implementation plan section 1-6

**Testing:**
- Unit test: enrichment function processes a profile synchronously, returns result
- Unit test: retry logic works (mock Apify failure, verify 3 attempts)
- Existing `backend/tests/unit/enrichment_pipeline/test_enrich_task.py` — simplify to test plain function, remove queue mocking
- Backend starts cleanly

**Complexity:** M

---

### 6D. Langfuse Default Off

**Goal:** Make Langfuse observability disabled by default. Guard all Langfuse imports so the app runs without `langfuse` installed (or with it installed but disabled).

**Acceptance criteria:**
- `LANGFUSE_ENABLED=false` by default (per `docs/decision/env-config-design.md`)
- All `from langfuse import observe` calls guarded: use a no-op decorator when disabled
- All `from langfuse import get_client` calls guarded: return a no-op context manager when disabled
- Backend starts and runs without any Langfuse config/keys set
- When `LANGFUSE_ENABLED=true` and keys are set, Langfuse works as before
- `langfuse` stays in `requirements.txt` (optional dep) but never crashes if keys are missing

**Files to modify (Langfuse `@observe` decorator — 9 files):**
- `backend/src/linkedout/intelligence/tools/career_tool.py`
- `backend/src/linkedout/intelligence/tools/vector_tool.py`
- `backend/src/linkedout/intelligence/tools/web_tool.py`
- `backend/src/linkedout/intelligence/tools/network_tool.py`
- `backend/src/linkedout/intelligence/tools/company_tool.py`
- `backend/src/linkedout/intelligence/tools/sql_tool.py`
- `backend/src/linkedout/intelligence/tools/result_set_tool.py`
- `backend/src/linkedout/intelligence/tools/intro_tool.py`
- `backend/src/linkedout/intelligence/tools/profile_tool.py`

**Files to modify (Langfuse `get_client` — 2 files):**
- `backend/src/linkedout/intelligence/controllers/search_controller.py`
- `backend/src/linkedout/intelligence/controllers/best_hop_controller.py`

**Files to modify (Langfuse agents — 1 file):**
- `backend/src/linkedout/intelligence/agents/search_agent.py`

**Files to modify (Langfuse explainer — 1 file):**
- `backend/src/linkedout/intelligence/explainer/why_this_person.py`

**Files to KEEP (prompt manager — resolved decision Q2):**
- `backend/src/utilities/prompt_manager/` — Keep this module. SJ decision: do not remove.

**Approach — create a guard module:**
Create `backend/src/shared/utilities/langfuse_guard.py`:
```python
"""Langfuse guard — provides no-op stubs when Langfuse is disabled."""
import functools
from shared.config.config import backend_config

def observe(*args, **kwargs):
    """No-op @observe decorator when Langfuse is disabled."""
    if getattr(backend_config, 'LANGFUSE_ENABLED', False):
        from langfuse import observe as real_observe
        return real_observe(*args, **kwargs)
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*a, **kw):
            return func(*a, **kw)
        return wrapper
    if args and callable(args[0]):
        return decorator(args[0])
    return decorator
```

Then replace all `from langfuse import observe` with `from shared.utilities.langfuse_guard import observe`.

Similarly, create a `get_client()` stub that returns a no-op context manager when disabled.

**Testing:**
- Unit test: import guard module, verify no-op when `LANGFUSE_ENABLED=false`
- Unit test: verify real Langfuse is called when `LANGFUSE_ENABLED=true` (mock the import)
- Backend starts with zero Langfuse config → no errors
- Backend starts with Langfuse enabled + valid keys → tracing works

**Complexity:** M

---

### 6E. CLI Surface Refactor

**Goal:** Replace the `rcv2` CLI with the flat `linkedout` namespace per `docs/decision/cli-surface.md` (Phase 0A decision). 13 user-facing commands + 1 internal-only command.

**Acceptance criteria:**
- New CLI entry point: `linkedout = "linkedout.cli:cli"` in `pyproject.toml`
- 13 user-facing commands work: `import-connections`, `import-contacts`, `compute-affinity`, `embed`, `reset-db`, `start-backend`, `download-seed`, `import-seed`, `diagnostics`, `status`, `version`, `config`, `report-issue`
- 1 internal command: `migrate`
- Category-grouped help text matching the format in `docs/decision/cli-surface.md`
- Implementation files moved from `dev_tools/` to `linkedout/commands/` (resolved decision Q6 — clean break, not thin wrappers)
- Legacy `rcv2` entry point and `dev_tools/cli.py` deleted
- Every write command supports `--dry-run`
- `status` and `diagnostics` support `--json`

**Files to create:**
- `backend/src/linkedout/cli.py` — new flat CLI using Click
  - Move implementation files from `dev_tools/` into `linkedout/commands/` (e.g., `linkedout/commands/import_connections.py`, `linkedout/commands/compute_affinity.py`)
  - Stub implementations for new commands (`download-seed`, `import-seed`, `diagnostics`, `status`, `version`, `config`, `report-issue`, `migrate`) — these will be fully implemented in their respective phases (7, 3, etc.) but need to exist as `click.command` stubs now so the CLI is complete
- `backend/src/linkedout/commands/` — new directory for command implementations (moved from dev_tools/)
- `backend/src/linkedout/cli_helpers.py` — shared utilities (OperationResult pattern, help text formatter)

**Files to modify:**
- `backend/pyproject.toml`:
  - Add `linkedout = "linkedout.cli:cli"` entry point
  - Remove legacy `rcv2` entry point (clean break — resolved decision Q6)
  - Remove individual legacy entry points (`reset-db`, `seed-db`, `verify-seed`, etc.) — they're replaced by `linkedout` commands
  - Remove `pm` entry point (retired — Langfuse-specific)
  - Remove `dev`, `be`, `fe`, `fe-setup`, `run-all-agents` entry points (retired)

**Command → implementation mapping:**

| Command | Implementation Source | Notes |
|---------|---------------------|-------|
| `import-connections` | `linkedout/commands/import_connections.py` (moved from `dev_tools/load_linkedin_csv.py`) | Add `--format` and `--dry-run` |
| `import-contacts` | `linkedout/commands/import_contacts.py` (moved from `dev_tools/load_gmail_contacts.py`) | Add `--format` and `--dry-run` |
| `compute-affinity` | `linkedout/commands/compute_affinity.py` (moved from `dev_tools/compute_affinity.py`) | Add `--dry-run`, remove `--user-id` |
| `embed` | `linkedout/commands/embed.py` (moved from `dev_tools/generate_embeddings.py`) | Add `--provider`, `--resume`, `--force` |
| `reset-db` | `linkedout/commands/reset_db.py` (moved from `dev_tools/db/reset_db.py`) | Simplify modes to default truncate + `--full` |
| `start-backend` | New (uvicorn wrapper) | Simple `uvicorn main:app` invocation with `--port`, `--host`, `--background` |
| `download-seed` | Stub | Full impl in Phase 7 |
| `import-seed` | Stub | Full impl in Phase 7 |
| `diagnostics` | Stub | Full impl in Phase 3 |
| `status` | Stub (basic DB check) | Full impl in Phase 3 |
| `version` | New (read VERSION file) | Simple — print version + ASCII logo |
| `config` | Stub (show + path) | Full impl in Phase 2 |
| `report-issue` | Stub | Full impl in Phase 3 |
| `migrate` | New (alembic wrapper) | Internal-only, `--dry-run` support |

**Integration points:**
- `docs/decision/cli-surface.md` — authoritative contract for command names, flags, help text, operation result pattern
- `docs/decision/logging-observability-strategy.md` — operation result pattern (Progress → Summary → Gaps → Next steps → Report path)

**Testing:**
- `linkedout --help` renders category-grouped help text
- Each carried-forward command runs without error (at minimum `--help` works)
- `linkedout version` prints version info
- `linkedout config path` prints config file location
- Stub commands print "Not yet implemented — coming in Phase N" message

**Complexity:** L

---

### 6F. Strip Hardcoded Paths

**Goal:** Remove all hardcoded `.` and similar dev-environment paths from the codebase.

**Acceptance criteria:**
- No references to `.` or `<linkedout-fe>` anywhere in source code
- All paths use config values or relative paths
- Dev-tool references to source repos are removed or made configurable

**Files to modify:**
- `backend/src/dev_tools/benchmark/runner.py:214` — remove hardcoded DB config path reference
- `backend/src/dev_tools/cli.py:374` — remove hardcoded `<linkedout-fe>` path for `fe_dir`

**Approach:**
- For benchmark runner: replace with a reference to `DATABASE_URL` from config/env
- For `fe_dir`: the `fe` command is retired (Phase 6E removes the entry point), so this code path may be dead. If so, verify and delete. If the `cli.py` `fe_command` is still referenced, refactor to use a config value or remove entirely.

**Search and verify:**
```bash
grep -rn "~/workspace" backend/src/ --include="*.py"
grep -rn "<home>" backend/src/ --include="*.py"
grep -rn "linkedout-fe" backend/src/ --include="*.py"
```

**Testing:**
- `grep` returns zero matches for hardcoded paths
- Backend starts and all commands work

**Complexity:** S

---

### 6G. Dependency Cleanup

**Goal:** Remove unused dependencies from `requirements.txt`. Create a separate `requirements-dev.txt` for dev-only tools.

**Acceptance criteria:**
- `requirements.txt` contains only production dependencies
- `requirements-dev.txt` contains dev/test dependencies (pytest, ruff, pyright, etc.)
- No unused packages in either file
- `uv pip install -r requirements.txt` succeeds
- `uv pip install -r requirements-dev.txt` succeeds (includes `-r requirements.txt`)

**Dependencies to remove from `requirements.txt` (verified in 6C):**
- `procrastinate` — removed in 6C
- `psycopg` — if only used by Procrastinate (verify; `psycopg2-binary` stays)
- `psycopg_pool` — if only used by Procrastinate (verify)

**Dependencies to evaluate:**
- `firebase-admin` — still needed if auth provider is kept (disabled by default, but code stays per 6A)
- `langfuse` — keep (guarded by LANGFUSE_ENABLED, but import still happens conditionally)
- Any unused deps discovered during the cleanup

**Dependencies to move to `requirements-dev.txt`:**
- `pytest`, `pytest-asyncio`, `pytest-cov`
- `ruff`
- `pyright`
- `httpx` (if only used in tests)
- Any test fixtures/factories

**Files to create:**
- `backend/requirements-dev.txt` — dev dependencies with `-r requirements.txt` at the top

**Files to modify:**
- `backend/requirements.txt` — remove retired deps, move dev deps out

**Testing:**
- Fresh venv: `uv pip install -r requirements.txt` succeeds
- Fresh venv: `uv pip install -r requirements-dev.txt` succeeds
- `pytest` runs with dev deps installed
- Backend starts with only production deps

**Complexity:** M

---

### 6H. Test Suite Green

**Goal:** All tests pass with mocked external services. No real API keys needed for CI.

**Acceptance criteria:**
- `pytest` passes with zero failures
- No tests require real API keys (OpenAI, Apify, Langfuse)
- `project_mgmt` tests are deleted (6B)
- Enrichment tests are updated for sync flow (6C)
- Langfuse-dependent tests are guarded or mocked (6D)
- `ruff check backend/src/` clean
- `pyright backend/src/` clean (or known baseline of acceptable issues)

**Files to modify:**
- `backend/tests/project_mgmt/` — deleted in 6B
- `backend/tests/unit/enrichment_pipeline/test_enrich_task.py` — simplified in 6C
- Any tests that import from `shared.queue` — remove/update
- Any tests that import from `project_mgmt` — remove/update
- Any tests that unconditionally import `langfuse` — guard

**Approach:**
1. Run `pytest --collect-only` to find all tests
2. Run `pytest` and triage failures:
   - Import errors from deleted modules → fix imports
   - Missing fixtures from deleted modules → remove or replace
   - Langfuse import errors → guard with `LANGFUSE_ENABLED=false`
   - Queue-related failures → update to sync flow
3. Run `ruff check` and fix any lint issues from the cleanup
4. Run `pyright` and address new type errors introduced by cleanup

**Testing:**
- `pytest` exit code 0
- `ruff check backend/src/` exit code 0
- CI would pass (no API keys needed)

**Complexity:** M

---

## Execution Order

Tasks can be partially parallelized:

```
6A (Auth verification — read-only, no code changes)
  ↓
6B (project_mgmt removal) ──┐
6C (Procrastinate removal) ──┤── can run in parallel (independent removals)
6D (Langfuse guard) ─────────┘
  ↓
6E (CLI refactor) ←── depends on 6B-6D being done (needs clean import tree)
  ↓
6F (Strip hardcoded paths) ←── can run in parallel with 6E
  ↓
6G (Dependency cleanup) ←── depends on 6B-6D knowing which deps are removed
  ↓
6H (Test suite green) ←── runs last, validates everything
```

Recommended serial order for a single implementer: 6A → 6B → 6C → 6D → 6F → 6E → 6G → 6H

---

## Exit Criteria Verification Checklist

- [ ] `ruff check backend/src/` — zero errors
- [ ] `pyright backend/src/` — zero new errors (may have baseline)
- [ ] `pytest backend/tests/` — zero failures, no API keys required
- [ ] No hardcoded secrets or private paths: `grep -rn "sk-\|~/workspace\|<home>" backend/src/` returns zero
- [ ] No `project_mgmt` references: `grep -rn "project_mgmt" backend/` returns zero (except migrations if kept for history)
- [ ] No Procrastinate references: `grep -rn "procrastinate" backend/src/` returns zero
- [ ] Langfuse disabled by default: backend starts with zero Langfuse config
- [ ] Auth works unchanged: backend serves API requests with system tenant
- [ ] CLI surface: `linkedout --help` shows 13 commands in category-grouped format
- [ ] CLI surface: `linkedout version` works
- [ ] CLI surface: `linkedout import-connections --help` works
- [ ] No unused entry points in `pyproject.toml` (no `pm`, `dev`, `be`, `fe`, `fe-setup`, `run-all-agents`, etc.)

---

## Phase 0 Decision Cross-References

| Decision Doc | How This Phase Applies It |
|-------------|--------------------------|
| `docs/decision/cli-surface.md` (0A) | 6E: Full CLI refactor to flat `linkedout` namespace with 13+1 commands |
| Phase 0B (Auth — no doc) | 6A: Verify auth works as-is, document it, make zero changes |
| Phase 0D (Multi-tenancy — no doc) | 6A: Verify multi-tenancy works as-is, make zero changes |
| Phase 0E (project_mgmt — no doc) | 6B: Strip entire `project_mgmt` domain |
| `docs/decision/queue-strategy.md` (0F) | 6C: Remove Procrastinate, inline enrichment synchronously |
| `docs/decision/env-config-design.md` (0G) | 6D: `LANGFUSE_ENABLED=false` default; 6E: CLI reads from unified config |
| `docs/decision/logging-observability-strategy.md` (0H) | 6E: CLI operation result pattern (Progress → Summary → Gaps → Next steps → Report path) |
| `docs/decision/2026-04-07-embedding-model-selection.md` | 6E: `linkedout embed` command references nomic as default local provider |
| `docs/decision/2026-04-07-data-directory-convention.md` | 6E: All data paths reference `~/linkedout-data/` |
| `docs/decision/2026-04-07-skill-distribution-pattern.md` | Not directly applied in Phase 6 (skills are Phase 8) |

---

## Resolved Decisions (2026-04-07, SJ)

1. **`common/` module scope:** **Investigate during implementation, delete only if confirmed unused.** Grep `from common` / `import common` before deciding. Don't delete blind.

2. **`utilities/prompt_manager/`:** **Keep it.** SJ decision — do not remove.

3. **Alembic migrations:** **One-way only (no down-migrations). EXPANDED: Replace entire migration history with a single fresh baseline migration for OSS.** The baseline includes:
   - All current tables (minus `project_mgmt` and `procrastinate_*`)
   - All indexes (HNSW pgvector, GIN pg_trgm, standard B-tree)
   - `CREATE EXTENSION IF NOT EXISTS` for `vector` and `pg_trgm`
   - `DROP TABLE IF EXISTS` for externally-created tables (Procrastinate tables that may have been created outside Alembic)
   - Note: some tables appeared in old migrations for `autogenerate` compatibility — the baseline replaces all of this
   - Old migration files are deleted — clean history for OSS launch

4. **`shared/test_endpoints/sse_router.py`:** **Remove.** Spike artifact. If SSE is needed later, build properly against actual requirements.

5. **Firebase auth provider code:** **Keep as-is, add comment.** `# Firebase auth preserved for potential multi-user support — see Phase 0B decision.`

6. **`dev_tools/` directory:** **Move implementation files to `linkedout/commands/`, delete `dev_tools/cli.py` and `rcv2` entry point.** Clean break — Phase 6 is the cleanup phase. No thin wrappers, no coexistence.

7. **`organization/` module:** **DO NOT REMOVE. Actively used.** Load-bearing tenant/BU/enrichment_config infrastructure. This is NOT template scaffolding — it's core to the auth/multi-tenancy model that Phase 0B/0D decided to keep.

### Cross-Phase Decisions Affecting This Phase

- **Phase 5 (embedding schema):** The dual-column pgvector schema (`embedding_openai vector(1536)`, `embedding_nomic vector(768)`) and HNSW indexes are included in the fresh baseline migration.
- **`start-backend` idempotency:** When implementing the CLI in 6E, `start-backend` must detect existing process on port, kill it, then start fresh. No "address already in use" errors.
- **Tooling:** Use `uv` and `requirements.txt` everywhere. Clean up `requirements.txt` / create `requirements-dev.txt` using `uv`.
