# Phase 2: Add Skip Guards for Infra-Dependent Tests

## RCA

Three groups of tests fail because they depend on infrastructure that doesn't exist in the standard test environment:
- **RCA #4:** Demo DB tests need CREATEDB privilege
- **RCA #5:** Eval tests need real LinkedIn data (connection table)
- **RCA #6:** Smoke tests need a specific demo database

## Scope

3 files. Simple skip guards.

## Dependencies

None. This phase is independent and can run in parallel with Phases 1 and 3.

## Changes

### 1. File: `tests/integration/cli/test_demo_db_integration.py`

Add a shared fixture (or module-level autouse fixture) that checks CREATEDB privilege and skips when missing. Add it after the existing imports and `pytestmark` line (around line 29):

```python
@pytest.fixture(autouse=True)
def _require_createdb(integration_db_engine):
    """Skip all tests in this module if the DB user lacks CREATEDB privilege."""
    from sqlalchemy import text
    with integration_db_engine.connect() as conn:
        has_priv = conn.execute(
            text("SELECT has_database_privilege(current_user, 'CREATE')")
        ).scalar()
    if not has_priv:
        pytest.skip("DB user lacks CREATEDB privilege — cannot test demo DB operations")
```

**Note:** This fixture depends on `integration_db_engine` from `tests/integration/conftest.py`. Since this file already has `pytestmark = pytest.mark.integration`, the integration conftest fixtures are available.

### 2. File: `tests/eval/conftest.py`

Modify the `app_user_id` fixture (line 54-65) to check for the `connection` table before querying it. Replace the existing fixture body:

```python
@pytest.fixture(scope="session")
def app_user_id(db_session):
    """Get the first real app_user_id that has connections."""
    # Check if the connection table exists at all
    table_exists = db_session.execute(
        text("SELECT to_regclass('public.connection')")
    ).scalar()
    if not table_exists:
        pytest.skip('No connection table — run LinkedIn CSV loader first')

    result = db_session.execute(text(
        "SELECT app_user_id FROM connection "
        "GROUP BY app_user_id "
        "ORDER BY count(*) DESC "
        "LIMIT 1"
    )).scalar()
    if not result:
        pytest.skip('No app_users with connections found — run LinkedIn CSV loader first')
    return result
```

### 3. File: `tests/smoke/test_demo_search_smoke.py`

Add a module-level connection guard. Insert after the config constants section (around line 38), before any test class or function:

```python
import pytest

def _can_connect_to_demo_db() -> bool:
    """Check if the demo smoke database exists and is connectable."""
    try:
        parsed = urlparse(DB_URL)
        demo_url = urlunparse(parsed._replace(path=f"/{DEMO_DB}"))
        conn = psycopg2.connect(demo_url)
        conn.close()
        return True
    except Exception:
        return False

pytestmark = pytest.mark.skipif(
    not _can_connect_to_demo_db(),
    reason=f"Database '{DEMO_DB}' does not exist — run demo setup first",
)
```

**Note:** `pytest`, `urlparse`, `urlunparse`, `psycopg2` are already imported in this file. Check if `pytestmark` is already defined — if so, make it a list: `pytestmark = [existing_mark, pytest.mark.skipif(...)]`.

## Verification

```bash
# Demo DB tests should skip gracefully
cd ./backend && uv run pytest tests/integration/cli/test_demo_db_integration.py -v 2>&1 | tail -20

# Eval tests should skip gracefully
cd ./backend && uv run pytest tests/eval/ -v 2>&1 | tail -20

# Smoke tests should skip gracefully
cd ./backend && uv run pytest tests/smoke/test_demo_search_smoke.py -v 2>&1 | tail -20
```

**Expected:** All tests in these files either pass (if infra is available) or skip with descriptive messages. No failures.
