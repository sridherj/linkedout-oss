# Enable RLS Integration Tests

## Context
The 10 RLS isolation tests in `test_rls_isolation.py` are skipped behind a `RUN_RLS_TESTS` env var because:
1. The integration test schema is created via `Base.metadata.create_all()` which doesn't run Alembic migrations — so RLS policies are never applied.
2. `set_engine()` overrides `_SearchSessionLocal` to use the same owner-role engine, so even if policies existed, the owner role would bypass RLS.

**Goal:** Make these tests run automatically as part of the normal integration test suite with zero prerequisites.

**Key facts from review:**
- `linkedout_search_role` already exists in the DB (no need to CREATE ROLE)
- `SEARCH_DATABASE_URL` is already in `.env.local` with credentials (`linkedout_search_role:search_role_pwd`)
- `linkedout_user` (test DB owner) does NOT have CREATEROLE but CAN grant on schemas it creates
- `linkedout_user` is the grantor for all existing search role grants

## Plan

### Step 1: Apply RLS policies in test schema fixture
**File:** `tests/integration/linkedout/intelligence/conftest.py`

Add a session-scoped fixture `rls_policies_applied` (depends on `intelligence_test_data` so tables + data exist). It executes the same SQL from migration `d1e2f3a4b5c6`:

1. Create composite index: `idx_connection_user_profile`
2. For `connection`: `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, create `app_user_isolation` policy
3. For `crawled_profile`, `experience`, `education`, `profile_skill`: `ENABLE RLS`, `FORCE RLS`, create `user_profiles` policy (subquery via connection table)
4. GRANT access to existing `linkedout_search_role`:
   - `GRANT USAGE ON SCHEMA {TEST_SCHEMA} TO linkedout_search_role`
   - `GRANT SELECT ON ALL TABLES IN SCHEMA {TEST_SCHEMA} TO linkedout_search_role`

Use the `integration_db_engine` (admin/owner connection) to execute these statements.

### Step 2: Create search engine fixture
**File:** `tests/integration/linkedout/intelligence/conftest.py`

Add a session-scoped fixture `rls_search_engine` (depends on `rls_policies_applied`):

1. Read `SEARCH_DATABASE_URL` from env (already has `linkedout_search_role` credentials)
2. Append schema option using `?` vs `&` check (same pattern as `tests/integration/conftest.py:145-148`):
   ```python
   if '?' in search_url:
       test_url = f'{search_url}&options=-csearch_path%3D{TEST_SCHEMA}%2Cpublic'
   else:
       test_url = f'{search_url}?options=-csearch_path%3D{TEST_SCHEMA}%2Cpublic'
   ```
3. Create a separate SQLAlchemy engine with this URL
4. Call `db_session_manager.set_search_engine(engine)` to wire it up
5. Yield; dispose on cleanup

If `SEARCH_DATABASE_URL` is not set, `pytest.skip()` with a clear message.

**Ordering note:** This fixture must run AFTER `integration_db_session` (which calls `set_engine()` and clobbers both engines). The dependency chain `rls_search_engine` → `rls_policies_applied` → `intelligence_test_data` → `integration_db_session` ensures correct ordering. However, `test_client` also calls `set_engine()` — RLS tests must NOT use `test_client` or the search engine will be overwritten.

### Step 3: Add `set_search_engine()` to DbSessionManager
**File:** `src/shared/infra/db/db_session_manager.py`

Add a minimal method that sets only the search engine without touching the main engine:

```python
def set_search_engine(self, engine: Engine) -> None:
    self._search_engine = engine
    self._SearchSessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False,
    )
```

This is the only production code change.

### Step 4: Update test file
**File:** `tests/integration/linkedout/intelligence/test_rls_isolation.py`

- Remove `RUN_RLS_TESTS` env var check, `skipif` marker, and `import os`
- Apply `rls_search_engine` via **module-level `usefixtures`**, not per-test parameter:
  ```python
  pytestmark = [
      pytest.mark.integration,
      pytest.mark.usefixtures("rls_search_engine"),
  ]
  ```
  This is critical because `TestRLSFailClosed` and `TestRLSReferenceDataAccessible` don't take `intelligence_test_data` — they access `_SearchSessionLocal` directly. Without `usefixtures`, those classes would never get the search engine wired to the restricted role.

## Files to modify
- `tests/integration/linkedout/intelligence/conftest.py` — add `rls_policies_applied` + `rls_search_engine` fixtures
- `tests/integration/linkedout/intelligence/test_rls_isolation.py` — remove skip gate, use `usefixtures` marker
- `src/shared/infra/db/db_session_manager.py` — add `set_search_engine()` method

## Prerequisites
**None.** The `linkedout_search_role` already exists, `SEARCH_DATABASE_URL` is already configured, and `linkedout_user` can grant on schemas it owns.

## Verification
```bash
# RLS tests run and pass (no skips)
uv run pytest tests/integration/linkedout/intelligence/test_rls_isolation.py --override-ini="addopts=" -v

# Full suite still passes
uv run pytest tests/unit tests/integration --override-ini="addopts=" -v
```
