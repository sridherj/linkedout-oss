# Phase 5: Update Specs to Match New Architecture

## Goal

Update 3 specs that describe behavior changed by the DbSessionManager DI refactor. Specs are the source of truth — they must reflect the post-refactor architecture.

## Dependencies

**Requires all of Phase 4 complete** (4a + 4b + 4c + 4d). Specs describe the code as it now exists.

## Changes

### 1. File: `docs/specs/database_session_management.collab.md` → Bump to v2

**Read the full spec first** to understand the current structure, then make these changes:

#### Frontmatter
- Bump `version: 1` → `version: 2`
- Update `last_verified` to today's date
- Add `backend/src/shared/infra/db/cli_db.py` to `linked_files`

#### Intent section
Replace "singleton" language:
- **Before:** "Provide a centralized database session manager (singleton) that enforces..."
- **After:** "Provide a database session manager with constructor-injected engine that enforces..."

#### Behaviors section

**Replace "DbSessionManager (Singleton)" heading** with "DbSessionManager (Injected)":
- **Remove** "Singleton pattern" behavior (only one instance, same object)
- **Remove** "Auto initialization" behavior (engine from config on first instantiation)
- **Remove** "Custom engine for tests" behavior (`set_engine()`)

**Add new behaviors:**
- **Constructor injection**: `DbSessionManager(engine: Engine)` — engine is provided at construction time, stored as instance attribute. Construction guarantees `_engine` and `_SessionLocal` are set. No `set_engine()`, no auto-initialization.
- **FastAPI Integration**: In production, the lifespan creates `DbSessionManager(engine)` and stores it on `app.state.db_manager`. Controllers access it via `request.app.state.db_manager`. The lifespan checks `hasattr(app.state, 'db_manager')` to allow integration tests to pre-set the manager before TestClient starts.
- **CLI Integration**: CLI commands and dev_tools scripts use `cli_db_manager()` from `shared.infra.db.cli_db` which creates `get_config().database_url` engine and returns `DbSessionManager(engine)`. Each entry point creates its own manager.

**Keep unchanged:**
- Session Types (READ/WRITE)
- RLS Support
- Entity Discovery
- Configuration (DATABASE_URL, db_echo_log)

#### Decision Table

**Update the existing decision:**
- **Before:** "Singleton | Module-level db_session_manager | Over dependency injection | Because simple"
- **After:** "Session Management | Constructor injection (DI) | Over singleton | Because mutable singleton caused non-deterministic xdist test failures from engine contamination across test categories"

### 2. File: `docs/specs/unit_tests.collab.md` → Bump to v2

**Read the full spec first**, then make these changes:

#### Frontmatter
- Bump version to 2
- Update `last_verified`

#### Changes
- **Replace any "set_engine()" references** throughout the spec with the new pattern
- **"Shared DB for read-only tests"**: Update to describe `_shared_db_resources` creating its own engine and passing it directly. No global mutation.
- **"Isolated DB for mutation tests"**: Same — each fixture creates its own `DbSessionManager(engine)` instance, no save-restore pattern.
- **Remove references to `default_db_session_manager_setup`** autouse fixture (deleted)
- **Remove references to `db_session_manager.set_engine()`** throughout
- **Update "Test Configuration" section** (if exists) to note that xdist parallel is safe after refactor (no singleton contamination)

**Add new section: "Mock Pattern Migration"**
Document the 3 post-refactor mock patterns:
1. **Controller tests**: Mock `request.app.state.db_manager` — no more patching `db_session_manager` at module level
2. **CLI command tests**: Patch `cli_db_manager` factory function instead of `db_session_manager` global
3. **Utility tests**: Pass `db_manager` as parameter — no patching needed

### 3. File: `docs/specs/integration_tests.collab.md` → Bump to v2

**Read the full spec first**, then make these changes:

#### Frontmatter
- Bump version to 2
- Update `last_verified`

#### Changes
- **"TestClient" behavior**: Update from `db_session_manager.set_engine(integration_db_engine)` to `app.state.db_manager = DbSessionManager(integration_db_engine)` set before `TestClient(app)` context entry. Note the lifespan's `hasattr` check skips creating a second manager.
- **"RLS context"**: Update to reference the local `DbSessionManager` instance rather than the `db_session_manager` global. Pattern: `db_manager.get_session(app_user_id=...)` where `db_manager` is from the fixture.
- **Remove any `set_engine()` references** throughout

**Add new decision to Decision Table:**
- "Session manager wiring | App-state DI | Over singleton set_engine | Because singleton mutation caused non-deterministic xdist failures"

## Verification

Specs don't have automated tests. Verify by reading each updated spec and confirming it matches the actual code:

```bash
# Verify the spec describes the actual code patterns
cd ./backend

# Check DbSessionManager has __init__(engine) and no set_engine
uv run python -c "
import inspect
from shared.infra.db.db_session_manager import DbSessionManager
sig = inspect.signature(DbSessionManager.__init__)
print(f'DbSessionManager.__init__ signature: {sig}')
assert 'engine' in sig.parameters, 'Missing engine parameter'
assert not hasattr(DbSessionManager, 'set_engine'), 'set_engine should be removed'
print('Spec alignment OK: constructor injection, no set_engine')
"

# Check cli_db_manager exists
uv run python -c "
from shared.infra.db.cli_db import cli_db_manager
print(f'cli_db_manager exists: {cli_db_manager}')
"

# Check app.state.db_manager pattern is in main.py
grep -n "db_manager" src/main.py
```

**Expected:** All checks confirm the specs accurately describe the current code.
