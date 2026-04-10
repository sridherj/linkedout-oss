# Shared Context: DbSessionManager DI Refactor

## Project Overview

LinkedOut OSS is a Python/FastAPI backend + Chrome extension for professional network intelligence. This execution plan refactors `DbSessionManager` from a mutable singleton to an injected dependency, fixing non-deterministic test failures under pytest-xdist.

## Source Plan

`docs/plan/2026-04-10-db-session-manager-di-refactor.md`

## Key Architecture

### MVCS Stack
- **Entity** -> `BaseEntity` (SQLAlchemy ORM)
- **Repository** -> `BaseRepository` (CRUD, filtering, pagination)
- **Service** -> `BaseService` (orchestration, schema conversion)
- **Controller** -> `CRUDRouterFactory` or hand-written FastAPI routers

### Multi-tenancy
URL pattern: `/tenants/{tenant_id}/bus/{bu_id}/...`
RLS: `app_user_id` passed to `get_session()` sets `app.current_user_id` for PostgreSQL RLS policies.

## Working Directory

All paths are relative to `./backend/` unless stated otherwise.

## Key Files (Pre-Refactor State)

| File | Role |
|------|------|
| `src/shared/infra/db/db_session_manager.py` | Singleton `DbSessionManager` with `set_engine()`, module-level `db_session_manager` global |
| `src/shared/infra/db/__init__.py` | Re-exports `DbSessionManager`, `DbSessionType`, `db_session_manager` |
| `src/main.py` | FastAPI app entry point (currently empty — app created in sub-modules) |
| `src/common/controllers/crud_router_factory.py` | Generic CRUD router factory, uses `db_session_manager` global |
| `src/common/controllers/base_controller_utils.py` | `create_service_dependency()` uses `db_session_manager` global |
| `src/shared/auth/dependencies/auth_dependencies.py` | `_get_read_session()` uses `db_session_manager` global |
| `conftest.py` | Root test conftest with `_shared_db_resources`, `default_db_session_manager_setup`, isolation fixtures |
| `tests/integration/conftest.py` | Integration test conftest with `integration_db_session`, `test_client` |

## Verification Commands

### Unit tests (fast, SQLite-based)
```bash
cd ./backend && uv run pytest -x -q --ignore=tests/integration --ignore=tests/eval --ignore=tests/smoke --ignore=tests/live_llm --ignore=tests/live_service -p no:xdist 2>&1 | tail -20
```

### Integration tests (PostgreSQL required)
```bash
cd ./backend && uv run pytest tests/integration/ -x -q -m integration -p no:xdist 2>&1 | tail -20
```

### Full suite (final verification)
```bash
cd ./backend && uv run precommit-tests --all
```

### Targeted test for a specific file
```bash
cd ./backend && uv run pytest <test_file> -x -v 2>&1 | tail -30
```

## Success Criteria

No test failures **caused by this refactor**. Pre-existing failures are out of scope — document and move on.

## Dependency Graph

```
Phase 1 ──┐
Phase 2 ──┼── (independent, can run in parallel)
Phase 3 ──┘
Phase 4a ──> Phase 4b ──┐
           ──> Phase 4c ──┼──> Phase 4d
                          │
Phase 5 <─────────────────┘
```

- Phases 1, 2, 3: Independent quick fixes, no interdependencies
- Phase 4a: Must complete before 4b, 4c
- Phase 4b, 4c: Can run in parallel after 4a
- Phase 4d: Depends on 4a + 4b + 4c (tests need both FastAPI and CLI patterns in place)
- Phase 5: Depends on all of Phase 4 (specs describe post-refactor architecture)

## Common Patterns After Refactor

### FastAPI pattern (Phase 4b)
```python
# In lifespan or app startup:
db_manager = DbSessionManager(engine)
app.state.db_manager = db_manager

# In controllers:
db_manager = request.app.state.db_manager
with db_manager.get_session(DbSessionType.READ) as session:
    ...
```

### CLI pattern (Phase 4c)
```python
from shared.infra.db.cli_db import cli_db_manager

@click.command()
def my_command():
    db_manager = cli_db_manager()
    with db_manager.get_session(DbSessionType.WRITE) as session:
        ...
```

### Test fixture pattern (Phase 4d)
```python
# No more set_engine() — create manager directly
manager = DbSessionManager(engine)
# For integration tests:
app.state.db_manager = DbSessionManager(integration_db_engine)
```
