# Phase 3: Example Domain — Project Management + AppUser

## Execution Context
**Depends on**: Phase 2 (generalized base classes with backref)
**Blocks**: Phase 4, Phase 5a, Phase 6a
**Parallel with**: Nothing — last sequential prerequisite

## Goal
Build the project-management domain in `src/project_mgmt/` alongside linkedout code. Create AppUser entities under `src/organization/`. Label and Priority MUST use CRUDRouterFactory. Packhouse stays as reference — NOT removed in this phase.

## Critical Reconciliation Decisions (Baked In)
- **B1**: AppUserEntity + AppUserTenantRoleEntity go in `src/organization/` (NOT Phase 4)
- **B2**: Do NOT touch TenantEntity/BuEntity — backref from TenantBuMixin handles reverse relationships automatically
- **B3**: Label AND Priority use `CRUDRouterFactory` (R3 requirement)
- **I4**: Module name is `project_mgmt` (NOT `project_management`)
- **I5**: Packhouse stays until Phase 8 — both domains coexist
- **I8**: Phase 3 data values are source of truth for all downstream phases

## Pre-Conditions
- Phase 2 DONE: TenantBuMixin uses backref, TableName has only TENANT/BU
- `precommit-tests` passes

## Post-Conditions (Definition of Done)
- `precommit-tests` passes (both old rcm tests AND new project_mgmt tests)
- All 5 example entities have complete MVCS stacks
- Label + Priority use CRUDRouterFactory
- Project + Task use custom controllers with status transition endpoints
- ProjectSummary is a read-model (no DB table)
- AppUserEntity + AppUserTenantRoleEntity exist under `src/organization/`
- API endpoints accessible at `/tenants/{tid}/bus/{bid}/...`
- Zero modifications to TenantEntity or BuEntity files

---

## Module Structure

```
src/project_mgmt/
  __init__.py
  enums.py                             # TaskStatus, ProjectStatus
  label/
    __init__.py
    entities/label_entity.py
    repositories/label_repository.py
    services/label_service.py
    controllers/label_controller.py    # Uses CRUDRouterFactory
    schemas/
      label_schema.py                  # Core Pydantic model
      label_api_schema.py              # Request/response schemas + SortByFields
  priority/                            # Same structure, uses CRUDRouterFactory
  project/                             # Same structure, custom controller
  task/                                # Same structure, custom controller
  project_summary/
    services/project_summary_service.py
    controllers/project_summary_controller.py
    schemas/project_summary_schema.py

src/organization/
  entities/app_user_entity.py
  entities/app_user_tenant_role_entity.py
  repositories/app_user_repository.py
  repositories/app_user_tenant_role_repository.py
  services/app_user_service.py
  services/app_user_tenant_role_service.py
```

---

## Sub-Phase 3a: Scaffold + Enums

Create all `__init__.py` files and directory structure. Create `src/project_mgmt/enums.py`:

```python
from enum import StrEnum

class TaskStatus(StrEnum):
    BACKLOG = 'backlog'
    TODO = 'todo'
    IN_PROGRESS = 'in_progress'
    IN_REVIEW = 'in_review'
    DONE = 'done'
    CANCELLED = 'cancelled'

class ProjectStatus(StrEnum):
    PLANNING = 'planning'
    ACTIVE = 'active'
    ON_HOLD = 'on_hold'
    COMPLETED = 'completed'
    ARCHIVED = 'archived'
```

**Verify**: Module imports work.

---

## Sub-Phase 3b: Label (L1 — CRUDRouterFactory)

### Entity
```python
class LabelEntity(TenantBuMixin, BaseEntity):
    __tablename__ = 'label'
    id_prefix = 'label'
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tasks: Mapped[list['TaskEntity']] = relationship('TaskEntity', back_populates='label')
```

### Repository
```python
class LabelRepository(BaseRepository[LabelEntity, LabelSortByFields]):
    _entity_class = LabelEntity
    _default_sort_field = 'name'
    _entity_name = 'label'
    def _get_filter_specs(self): return [
        FilterSpec('name', 'ilike'),
        FilterSpec('label_ids', 'in', entity_field='id'),
    ]
```

### Service
Standard BaseService subclass. `_entity_id_field = 'label_id'`.

### Controller — CRUDRouterFactory
```python
from common.controllers.crud_router_factory import create_crud_router, CRUDRouterConfig

config = CRUDRouterConfig(
    prefix='/tenants/{tenant_id}/bus/{bu_id}/labels',
    tags=['labels'],
    service_class=LabelService,
    entity_name='label',
    entity_name_plural='labels',
    # ... all schema classes
)
labels_router = create_crud_router(config)
```

### Schemas
- `LabelSchema` with `model_config = ConfigDict(from_attributes=True)`
- `LabelSortByFields(StrEnum)`: NAME, CREATED_AT
- Standard request/response schemas using base schema mixins

### Filter patterns: ilike (name), in (label_ids)

### Tests (3 unit + 1 integration)
Follow existing wiring test pattern: repository wiring, service wiring, controller wiring, integration CRUD.

**Verify**: `precommit-tests` passes

---

## Sub-Phase 3c: Priority (L1 — CRUDRouterFactory)

Same pattern as Label but with:
- `level: Mapped[int]` field for numeric ordering
- Filters: eq (name, level), gte/lte (level range)
- Uses CRUDRouterFactory

**Verify**: `precommit-tests` passes

---

## Sub-Phase 3d: Project (L2 — Custom Controller)

### Entity
```python
class ProjectEntity(TenantBuMixin, BaseEntity):
    __tablename__ = 'project'
    id_prefix = 'project'
    name, description, status (default PLANNING), owner_id, start_date, target_end_date, actual_end_date, tags (JSONB)
    tasks: relationship('TaskEntity', back_populates='project', cascade='all, delete-orphan')
```

### Service — With Orchestration
```python
def update_project_status(self, tenant_id, bu_id, project_id, new_status) -> ProjectSchema:
    # Validate transitions: PLANNING->ACTIVE, ACTIVE->ON_HOLD/COMPLETED, etc.
    # Side effect: COMPLETED sets actual_end_date
```

### Controller — Custom (NOT CRUDRouterFactory)
Standard 6 CRUD endpoints + `POST /{project_id}/status`

### Filters: ilike (name), eq (status, owner_id), in (status_in, project_ids), gte/lte (start_date)

**Verify**: `precommit-tests` passes

---

## Sub-Phase 3e: Task (L2 — Custom Controller + Orchestration)

### Entity
```python
class TaskEntity(TenantBuMixin, BaseEntity):
    __tablename__ = 'task'
    id_prefix = 'task'
    project_id: FK to project.id (CASCADE)
    title, description, status (default BACKLOG)
    label_id: FK to label.id (SET NULL), priority_id: FK to priority.id (SET NULL)
    assignee_id, due_date, completed_at, estimated_hours, actual_hours, sort_order
    project: relationship('ProjectEntity', back_populates='tasks')
    label: relationship('LabelEntity', back_populates='tasks')
    priority: relationship('PriorityEntity', back_populates='tasks')
```

### Service — Non-Trivial Orchestration
```python
def transition_status(self, tenant_id, bu_id, task_id, new_status) -> TaskSchema:
    # Valid transitions:
    # BACKLOG->TODO, TODO->IN_PROGRESS/CANCELLED, IN_PROGRESS->IN_REVIEW/TODO/CANCELLED
    # IN_REVIEW->DONE/IN_PROGRESS, CANCELLED->TODO
    # Side effects: DONE sets completed_at, leaving DONE clears completed_at
```

### Controller — Custom
Standard 6 CRUD + `POST /{task_id}/status`

### Filters: eq (project_id, status, label_id, priority_id, assignee_id), in (status_in, task_ids), ilike (title), gte/lte (due_date)

**Verify**: `precommit-tests` passes

---

## Sub-Phase 3f: ProjectSummary (L3 — Read Model)

No database entity. Service composes ProjectRepository + TaskRepository:
- `get_project_summary()` — aggregates task counts, completion %, overdue count
- `list_project_summaries()` — paginated list with aggregation

Controller: `GET /tenants/{tid}/bus/{bid}/project-summaries` and `GET .../project-summaries/{project_id}`

**Verify**: `precommit-tests` passes

---

## Sub-Phase 3g: AppUser Entities (Organization Domain)

### AppUserEntity (`src/organization/entities/app_user_entity.py`)
```python
class AppUserEntity(BaseEntity):
    __tablename__ = 'app_user'
    id_prefix = 'usr'
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    auth_provider_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True)
    api_key_prefix: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    api_key_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
```
Note: AppUser is NOT scoped to tenant/BU — it sits above the scoping hierarchy (like Tenant itself).

### AppUserTenantRoleEntity (`src/organization/entities/app_user_tenant_role_entity.py`)
```python
class AppUserTenantRoleEntity(BaseEntity):
    __tablename__ = 'app_user_tenant_role'
    id_prefix = 'autr'
    app_user_id: FK to app_user.id
    tenant_id: FK to tenant.id
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # TenantRole enum value
```

### Services
- `AppUserService` — `get_by_auth_provider_id(auth_provider_id) -> Optional[AppUserSchema]`
- `AppUserTenantRoleService` — `has_tenant_access(user_id, tenant_id) -> bool`, `get_roles(user_id, tenant_id) -> List[str]`

These services have custom implementations (NOT BaseService) since AppUser is not tenant/BU-scoped.

**Verify**: `precommit-tests` passes

---

## Sub-Phase 3h: Wire into main.py + Seed Data

### main.py
Add new routers alongside existing rcm routers (both coexist):
```python
from project_mgmt.label.controllers.label_controller import labels_router
from project_mgmt.priority.controllers.priority_controller import priorities_router
from project_mgmt.project.controllers.project_controller import projects_router
from project_mgmt.task.controllers.task_controller import tasks_router
from project_mgmt.project_summary.controllers.project_summary_controller import project_summaries_router

app.include_router(labels_router)
app.include_router(priorities_router)
app.include_router(projects_router)
app.include_router(tasks_router)
app.include_router(project_summaries_router)
```

### TableName Update (base_entity.py)
Add project_mgmt entries:
```python
class TableName(StrEnum):
    TENANT = 'tenant'
    BU = 'bu'
    LABEL = 'label'
    PRIORITY = 'priority'
    PROJECT = 'project'
    TASK = 'task'
    APP_USER = 'app_user'
    APP_USER_TENANT_ROLE = 'app_user_tenant_role'
```

### conftest.py
Add new entity imports (keep existing rcm imports):
```python
import project_mgmt.label.entities.label_entity  # noqa
import project_mgmt.priority.entities.priority_entity  # noqa
import project_mgmt.project.entities.project_entity  # noqa
import project_mgmt.task.entities.task_entity  # noqa
import organization.entities.app_user_entity  # noqa
import organization.entities.app_user_tenant_role_entity  # noqa
```

### Seed Data
Add minimal seed data for project_mgmt entities alongside existing rcm data. Both domains are seeded.

**Verify**: `precommit-tests` passes (all old + new tests green)

---

## DO NOT Do in This Phase
- Do NOT remove `src/rcm/` (Phase 8)
- Do NOT modify TenantEntity or BuEntity (backref handles it)
- Do NOT overhaul `conftest.py` (Phase 5)
- Do NOT overhaul seed infrastructure (Phase 5)
- Do NOT add auth (Phase 4)
- Do NOT create AgentRun (Phase 6)

---

## Files Summary

### Create (~45 files)
| Directory | Files |
|-----------|-------|
| `src/project_mgmt/` | ~35 files (5 entities x MVCS stack + enums + __init__.py) |
| `src/organization/` | ~6 files (AppUser + AppUserTenantRole MVCS) |
| `tests/project_mgmt/` | ~20 test files |
| `tests/integration/project_mgmt/` | ~5 integration test files |

### Modify (~5 files)
| File | Change |
|------|--------|
| `main.py` | Add project_mgmt + organization router imports |
| `src/common/entities/base_entity.py` | Add LABEL, PRIORITY, PROJECT, TASK, APP_USER, APP_USER_TENANT_ROLE to TableName |
| `conftest.py` | Add project_mgmt + organization entity imports |
| `migrations/env.py` | Add project_mgmt + organization entity imports |

### Delete: 0 files
