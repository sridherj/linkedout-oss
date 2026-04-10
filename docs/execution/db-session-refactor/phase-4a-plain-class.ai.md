# Phase 4a: Make DbSessionManager a Plain Class + Create cli_db.py

## Goal

Convert `DbSessionManager` from a mutable singleton to a plain class that takes `engine` as a constructor argument. Create a `cli_db_manager()` factory for CLI entry points. Migrate the 4 files (7 call sites) that use `DbSessionManager()` zero-arg constructor.

## Dependencies

None from Phases 1-3. This is the foundation for Phases 4b, 4c, and 4d.

## Changes

### 1. File: `src/shared/infra/db/db_session_manager.py`

This is the core change. Transform the singleton into a plain class.

**Current state (lines 50-127, 242-243):**
```python
class DbSessionManager:
    _instance: Optional['DbSessionManager'] = None
    _engine: Optional[Engine] = None
    _SessionLocal = None

    def __new__(cls) -> 'DbSessionManager':
        if cls._instance is None:
            cls._instance = super(DbSessionManager, cls).__new__(cls)
            cls._instance._initialize_engine()
        return cls._instance

    def _initialize_engine(self) -> None:
        if not self._engine:
            settings = get_config()
            self._engine = create_engine(settings.database_url, echo=settings.db_echo_log)
            self._SessionLocal = sessionmaker(bind=self._engine, autoflush=False, autocommit=False)

    def set_engine(self, engine: Engine) -> None:
        self._engine = engine
        self._SessionLocal = sessionmaker(bind=self._engine, autoflush=False, autocommit=False)
    ...

db_session_manager = DbSessionManager()
```

**Target state:**
```python
class DbSessionManager:
    """Database session manager with injected engine.

    Engine is provided at construction time. FastAPI apps create the manager
    in lifespan; CLI commands use ``cli_db_manager()``; tests create their
    own manager per fixture.

    RLS support: pass ``app_user_id`` to ``get_session()`` to set
    ``app.current_user_id`` for the transaction.
    """

    def __init__(self, engine: Engine) -> None:
        """Create a session manager bound to the given engine.

        Args:
            engine: SQLAlchemy engine to bind sessions to.
        """
        self._engine: Engine = engine
        self._SessionLocal = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
        )
```

**Specific removals:**
- Remove `_instance: Optional['DbSessionManager'] = None` (class variable, line 82)
- Remove `_engine: Optional[Engine] = None` (class variable, line 83)
- Remove `_SessionLocal = None` (class variable, line 84)
- Remove entire `__new__` method (lines 86-92)
- Remove entire `_initialize_engine` method (lines 94-107)
- Remove entire `set_engine` method (lines 109-126)
- Remove `if not self._SessionLocal:` guard in `get_session()` (line 198) — construction guarantees it's set. Remove the guard + RuntimeError block; the `db = self._SessionLocal()` call on line 201 stays.
- Remove `if not self._SessionLocal:` guard in `get_raw_session()` (line 142) — same reason. Remove the guard + RuntimeError block; `return self._SessionLocal()` on line 146 stays.
- Remove `db_session_manager = DbSessionManager()` (line 243) — module-level global deleted

**Keep unchanged:**
- All entity discovery imports at the top (lines 16-36)
- `DbSessionType` enum (lines 39-48)
- `get_raw_session()` method body (minus the None guard)
- `_try_set_transaction_read_only()`, `_try_set_transaction_write()` methods
- `get_session()` context manager body (minus the None guard)
- `_try_set_rls_user()` method

**Remove imports that are no longer needed:**
- `from shared.config import get_config` — engine comes from caller, not auto-init
- `Optional` from typing (if no longer used after removing Optional[Engine])

### 2. File: `src/shared/infra/db/__init__.py`

Update to remove the `db_session_manager` global re-export:

**Current:**
```python
from shared.infra.db.db_session_manager import (
    DbSessionManager,
    DbSessionType,
    db_session_manager
)

__all__ = ['DbSessionManager', 'DbSessionType', 'db_session_manager']
```

**Target:**
```python
from shared.infra.db.db_session_manager import (
    DbSessionManager,
    DbSessionType,
)

__all__ = ['DbSessionManager', 'DbSessionType']
```

### 3. New file: `src/shared/infra/db/cli_db.py`

Create this new file:

```python
# SPDX-License-Identifier: Apache-2.0
"""CLI database helper — creates a DbSessionManager for CLI entry points."""
from sqlalchemy import create_engine

from shared.config import get_config
from shared.infra.db.db_session_manager import DbSessionManager


def cli_db_manager() -> DbSessionManager:
    """Create a DbSessionManager for CLI commands and scripts.

    Each CLI entry point calls this to get its own manager instance.
    """
    settings = get_config()
    engine = create_engine(settings.database_url, echo=settings.db_echo_log)
    return DbSessionManager(engine)
```

### 4. File: `src/linkedout/dashboard/controller.py`

**Current (line 27):**
```python
def _run() -> DashboardResponse:
    db = DbSessionManager()
    with db.get_session(DbSessionType.READ, app_user_id=app_user_id) as session:
```

**Target:** Use `request.app.state.db_manager`. Add `request: Request` parameter to the endpoint:

```python
from fastapi import APIRouter, Header, Request
...

@dashboard_router.get("", response_model=DashboardResponse)
async def get_dashboard(
    request: Request,
    tenant_id: str,
    bu_id: str,
    app_user_id: str = Header(..., alias="X-App-User-Id"),
) -> DashboardResponse:
    """Return network aggregation data for the authenticated user."""
    db_manager = request.app.state.db_manager

    def _run() -> DashboardResponse:
        with db_manager.get_session(DbSessionType.READ, app_user_id=app_user_id) as session:
            repo = DashboardRepository(session)
            service = DashboardService(repo)
            return service.get_dashboard(tenant_id, bu_id, app_user_id)

    return await asyncio.to_thread(_run)
```

**Important:** Capture `db_manager` **before** `asyncio.to_thread` — the `request` object may not be safe to access from a different thread.

Also update the import — change `from shared.infra.db.db_session_manager import DbSessionManager, DbSessionType` to `from shared.infra.db.db_session_manager import DbSessionType` (no longer needs `DbSessionManager` class).

### 5. File: `src/shared/utilities/health_checks.py`

Two functions create `DbSessionManager()` zero-arg: `check_db_connection()` (line 72) and `get_db_stats()` (line 262).

**Change both to accept `db_manager` as a parameter:**

For `check_db_connection()` (line 55):
```python
def check_db_connection(db_manager: 'DbSessionManager | None' = None) -> HealthCheckResult:
    """Test PostgreSQL connectivity."""
    try:
        if db_manager is None:
            from shared.infra.db.cli_db import cli_db_manager
            db_manager = cli_db_manager()

        from shared.infra.db.db_session_manager import DbSessionType
        with db_manager.get_session(DbSessionType.READ) as session:
            session.execute(text('SELECT 1'))
        return HealthCheckResult(check='db_connection', status='pass')
    except Exception as e:
        return HealthCheckResult(check='db_connection', status='fail', detail=str(e))
```

For `get_db_stats()` — similar pattern. Find the function (around line 200+), add `db_manager` parameter with `None` default, fall back to `cli_db_manager()` when not provided. The function already accepts `session` as optional — keep that, and add `db_manager` as a second fallback.

### 6. File: `src/dev_tools/diagnostics.py`

Three sites create `DbSessionManager()` (lines 80, 403, 442). These are all within diagnostic functions.

**Change each to use `cli_db_manager()`:**

Replace:
```python
from shared.infra.db.db_session_manager import DbSessionManager, DbSessionType
db_mgr = DbSessionManager()
```

With:
```python
from shared.infra.db.cli_db import cli_db_manager
from shared.infra.db.db_session_manager import DbSessionType
db_mgr = cli_db_manager()
```

For the functions that call health_checks, pass `db_manager` through:
```python
db_mgr = cli_db_manager()
result = check_db_connection(db_manager=db_mgr)
stats = get_db_stats(db_manager=db_mgr)
```

## Verification

After this phase, the codebase should import successfully but **will not pass full tests** because:
- `crud_router_factory.py` and `base_controller_utils.py` still reference `db_session_manager` global (fixed in Phase 4b)
- CLI commands still reference `db_session_manager` global (fixed in Phase 4c)
- Test fixtures still use `set_engine()` (fixed in Phase 4d)

**Verify the module imports cleanly:**
```bash
cd ./backend && uv run python -c "
from shared.infra.db.db_session_manager import DbSessionManager, DbSessionType
from shared.infra.db.cli_db import cli_db_manager
from sqlalchemy import create_engine
engine = create_engine('sqlite:///:memory:')
mgr = DbSessionManager(engine)
print(f'DbSessionManager created successfully with engine: {engine}')
print(f'cli_db_manager function available: {cli_db_manager}')
"
```

**Verify diagnostics can create a manager:**
```bash
cd ./backend && uv run python -c "
from shared.infra.db.cli_db import cli_db_manager
print('cli_db_manager imports OK')
"
```

**Do NOT run the full test suite** — it will fail until Phases 4b-4d are complete.
