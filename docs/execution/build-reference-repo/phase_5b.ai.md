# Phase 5b: Auth Mocking + Agent Test Patterns

## Execution Context
**Depends on**: Phase 4 (auth exists to mock), Phase 5a (basic test infra), Phase 6a (AgentRun MVCS exists)
**Blocks**: Phase 7
**Parallel with**: Phase 6b (TaskTriageAgent)

## Goal
Complete the test infrastructure with auth mocking patterns and agent test patterns. This phase adds the auth- and agent-dependent test capabilities that Phase 5a deferred.

## Pre-Conditions
- Phase 4 DONE: Auth dependencies, AuthContext, role enums exist
- Phase 5a DONE: Basic test infra, seed data, entity factories in place
- Phase 6a DONE: AgentRunEntity, AgentRunService, BaseAgent exist
- `precommit-tests` passes

## Post-Conditions (Definition of Done)
- `precommit-tests` passes
- Auth is mockable/bypassable in all test layers via `override_auth` fixture
- AgentRun test patterns work (create, lifecycle, mocked LLM)
- Integration tests use auth override correctly
- All test layers have auth-aware examples

---

## Step 1: Auth Mock Fixtures

### File: `conftest.py` (add to root conftest)

```python
from shared.auth.dependencies.schemas.auth_context import AuthContext, Principal, Actor, Subject
from shared.auth.dependencies.schemas.role_enums import TenantRole, BuRole

@pytest.fixture
def mock_auth_context():
    """Pre-built AuthContext for tests needing authenticated requests."""
    return AuthContext(
        principal=Principal(
            auth_provider_id="test-uid-001",
            user_id="test-user-001",
            email="test@example.com",
            name="Test User",
        ),
        actor=Actor(
            id="test-user-001",
            current_tenant_roles=[TenantRole.ADMIN],
            current_bu_roles=[BuRole.ADMIN],
        ),
        subject=Subject(tenant_id="tenant-test-001", bu_id="bu-test-001"),
    )

@pytest.fixture
def override_auth(mock_auth_context):
    """Override auth dependencies in FastAPI app for testing."""
    from main import app
    from shared.auth.dependencies.auth_dependencies import is_valid_user, get_valid_user

    app.dependency_overrides[is_valid_user] = lambda: mock_auth_context
    app.dependency_overrides[get_valid_user] = lambda: mock_auth_context
    yield mock_auth_context
    app.dependency_overrides.clear()
```

### Usage Pattern
Controller tests and integration tests that hit auth-protected endpoints should use `override_auth`:
```python
class TestCreateLabelEndpoint:
    def test_create_label_success(self, override_auth, client):
        response = client.post('/tenants/t1/bus/b1/labels', json={...})
        assert response.status_code == 201
```

---

## Step 2: Update Existing Controller Tests for Auth

If Phase 4 wired auth into CRUDRouterFactory or custom controllers, existing controller tests from Phase 5a may now fail with 401. Update them to use `override_auth` fixture.

Pattern: Add `override_auth` to test class/function parameters.

---

## Step 3: AgentRun Test Fixtures

### Add to `conftest.py` or `tests/conftest_agent.py`

```python
@pytest.fixture
def seeded_agent_run(function_scoped_isolated_db_session):
    """Create a seeded AgentRun entity for testing."""
    from common.entities.agent_run_entity import AgentRunEntity
    entity = AgentRunEntity(
        tenant_id='tenant-test-001',
        bu_id='bu-test-001',
        agent_type='task_triage',
        status='PENDING',
        input_params={'task_id': 'task-test-001'},
    )
    function_scoped_isolated_db_session.add(entity)
    function_scoped_isolated_db_session.commit()
    return entity
```

### Add AgentRun to EntityFactory
```python
def create_agent_run(self, overrides=None, auto_commit=False, add_to_session=True):
    data = {
        'tenant_id': 'tenant-test-001',
        'bu_id': 'bu-test-001',
        'agent_type': 'task_triage',
        'status': 'PENDING',
        'input_params': {},
    }
    return self._create_entity(AgentRunEntity, data, overrides, auto_commit, add_to_session)
```

### Add AgentRun to Fixed Data
```python
FIXED_AGENT_RUNS = [
    {
        'id': 'arn-test-001',
        'tenant_id': 'tenant-test-001',
        'bu_id': 'bu-test-001',
        'agent_type': 'task_triage',
        'status': 'completed',
        'input_params': {'task_id': 'task-test-001'},
    },
]
```

### Add to BaseSeeder ENTITY_ORDER
```python
('agent_run', ['bu']),
```

### Add to seed_db.py TableName
```python
AGENT_RUN = 'agent_run'
```

---

## Step 4: AgentRun Repository Tests

### File: `tests/common/repositories/test_agent_run_repository.py`

**Wiring tests**:
- inherits BaseRepository
- entity_class = AgentRunEntity
- default_sort_field = 'created_at'
- filter_specs: agent_type (eq), status (eq)

**Integration tests** (isolated SQLite):
- create with arn prefix
- list with agent_type filter
- list with status filter

---

## Step 5: AgentRun Service Tests

### File: `tests/common/services/test_agent_run_service.py`

- Wiring: inherits BaseService, correct classes
- create_agent_run: creates with PENDING status
- update_status: transitions PENDING -> RUNNING -> COMPLETED
- update_status with error: sets error_message
- update_status with metrics: sets llm_cost_usd, llm_latency_ms

---

## Step 6: AgentRun Controller Tests

### File: `tests/common/controllers/test_agent_run_controller.py`

- POST /agent-runs: returns 202 with agent_run_id
- GET /agent-runs: list with pagination
- GET /agent-runs/{id}: returns agent run details
- GET /agent-runs/{id}: 404 for unknown ID

---

## Step 7: Integration Test Updates

### File: `tests/integration/conftest.py`

Add AgentRunEntity to integration test entity imports. Update `IntegrationTestSeeder` to seed project_mgmt + agent_run entities.

### File: `tests/integration/test_agent_run_integration.py`

- Create agent run via POST, verify 202
- List agent runs, verify seeded data
- Get agent run by ID

---

## Files Summary

### Create (~6 files)
| File | Description |
|------|-------------|
| `tests/common/repositories/test_agent_run_repository.py` | AgentRun repo tests |
| `tests/common/services/test_agent_run_service.py` | AgentRun service tests |
| `tests/common/controllers/test_agent_run_controller.py` | AgentRun controller tests |
| `tests/integration/test_agent_run_integration.py` | AgentRun integration tests |
| `tests/common/__init__.py` | Init files |
| Various `__init__.py` | Directory init files |

### Modify (~5 files)
| File | Change |
|------|--------|
| `conftest.py` | Add mock_auth_context + override_auth fixtures |
| `src/dev_tools/db/fixed_data.py` | Add FIXED_AGENT_RUNS |
| `src/shared/test_utils/entity_factories.py` | Add create_agent_run() |
| `src/shared/test_utils/seeders/base_seeder.py` | Add agent_run to ENTITY_ORDER |
| `tests/seed_db.py` | Add AGENT_RUN to TableName |
| Existing controller test files | Add override_auth fixture usage |
