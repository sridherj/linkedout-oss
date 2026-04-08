# Integration Tests

This directory contains end-to-end integration tests that verify all API endpoints work correctly against a real PostgreSQL database.

## Test Categories

### 1. Controller Tests
CRUD endpoint tests for every entity (list, get, create, update, delete). These use seeded data and don't require LLM API keys.

### 2. Intelligence Tests
Search, SQL tool, vector search, affinity scoring, and RLS isolation tests in `linkedout/intelligence/`. These create additional test data (two users with separate connections) and test the search pipeline against real PostgreSQL.

### 3. RLS Isolation Tests
`test_rls_isolation.py` verifies Row-Level Security tenant isolation. These apply RLS policies to the test schema and use `get_session(app_user_id=...)` to set the RLS context, matching production behavior.

## Running Integration Tests

```bash
# Run all integration tests (parallel - each worker gets its own schema)
uv run pytest tests/integration/ -m integration -n4 --dist=loadfile -v --tb=short

# Run specific domain
uv run pytest tests/integration/organization/ -m integration -n4 --dist=loadfile -v

# Quick summary (less verbose)
uv run pytest tests/integration/ -m integration -n4 --dist=loadfile --tb=no -q

# Sequential execution (still supported)
uv run pytest tests/integration/ -m integration -n0 -v --tb=short
```

## Test Structure

```
tests/integration/
├── conftest.py                          # PostgreSQL fixtures, TestClient setup
├── organization/                        # Tenant, BU tests
└── linkedout/
    └── intelligence/
        ├── conftest.py                  # Intelligence test data + RLS fixtures
        ├── test_search_integration.py   # SQL tool, vector search, warm intros
        └── test_rls_isolation.py        # RLS tenant isolation (10 tests)
```

## How It Works

1. **Setup**: Creates a per-worker schema in PostgreSQL (e.g. `integration_test_gw0`, `integration_test_gw1`) so xdist workers don't collide
2. **Migrate**: Runs table creation in the test schema
3. **Seed**: Populates with deterministic test data via BaseSeeder
4. **Test**: Runs all tests using FastAPI TestClient
5. **Teardown**: Drops the test schema

### RLS Test Lifecycle (additional steps for `test_rls_isolation.py`)

RLS tests use a module-scoped `rls_policies_applied` fixture:

1. **Apply policies**: `rls_policies_applied` runs the same DDL as migration `d1e2f3a4b5c6` (ENABLE/FORCE RLS, CREATE POLICY) on the test schema
2. **Run RLS tests**: Use `get_session(app_user_id=...)` to set RLS context per-session. Tests cover cross-user isolation, fail-closed, reference data access, and complex query patterns
3. **Teardown**: Drops policies, disables RLS — other test modules are unaffected

**Why module-scoped?** `FORCE ROW LEVEL SECURITY` applies to the table owner too. Session-scoped would break every other test that queries these tables through the owner connection.

## Key Fixtures

- `test_client` - FastAPI TestClient for HTTP requests
- `seeded_data` - Dictionary of seeded entities by entity type
- `test_tenant_id`, `test_bu_id` - IDs for path parameters

## Writing New Tests

### Controller Tests

```python
import pytest

pytestmark = pytest.mark.integration


class TestYourControllerIntegration:
    def test_list_returns_data(self, test_client, seeded_data, test_tenant_id, test_bu_id):
        response = test_client.get(
            f"/tenants/{test_tenant_id}/bus/{test_bu_id}/your-entities"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) > 0
```
