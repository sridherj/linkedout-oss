# Full Test Suite Assessment & RCA

## Overall Results (2,459 tests, all markers included)

| Outcome | Count |
|---------|-------|
| **Passed** | 2,399 |
| **Failed** | 20 |
| **Errors** | 32 |
| **Skipped** | 7 |
| **xfailed** | 1 |

---

## 7 Skipped Tests (all legitimate)

| Tests | Reason |
|-------|--------|
| 2x `test_search_integration.py` (vector search) | `pgvector not available in test schema` |
| 2x `test_langfuse_prompt_store.py` | `langfuse_public_key not configured` |
| 3x `test_affinity_integration.py` (embedding similarity) | `pgvector not available in test schema` |

No action needed.

---

## RCA #1: DbSessionManager Singleton Contamination

### Root Cause

`DbSessionManager` is a mutable process-global singleton (class-level `_instance`, `_engine`, `_SessionLocal`). 14 call sites across 4 files call `set_engine()`, replacing the engine for the entire process. Per-worker PostgreSQL schemas protect at the DB layer, but within a single xdist worker, different test categories (unit/integration/eval/CLI) mutate the same singleton, causing non-deterministic failures:

- **ObjectDeletedError**: `seeded_data` ORM objects expire after rollback, lazy-load hits wrong engine
- **Config env bleed**: `LinkedOutSettings()` picks up env vars from other fixtures' `load_dotenv()`
- **ImportError**: embedding provider resolves to `local` (wrong engine context)

### Fix: Refactor DbSessionManager from mutable singleton to injected dependency

**Principle:** Engine is created at the boundary (app startup, CLI entry point, test fixture), flows inward as a constructor arg, never mutated.

#### Step 1: Make DbSessionManager a plain class

**File:** `src/shared/infra/db/db_session_manager.py`

Changes:
- Remove `_instance` class variable and `__new__` singleton pattern
- Remove class-level `_engine: Optional[Engine] = None` and `_SessionLocal = None` declarations
- Add `__init__(self, engine: Engine)` that sets **instance attributes**: `self._engine: Engine = engine` and `self._SessionLocal = sessionmaker(bind=engine, ...)`. Type `_engine` as `Engine` (not `Optional`) — construction guarantees it is set
- Remove `_initialize_engine()` — engine comes from caller
- Delete `set_engine()` entirely
- Remove `_SessionLocal` None guards in `get_session()` (line 198) and `get_raw_session()` (line 142) — construction guarantees these are set, guards are dead code after refactor
- `get_session()` and `get_raw_session()` otherwise unchanged (read from `self._engine`)
- Entity discovery imports stay (they register metadata, not engine-dependent)
- Remove module-level `db_session_manager = DbSessionManager()` global

**Also migrate `DbSessionManager()` zero-arg constructor call sites (4 files, 7 sites):**

A grep for the `db_session_manager` variable won't find these — grep for `DbSessionManager()` separately.

| File | Sites | Migration |
|---|---|---|
| `src/shared/infra/db/db_session_manager.py:243` | 1 | Deleted (module-level global) |
| `src/linkedout/dashboard/controller.py:27` | 1 | `request.app.state.db_manager` — capture before `asyncio.to_thread` |
| `src/shared/utilities/health_checks.py:72,262` | 2 | Take `db_manager: DbSessionManager` as parameter from caller |
| `src/dev_tools/diagnostics.py:80,403,442` | 3 | Use `cli_db_manager()` at entry, pass `db_manager` to health_checks functions |

#### Step 2: FastAPI app — engine owned by app, accessed via `request.app.state`

**Decision (OQ2 resolved):** Use `request.app.state.db_manager` pattern — no `Depends()` helper needed. Each endpoint/closure reads `request.app.state.db_manager` directly. This preserves `yield from` delegation in CRUDRouterFactory and avoids FastAPI DI complexity.

**`src/main.py` (lifespan):**
- In lifespan: create engine from `get_config().database_url` with `echo=settings.db_echo_log`, create `DbSessionManager(engine)`, store on `app.state.db_manager`
- **Important:** Check `hasattr(app.state, 'db_manager')` before creating — integration tests pre-set `app.state.db_manager` before TestClient triggers the lifespan. Skip creation if already set.
- Dispose engine on shutdown (only if lifespan created it — track via `app.state._owns_engine = True`)

**`src/shared/auth/dependencies/auth_dependencies.py`:**
- `_get_read_session()` reads `request.app.state.db_manager` instead of global

**`src/common/controllers/base_controller_utils.py`:**
- `create_service_dependency()` gains `request: Request` as first parameter, reads `request.app.state.db_manager`

**`src/common/controllers/crud_router_factory.py`** (key change):
```python
def _get_service(request: Request, session_type=DbSessionType.READ):
    db_manager = request.app.state.db_manager
    with db_manager.get_session(session_type) as session:
        yield config.service_class(session)

def _get_write_service(request: Request):
    yield from _get_service(request, session_type=DbSessionType.WRITE)
```

Note: Both `_get_service` and `_get_write_service` gain `request: Request`. FastAPI auto-injects `request` at the top-level dependency; it flows through `yield from` as a plain Python argument.

**Other controllers that bypass `create_service_dependency()` (7 files):**
- `src/common/controllers/agent_run_controller.py`
- `src/linkedout/intelligence/controllers/search_controller.py`
- `src/linkedout/intelligence/controllers/best_hop_controller.py`
- `src/linkedout/intelligence/controllers/_sse_helpers.py`
- `src/linkedout/crawled_profile/controllers/crawled_profile_controller.py`
- `src/linkedout/enrichment_pipeline/controller.py`
- `src/linkedout/dashboard/controller.py`

**~20 controllers that only import `DbSessionType`** — zero changes.
**All services and repositories** — zero changes (already take `session` as constructor arg).

**`.claude/agents/` updates:**
- `custom-controller-agent.md` — update service dependency template to pass `request: Request` through to `create_service_dependency`:
  ```python
  def _get_<entity>_service(request: Request) -> Generator[<Entity>Service, None, None]:
      yield from create_service_dependency(request, <Entity>Service, DbSessionType.READ)

  def _get_write_<entity>_service(request: Request) -> Generator[<Entity>Service, None, None]:
      yield from create_service_dependency(request, <Entity>Service, DbSessionType.WRITE)
  ```
  Also add `from fastapi import Request` to import template.
- `entity-creation-agent.md` — no change (entity discovery imports unaffected)
- `crud-compliance-checker-agent.md` — no change (entity discovery checklist still valid)

#### Step 3: CLI commands — every entry point calls `cli_db_manager()` directly

**Decision (OQ1 resolved):** Universal pattern — every CLI entry point creates its own `db_manager` via `cli_db_manager()`. No Click `ctx.obj` injection, no CLI group changes. One pattern everywhere, whether the command is registered in the CLI group or a standalone dev_tools script.

**New file:** `src/shared/infra/db/cli_db.py`
```python
def cli_db_manager() -> DbSessionManager:
    settings = get_config()
    engine = create_engine(settings.database_url, echo=settings.db_echo_log)
    return DbSessionManager(engine)
```

Each CLI command/script creates its own manager at entry:
```python
@click.command()
def import_seed(...):
    db_manager = cli_db_manager()
    with db_manager.get_session(DbSessionType.WRITE, ...) as session:
        ...
```

**Registered CLI commands (5 files):**
- `src/linkedout/commands/import_seed.py`
- `src/linkedout/commands/import_connections.py`
- `src/linkedout/commands/import_contacts.py`
- `src/linkedout/commands/embed.py`
- `src/linkedout/commands/compute_affinity.py`

**Standalone dev_tools scripts (~19 files):**
- `src/dev_tools/db/seed.py`
- `src/dev_tools/db/load_fixtures.py`
- `src/dev_tools/db/validate_orm.py`
- `src/dev_tools/db/verify_seed.py`
- `src/dev_tools/seed_companies.py`
- `src/dev_tools/reconcile_stubs.py`
- `src/dev_tools/classify_roles.py`
- `src/dev_tools/import_pdl_companies.py`
- `src/dev_tools/fix_none_names.py`
- `src/dev_tools/backfill_experience_dates.py`
- `src/dev_tools/backfill_seniority.py`
- `src/dev_tools/load_apify_profiles.py`
- `src/dev_tools/download_profile_pics.py`
- `src/dev_tools/enrich_companies.py`
- `src/dev_tools/seed_export.py`
- `src/shared/utilities/health_checks.py`
- `src/dev_tools/diagnostics.py`
- `src/linkedout/version.py`

**`src/common/services/agent_executor_service.py`** — **Decision (OQ4 resolved):** Uses `cli_db_manager()` internally to create its own manager. Agent executor runs background tasks via FastAPI `BackgroundTasks` — creating its own manager per call is acceptable for a personal tool with infrequent agent runs.

#### Step 4: Tests — each fixture creates its own manager, no set_engine()

**`backend/conftest.py` (root):**
- Remove all 8 `set_engine()` calls (lines 243, 254, 266, 354, 362, 399, 407, 479)
- Note: `SeedDb` already creates its own `sessionmaker` from `config.custom_engine` — it does NOT use `db_session_manager`. The save-restore `set_engine` pattern was for code under test, not for seeding.
- `_shared_db_resources` creates `DbSessionManager(sqlite_engine)` instead of mutating global
- `default_db_session_manager_setup` deleted (was autouse, unconditional `set_engine`)
- Function/class-scoped fixtures (`function_scoped_isolated_db_session`, `class_scoped_isolated_db_session`) create their own `DbSessionManager(isolated_engine)` — no save-restore pattern needed
- `db_session` legacy fixture creates manager locally

**`tests/integration/conftest.py`:**
- `integration_db_session` creates `DbSessionManager(integration_db_engine)` — no global mutation
- `test_client` sets `app.state.db_manager = DbSessionManager(integration_db_engine)` **before** entering `TestClient(app)` context — the lifespan's `hasattr` check skips creating a second manager
- Remove `db_session_manager.set_engine()` calls (lines 189, 270)

**`tests/integration/linkedout/intelligence/test_best_hop_integration.py`:**
- Remove 2 ad-hoc `set_engine()` calls (lines 374, 434)
- Use `app.state.db_manager = DbSessionManager(engine)` instead

**Unit test mock pattern migration (6 files, 3 patterns):**

*Pattern 1 — Custom controller tests (4 files):*
`test_warm_intros.py`, `test_search_controller_streaming.py`, `test_best_hop_controller.py`, `test_people_like_x.py`

These patch `db_session_manager` at the controller module level. After refactor, controllers use `request.app.state.db_manager`. Tests that call endpoint functions directly must pass a mock request:

```python
@pytest.fixture()
def _mock_db():
    mock_request = MagicMock()
    mock_session = MagicMock()
    mock_db = MagicMock()
    mock_db.get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)
    mock_request.app.state.db_manager = mock_db
    yield mock_request, mock_session
```

Calls change: `await find_intro_paths(mock_request, tenant_id, ...)` instead of `await find_intro_paths(tenant_id, ...)`.

*Pattern 2 — CLI command test (1 file):*
`tests/unit/cli/test_embed_command.py`

Patch target changes from instance to factory function:
```python
with patch('linkedout.commands.embed.cli_db_manager') as mock_cli_db:
    mock_db = MagicMock()
    mock_db.get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)
    mock_cli_db.return_value = mock_db
```

*Pattern 3 — Utility test (1 file):*
`tests/unit/shared/utilities/test_health_checks.py`

After refactor, `health_checks.py` takes `db_manager` as parameter — no patching needed:
```python
def test_returns_pass_on_successful_connection(self):
    mock_db = MagicMock()
    result = check_db_connection(db_manager=mock_db)
```

**Other test files that reference `db_session_manager` (~2 files):**
- `tests/common/test_base_controller_utils.py` — update to pass mock request to `create_service_dependency`
- `tests/integration/linkedout/intelligence/test_rls_isolation.py` — use local `DbSessionManager(engine)` instead of global

#### Blast Radius Summary

| Category | Files | Effort |
|---|---|---|
| DbSessionManager class | 1 | Small |
| New CLI helper | 1 | Small |
| DbSessionManager() constructor sites | 3 (dashboard, health_checks, diagnostics) | Small |
| FastAPI DI plumbing | 3 core + 7 controllers | Medium |
| `.claude/agents/` templates | 1 (custom-controller-agent.md) | Small |
| CLI commands + dev_tools | ~24 | Mechanical |
| Test fixtures (conftest + integration) | ~5 | Medium |
| Unit test mock migration | 6 | Medium |
| Other test files | 2 | Small |
| Services / Repos / import-only controllers | 0 | Zero |
| **Total** | **~53 files** | |

---

## RCA #2: Seed Pipeline SQL Generation Bug (5 tests)

### Tests
All 5 in `tests/integration/cli/test_seed_pipeline.py`

### Fails when run alone: YES

### Error
```sql
INSERT INTO public.company ()
SELECT  FROM _seed_staging.company
-- SyntaxError: syntax error at or near ")"
```

### Root Cause
`_build_staging_upsert_sql()` in `src/linkedout/commands/import_seed.py:100-125` generates SQL from `_get_intersected_columns()`. The test fixture `tests/fixtures/test-seed-core.dump` was built against a previous schema version. When restored into `_seed_staging`, the column intersection with the current `public.company` table is empty, producing `col_list = ""` → invalid SQL.

The function has no guard for empty columns:
```python
def _build_staging_upsert_sql(table: str, columns: list[str]) -> str:
    col_list = ", ".join(columns)  # empty string if columns is []
    non_pk = [c for c in columns if c != "id"]  # also empty
```

### Fix

**Decision (OQ3 resolved):** Option C — generate `.dump` fixture dynamically in test setup.

1. **Code guard:** Add empty-column check at top of `_build_staging_upsert_sql()` — return `None` or raise with descriptive message when `columns` is empty. Caller skips table with warning.
2. **Generate fixture in test setup:** `tests/fixtures/generate_test_seed.py` already exists with all the generation logic (creates staging tables from entity metadata, inserts synthetic data, calls `pg_dump`). Refactor its core functions to be importable and call them from the test fixture instead of loading a static file. This exercises the full pg_restore → upsert pipeline while staying schema-drift-proof. Delete the stale checked-in `tests/fixtures/test-seed-core.dump`.

### Files
- `src/linkedout/commands/import_seed.py` — add guard
- `tests/fixtures/generate_test_seed.py` — refactor for importability
- `tests/integration/cli/test_seed_pipeline.py` — generate fixture dynamically in module-scoped fixture
- `tests/fixtures/test-seed-core.dump` — delete (no longer needed)

---

## RCA #3: Skill Install Path Mismatch (1 test)

### Test
`tests/linkedout/setup/test_skill_install.py::TestDetectPlatforms::test_platform_info_has_correct_paths`

### Fails when run alone: YES

### Error
```
assert PosixPath('.../.claude/skills') == PosixPath('.../.claude/skills/linkedout')
```

### Root Cause
Code at `src/linkedout/setup/skill_install.py:30` defines `skill_install_dir: ".claude/skills"`.
Test at line 56 expects `.claude/skills/linkedout`.

The code was intentionally changed — `skill_install_dir` is the directory *where* skills get installed. `install_skills_for_platform()` (line 177) uses it as the target and copies skill subdirectories *into* it. The test expectation is stale.

### Fix
Update test assertion: `assert claude.skill_install_dir == tmp_path / ".claude" / "skills"`

### File
- `tests/linkedout/setup/test_skill_install.py`

---

## RCA #4: Demo DB Permission Denied (5 tests)

### Tests
All 5 in `tests/integration/cli/test_demo_db_integration.py`

### Fails when run alone: YES

### Error
`RuntimeError: Failed to create demo database: ERROR: permission denied to create database`

### Root Cause
`create_demo_database()` in `src/linkedout/demo/db_utils.py` runs `CREATE DATABASE` via psql. The test DB user (`linkedout:test`) lacks `CREATEDB` privilege.

### Fix
Add a shared fixture that checks `SELECT has_database_privilege(current_user, 'CREATE')` and calls `pytest.skip()` when privilege is missing. Apply to all tests in this file.

### File
- `tests/integration/cli/test_demo_db_integration.py`

---

## RCA #5: Eval Tests — Missing Connection Table (32 errors)

### Tests
All 30 in `tests/eval/test_search_quality.py` + 2 in `tests/eval/test_multiturn_poc.py`

### Error
`relation "connection" does not exist`

### Root Cause
Eval tests query `SELECT app_user_id FROM connection ...` against the production database. The `connection` table only exists when real LinkedIn data has been imported. These are quality benchmarks, not regression tests — they need real data.

### Fix
Add skip guard in eval conftest's `app_user_id` fixture: check `SELECT to_regclass('public.connection')` before querying. Skip with message "No connection table — run LinkedIn CSV loader first."

### File
- `tests/eval/conftest.py` — add table-existence check in `app_user_id` fixture

---

## RCA #6: Demo Smoke Tests — Missing Database (6 tests)

### Tests
All 6 in `tests/smoke/test_demo_search_smoke.py`

### Error
`database "linkedout_demo_smoke" does not exist`

### Root Cause
Smoke tests connect directly to `linkedout_demo_smoke` database via psycopg2. This DB is only created by the demo setup flow and doesn't exist in the test environment.

### Fix
Add a connection guard at the top of the test module that attempts to connect and calls `pytest.skip()` if the DB doesn't exist.

### File
- `tests/smoke/test_demo_search_smoke.py`

---

## Spec Updates Required

Three specs describe behavior that this refactor changes. They must be updated to match.

### 1. `docs/specs/database_session_management.collab.md` → v2

Current spec describes singleton pattern and `set_engine()`. Must update:

- **Singleton pattern** section → replace with constructor injection pattern: `DbSessionManager(engine: Engine)` with instance-only attributes
- **"Custom engine for tests"** behavior (`set_engine`) → delete, replace with "Tests create their own `DbSessionManager(engine)` instance"
- **"Auto initialization"** behavior → replace with "Engine is provided at construction. FastAPI apps create the manager in lifespan; CLI commands use `cli_db_manager()`"
- **Decision table** row "Singleton | Module-level db_session_manager | Over dependency injection | Because simple" → reverse this decision, document why DI is now chosen over singleton (non-deterministic xdist failures from mutable global state)
- **Entity Discovery** section → unchanged (imports stay in module)
- Add new **FastAPI Integration** section documenting `app.state.db_manager` + `request.app.state.db_manager` pattern, including lifespan `hasattr` check for test pre-injection
- Add new **CLI Integration** section documenting `cli_db_manager()` factory with `echo=settings.db_echo_log`

### 2. `docs/specs/unit_tests.collab.md` → v2

Current spec references `set_engine()` and the autouse fixture. Must update:

- **"Shared DB for read-only tests"** → update to describe `DbSessionManager(sqlite_engine)` created per fixture, no global mutation
- **"Isolated DB for mutation tests"** → same pattern, each fixture creates its own manager
- Remove references to `db_session_manager.set_engine()` throughout
- **"Test Configuration"** section → update to reflect that xdist parallel is safe after refactor (no more singleton contamination)
- Add **Mock Pattern Migration** section documenting the 3 post-refactor patterns: mock request for controllers, patch `cli_db_manager` for CLI tests, parameter injection for utilities

### 3. `docs/specs/integration_tests.collab.md` → v2

Current spec says "TestClient is configured by setting `db_session_manager.set_engine()`". Must update:

- **"TestClient"** behavior → update to `app.state.db_manager = DbSessionManager(integration_db_engine)` set before `TestClient(app)` context entry; lifespan skips creation via `hasattr` check
- **"RLS context via `get_session(app_user_id=...)`"** → update to reference `integration_db_manager.get_session()` instead of `db_session_manager.get_session()`
- **Decision table** → add new decision: "Session manager wiring | App-state DI | Over singleton set_engine | Because singleton mutation caused non-deterministic xdist failures"

---

## Resolved Decisions Summary

| OQ | Decision | Choice |
|---|---|---|
| OQ1 | CLI command DI pattern | **Every entry point calls `cli_db_manager()` directly** — universal pattern for both registered CLI commands and standalone dev_tools scripts. No Click `ctx.obj`, no group-level injection. |
| OQ2 | CRUDRouterFactory DI pattern | **`request.app.state.db_manager`** — preserves `yield from` delegation, no Depends() complexity. `request: Request` flows through as plain Python arg. |
| OQ3 | Test fixture regeneration | **Generate `.dump` in test setup via existing `generate_test_seed.py`** — exercises full pg_restore→upsert pipeline, always matches current schema |
| OQ4 | `agent_executor_service.py` | **Own manager via `cli_db_manager()`** — acceptable for personal tool with infrequent agent runs |

## Execution Order

| Phase | RCA | What | Files | Risk |
|---|---|---|---|---|
| 1 | #3 | Fix stale test assertion | 1 | None |
| 2 | #4, #5, #6 | Add skip guards for infra-dependent tests | 3 | None |
| 3 | #2 | Fix seed pipeline SQL guard + generate fixture dynamically | 4 | Low |
| 4 | #1 | Refactor DbSessionManager from singleton to DI | ~53 | Medium |
| 5 | Specs | Update 3 specs to match new architecture | 3 | None |

Phases 1-3 are independent quick fixes (can be done in parallel).
Phase 4 is the structural refactor — largest change, needs careful verification.
Phase 5 follows phase 4 — specs reflect the new code.

### Verification

After all phases:
```bash
# All test suites pass:
precommit-tests --all

# Covers:
# - Unit tests (pytest -n auto --dist=loadfile, excludes integration/live/eval)
# - Integration tests (PostgreSQL, -m integration)
# - Installation flow tests
# - Skill template tests
# - Live LLM tests
# - Live service tests
```

**Success criteria:** No test failures **caused by this refactor**. If `precommit-tests --all` fails after a phase, diagnose whether the failure is:
1. **Caused by the refactor** → fix before proceeding
2. **Pre-existing** (failed before the refactor too) → document and move on, do not fix on the fly

Pre-existing failures are out of scope. RCAs #3-#6 add skip guards so infra-dependent tests skip gracefully instead of failing — but other pre-existing failures may exist and should not block this work.
