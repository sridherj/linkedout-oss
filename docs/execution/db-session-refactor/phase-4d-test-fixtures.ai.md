# Phase 4d: Test Fixtures — Each Creates Own Manager

## Goal

Remove all `set_engine()` calls and `db_session_manager` global references from test code. Each test fixture creates its own `DbSessionManager(engine)` instance. Integration tests pre-set `app.state.db_manager` before `TestClient(app)`.

## Dependencies

**Requires Phases 4a + 4b + 4c complete** — the `DbSessionManager` class, FastAPI `app.state.db_manager` pattern, and `cli_db_manager()` must all be in place.

## Changes

### 1. File: `conftest.py` (root — backend/conftest.py)

This is the most important file. It has multiple `set_engine()` calls and the autouse fixture.

#### 1a. Remove `db_session_manager` import (line 128)
```python
# Remove this line:
from shared.infra.db.db_session_manager import db_session_manager
# Add this import instead:
from shared.infra.db.db_session_manager import DbSessionManager
```

#### 1b. Fix `_shared_db_resources` (lines 228-256)
**Current:**
```python
@pytest.fixture(scope='session')
def _shared_db_resources():
    engine = _create_test_engine()
    Base.metadata.create_all(engine)
    
    original_engine = getattr(db_session_manager, '_engine', None)
    db_session_manager.set_engine(engine)
    
    seeder = SeedDb()
    seed_config = SeedDb.SeedConfig()
    seed_config.custom_engine = engine
    seeder.init(config=seed_config)
    seeded_data = seeder.seed_data()
    
    if original_engine is not None and original_engine is not engine:
        db_session_manager.set_engine(original_engine)
    
    return engine, seeded_data
```

**Target — no set_engine, no save-restore:**
```python
@pytest.fixture(scope='session')
def _shared_db_resources():
    engine = _create_test_engine()
    Base.metadata.create_all(engine)
    
    # SeedDb uses its own sessionmaker from config.custom_engine — it doesn't need db_session_manager
    seeder = SeedDb()
    seed_config = SeedDb.SeedConfig()
    seed_config.custom_engine = engine
    seeder.init(config=seed_config)
    seeded_data = seeder.seed_data()
    
    return engine, seeded_data
```

#### 1c. Delete `default_db_session_manager_setup` (lines 259-266)
Remove this entire fixture:
```python
@pytest.fixture(scope='session', autouse=True)
def default_db_session_manager_setup(_shared_db_resources):
    shared_engine, _ = _shared_db_resources
    db_session_manager.set_engine(shared_engine)
```

This was an autouse fixture that mutated the global singleton. No longer needed.

#### 1d. Fix `function_scoped_isolated_db_session` (lines 336-375)
**Remove the save-restore pattern (lines 353-354, 361-362):**
```python
# Remove these lines:
original_engine = getattr(db_session_manager, '_engine', None)
db_session_manager.set_engine(isolated_engine)
...
if original_engine is not None:
    db_session_manager.set_engine(original_engine)
```

The `SeedDb` uses `config.custom_engine` directly — it doesn't go through `db_session_manager`.

#### 1e. Fix `class_scoped_isolated_db_session` (lines 378-425)
Same removal — remove `set_engine()` and save-restore pattern (lines 398-399, 406-407).

#### 1f. Fix `db_session` legacy fixture (lines 469-485)
**Current (line 479):**
```python
db_session_manager.set_engine(db_engine)
```
**Remove this line entirely.** The legacy `db_session` fixture provides a raw session — it doesn't need to configure the global.

### 2. File: `tests/integration/conftest.py`

#### 2a. Remove `db_session_manager` import (line 50)
```python
# Remove:
from shared.infra.db.db_session_manager import db_session_manager
# Add:
from shared.infra.db.db_session_manager import DbSessionManager
```

#### 2b. Fix `integration_db_session` (lines 168-196)
**Remove line 189:**
```python
db_session_manager.set_engine(integration_db_engine)
```
This line is no longer needed — the integration session is used directly.

#### 2c. Fix `test_client` (lines 252-277)
**Current:**
```python
@pytest.fixture(scope='session')
def test_client(integration_db_engine, seeded_data):
    db_session_manager.set_engine(integration_db_engine)
    from main import app
    with TestClient(app) as client:
        yield client
```

**Target — pre-set app.state.db_manager:**
```python
@pytest.fixture(scope='session')
def test_client(integration_db_engine, seeded_data):
    from main import app
    
    # Pre-set db_manager so the lifespan's hasattr check skips creating one
    app.state.db_manager = DbSessionManager(integration_db_engine)
    
    with TestClient(app) as client:
        yield client
```

### 3. File: `tests/integration/linkedout/intelligence/test_best_hop_integration.py`

Two sites use `set_engine()` (lines 374, 434). These are inside test methods that create their own `TestClient` via `httpx`:

**Current pattern (line 374):**
```python
from shared.infra.db.db_session_manager import db_session_manager
db_session_manager.set_engine(integration_db_engine)
from main import app
```

**Target — use app.state.db_manager:**
```python
from shared.infra.db.db_session_manager import DbSessionManager
from main import app
app.state.db_manager = DbSessionManager(integration_db_engine)
```

Apply this pattern at both line 374 and line 434.

### 4. File: `tests/integration/linkedout/intelligence/test_rls_isolation.py`

This file uses `db_session_manager` directly (lines 35, 46, 57, 70, 88, 113, 130, 154, 168, 184). It uses `db_session_manager.get_session(app_user_id=...)` and `db_session_manager._SessionLocal` directly.

**Target — create a local `DbSessionManager`:**

Add a fixture at the top of the test class (or module):
```python
from shared.infra.db.db_session_manager import DbSessionManager

@pytest.fixture(scope='session')
def rls_db_manager(integration_db_engine):
    return DbSessionManager(integration_db_engine)
```

Then replace all `db_session_manager.get_session(...)` calls with `rls_db_manager.get_session(...)` in test methods.

For lines that access `db_session_manager._SessionLocal` directly (lines 88, 113, 130), use `rls_db_manager._SessionLocal` instead. These are tests checking RLS behavior without setting the session variable — the pattern is valid, just needs the instance swap.

### 5. Unit test mock pattern migration (6 files)

After the refactor, controllers no longer import `db_session_manager` — they use `request.app.state.db_manager`. The mock patterns must change.

#### Pattern 1: Custom controller tests (4 files)

These files patch `db_session_manager` at the controller module level:
- `tests/unit/linkedout/intelligence/test_warm_intros.py`
- `tests/unit/linkedout/intelligence/test_search_controller_streaming.py`
- `tests/unit/linkedout/intelligence/test_best_hop_controller.py`
- `tests/unit/linkedout/intelligence/test_people_like_x.py`

**Current pattern (e.g., test_warm_intros.py):**
```python
@pytest.fixture()
def _mock_db():
    with patch("linkedout.intelligence.controllers.search_controller.db_session_manager") as mock_db:
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)
        yield mock_db, mock_session
```

**Post-refactor:** Controllers no longer have a `db_session_manager` to patch. They read from `request.app.state.db_manager`. For tests that call endpoint functions directly, you need to provide a mock request with `app.state.db_manager`:

**Important:** The exact new pattern depends on how each test calls the endpoint. Read each test file to determine:
- If tests call the endpoint function directly → pass a mock `request` with `request.app.state.db_manager` set
- If tests use `TestClient` or `httpx` → set `app.state.db_manager` before creating the client
- If tests use `asyncio.to_thread` mocking → the `db_manager` is captured before the thread, so mock it on `request.app.state`

For the search_controller and best_hop_controller tests that use `@patch` decorators, the simplest approach is to check what these tests actually do after Phase 4b changes the controllers. The patch targets will need to change to wherever `db_manager` is now sourced.

**Read each test file fully before making changes** — the exact mock setup depends on the test structure.

#### Pattern 2: CLI command test (1 file)

**File:** `tests/unit/cli/test_embed_command.py`

**Current (5 sites):**
```python
with patch('linkedout.commands.embed.db_session_manager') as mock_db:
```

**Target — patch `cli_db_manager` instead:**
```python
with patch('linkedout.commands.embed.cli_db_manager') as mock_cli_db:
    mock_db = MagicMock()
    mock_db.get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)
    mock_cli_db.return_value = mock_db
```

Apply this pattern at all 5 patch sites (lines 41, 117, 154, 183, 216).

#### Pattern 3: Utility test (1 file)

**File:** `tests/unit/shared/utilities/test_health_checks.py`

**Current (line 47):**
```python
@patch('shared.infra.db.db_session_manager.DbSessionManager')
```

After refactor, `check_db_connection()` takes `db_manager` as an optional parameter. Tests can pass it directly — no patching needed:

```python
def test_returns_pass_on_successful_connection(self):
    mock_db = MagicMock()
    result = check_db_connection(db_manager=mock_db)
    assert result.status == 'pass'
```

For `get_db_stats()` — same pattern, pass `db_manager` directly.

**Also update the test at line 224** which patches `DbSessionManager` constructor to raise an error — this should now patch `cli_db_manager` instead:
```python
with patch('shared.utilities.health_checks.cli_db_manager', side_effect=Exception('no db')):
    stats = get_db_stats()
```

### 6. File: `tests/common/test_base_controller_utils.py`

After refactor, `create_service_dependency()` takes `request: Request` as first parameter. Tests must pass a mock request:

**Current pattern (e.g., line 227-229):**
```python
monkeypatch.setattr(
    'common.controllers.base_controller_utils.db_session_manager',
    mock_db_session_manager,
)
gen = create_service_dependency(mock_service_class)
```

**Target:**
```python
mock_request = Mock()
mock_request.app.state.db_manager = mock_db_session_manager
gen = create_service_dependency(mock_request, mock_service_class)
```

No monkeypatch needed — the function reads from the request object directly. Update all test methods in `TestCreateServiceDependency` class.

## Verification

This is the critical phase — after this, the full test suite should pass.

```bash
# Run unit tests first (fast, SQLite)
cd ./backend && uv run pytest -x -q --ignore=tests/integration --ignore=tests/eval --ignore=tests/smoke --ignore=tests/live_llm --ignore=tests/live_service -p no:xdist 2>&1 | tail -30

# Then integration tests
cd ./backend && uv run pytest tests/integration/ -x -q -m integration -p no:xdist 2>&1 | tail -30

# Then the full suite
cd ./backend && uv run precommit-tests --all

# Verify no remaining references to db_session_manager global or set_engine
cd ./backend && grep -rn "db_session_manager\.\(get_session\|set_engine\|_SessionLocal\)" tests/ --include="*.py" | head -20
cd ./backend && grep -rn "from.*import.*db_session_manager" tests/ conftest.py --include="*.py" | head -20
```

**Expected:** All tests pass (or skip gracefully for infra-dependent ones). Zero references to `db_session_manager` global or `set_engine()` in test code.

**Success criteria:** No test failures **caused by this refactor**. Pre-existing failures are out of scope.
