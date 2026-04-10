# Phase 5a: Basic Test Infrastructure (No Auth/Agent Dependency)

## Execution Context
**Depends on**: Phase 3 (domain entities exist)
**Blocks**: Phase 5b
**Parallel with**: Phase 4 (auth), Phase 6a (agent infra)

## Goal
Overhaul test infrastructure for project-management domain: seed data, entity factories, base seeder, conftest patterns. This phase handles everything that does NOT depend on auth (Phase 4) or agents (Phase 6).

## What Phase 5a Does NOT Do
- Auth mocking/bypass patterns (Phase 5b, after Phase 4)
- AgentRun test patterns (Phase 5b, after Phase 6)
- Packhouse test deletion (Phase 8)

## Pre-Conditions
- Phase 3 DONE: Label, Priority, Project, Task, ProjectSummary, AppUser entities exist
- `precommit-tests` passes

## Post-Conditions (Definition of Done)
- `precommit-tests` passes (both old rcm tests AND new project_mgmt tests)
- New `fixed_data.py` has project_mgmt deterministic test data
- New `EntityFactory` methods for all project_mgmt entities
- New `BaseSeeder.ENTITY_ORDER` for project_mgmt dependency graph
- New `tests/seed_db.py` with project_mgmt TableName enum
- Root `conftest.py` updated with project_mgmt entity imports
- All 4 test layers have examples for Label and Task at minimum
- Tests run in parallel without interference (`pytest -n auto`)

---

## Step 1: New Fixed Data

### File: `src/dev_tools/db/fixed_data.py`

**Add** project_mgmt data alongside existing rcm data (both coexist until Phase 8):

```python
FIXED_TENANT = {'id': 'tenant-test-001', 'name': 'Acme Corp'}
FIXED_BUS = [
    {'id': 'bu-test-001', 'tenant_id': 'tenant-test-001', 'name': 'Engineering'},
    {'id': 'bu-test-002', 'tenant_id': 'tenant-test-001', 'name': 'Marketing'},
]
FIXED_LABELS = [
    {'id': 'lbl-test-001', 'tenant_id': 'tenant-test-001', 'bu_id': 'bu-test-001', 'name': 'bug', 'color': '#FF0000'},
    {'id': 'lbl-test-002', 'tenant_id': 'tenant-test-001', 'bu_id': 'bu-test-001', 'name': 'feature', 'color': '#00FF00'},
    {'id': 'lbl-test-003', 'tenant_id': 'tenant-test-001', 'bu_id': 'bu-test-001', 'name': 'docs', 'color': '#0000FF'},
]
FIXED_PRIORITIES = [
    {'id': 'pri-test-001', ..., 'name': 'Critical', 'level': 1, 'color': '#FF0000'},
    {'id': 'pri-test-002', ..., 'name': 'High', 'level': 2},
    {'id': 'pri-test-003', ..., 'name': 'Medium', 'level': 3},
    {'id': 'pri-test-004', ..., 'name': 'Low', 'level': 4},
]
FIXED_PROJECTS = [
    {'id': 'proj-test-001', ..., 'name': 'Backend Rewrite', 'status': 'active'},
    {'id': 'proj-test-002', ..., 'name': 'Mobile App', 'status': 'active'},
]
FIXED_TASKS = [
    {'id': 'task-test-001', ..., 'project_id': 'proj-test-001', 'title': 'Set up CI/CD', 'status': 'backlog', 'priority_id': 'pri-test-002'},
    {'id': 'task-test-002', ..., 'project_id': 'proj-test-001', 'title': 'Implement auth', 'status': 'in_progress', 'priority_id': 'pri-test-001'},
    {'id': 'task-test-003', ..., 'project_id': 'proj-test-002', 'title': 'Design login', 'status': 'backlog', 'priority_id': 'pri-test-003'},
]
```

Note: Task status uses Phase 3 `TaskStatus` enum values (backlog, in_progress, etc.), NOT 'open'.

---

## Step 2: New EntityFactory Methods

### File: `src/shared/test_utils/entity_factories.py`

**Add** project_mgmt factory methods alongside existing rcm ones:
- `create_label(overrides=None)` — default tenant/BU, auto-incrementing name
- `create_priority(overrides=None)` — default tenant/BU, auto-incrementing level
- `create_project(overrides=None)` — default tenant/BU, status='active'
- `create_task(overrides=None)` — requires project_id via overrides
- `create_app_user(overrides=None)` — email, name, auth_provider_id

**Keep** all existing rcm factory methods until Phase 8.

---

## Step 3: New BaseSeeder Entity Order

### File: `src/shared/test_utils/seeders/base_seeder.py`

**Add** project_mgmt entities to `ENTITY_ORDER` (after existing rcm entries):
```python
('label', ['bu']),
('priority', ['bu']),
('project', ['bu']),
('task', ['project', 'priority']),
('app_user', []),
('app_user_tenant_role', ['app_user', 'tenant']),
```

**Add** corresponding `_seed_label()`, `_seed_priority()`, `_seed_project()`, `_seed_task()` methods.

**Keep** existing rcm seed methods until Phase 8.

---

## Step 4: New seed_db.py TableName Entries

### File: `tests/seed_db.py`

**Add** project_mgmt entries to the test-specific `TableName` enum:
```python
LABEL = 'label'
PRIORITY = 'priority'
PROJECT = 'project'
TASK = 'task'
APP_USER = 'app_user'
APP_USER_TENANT_ROLE = 'app_user_tenant_role'
```

**Add** corresponding count parameters to `SeedConfig`.

**Keep** existing rcm entries until Phase 8.

---

## Step 5: Root conftest.py Updates

### File: `conftest.py`

**Add** project_mgmt entity imports (keep rcm imports):
```python
import project_mgmt.label.entities.label_entity  # noqa
import project_mgmt.priority.entities.priority_entity  # noqa
import project_mgmt.project.entities.project_entity  # noqa
import project_mgmt.task.entities.task_entity  # noqa
import organization.entities.app_user_entity  # noqa
import organization.entities.app_user_tenant_role_entity  # noqa
```

All fixture patterns are already generic — no changes needed to shared_db, isolated_db, class_scoped fixtures.

---

## Step 6: New Test Files — Repository Layer

### Pattern: `tests/project_mgmt/label/repositories/test_label_repository.py`

**Wiring tests** (mocked Session):
- test_inherits_from_base_repository
- test_entity_class_configured
- test_default_sort_field_configured
- test_filter_specs_defined (verify names and types)

**Integration tests** (isolated SQLite):
- test_create_with_prefix
- test_list_with_ilike_filter

Same pattern for Priority, Project, Task repositories.

---

## Step 7: New Test Files — Service Layer

### Pattern: `tests/project_mgmt/label/services/test_label_service.py`

**Wiring tests**: inherits BaseService, correct repo/schema/entity class
**Filter extraction**: maps all fields, handles None
**Entity creation**: maps all create fields
**Entity update**: updates provided fields, None changes nothing

Task service gets additional: `TestTaskServiceStatusTransition` (valid/invalid transitions, side effects)

---

## Step 8: New Test Files — Controller Layer

### Pattern: `tests/project_mgmt/label/controllers/test_label_controller.py`

Using `TestClient(app)` with `app.dependency_overrides` for mocked service:
- TestListEndpointWiring: endpoint exists, calls service
- TestGetByIdEndpointWiring: 200, 404
- TestCreateEndpointWiring: 201, 422 (missing required)
- TestUpdateEndpointWiring: 200, 404
- TestDeleteEndpointWiring: 204, 404
- TestBulkCreateEndpointWiring: 201

Task controller gets: test for `POST /{task_id}/status` endpoint

---

## Step 9: New Test Files — Integration Layer

### Pattern: `tests/integration/project_mgmt/test_label_controller.py`

Full CRUD against PostgreSQL with per-worker schema isolation:
- list returns seeded data
- list with filter, pagination
- get by id, 404
- create success, minimal, bulk
- create missing required (422)
- update success, 404
- delete success, 404

---

## Files Summary

### Create (~25 files)
| Directory | Files |
|-----------|-------|
| `tests/project_mgmt/label/` | 3 (repo, service, controller tests) |
| `tests/project_mgmt/priority/` | 3 |
| `tests/project_mgmt/project/` | 3 |
| `tests/project_mgmt/task/` | 3 |
| `tests/project_mgmt/project_summary/` | 2 (service, controller) |
| `tests/integration/project_mgmt/` | 5 |
| `__init__.py` files | ~10 |

### Modify (~5 files)
| File | Change |
|------|--------|
| `src/dev_tools/db/fixed_data.py` | Add project_mgmt fixed data |
| `src/shared/test_utils/entity_factories.py` | Add project_mgmt factory methods |
| `src/shared/test_utils/seeders/base_seeder.py` | Add project_mgmt entity order + seed methods |
| `tests/seed_db.py` | Add project_mgmt TableName entries + SeedConfig counts |
| `conftest.py` | Add project_mgmt entity imports |
