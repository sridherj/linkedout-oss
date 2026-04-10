# Phase 5: Testing Infrastructure — Detailed Execution Plan

## Goal
Replace all linkedout/rcm test infrastructure with project-management domain tests. All 4 test layers with representative examples, declarative seeding, and parallel execution verified.

## Pre-Conditions
- Phase 3 DONE: Project-management entities exist (Label, Priority, Project, Task, ProjectSummary, AgentRun)
- Phase 4 DONE: Auth dependencies exist and are mockable
- `precommit-tests` passes

## Post-Conditions (Definition of Done)
- `precommit-tests` passes with new domain tests replacing all rcm tests
- Zero rcm/linkedout references in `tests/`, `src/shared/test_utils/`, `src/dev_tools/db/`
- All 4 test layers have representative tests for at least Label and Task
- Seeding is declarative and reusable for project-management domain
- Tests run in parallel without interference (`pytest -n auto`)
- Integration tests run against PostgreSQL with per-worker schema isolation
- Auth is mockable/bypassable in all test layers

---

## Key Findings from Code Review

### Current State (What Exists)

| Component | Location | Status |
|-----------|----------|--------|
| Root `conftest.py` | `conftest.py` | Imports 30+ rcm entities, uses `SeedDb` with rcm `TableName` |
| `seed_db.py` | `tests/seed_db.py` | Has its own `TableName` enum with 30+ rcm entries, wraps `BaseSeeder` |
| `EntityFactory` | `src/shared/test_utils/entity_factories.py` | 30+ `create_*` methods for rcm entities |
| `BaseSeeder` | `src/shared/test_utils/seeders/base_seeder.py` | `ENTITY_ORDER` with 38 rcm entities in dependency order |
| `SeedConfig` | `src/shared/test_utils/seeders/seed_config.py` | Generic — no rcm refs (keep as-is) |
| `fixed_data.py` | `src/dev_tools/db/fixed_data.py` | Packhouse-specific deterministic data (FIXED_TENANT, FIXED_COMMODITIES, etc.) |
| `verify_seed.py` | `src/dev_tools/db/verify_seed.py` | Imports 25+ rcm entities for count verification |
| `pytest.ini` | `pytest.ini` | Generic — no domain refs (keep as-is) |

### What's Already Generic (Keep As-Is)
- `SeedConfig`, `DevSeedConfig`, `IntegrationSeedConfig` in `seed_config.py` — fully generic
- `conftest.py` fixture patterns (shared_db, isolated_db, class_scoped) — pattern is generic, only imports need changing
- Integration `conftest.py` fixture patterns (per-worker schema, TestClient) — pattern is generic
- `pytest.ini` — no domain refs
- `DateTimeComparator` utility in root conftest

### What Needs Full Replacement
- `tests/seed_db.py` `TableName` enum → project-management entities
- `EntityFactory` methods → project-management entity creators
- `BaseSeeder.ENTITY_ORDER` → project-management dependency graph
- `fixed_data.py` → project-management deterministic data
- Root `conftest.py` entity imports → project-management entities
- Integration `conftest.py` entity imports → project-management entities
- `verify_seed.py` → project-management entity counts
- All test files under `tests/rcm/` → replaced by `tests/project_mgmt/`
- All test files under `tests/integration/rcm/` → replaced by `tests/integration/project_mgmt/`

---

## Step 1: New `fixed_data.py` — Deterministic Test Data

### File: `src/dev_tools/db/fixed_data.py`

**Replace all rcm data with project-management domain data.**

```python
# ============================================================================
# ORGANIZATION (same structure, rename Packhouse → reference names)
# ============================================================================

FIXED_TENANT = {
    'id': 'tenant-test-001',
    'name': 'Acme Corp',
}

FIXED_BUS = [
    {
        'id': 'bu-test-001',
        'tenant_id': 'tenant-test-001',
        'name': 'Engineering',
    },
    {
        'id': 'bu-test-002',
        'tenant_id': 'tenant-test-001',
        'name': 'Marketing',
    },
]

# ============================================================================
# LABELS (L1 — simple CRUD)
# ============================================================================

FIXED_LABELS = [
    {
        'id': 'lbl-test-001',
        'tenant_id': 'tenant-test-001',
        'bu_id': 'bu-test-001',
        'name': 'bug',
        'color': '#FF0000',
        'description': 'Something is broken',
    },
    {
        'id': 'lbl-test-002',
        'tenant_id': 'tenant-test-001',
        'bu_id': 'bu-test-001',
        'name': 'feature',
        'color': '#00FF00',
        'description': 'New functionality',
    },
    {
        'id': 'lbl-test-003',
        'tenant_id': 'tenant-test-001',
        'bu_id': 'bu-test-001',
        'name': 'docs',
        'color': '#0000FF',
        'description': 'Documentation changes',
    },
]

# ============================================================================
# PRIORITIES (L1 — CRUD + enum/ordering)
# ============================================================================

FIXED_PRIORITIES = [
    {
        'id': 'pri-test-001',
        'tenant_id': 'tenant-test-001',
        'bu_id': 'bu-test-001',
        'name': 'Critical',
        'level': 1,
        'color': '#FF0000',
    },
    {
        'id': 'pri-test-002',
        'tenant_id': 'tenant-test-001',
        'bu_id': 'bu-test-001',
        'name': 'High',
        'level': 2,
        'color': '#FF8800',
    },
    {
        'id': 'pri-test-003',
        'tenant_id': 'tenant-test-001',
        'bu_id': 'bu-test-001',
        'name': 'Medium',
        'level': 3,
        'color': '#FFFF00',
    },
    {
        'id': 'pri-test-004',
        'tenant_id': 'tenant-test-001',
        'bu_id': 'bu-test-001',
        'name': 'Low',
        'level': 4,
        'color': '#00FF00',
    },
]

# ============================================================================
# PROJECTS (L2 — parent entity)
# ============================================================================

FIXED_PROJECTS = [
    {
        'id': 'proj-test-001',
        'tenant_id': 'tenant-test-001',
        'bu_id': 'bu-test-001',
        'name': 'Backend Rewrite',
        'description': 'Rewrite the backend in FastAPI',
        'status': 'active',
    },
    {
        'id': 'proj-test-002',
        'tenant_id': 'tenant-test-001',
        'bu_id': 'bu-test-001',
        'name': 'Mobile App',
        'description': 'Build the mobile application',
        'status': 'active',
    },
]

# ============================================================================
# TASKS (L2 — child entity, orchestration)
# ============================================================================

FIXED_TASKS = [
    {
        'id': 'task-test-001',
        'tenant_id': 'tenant-test-001',
        'bu_id': 'bu-test-001',
        'project_id': 'proj-test-001',
        'title': 'Set up CI/CD pipeline',
        'description': 'Configure GitHub Actions',
        'status': 'open',
        'priority_id': 'pri-test-002',
    },
    {
        'id': 'task-test-002',
        'tenant_id': 'tenant-test-001',
        'bu_id': 'bu-test-001',
        'project_id': 'proj-test-001',
        'title': 'Implement auth middleware',
        'description': 'Add JWT-based auth',
        'status': 'in_progress',
        'priority_id': 'pri-test-001',
    },
    {
        'id': 'task-test-003',
        'tenant_id': 'tenant-test-001',
        'bu_id': 'bu-test-001',
        'project_id': 'proj-test-002',
        'title': 'Design login screen',
        'description': 'Create the login UI',
        'status': 'open',
        'priority_id': 'pri-test-003',
    },
]

# ============================================================================
# AGENT RUNS (L4 — AI lifecycle tracking)
# ============================================================================

FIXED_AGENT_RUNS = [
    {
        'id': 'ar-test-001',
        'tenant_id': 'tenant-test-001',
        'bu_id': 'bu-test-001',
        'agent_type': 'task_triage',
        'status': 'completed',
        'input_params': {'task_id': 'task-test-001'},
    },
]
```

**Exact fields depend on Phase 3 entity definitions** — adjust field names to match actual entity schemas. The pattern (deterministic IDs with known values for assertions) stays the same.

---

## Step 2: New `EntityFactory` Methods

### File: `src/shared/test_utils/entity_factories.py`

**Replace all rcm entity imports and factory methods with project-management equivalents.**

### Imports to replace
```python
# Remove all rcm.* imports

# Add project_mgmt imports:
from project_mgmt.entities.label_entity import LabelEntity
from project_mgmt.entities.priority_entity import PriorityEntity
from project_mgmt.entities.project_entity import ProjectEntity
from project_mgmt.entities.task_entity import TaskEntity
# Keep organization imports (TenantEntity, BuEntity)
# Add AgentRun import from wherever Phase 6 places it
```

### Factory methods to add

Each follows the existing pattern: `_create_entity(ModelClass, defaults_dict, overrides, auto_commit, add_to_session)`.

```python
def create_label(self, overrides=None, auto_commit=False, add_to_session=True):
    data = {
        'tenant_id': 'tenant-test-001',
        'bu_id': 'bu-test-001',
        'name': f'Label-{self._next_id("label")}',
        'color': '#FF0000',
    }
    return self._create_entity(LabelEntity, data, overrides, auto_commit, add_to_session)

def create_priority(self, overrides=None, auto_commit=False, add_to_session=True):
    data = {
        'tenant_id': 'tenant-test-001',
        'bu_id': 'bu-test-001',
        'name': f'Priority-{self._next_id("priority")}',
        'level': self._next_id("priority_level"),
        'color': '#FF8800',
    }
    return self._create_entity(PriorityEntity, data, overrides, auto_commit, add_to_session)

def create_project(self, overrides=None, auto_commit=False, add_to_session=True):
    data = {
        'tenant_id': 'tenant-test-001',
        'bu_id': 'bu-test-001',
        'name': f'Project-{self._next_id("project")}',
        'description': 'Auto-generated test project',
        'status': 'active',
    }
    return self._create_entity(ProjectEntity, data, overrides, auto_commit, add_to_session)

def create_task(self, overrides=None, auto_commit=False, add_to_session=True):
    data = {
        'tenant_id': 'tenant-test-001',
        'bu_id': 'bu-test-001',
        'project_id': None,  # Must be provided via overrides or seeder
        'title': f'Task-{self._next_id("task")}',
        'description': 'Auto-generated test task',
        'status': 'open',
        'priority_id': None,
    }
    return self._create_entity(TaskEntity, data, overrides, auto_commit, add_to_session)

def create_agent_run(self, overrides=None, auto_commit=False, add_to_session=True):
    data = {
        'tenant_id': 'tenant-test-001',
        'bu_id': 'bu-test-001',
        'agent_type': 'task_triage',
        'status': 'pending',
        'input_params': {},
    }
    return self._create_entity(AgentRunEntity, data, overrides, auto_commit, add_to_session)
```

**Keep**: `create_tenant()`, `create_bu()`, and the `_create_entity()` helper — these are generic.

**Remove**: All `create_commodity_master()`, `create_lot()`, `create_bin()`, etc.

---

## Step 3: New `BaseSeeder.ENTITY_ORDER`

### File: `src/shared/test_utils/seeders/base_seeder.py`

**Replace the 38-entry rcm dependency graph with project-management equivalents.**

```python
ENTITY_ORDER = [
    ('tenant', []),
    ('bu', ['tenant']),
    ('label', ['bu']),
    ('priority', ['bu']),
    ('project', ['bu']),
    ('task', ['project', 'priority']),
    ('agent_run', ['bu']),
    # ProjectSummary is a read-model (view/aggregation), not seeded
]
```

**Also replace**: All `_seed_<entity>()` methods with project-management equivalents. Each method follows the same pattern:
1. Seed fixed data (from `fixed_data.py`) if `config.include_fixed`
2. Generate random data using `EntityFactory` for `config.get_count(entity_type)` items
3. Append to `self._data[entity_type]`
4. Commit

**Remove**: All rcm-specific seed methods (`_seed_commodity_master`, `_seed_lot`, `_seed_bin`, etc.) and their rcm enum imports.

---

## Step 4: New `tests/seed_db.py`

### File: `tests/seed_db.py`

**Replace `TableName` enum and `SeedConfig` counts with project-management entities.**

```python
class TableName(str, Enum):
    """Enum for table names used in seeding configuration."""
    # Organization (always seeded first)
    TENANT = 'tenant'
    BU = 'bu'
    # Project management domain
    LABEL = 'label'
    PRIORITY = 'priority'
    PROJECT = 'project'
    TASK = 'task'
    # AI agent lifecycle
    AGENT_RUN = 'agent_run'

    @classmethod
    def get_all(cls) -> List['TableName']:
        return list(cls)
```

**SeedConfig defaults**:
```python
class SeedConfig:
    def __init__(
        self,
        custom_engine=None,
        tables_to_populate=None,
        tenant_count: int = 3,
        bu_count_per_tenant: int = 2,
        label_count: int = 5,
        priority_count: int = 4,
        project_count: int = 3,
        task_count: int = 5,       # per project
        agent_run_count: int = 2,
    ):
        ...
```

The rest of the `SeedDb` class stays structurally identical — it's a thin wrapper around `BaseSeeder`.

---

## Step 5: Root `conftest.py` Updates

### File: `conftest.py`

### 5a. Replace entity imports

**Remove** (lines 115-153):
```python
# Remove ALL rcm.* and organization.* entity imports
```

**Add**:
```python
# Organization entities
import organization.entities.tenant_entity  # noqa
import organization.entities.bu_entity  # noqa

# Project management entities
import project_mgmt.entities.label_entity  # noqa
import project_mgmt.entities.priority_entity  # noqa
import project_mgmt.entities.project_entity  # noqa
import project_mgmt.entities.task_entity  # noqa
# AgentRun entity (location TBD by Phase 6, likely project_mgmt.entities or common)
```

### 5b. Update SeedDb import
No change — `tests/seed_db.py` is still `SeedDb` with the same interface.

### 5c. Keep all fixture patterns unchanged
The fixtures (`_shared_db_resources`, `shared_db_session`, `class_scoped_isolated_db_session`, `function_scoped_isolated_db_session`, `_get_seed_config_from_marker`, `DateTimeComparator`) are **fully generic** and need no changes beyond the entity imports at the top of the file.

### 5d. Update auto-markers
```python
def pytest_collection_modifyitems(config, items):
    for item in items:
        if 'repositories' in str(item.fspath) or 'services' in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif 'controllers' in str(item.fspath):
            item.add_marker(pytest.mark.integration)
```
No change needed — path-based markers are generic.

---

## Step 6: New Test Files — Repository Layer (SQLite)

### Directory: `tests/project_mgmt/`

Structure:
```
tests/project_mgmt/
    __init__.py
    labels/
        __init__.py
        repositories/
            __init__.py
            test_label_repository.py
        services/
            __init__.py
            test_label_service.py
        controllers/
            __init__.py
            test_label_controller.py
    priorities/
        __init__.py
        repositories/ services/ controllers/  (same structure)
    projects/
        __init__.py
        repositories/ services/ controllers/
    tasks/
        __init__.py
        repositories/ services/ controllers/
```

### 6a. Repository Test Pattern: `test_label_repository.py`

**Wiring tests** (mocked Session — no DB):
```python
class TestLabelRepositoryWiring:
    def test_inherits_from_base_repository(self):
        assert issubclass(LabelRepository, BaseRepository)

    def test_entity_class_configured(self):
        assert LabelRepository._entity_class == LabelEntity

    def test_default_sort_field_configured(self):
        assert LabelRepository._default_sort_field == 'name'

    def test_filter_specs_defined(self):
        mock_session = Mock(spec=Session)
        repo = LabelRepository(mock_session)
        specs = repo._get_filter_specs()
        assert isinstance(specs, list)
        assert all(isinstance(s, FilterSpec) for s in specs)
        spec_names = {s.field_name for s in specs}
        assert {'search', 'statuses'}.issubset(spec_names)

    def test_filter_specs_have_correct_types(self):
        # Verify ilike for search, in for statuses, etc.
        ...
```

**Integration tests** (isolated SQLite DB — real queries):
```python
SEED_CONFIG = SeedDb.SeedConfig(
    tables_to_populate=[TableName.TENANT, TableName.BU],
    tenant_count=1, bu_count_per_tenant=1, label_count=0,
)

@pytest.mark.seed_config(SEED_CONFIG)
class TestLabelRepositoryIntegration:
    @pytest.fixture(scope='class')
    def class_db_resources(self, class_scoped_isolated_db_session):
        return class_scoped_isolated_db_session

    @pytest.fixture(scope='class')
    def db_session(self, class_db_resources):
        session, _ = class_db_resources
        return session

    @pytest.fixture(scope='class')
    def seeded_data(self, class_db_resources):
        _, data = class_db_resources
        return data

    def test_create_and_retrieve_label(self, db_session, seeded_data):
        tenant = seeded_data[TableName.TENANT][0]
        bu = seeded_data[TableName.BU][0]
        repo = LabelRepository(db_session)
        label = LabelEntity(
            tenant_id=tenant.id, bu_id=bu.id,
            name='test-label', color='#FF0000',
        )
        created = repo.create(label)
        db_session.commit()
        fetched = repo.get_by_id(tenant.id, bu.id, created.id)
        assert fetched.name == 'test-label'
```

### 6b. Repository Test Pattern: `test_task_repository.py`

Same wiring + integration structure. Task-specific additions:
- Filter by `project_id` (exact match)
- Filter by `status` (in-list)
- Filter by `priority_id` (exact match)
- Filter by `title` (ilike/search)
- Sort by `created_at`, `title`

```python
class TestTaskRepositoryWiring:
    def test_filter_specs_include_project_and_status(self):
        mock_session = Mock(spec=Session)
        repo = TaskRepository(mock_session)
        specs = repo._get_filter_specs()
        spec_names = {s.field_name for s in specs}
        assert {'project_id', 'statuses', 'priority_id', 'search'}.issubset(spec_names)
```

---

## Step 7: New Test Files — Service Layer (Mocked)

### 7a. Service Test Pattern: `test_label_service.py`

```python
@pytest.fixture
def mock_session():
    return create_autospec(Session, instance=True, spec_set=True)

@pytest.fixture
def mock_label_repository():
    return create_autospec(LabelRepository, instance=True, spec_set=True)

@pytest.fixture
def label_service(mock_session, mock_label_repository):
    service = LabelService(mock_session)
    service._repository = mock_label_repository
    return service

@pytest.fixture
def mock_label_entity():
    entity = LabelEntity(
        tenant_id='tenant_1', bu_id='bu_1',
        name='Test Label', color='#FF0000',
    )
    entity.id = 'lbl_test123'
    entity.created_at = datetime.now(timezone.utc)
    entity.updated_at = datetime.now(timezone.utc)
    return entity

class TestLabelServiceListEntities:
    def test_list_entities_returns_schemas_and_count(
        self, label_service, mock_label_repository, mock_label_entity
    ):
        mock_label_repository.list_with_filters.return_value = [mock_label_entity]
        mock_label_repository.count_with_filters.return_value = 1

        list_request = ListLabelsRequestSchema(
            tenant_id='tenant_1', bu_id='bu_1',
            limit=20, offset=0,
        )

        schemas, count = label_service.list_entities(list_request)

        assert count == 1
        assert len(schemas) == 1
        assert isinstance(schemas[0], LabelSchema)
        assert schemas[0].name == 'Test Label'

class TestLabelServiceCreateEntity:
    def test_create_entity_calls_repository(self, label_service, mock_label_repository, mock_label_entity):
        mock_label_repository.create.return_value = mock_label_entity
        # ... test create flow
```

### 7b. Service Test Pattern: `test_task_service.py`

Task service tests must cover **orchestration** — the key differentiator from simple CRUD:

```python
class TestTaskServiceStatusTransition:
    """Test status transitions that involve service-to-service orchestration."""

    def test_transition_to_completed_updates_project_summary(self, ...):
        # Verify that completing a task triggers project summary recalculation
        ...

    def test_cannot_transition_from_closed_to_open(self, ...):
        # Verify business rule enforcement
        ...

class TestTaskServiceCreateEntity:
    def test_create_task_validates_project_exists(self, ...):
        # Verify cross-service validation
        ...
```

---

## Step 8: New Test Files — Controller Layer (Mocked Service)

### 8a. Controller Test Pattern: `test_label_controller.py`

```python
@pytest.fixture
def mock_label_service():
    return create_autospec(LabelService, instance=True, spec_set=True)

@pytest.fixture
def override_dependencies(mock_label_service):
    def _get_mock_service():
        yield mock_label_service
    app.dependency_overrides[_get_label_service] = _get_mock_service
    app.dependency_overrides[_get_write_label_service] = _get_mock_service
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def test_client(override_dependencies):
    return TestClient(app)

BASE_URL = '/tenants/tenant_1/bus/bu_1/labels'

class TestListLabelsEndpoint:
    def test_list_labels_success_default_pagination(
        self, test_client, mock_label_service, mock_label_schema
    ):
        mock_label_service.list_entities.return_value = ([mock_label_schema], 1)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
        assert len(data['labels']) == 1

    def test_list_labels_with_search_filter(self, ...):
        ...

    def test_list_labels_empty_result(self, ...):
        ...

class TestCreateLabelEndpoint:
    def test_create_label_success(self, test_client, mock_label_service, mock_label_schema):
        mock_label_service.create_entity.return_value = mock_label_schema
        response = test_client.post(BASE_URL, json={
            'name': 'new-label', 'color': '#00FF00',
        })
        assert response.status_code == 201

    def test_create_label_missing_required_field(self, test_client, ...):
        response = test_client.post(BASE_URL, json={'color': '#00FF00'})
        assert response.status_code == 422

class TestGetLabelEndpoint:
    ...

class TestUpdateLabelEndpoint:
    ...

class TestDeleteLabelEndpoint:
    ...

class TestBulkCreateLabelsEndpoint:
    ...
```

### 8b. Controller Test Pattern: `test_task_controller.py`

Same structure as label, plus:
- Test task-specific filters (project_id, status, priority_id)
- Test orchestration endpoints (e.g., PATCH status transition)
- Test parent-child URL pattern: `/tenants/{tid}/bus/{bid}/projects/{pid}/tasks` (if tasks are nested under projects)

---

## Step 9: Auth Mocking in Tests

### How auth bypass works

Phase 4 introduces a dependency-based auth chain. In tests:

**Unit tests (service/repository)**: No auth involved — services are instantiated directly with mocked deps.

**Controller tests**: Override auth dependencies in `app.dependency_overrides`:
```python
from shared.auth.dependencies import is_valid_user, get_valid_user

@pytest.fixture
def override_auth():
    """Bypass auth for controller tests."""
    def _mock_is_valid_user():
        return AuthContext(
            principal=Principal(id='test-user', email='test@example.com'),
        )

    def _mock_get_valid_user(tenant_id: str, bu_id: str):
        return AuthContext(
            principal=Principal(id='test-user', email='test@example.com'),
            actor=Actor(app_user_id='test-user', roles=['admin']),
            subject=Subject(tenant_id=tenant_id, bu_id=bu_id),
        )

    app.dependency_overrides[is_valid_user] = _mock_is_valid_user
    app.dependency_overrides[get_valid_user] = _mock_get_valid_user
    yield
    app.dependency_overrides.clear()
```

**Integration tests**: Use config-driven bypass (`AUTH_ENABLED=false`) set in integration conftest:
```python
os.environ['AUTH_ENABLED'] = 'false'
```

**Place auth override fixtures** in:
- `tests/conftest.py` (for controller tests that need it)
- `tests/integration/conftest.py` (environment variable approach)

---

## Step 10: Integration Test Updates

### 10a. Integration `conftest.py`

### File: `tests/integration/conftest.py`

**Replace entity imports**:
```python
# Remove:
import rcm.common.entities  # noqa
import rcm.inventory.entities  # noqa
# etc.

# Add:
import organization.entities  # noqa
import project_mgmt.entities  # noqa
```

**Keep everything else** — the fixture patterns (per-worker schema, TestClient, seeded_data) are generic.

### 10b. New `IntegrationTestSeeder` Counts

### File: `tests/integration/fixtures/integration_seed.py`

```python
counts = {
    'tenant': 1,
    'bu': 1,
    'label': 3,
    'priority': 4,
    'project': 2,
    'task': 3,        # spread across projects
    'agent_run': 1,
}
```

**Remove**: All rcm entity counts and rcm-specific seed fixtures.

**Remove files**:
- `tests/integration/fixtures/lot_planner_seed.py`
- `tests/integration/fixtures/scheduler_seed.py`
- `tests/integration/fixtures/inventory_assessment_seed.py`
- `tests/integration/fixtures/worker_availability_forecast_seed.py`
- `tests/integration/fixtures/resource_availability_assessment_seed.py`
- `tests/integration/fixtures/machine_downtime_forecast_seed.py`
- `tests/integration/fixtures/line_layout_optimization_seed.py`

Keep `helpers.py` if it has generic utilities.

### 10c. New Integration Test: `tests/integration/project_mgmt/test_label_controller.py`

```python
pytestmark = pytest.mark.integration

class TestLabelControllerIntegration:
    def test_list_labels_returns_seeded_data(
        self, test_client, test_tenant_id, test_bu_id, seeded_data
    ):
        response = test_client.get(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/labels'
        )
        assert response.status_code == 200
        data = response.json()
        assert data['total'] >= 1

    def test_create_and_get_label(
        self, test_client, test_tenant_id, test_bu_id
    ):
        # Create
        response = test_client.post(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/labels',
            json={'name': 'integration-test-label', 'color': '#AABBCC'},
        )
        assert response.status_code == 201
        label_id = response.json()['id']

        # Get
        response = test_client.get(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/labels/{label_id}'
        )
        assert response.status_code == 200
        assert response.json()['name'] == 'integration-test-label'

    def test_update_label(self, ...):
        ...

    def test_delete_label(self, ...):
        ...

    def test_list_labels_with_search_filter(self, ...):
        ...

    def test_list_labels_with_pagination(self, ...):
        ...
```

### 10d. New Integration Test: `tests/integration/project_mgmt/test_task_controller.py`

Task-specific integration tests covering:
- Create task within a project
- List tasks filtered by project_id
- Status transition (PATCH)
- Filter by priority, status
- Verify parent-child relationship integrity

---

## Step 11: `verify_seed.py` Updates

### File: `src/dev_tools/db/verify_seed.py`

**Replace all entity imports and counts**:

```python
from project_mgmt.entities.label_entity import LabelEntity
from project_mgmt.entities.priority_entity import PriorityEntity
from project_mgmt.entities.project_entity import ProjectEntity
from project_mgmt.entities.task_entity import TaskEntity

counts = {
    'Tenants': session.query(TenantEntity).count(),
    'Business Units': session.query(BuEntity).count(),
    'Labels': session.query(LabelEntity).count(),
    'Priorities': session.query(PriorityEntity).count(),
    'Projects': session.query(ProjectEntity).count(),
    'Tasks': session.query(TaskEntity).count(),
}
```

---

## Step 12: Per-Worker Schema Isolation Verification

### What to verify

The existing pattern in `tests/integration/conftest.py` (lines 67-68) already handles this:
```python
_worker_id = os.environ.get('PYTEST_XDIST_WORKER', 'gw0')
TEST_SCHEMA = f'integration_test_{_worker_id}'
```

**No code changes needed** — this is generic infrastructure. But we need to **verify** it works:

### Verification test (add to integration tests)
```python
class TestWorkerIsolation:
    """Verify per-worker schema isolation works correctly."""

    def test_schema_name_includes_worker_id(self):
        """Verify test schema is named with worker ID."""
        import os
        worker_id = os.environ.get('PYTEST_XDIST_WORKER', 'gw0')
        expected = f'integration_test_{worker_id}'
        # This is verified by the fact that integration tests pass with -n auto
        # But we can also check the schema directly:
        assert 'integration_test_' in expected

    def test_seeded_data_is_accessible(self, test_client, test_tenant_id, test_bu_id):
        """Verify seeded data is accessible in this worker's schema."""
        response = test_client.get(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/labels'
        )
        assert response.status_code == 200
```

### Run command for verification
```bash
# Run integration tests with 2 workers to verify isolation
pytest tests/integration/ -n 2 --dist=loadfile -m integration -v
```

---

## Step 13: Parallel Test Execution Verification

### What to verify

`pytest.ini` already configures `-n auto --dist=loadfile`. The key requirement is that tests don't interfere with each other.

### Potential interference points and mitigations

| Risk | Mitigation | Status |
|------|-----------|--------|
| Shared DB mutation | Read-only tests use `shared_db_session` (auto-rollback). Mutation tests use `class_scoped_isolated_db_session` (separate engine) | Already handled by existing fixtures |
| Global `db_session_manager` state | Session-scoped setup configures once per worker. Isolated fixtures save/restore engine | Already handled |
| `app.dependency_overrides` pollution | Each controller test fixture clears overrides in teardown | Pattern already established |
| Integration test schema collisions | Per-worker schema naming (`integration_test_gw0`, etc.) | Already handled |

### Verification
```bash
# Run unit tests in parallel
pytest tests/project_mgmt/ -n auto --dist=loadfile -v

# Run all tests excluding integration
pytest tests/ -n auto --dist=loadfile -m "not integration" -v

# Run integration tests in parallel
pytest tests/integration/ -n 2 -m integration -v
```

---

## Step 14: Agent Test Patterns (Phase 6 Preparation)

### Location: `tests/project_mgmt/agents/` (or `tests/agents/`)

Agent tests cover the lifecycle without live LLM calls. Pattern:

```python
class TestTaskTriageAgent:
    """Test TaskTriageAgent lifecycle with mocked LLM."""

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM client that returns structured output."""
        client = create_autospec(LLMClient, instance=True)
        client.invoke.return_value = TriageResult(
            priority='high',
            labels=['bug', 'urgent'],
            reasoning='Task involves production breakage',
        )
        return client

    @pytest.fixture
    def mock_prompt_manager(self):
        """Mock prompt manager returning local prompt."""
        pm = create_autospec(PromptManager, instance=True)
        pm.get_prompt.return_value = "Triage this task: {task_description}"
        return pm

    # ----- Invocation -----
    def test_agent_invocation_creates_agent_run(
        self, db_session, mock_llm_client, mock_prompt_manager
    ):
        """Test that running the agent creates an AgentRun entity."""
        agent = TaskTriageAgent(
            session=db_session,
            llm_client=mock_llm_client,
            prompt_manager=mock_prompt_manager,
        )
        result = agent.run(task_id='task-test-001', tenant_id='t1', bu_id='b1')

        # Agent run was persisted
        assert result.agent_run_id is not None
        run = db_session.query(AgentRunEntity).get(result.agent_run_id)
        assert run.status == 'completed'
        assert run.agent_type == 'task_triage'

    # ----- Mocked LLM call -----
    def test_agent_calls_llm_with_context(
        self, db_session, mock_llm_client, mock_prompt_manager
    ):
        """Test that agent builds context and calls LLM."""
        agent = TaskTriageAgent(...)
        agent.run(task_id='task-test-001', ...)

        mock_llm_client.invoke.assert_called_once()
        call_args = mock_llm_client.invoke.call_args
        assert 'task_description' in str(call_args)

    # ----- Post-validation -----
    def test_agent_validates_llm_output(
        self, db_session, mock_llm_client, mock_prompt_manager
    ):
        """Test that invalid LLM output is caught by post-validation."""
        mock_llm_client.invoke.return_value = TriageResult(
            priority='invalid_priority',  # Should fail validation
            labels=[], reasoning='',
        )
        agent = TaskTriageAgent(...)
        result = agent.run(...)
        assert result.status == 'failed'  # or raises ValidationError

    # ----- Post-enrichment -----
    def test_agent_enriches_result_with_metadata(
        self, db_session, mock_llm_client, mock_prompt_manager
    ):
        """Test that agent enriches output with additional data."""
        agent = TaskTriageAgent(...)
        result = agent.run(...)
        # Enrichment adds timestamp, cost, model info
        assert result.metadata.get('model') is not None
        assert result.metadata.get('latency_ms') is not None

    # ----- Persistence -----
    def test_agent_persists_results(
        self, db_session, mock_llm_client, mock_prompt_manager
    ):
        """Test that agent results are persisted to the database."""
        agent = TaskTriageAgent(...)
        result = agent.run(task_id='task-test-001', ...)

        # Check task was updated with triage result
        task = db_session.query(TaskEntity).get('task-test-001')
        assert task.priority_id is not None  # was set by triage

    # ----- Lifecycle state transitions -----
    def test_agent_run_transitions_through_states(
        self, db_session, mock_llm_client, mock_prompt_manager
    ):
        """Test PENDING -> RUNNING -> COMPLETED lifecycle."""
        # This can be verified by checking agent_run status at each stage
        # or by using a callback/hook pattern
        ...

    # ----- Error handling -----
    def test_agent_handles_llm_error_gracefully(
        self, db_session, mock_llm_client, mock_prompt_manager
    ):
        """Test that LLM errors result in FAILED agent run."""
        mock_llm_client.invoke.side_effect = Exception("LLM timeout")
        agent = TaskTriageAgent(...)
        result = agent.run(...)
        assert result.status == 'failed'
        run = db_session.query(AgentRunEntity).get(result.agent_run_id)
        assert run.status == 'failed'
        assert 'LLM timeout' in run.error_message
```

**Important**: These tests use `@pytest.mark.unit` (mocked LLM) by default. A separate `@pytest.mark.live_llm` test can verify real LLM invocation but is excluded from `precommit-tests`.

---

## Step 15: File Deletion Checklist

### Remove entirely
```
tests/rcm/              (entire directory — all rcm unit tests)
tests/organization/            (if exists — replaced by integration tests)
tests/integration/rcm/   (entire directory — all rcm integration tests)
tests/integration/fixtures/inventory_assessment_seed.py
tests/integration/fixtures/scheduler_seed.py
tests/integration/fixtures/worker_availability_forecast_seed.py
tests/integration/fixtures/resource_availability_assessment_seed.py
tests/integration/fixtures/machine_downtime_forecast_seed.py
tests/integration/fixtures/lot_planner_seed.py
tests/integration/fixtures/line_layout_optimization_seed.py
```

### Keep (may need minor updates)
```
tests/common/test_base_service.py        (tests generic base — keep, verify still passes)
tests/common/test_base_repository.py     (tests generic base — keep, verify still passes)
tests/common/test_crud_engine.py         (tests generic CRUD — keep, verify still passes)
tests/common/test_base_controller_utils.py (tests generic utils — keep, verify still passes)
tests/integration/fixtures/helpers.py    (keep if generic)
tests/integration/conftest.py            (update imports only)
tests/integration/organization/          (keep — Tenant/BU integration tests)
```

---

## Execution Order

```
1. Step 1: New fixed_data.py
   → verify: imports work, data structures are valid

2. Step 2: New EntityFactory methods
   → verify: factory.create_label(), etc. work in isolation

3. Step 3: New BaseSeeder.ENTITY_ORDER
   → verify: seeder can seed all entities in correct dependency order

4. Step 4: New tests/seed_db.py
   → verify: SeedDb with new TableName works

5. Step 5: Root conftest.py updates
   → verify: `pytest --collect-only` succeeds (no import errors)

6. Steps 6-8: New test files (repo/service/controller)
   → verify: `pytest tests/project_mgmt/ -v` passes

7. Step 9: Auth mocking fixtures
   → verify: controller tests pass with auth overrides

8. Steps 10-11: Integration test updates
   → verify: `pytest tests/integration/ -m integration -v` passes

9. Step 12-13: Parallel execution verification
   → verify: `pytest tests/ -n auto` passes

10. Step 14: Agent test stubs (Phase 6 prep)
    → verify: test structure is in place, passes with skip markers

11. Step 15: Delete rcm test files
    → verify: `precommit-tests` passes with zero rcm references

Gate: `precommit-tests` passes (unit + integration + live_llm)
```

---

## Entities Requiring Tests at Each Layer

| Entity | Repository | Service | Controller | Integration | Notes |
|--------|-----------|---------|-----------|-------------|-------|
| Label | Yes | Yes | Yes | Yes | L1 — simple CRUD, demonstrates generic patterns |
| Priority | Yes | Yes | Yes | Yes | L1 — ordering, enum fields |
| Project | Yes | Yes | Yes | Yes | L2 — parent entity |
| Task | Yes | Yes | Yes | Yes | L2 — orchestration, parent-child, status transitions |
| ProjectSummary | No (read model) | Yes (assembly) | Yes | Yes | L3 — multi-repo aggregation |
| AgentRun | Yes | Yes | Yes | Yes | L4 — lifecycle tracking (Phase 6) |

**Minimum for Phase 5**: Label + Task at all 4 layers. Priority + Project can have lighter coverage (wiring tests + one integration test each). ProjectSummary and AgentRun test patterns are scaffolded but fully implemented in Phase 6.
