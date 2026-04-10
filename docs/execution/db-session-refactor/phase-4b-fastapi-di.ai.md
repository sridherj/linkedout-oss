# Phase 4b: FastAPI DI — Engine via app.state

## Goal

Wire FastAPI to use `request.app.state.db_manager` instead of the `db_session_manager` global. This covers the app lifespan, CRUDRouterFactory, `create_service_dependency()`, auth dependencies, and all custom controllers that directly reference `db_session_manager`.

## Dependencies

**Requires Phase 4a complete** — `DbSessionManager` must accept `engine` as constructor arg and the `db_session_manager` global must be removed.

## Changes

### 1. File: `src/main.py`

Add lifespan that creates and owns the `DbSessionManager`:

```python
from contextlib import asynccontextmanager
from sqlalchemy import create_engine
from shared.config import get_config
from shared.infra.db.db_session_manager import DbSessionManager

@asynccontextmanager
async def lifespan(app):
    # Skip if tests pre-set db_manager (integration tests do this)
    if not hasattr(app.state, 'db_manager'):
        settings = get_config()
        engine = create_engine(settings.database_url, echo=settings.db_echo_log)
        app.state.db_manager = DbSessionManager(engine)
        app.state._owns_engine = True
    else:
        app.state._owns_engine = False
    
    yield
    
    # Dispose engine on shutdown (only if lifespan created it)
    if app.state._owns_engine:
        app.state.db_manager._engine.dispose()
```

Then pass `lifespan=lifespan` to the `FastAPI()` constructor. Check how the app is currently created — it may be in `main.py` or imported from elsewhere.

**Important:** Read `src/main.py` first to understand the current app creation pattern before modifying.

### 2. File: `src/common/controllers/crud_router_factory.py`

The `_get_service` and `_get_write_service` closures (inside `create_crud_router()`) currently use `db_session_manager` global.

**Current (lines 146-160):**
```python
def _get_service(
    session_type: DbSessionType = DbSessionType.READ,
) -> Generator[BaseService, None, None]:
    with db_session_manager.get_session(session_type) as session:
        yield config.service_class(session)

def _get_write_service() -> Generator[BaseService, None, None]:
    yield from _get_service(session_type=DbSessionType.WRITE)
```

**Target:**
```python
def _get_service(
    request: Request,
    session_type: DbSessionType = DbSessionType.READ,
) -> Generator[BaseService, None, None]:
    db_manager = request.app.state.db_manager
    with db_manager.get_session(session_type) as session:
        yield config.service_class(session)

def _get_write_service(request: Request) -> Generator[BaseService, None, None]:
    yield from _get_service(request, session_type=DbSessionType.WRITE)
```

FastAPI auto-injects `request: Request` when it's a dependency parameter. The `yield from` delegation passes `request` as a plain Python arg.

**Also remove the `db_session_manager` import** — change line 13 from:
```python
from shared.infra.db.db_session_manager import DbSessionType, db_session_manager
```
to:
```python
from shared.infra.db.db_session_manager import DbSessionType
```

### 3. File: `src/common/controllers/base_controller_utils.py`

**Current `create_service_dependency()` (lines 104-132):**
```python
def create_service_dependency(
    service_class: Type[TService],
    session_type: DbSessionType = DbSessionType.READ,
    app_user_id: str | None = None,
) -> Generator[TService, None, None]:
    with db_session_manager.get_session(session_type, app_user_id=app_user_id) as session:
        yield service_class(session)
```

**Target — add `request: Request` as first parameter:**
```python
def create_service_dependency(
    request: Request,
    service_class: Type[TService],
    session_type: DbSessionType = DbSessionType.READ,
    app_user_id: str | None = None,
) -> Generator[TService, None, None]:
    db_manager = request.app.state.db_manager
    with db_manager.get_session(session_type, app_user_id=app_user_id) as session:
        yield service_class(session)
```

**Remove `db_session_manager` import** — change:
```python
from shared.infra.db.db_session_manager import DbSessionType, db_session_manager
```
to:
```python
from shared.infra.db.db_session_manager import DbSessionType
```

### 4. File: `src/shared/auth/dependencies/auth_dependencies.py`

**Current `_get_read_session()` (lines 30-32):**
```python
def _get_read_session() -> Generator[Session, None, None]:
    with db_session_manager.get_session(DbSessionType.READ) as session:
        yield session
```

**Target — add `request: Request`:**
```python
def _get_read_session(request: Request) -> Generator[Session, None, None]:
    db_manager = request.app.state.db_manager
    with db_manager.get_session(DbSessionType.READ) as session:
        yield session
```

FastAPI injects `request` automatically. Functions that depend on `_get_read_session` via `Depends()` (like `get_valid_user`) don't need changes — FastAPI's DI handles the injection chain.

**Remove `db_session_manager` import** — change:
```python
from shared.infra.db.db_session_manager import DbSessionType, db_session_manager
```
to:
```python
from shared.infra.db.db_session_manager import DbSessionType
```

### 5. Custom Controllers (7 files that bypass `create_service_dependency`)

Each of these files directly uses `db_session_manager.get_session()`. Change them to use `request.app.state.db_manager`. The pattern is the same for each:

#### 5a. `src/common/controllers/agent_run_controller.py`

The `invoke_agent` endpoint (line 88) uses `db_session_manager.get_session()`. Change to:
```python
db_manager = request.app.state.db_manager
with db_manager.get_session(DbSessionType.WRITE) as session:
```
Add `request: Request` to the endpoint function signature if not already present. Remove `db_session_manager` from imports.

#### 5b. `src/linkedout/intelligence/controllers/search_controller.py`

Multiple `db_session_manager.get_session()` calls (lines 90, 167, 228, 273, 306). These are inside nested `_run()` functions called via `asyncio.to_thread()`.

**Pattern:** Capture `db_manager` from `request.app.state.db_manager` **before** `asyncio.to_thread()`, then use it inside `_run()`:
```python
async def find_people(request: Request, ...):
    db_manager = request.app.state.db_manager
    
    def _run():
        with db_manager.get_session(app_user_id=app_user_id) as session:
            ...
    
    return await asyncio.to_thread(_run)
```

**Important:** `request` is already a parameter in most of these endpoints. If not, add it.

Remove `from shared.infra.db.db_session_manager import db_session_manager` import.

#### 5c. `src/linkedout/intelligence/controllers/best_hop_controller.py`

Line 96 uses `db_session_manager.get_session()` inside `_run_ranking()` called via `asyncio.to_thread()`. Same pattern as search_controller — capture `db_manager` before `asyncio.to_thread`.

Remove `from shared.infra.db.db_session_manager import db_session_manager` import.

#### 5d. `src/linkedout/intelligence/controllers/_sse_helpers.py`

Lines 75 and 138 use `db_session_manager.get_session()`. These are utility functions called from search_controller.

**Important:** These are NOT FastAPI endpoints — they're plain functions. They need `db_manager` passed in as a parameter:

```python
def create_or_resume_session(
    db_manager: DbSessionManager,
    app_user_id: str,
    query: str,
    session_id: str | None,
) -> tuple[str, list[dict] | None]:
    with db_manager.get_session(DbSessionType.WRITE) as db:
        ...
```

Similarly for `save_session_state()`. Update callers in `search_controller.py` to pass `db_manager`.

#### 5e. `src/linkedout/crawled_profile/controllers/crawled_profile_controller.py`

Line 61 uses `db_session_manager.get_session()`. This is in `_get_enrichment_service()` dependency function.

**Change to accept `request: Request`:**
```python
def _get_enrichment_service(
    request: Request,
    app_user_id: str = Header(..., alias="X-App-User-Id"),
) -> Generator[ProfileEnrichmentService, None, None]:
    db_manager = request.app.state.db_manager
    with db_manager.get_session(DbSessionType.WRITE, app_user_id=app_user_id) as session:
        ...
```

#### 5f. `src/linkedout/enrichment_pipeline/controller.py`

Line 273 uses `db_session_manager.get_session()`. Change to `request.app.state.db_manager`. Add `request: Request` to the endpoint function if not already present.

#### 5g. Controllers with their own `_get_service` patterns

These controllers define their own `_get_service()` closures that use `db_session_manager`:
- `src/organization/enrichment_config/controllers/enrichment_config_controller.py` (line 31)
- `src/organization/controllers/tenant_controller.py` (line 52)
- `src/organization/controllers/bu_controller.py` (line 52)
- `src/linkedout/role_alias/controllers/role_alias_controller.py` (line 37)

**Pattern — add `request: Request` to `_get_service()`:**
```python
def _get_service(
    request: Request,
    session_type: DbSessionType = DbSessionType.READ,
) -> Generator[SomeService, None, None]:
    db_manager = request.app.state.db_manager
    with db_manager.get_session(session_type) as session:
        yield SomeService(session)

def _get_write_service(request: Request) -> Generator[SomeService, None, None]:
    yield from _get_service(request, session_type=DbSessionType.WRITE)
```

### 6. Controllers that call `create_service_dependency()` (callers need `request:`)

Any controller that calls `create_service_dependency()` needs to pass `request` as the first argument now. Search for all callers:

```bash
grep -rn "create_service_dependency" backend/src/ --include="*.py"
```

Each caller's dependency function needs `request: Request` added:
```python
def _get_foo_service(request: Request) -> Generator[FooService, None, None]:
    yield from create_service_dependency(request, FooService, DbSessionType.READ)
```

### 7. File: `src/common/services/agent_executor_service.py`

This service runs background tasks and has 4 `db_session_manager.get_session()` calls (lines 82, 105, 116, 134). Per the plan decision (OQ4), this should use `cli_db_manager()`:

```python
from shared.infra.db.cli_db import cli_db_manager

# Replace each:
#   with db_session_manager.get_session(DbSessionType.WRITE) as session:
# With:
    db_manager = cli_db_manager()
    with db_manager.get_session(DbSessionType.WRITE) as session:
```

**Note:** Creating a new `cli_db_manager()` per call is acceptable — each creates its own engine. For agent execution (infrequent), this is fine.

Remove `db_session_manager` from imports.

### 8. File: `.claude/agents/custom-controller-agent.md`

Update the service dependency template to show the `request: Request` pattern:

```python
def _get_<entity>_service(request: Request) -> Generator[<Entity>Service, None, None]:
    yield from create_service_dependency(request, <Entity>Service, DbSessionType.READ)

def _get_write_<entity>_service(request: Request) -> Generator[<Entity>Service, None, None]:
    yield from create_service_dependency(request, <Entity>Service, DbSessionType.WRITE)
```

Also add `from fastapi import Request` to the import template.

## Verification

```bash
# Verify the app starts and basic routes work
cd ./backend && uv run python -c "
from main import app
print(f'App created: {app.title}')
print(f'Routes: {len(app.routes)}')
"

# Run unit tests for controllers (these use mocks, no DB needed)
# NOTE: These will likely fail until Phase 4d updates the mock patterns
# Just verify imports work:
cd ./backend && uv run python -c "
from common.controllers.crud_router_factory import create_crud_router
from common.controllers.base_controller_utils import create_service_dependency
print('Controller imports OK')
"
```

**Do NOT run the full test suite** — test fixtures still use `set_engine()` (fixed in Phase 4d).
