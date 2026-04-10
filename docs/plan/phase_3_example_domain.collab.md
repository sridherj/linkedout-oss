# Phase 3: Example Domain — Project Management (Detailed Execution Plan)

## Overview

Replace the linkedout rcm domain with a coherent project-management domain that demonstrates all MVCS patterns. Build new entities alongside existing linkedout code, verify, then remove linkedout.

**Verification gate**: `precommit-tests` must pass after each sub-phase.

---

## Module Structure

```
src/project_mgmt/
  __init__.py                          # Module init, exports all routers
  enums.py                             # Shared enums (TaskStatus, TaskPriority values)
  label/
    __init__.py
    entities/
      __init__.py
      label_entity.py
    repositories/
      __init__.py
      label_repository.py
    services/
      __init__.py
      label_service.py
    controllers/
      __init__.py
      label_controller.py
    schemas/
      __init__.py
      label_schema.py                  # Core Pydantic model (LabelSchema)
      label_api_schema.py              # All request/response schemas + SortByFields
  priority/
    __init__.py
    entities/
      __init__.py
      priority_entity.py
    repositories/
      __init__.py
      priority_repository.py
    services/
      __init__.py
      priority_service.py
    controllers/
      __init__.py
      priority_controller.py
    schemas/
      __init__.py
      priority_schema.py
      priority_api_schema.py
  project/
    __init__.py
    entities/
      __init__.py
      project_entity.py
    repositories/
      __init__.py
      project_repository.py
    services/
      __init__.py
      project_service.py
    controllers/
      __init__.py
      project_controller.py
    schemas/
      __init__.py
      project_schema.py
      project_api_schema.py
  task/
    __init__.py
    entities/
      __init__.py
      task_entity.py
    repositories/
      __init__.py
      task_repository.py
    services/
      __init__.py
      task_service.py
    controllers/
      __init__.py
      task_controller.py
    schemas/
      __init__.py
      task_schema.py
      task_api_schema.py
  project_summary/
    __init__.py
    services/
      __init__.py
      project_summary_service.py
    controllers/
      __init__.py
      project_summary_controller.py
    schemas/
      __init__.py
      project_summary_schema.py
```

### Test Structure (mirrors source)

```
tests/
  project_mgmt/
    __init__.py
    label/
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
    priority/
      repositories/test_priority_repository.py
      services/test_priority_service.py
      controllers/test_priority_controller.py
    project/
      repositories/test_project_repository.py
      services/test_project_service.py
      controllers/test_project_controller.py
    task/
      repositories/test_task_repository.py
      services/test_task_service.py
      controllers/test_task_controller.py
    project_summary/
      services/test_project_summary_service.py
      controllers/test_project_summary_controller.py
  integration/
    project_mgmt/
      __init__.py
      test_label_controller.py
      test_priority_controller.py
      test_project_controller.py
      test_task_controller.py
      test_project_summary_controller.py
```

---

## Shared Enums (`src/project_mgmt/enums.py`)

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

---

## Entity 1: Label (L1 — Simple CRUD)

**Purpose**: Demonstrates the simplest generic CRUD entity with filtering and list semantics.

### Entity (`label_entity.py`)

```python
class LabelEntity(TenantBuMixin, BaseEntity):
    __tablename__ = 'label'
    id_prefix = 'label'

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)  # hex color e.g. #FF5733
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    tasks: Mapped[list['TaskEntity']] = relationship(
        'TaskEntity', back_populates='label'
    )
```

### Repository (`label_repository.py`)

```python
class LabelRepository(BaseRepository[LabelEntity, LabelSortByFields]):
    _entity_class = LabelEntity
    _default_sort_field = 'name'
    _entity_name = 'label'

    def _get_filter_specs(self) -> List[FilterSpec]:
        return [
            FilterSpec('name', 'ilike'),          # text search on name
            FilterSpec('label_ids', 'in', entity_field='id'),  # in-list filter
        ]
```

### Service (`label_service.py`)

```python
class LabelService(BaseService[LabelEntity, LabelSchema, LabelRepository]):
    _repository_class = LabelRepository
    _schema_class = LabelSchema
    _entity_class = LabelEntity
    _entity_name = 'label'
    _entity_id_field = 'label_id'

    def _extract_filter_kwargs(self, list_request: Any) -> dict:
        return {
            'name': list_request.name,
            'label_ids': list_request.label_ids,
        }

    def _create_entity_from_request(self, create_request: Any) -> LabelEntity:
        return LabelEntity(
            tenant_id=create_request.tenant_id,
            bu_id=create_request.bu_id,
            name=create_request.name,
            color=create_request.color,
            description=create_request.description,
        )

    def _update_entity_from_request(self, entity: LabelEntity, update_request: Any) -> None:
        if update_request.name is not None:
            entity.name = update_request.name
        if update_request.color is not None:
            entity.color = update_request.color
        if update_request.description is not None:
            entity.description = update_request.description
```

### Controller (`label_controller.py`)

Use **manual controller** pattern (like demand_controller.py), not CRUDRouterFactory, to stay consistent with the existing codebase pattern.

```python
labels_router = APIRouter(
    prefix='/tenants/{tenant_id}/bus/{bu_id}/labels',
    tags=['labels']
)
# Standard 6 endpoints: GET /, POST /, POST /bulk, PATCH /{label_id}, GET /{label_id}, DELETE /{label_id}
```

### Schemas

**`label_schema.py`** (core model):
```python
class LabelSchema(BaseModel):
    id: str
    tenant_id: str
    bu_id: str
    name: str
    color: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

**`label_api_schema.py`** (request/response):
```python
class LabelSortByFields(StrEnum):
    NAME = 'name'
    CREATED_AT = 'created_at'

class ListLabelsRequestSchema(PaginateRequestSchema):
    tenant_id: Optional[str] = None
    bu_id: Optional[str] = None
    sort_by: LabelSortByFields = LabelSortByFields.NAME
    sort_order: SortOrder = SortOrder.ASC
    name: Optional[str] = None          # ilike search
    label_ids: Optional[list[str]] = None  # in-list filter

class CreateLabelRequestSchema(BaseRequestSchema):
    tenant_id: Optional[str] = None
    bu_id: Optional[str] = None
    name: str
    color: Optional[str] = None
    description: Optional[str] = None

class CreateLabelsRequestSchema(BaseRequestSchema):
    tenant_id: Optional[str] = None
    bu_id: Optional[str] = None
    labels: List[CreateLabelRequestSchema]

class UpdateLabelRequestSchema(BaseRequestSchema):
    tenant_id: Optional[str] = None
    bu_id: Optional[str] = None
    label_id: Optional[str] = None
    name: Optional[str] = None
    color: Optional[str] = None
    description: Optional[str] = None

class GetLabelByIdRequestSchema(BaseRequestSchema):
    tenant_id: Optional[str] = None
    bu_id: Optional[str] = None
    label_id: Optional[str] = None

class DeleteLabelByIdRequestSchema(BaseRequestSchema):
    tenant_id: Optional[str] = None
    bu_id: Optional[str] = None
    label_id: Optional[str] = None

class ListLabelsResponseSchema(PaginateResponseSchema):
    labels: List[LabelSchema]

class CreateLabelResponseSchema(BaseResponseSchema):
    label: LabelSchema

class CreateLabelsResponseSchema(BaseResponseSchema):
    labels: List[LabelSchema]

class UpdateLabelResponseSchema(BaseResponseSchema):
    label: LabelSchema

class GetLabelByIdResponseSchema(BaseResponseSchema):
    label: LabelSchema
```

### Filter patterns demonstrated
- `ilike` on name (text search)
- `in` on label_ids (list filter)

### URL routing
`/tenants/{tenant_id}/bus/{bu_id}/labels`

---

## Entity 2: Priority (L1 — CRUD + Enum/Config)

**Purpose**: Demonstrates enum-like config entity with ordering support.

### Entity (`priority_entity.py`)

```python
class PriorityEntity(TenantBuMixin, BaseEntity):
    __tablename__ = 'priority'
    id_prefix = 'priority'

    name: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "Critical", "High", "Medium", "Low"
    level: Mapped[int] = mapped_column(Integer, nullable=False)     # 1=highest, numeric ordering
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    tasks: Mapped[list['TaskEntity']] = relationship(
        'TaskEntity', back_populates='priority'
    )
```

### Repository (`priority_repository.py`)

```python
class PriorityRepository(BaseRepository[PriorityEntity, PrioritySortByFields]):
    _entity_class = PriorityEntity
    _default_sort_field = 'level'
    _entity_name = 'priority'

    def _get_filter_specs(self) -> List[FilterSpec]:
        return [
            FilterSpec('name', 'eq'),
            FilterSpec('level', 'eq'),
            FilterSpec('level_gte', 'gte', entity_field='level'),
            FilterSpec('level_lte', 'lte', entity_field='level'),
        ]
```

### Service (`priority_service.py`)

```python
class PriorityService(BaseService[PriorityEntity, PrioritySchema, PriorityRepository]):
    _repository_class = PriorityRepository
    _schema_class = PrioritySchema
    _entity_class = PriorityEntity
    _entity_name = 'priority'
    _entity_id_field = 'priority_id'

    def _extract_filter_kwargs(self, list_request: Any) -> dict:
        return {
            'name': list_request.name,
            'level': list_request.level,
            'level_gte': list_request.level_gte,
            'level_lte': list_request.level_lte,
        }

    def _create_entity_from_request(self, create_request: Any) -> PriorityEntity:
        return PriorityEntity(
            tenant_id=create_request.tenant_id,
            bu_id=create_request.bu_id,
            name=create_request.name,
            level=create_request.level,
            color=create_request.color,
            description=create_request.description,
        )

    def _update_entity_from_request(self, entity: PriorityEntity, update_request: Any) -> None:
        if update_request.name is not None:
            entity.name = update_request.name
        if update_request.level is not None:
            entity.level = update_request.level
        if update_request.color is not None:
            entity.color = update_request.color
        if update_request.description is not None:
            entity.description = update_request.description
```

### Schemas

**`priority_schema.py`**:
```python
class PrioritySchema(BaseModel):
    id: str
    tenant_id: str
    bu_id: str
    name: str
    level: int
    color: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

**`priority_api_schema.py`**:
```python
class PrioritySortByFields(StrEnum):
    LEVEL = 'level'
    NAME = 'name'
    CREATED_AT = 'created_at'

# ListPrioritiesRequestSchema, CreatePriorityRequestSchema, etc. — same pattern as Label
# Filters: name (eq), level (eq), level_gte (gte), level_lte (lte)
```

### Filter patterns demonstrated
- `eq` on name and level (exact match)
- `gte`/`lte` on level (range filters)

### URL routing
`/tenants/{tenant_id}/bus/{bu_id}/priorities`

---

## Entity 3: Project (L2 — Parent Entity)

**Purpose**: Demonstrates parent entity in parent-child relationship, richer fields, and status management.

### Entity (`project_entity.py`)

```python
class ProjectEntity(TenantBuMixin, BaseEntity):
    __tablename__ = 'project'
    id_prefix = 'project'

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ProjectStatus.PLANNING
    )
    owner_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # who owns this project
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    target_end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)  # ["backend", "urgent"]

    # Relationships
    tasks: Mapped[list['TaskEntity']] = relationship(
        'TaskEntity', back_populates='project', cascade='all, delete-orphan'
    )
```

### Repository (`project_repository.py`)

```python
class ProjectRepository(BaseRepository[ProjectEntity, ProjectSortByFields]):
    _entity_class = ProjectEntity
    _default_sort_field = 'created_at'
    _entity_name = 'project'

    def _get_filter_specs(self) -> List[FilterSpec]:
        return [
            FilterSpec('name', 'ilike'),
            FilterSpec('status', 'eq'),
            FilterSpec('status_in', 'in', entity_field='status'),
            FilterSpec('owner_id', 'eq'),
            FilterSpec('start_date_gte', 'gte', entity_field='start_date'),
            FilterSpec('start_date_lte', 'lte', entity_field='start_date'),
            FilterSpec('project_ids', 'in', entity_field='id'),
        ]
```

### Service (`project_service.py`)

Standard BaseService implementation plus one orchestration method:

```python
class ProjectService(BaseService[ProjectEntity, ProjectSchema, ProjectRepository]):
    _repository_class = ProjectRepository
    _schema_class = ProjectSchema
    _entity_class = ProjectEntity
    _entity_name = 'project'
    _entity_id_field = 'project_id'

    # Standard abstract methods: _extract_filter_kwargs, _create_entity_from_request, _update_entity_from_request

    def update_project_status(self, tenant_id: str, bu_id: str, project_id: str, new_status: str) -> ProjectSchema:
        """
        Orchestration method: Update project status with validation.

        Validates status transitions:
        - PLANNING -> ACTIVE
        - ACTIVE -> ON_HOLD, COMPLETED
        - ON_HOLD -> ACTIVE, ARCHIVED
        - COMPLETED -> ARCHIVED
        """
        entity = self._repository.get_by_id(tenant_id, bu_id, project_id)
        if not entity:
            raise ValueError(f'Project {project_id} not found')

        # Validate transition (define VALID_TRANSITIONS dict)
        current = entity.status
        if new_status not in VALID_PROJECT_TRANSITIONS.get(current, []):
            raise ValueError(f'Invalid transition: {current} -> {new_status}')

        entity.status = new_status
        if new_status == ProjectStatus.COMPLETED:
            entity.actual_end_date = datetime.now(timezone.utc)

        return ProjectSchema.model_validate(entity)
```

Valid transitions:
```python
VALID_PROJECT_TRANSITIONS = {
    ProjectStatus.PLANNING: [ProjectStatus.ACTIVE],
    ProjectStatus.ACTIVE: [ProjectStatus.ON_HOLD, ProjectStatus.COMPLETED],
    ProjectStatus.ON_HOLD: [ProjectStatus.ACTIVE, ProjectStatus.ARCHIVED],
    ProjectStatus.COMPLETED: [ProjectStatus.ARCHIVED],
}
```

### Controller (`project_controller.py`)

Standard 6 CRUD endpoints plus one custom endpoint:

```python
projects_router = APIRouter(
    prefix='/tenants/{tenant_id}/bus/{bu_id}/projects',
    tags=['projects']
)

# Standard CRUD: GET /, POST /, POST /bulk, PATCH /{project_id}, GET /{project_id}, DELETE /{project_id}

# Custom endpoint for status transitions
@projects_router.post('/{project_id}/status')
def update_project_status(tenant_id, bu_id, project_id, body: UpdateProjectStatusRequestSchema, ...):
    """Update project status with transition validation."""
```

### Schemas

**`project_schema.py`**:
```python
class ProjectSchema(BaseModel):
    id: str
    tenant_id: str
    bu_id: str
    name: str
    description: Optional[str] = None
    status: str
    owner_id: Optional[str] = None
    start_date: Optional[datetime] = None
    target_end_date: Optional[datetime] = None
    actual_end_date: Optional[datetime] = None
    tags: Optional[list] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

**`project_api_schema.py`**:
```python
class ProjectSortByFields(StrEnum):
    NAME = 'name'
    STATUS = 'status'
    START_DATE = 'start_date'
    CREATED_AT = 'created_at'

# ListProjectsRequestSchema — filters: name (ilike), status (eq), status_in (in), owner_id (eq),
#   start_date_gte (gte), start_date_lte (lte), project_ids (in)
# CreateProjectRequestSchema — name (required), description, status (default PLANNING), owner_id, start_date, target_end_date, tags
# UpdateProjectRequestSchema — all optional
# UpdateProjectStatusRequestSchema — new_status: str (required) — for the /status endpoint
# Standard response schemas
```

### Filter patterns demonstrated
- `ilike` on name
- `eq` on status, owner_id
- `in` on status_in, project_ids
- `gte`/`lte` on start_date

### URL routing
- CRUD: `/tenants/{tenant_id}/bus/{bu_id}/projects`
- Status: `POST /tenants/{tenant_id}/bus/{bu_id}/projects/{project_id}/status`

---

## Entity 4: Task (L2 — Child Entity + Orchestration)

**Purpose**: Demonstrates child entity with FK to parent (Project), service-to-service orchestration, status transitions, and rich filtering.

### Entity (`task_entity.py`)

```python
class TaskEntity(TenantBuMixin, BaseEntity):
    __tablename__ = 'task'
    id_prefix = 'task'

    # Parent relationship
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey('project.id', ondelete='CASCADE'), nullable=False
    )

    # Core fields
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TaskStatus.BACKLOG
    )

    # References to Label and Priority
    label_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey('label.id', ondelete='SET NULL'), nullable=True
    )
    priority_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey('priority.id', ondelete='SET NULL'), nullable=True
    )

    # Assignment and scheduling
    assignee_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    estimated_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Ordering within project
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    project: Mapped['ProjectEntity'] = relationship('ProjectEntity', back_populates='tasks')
    label: Mapped[Optional['LabelEntity']] = relationship('LabelEntity', back_populates='tasks')
    priority: Mapped[Optional['PriorityEntity']] = relationship('PriorityEntity', back_populates='tasks')
```

### Repository (`task_repository.py`)

```python
class TaskRepository(BaseRepository[TaskEntity, TaskSortByFields]):
    _entity_class = TaskEntity
    _default_sort_field = 'sort_order'
    _entity_name = 'task'

    def _get_filter_specs(self) -> List[FilterSpec]:
        return [
            FilterSpec('project_id', 'eq'),
            FilterSpec('status', 'eq'),
            FilterSpec('status_in', 'in', entity_field='status'),
            FilterSpec('label_id', 'eq'),
            FilterSpec('priority_id', 'eq'),
            FilterSpec('assignee_id', 'eq'),
            FilterSpec('title', 'ilike'),
            FilterSpec('due_date_gte', 'gte', entity_field='due_date'),
            FilterSpec('due_date_lte', 'lte', entity_field='due_date'),
            FilterSpec('task_ids', 'in', entity_field='id'),
        ]
```

### Service (`task_service.py`)

This is the **non-trivial service** that demonstrates orchestration:

```python
class TaskService(BaseService[TaskEntity, TaskSchema, TaskRepository]):
    _repository_class = TaskRepository
    _schema_class = TaskSchema
    _entity_class = TaskEntity
    _entity_name = 'task'
    _entity_id_field = 'task_id'

    # Standard abstract methods: _extract_filter_kwargs, _create_entity_from_request, _update_entity_from_request

    def transition_status(
        self, tenant_id: str, bu_id: str, task_id: str, new_status: str
    ) -> TaskSchema:
        """
        Orchestration: Transition task status with validation and side effects.

        Valid transitions:
        - BACKLOG -> TODO
        - TODO -> IN_PROGRESS, CANCELLED
        - IN_PROGRESS -> IN_REVIEW, TODO, CANCELLED
        - IN_REVIEW -> DONE, IN_PROGRESS
        - DONE -> (terminal, no transitions out except reopening which is a separate action)
        - CANCELLED -> TODO (reopen)

        Side effects:
        - Transitioning to DONE sets completed_at timestamp
        - Transitioning from DONE clears completed_at
        """
        entity = self._repository.get_by_id(tenant_id, bu_id, task_id)
        if not entity:
            raise ValueError(f'Task {task_id} not found')

        current = entity.status
        if new_status not in VALID_TASK_TRANSITIONS.get(current, []):
            raise ValueError(f'Invalid transition: {current} -> {new_status}')

        entity.status = new_status
        if new_status == TaskStatus.DONE:
            entity.completed_at = datetime.now(timezone.utc)
        elif current == TaskStatus.DONE:
            entity.completed_at = None

        return TaskSchema.model_validate(entity)
```

Valid transitions:
```python
VALID_TASK_TRANSITIONS = {
    TaskStatus.BACKLOG: [TaskStatus.TODO],
    TaskStatus.TODO: [TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED],
    TaskStatus.IN_PROGRESS: [TaskStatus.IN_REVIEW, TaskStatus.TODO, TaskStatus.CANCELLED],
    TaskStatus.IN_REVIEW: [TaskStatus.DONE, TaskStatus.IN_PROGRESS],
    TaskStatus.CANCELLED: [TaskStatus.TODO],
}
```

### Controller (`task_controller.py`)

Standard 6 CRUD endpoints plus custom orchestration endpoints:

```python
tasks_router = APIRouter(
    prefix='/tenants/{tenant_id}/bus/{bu_id}/tasks',
    tags=['tasks']
)

# Standard CRUD: GET /, POST /, POST /bulk, PATCH /{task_id}, GET /{task_id}, DELETE /{task_id}

# Custom: Status transition
@tasks_router.post('/{task_id}/status')
def transition_task_status(tenant_id, bu_id, task_id, body: TransitionTaskStatusRequestSchema, ...):
    """Transition task status with validation."""
```

### Schemas

**`task_schema.py`**:
```python
class TaskSchema(BaseModel):
    id: str
    tenant_id: str
    bu_id: str
    project_id: str
    title: str
    description: Optional[str] = None
    status: str
    label_id: Optional[str] = None
    priority_id: Optional[str] = None
    assignee_id: Optional[str] = None
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    sort_order: int = 0
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

**`task_api_schema.py`**:
```python
class TaskSortByFields(StrEnum):
    TITLE = 'title'
    STATUS = 'status'
    DUE_DATE = 'due_date'
    SORT_ORDER = 'sort_order'
    CREATED_AT = 'created_at'

# ListTasksRequestSchema — filters: project_id (eq), status (eq), status_in (in), label_id (eq),
#   priority_id (eq), assignee_id (eq), title (ilike), due_date_gte (gte), due_date_lte (lte), task_ids (in)
# CreateTaskRequestSchema — project_id (required), title (required), description, status (default BACKLOG),
#   label_id, priority_id, assignee_id, due_date, estimated_hours, sort_order
# UpdateTaskRequestSchema — all optional
# TransitionTaskStatusRequestSchema — new_status: str (required) — for the /status endpoint
# Standard response schemas
```

### Filter patterns demonstrated
- `eq` on project_id, status, label_id, priority_id, assignee_id
- `in` on status_in, task_ids
- `ilike` on title
- `gte`/`lte` on due_date

### URL routing
- CRUD: `/tenants/{tenant_id}/bus/{bu_id}/tasks`
- Status: `POST /tenants/{tenant_id}/bus/{bu_id}/tasks/{task_id}/status`

---

## Entity 5: ProjectSummary (L3 — Read-Model / Aggregation)

**Purpose**: Demonstrates read-model pattern — assembles data from multiple repositories, no entity/table of its own.

### Design

ProjectSummary is **not a database entity**. It's an aggregation that combines:
- Project data
- Task count by status
- Completion percentage
- Overdue task count

### Service (`project_summary_service.py`)

```python
class ProjectSummaryService:
    """
    Read-model service that aggregates project + task data.

    Does NOT inherit from BaseService — it's a pure read service
    that composes data from multiple repositories.
    """

    def __init__(self, session: Session):
        self._project_repo = ProjectRepository(session)
        self._task_repo = TaskRepository(session)

    def get_project_summary(
        self, tenant_id: str, bu_id: str, project_id: str
    ) -> Optional[ProjectSummarySchema]:
        """Get aggregated summary for a single project."""
        project = self._project_repo.get_by_id(tenant_id, bu_id, project_id)
        if not project:
            return None

        tasks = self._task_repo.list_with_filters(
            tenant_id=tenant_id, bu_id=bu_id, project_id=project_id, limit=1000
        )

        return self._build_summary(project, tasks)

    def list_project_summaries(
        self, tenant_id: str, bu_id: str, limit: int = 20, offset: int = 0,
        status: Optional[str] = None
    ) -> Tuple[List[ProjectSummarySchema], int]:
        """List project summaries with basic filtering."""
        projects = self._project_repo.list_with_filters(
            tenant_id=tenant_id, bu_id=bu_id, limit=limit, offset=offset, status=status
        )
        total = self._project_repo.count_with_filters(
            tenant_id=tenant_id, bu_id=bu_id, status=status
        )

        summaries = []
        for project in projects:
            tasks = self._task_repo.list_with_filters(
                tenant_id=tenant_id, bu_id=bu_id, project_id=project.id, limit=1000
            )
            summaries.append(self._build_summary(project, tasks))

        return summaries, total

    def _build_summary(self, project: ProjectEntity, tasks: list) -> ProjectSummarySchema:
        """Build a summary from project entity and its tasks."""
        total_tasks = len(tasks)
        done_count = sum(1 for t in tasks if t.status == TaskStatus.DONE)
        overdue_count = sum(
            1 for t in tasks
            if t.due_date and t.due_date < datetime.now(timezone.utc)
            and t.status not in (TaskStatus.DONE, TaskStatus.CANCELLED)
        )

        status_counts = {}
        for t in tasks:
            status_counts[t.status] = status_counts.get(t.status, 0) + 1

        completion_pct = (done_count / total_tasks * 100) if total_tasks > 0 else 0.0

        return ProjectSummarySchema(
            project_id=project.id,
            project_name=project.name,
            project_status=project.status,
            owner_id=project.owner_id,
            total_tasks=total_tasks,
            tasks_by_status=status_counts,
            completion_percentage=round(completion_pct, 1),
            overdue_task_count=overdue_count,
            start_date=project.start_date,
            target_end_date=project.target_end_date,
        )
```

### Controller (`project_summary_controller.py`)

```python
project_summaries_router = APIRouter(
    prefix='/tenants/{tenant_id}/bus/{bu_id}/project-summaries',
    tags=['project-summaries']
)

@project_summaries_router.get('')
def list_project_summaries(tenant_id, bu_id, limit, offset, status, ...):
    """List project summaries with task aggregation."""

@project_summaries_router.get('/{project_id}')
def get_project_summary(tenant_id, bu_id, project_id, ...):
    """Get summary for a single project."""
```

### Schemas (`project_summary_schema.py`)

```python
class ProjectSummarySchema(BaseModel):
    project_id: str
    project_name: str
    project_status: str
    owner_id: Optional[str] = None
    total_tasks: int
    tasks_by_status: dict[str, int]    # {"todo": 3, "in_progress": 2, "done": 5}
    completion_percentage: float
    overdue_task_count: int
    start_date: Optional[datetime] = None
    target_end_date: Optional[datetime] = None

class ListProjectSummariesRequestSchema(PaginateRequestSchema):
    tenant_id: Optional[str] = None
    bu_id: Optional[str] = None
    status: Optional[str] = None  # filter by project status

class GetProjectSummaryResponseSchema(BaseResponseSchema):
    project_summary: ProjectSummarySchema

class ListProjectSummariesResponseSchema(PaginateResponseSchema):
    project_summaries: List[ProjectSummarySchema]
```

### URL routing
- `GET /tenants/{tenant_id}/bus/{bu_id}/project-summaries`
- `GET /tenants/{tenant_id}/bus/{bu_id}/project-summaries/{project_id}`

---

## Wiring into main.py

Replace all rcm router imports with project_mgmt routers:

```python
# Remove all rcm.* router imports
# Remove all rcm.* app.include_router() calls

# Add:
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

Keep `tenants_router` and `bus_router` from organization module.

---

## Organization Module Updates

### TenantEntity relationships update
Replace all 30+ rcm relationships with:
```python
# Project management domain relationships
labels: relationship('LabelEntity', back_populates='tenant')
priorities: relationship('PriorityEntity', back_populates='tenant')
projects: relationship('ProjectEntity', back_populates='tenant')
tasks: relationship('TaskEntity', back_populates='tenant')
```

### BuEntity relationships update
Same pattern — replace rcm relationships with project_mgmt ones.

### TableName enum update
Replace all rcm table names with:
```python
class TableName(str, Enum):
    TENANT = 'tenant'
    BU = 'bu'
    LABEL = 'label'
    PRIORITY = 'priority'
    PROJECT = 'project'
    TASK = 'task'

    @classmethod
    def get_project_mgmt_tables(cls):
        return [cls.LABEL, cls.PRIORITY, cls.PROJECT, cls.TASK]

    @classmethod
    def get_all_tables_in_order(cls):
        """Dependency order for seeding."""
        return [cls.TENANT, cls.BU, cls.LABEL, cls.PRIORITY, cls.PROJECT, cls.TASK]
```

---

## Test Plan

### Test Approach

Follow the existing "wiring test" pattern established in linkedout:
- **Repository tests**: Verify correct inheritance, filter specs, one integration test with real DB
- **Service tests**: Verify configuration, filter extraction, entity creation, entity update
- **Controller tests**: Verify endpoints exist, service wiring, error handling (404, 422)
- **Integration tests**: Full CRUD against PostgreSQL

### Tests per Entity

Each entity gets 3 unit test files + 1 integration test file. Pattern identical to demand tests.

#### Label Tests (representative example — other L1/L2 entities follow same pattern)

**`tests/project_mgmt/label/repositories/test_label_repository.py`**:
- `TestLabelRepositoryWiring`: inherits BaseRepository, entity_class, default_sort, entity_name, filter_specs
- `TestLabelRepositoryIntegration`: create with prefix, list_with_filters with ilike

**`tests/project_mgmt/label/services/test_label_service.py`**:
- `TestLabelServiceWiring`: inherits BaseService, repo/schema/entity class, entity_name, entity_id_field
- `TestLabelServiceFilterExtraction`: maps all fields, handles None
- `TestLabelServiceEntityCreation`: maps all fields
- `TestLabelServiceEntityUpdate`: updates provided fields, all-None changes nothing

**`tests/project_mgmt/label/controllers/test_label_controller.py`**:
- `TestListLabelsEndpointWiring`: endpoint exists, calls service
- `TestGetLabelByIdEndpointWiring`: returns 200, returns 404
- `TestCreateLabelEndpointWiring`: returns 201, validates required fields (422)
- `TestUpdateLabelEndpointWiring`: returns 200, returns 404
- `TestDeleteLabelEndpointWiring`: returns 204, returns 404
- `TestCreateLabelsBulkEndpointWiring`: returns 201

**`tests/integration/project_mgmt/test_label_controller.py`**:
- list returns seeded data
- list with name filter (ilike)
- list with pagination
- get by id
- get by id 404
- create success
- create minimal
- create bulk
- create missing required (422)
- update success
- update 404
- delete success
- delete 404

#### Task-Specific Additional Tests

- **Service**: `TestTaskServiceStatusTransition` — valid transitions, invalid transitions raise ValueError, completed_at side effects
- **Controller**: Test for `POST /{task_id}/status` endpoint
- **Integration**: Status transition end-to-end, verify completed_at

#### Project-Specific Additional Tests

- **Service**: `TestProjectServiceStatusTransition` — valid transitions, invalid transitions, actual_end_date side effects
- **Controller**: Test for `POST /{project_id}/status` endpoint
- **Integration**: Status transition end-to-end

#### ProjectSummary Tests

- **Service tests** (`tests/project_mgmt/project_summary/services/test_project_summary_service.py`):
  - Mock ProjectRepository and TaskRepository
  - Test `get_project_summary` returns correct aggregation
  - Test `_build_summary` calculates completion_percentage, overdue_count, tasks_by_status
  - Test project not found returns None
  - Test empty tasks returns zero counts

- **Controller tests** (`tests/project_mgmt/project_summary/controllers/test_project_summary_controller.py`):
  - GET / returns list
  - GET /{project_id} returns summary
  - GET /{project_id} returns 404

- **Integration** (`tests/integration/project_mgmt/test_project_summary_controller.py`):
  - Summary reflects actual task counts
  - Summary with no tasks
  - List summaries

---

## Seed Data Updates

### `src/dev_tools/db/seed.py` updates

Replace rcm seeding with project_mgmt seeding:

```python
# Seed order for project_mgmt (respects FK dependencies):
# 1. Tenant
# 2. BU
# 3. Label (no FK deps beyond tenant/bu)
# 4. Priority (no FK deps beyond tenant/bu)
# 5. Project (no FK deps beyond tenant/bu)
# 6. Task (FK to project, label, priority)
```

### `tests/seed_db.py` updates

Update `SeedDb` and `SeedConfig` to support project_mgmt entities:

```python
class SeedConfig:
    tables_to_populate: List[TableName]
    tenant_count: int = 1
    bu_count_per_tenant: int = 1
    label_count: int = 0
    priority_count: int = 0
    project_count: int = 0
    task_count_per_project: int = 0
```

Factory methods for test data:
```python
def _create_label(self, tenant_id, bu_id) -> LabelEntity
def _create_priority(self, tenant_id, bu_id, level) -> PriorityEntity
def _create_project(self, tenant_id, bu_id) -> ProjectEntity
def _create_task(self, tenant_id, bu_id, project_id, label_id, priority_id) -> TaskEntity
```

### `src/dev_tools/db/fixed_data.py` updates

Seed default priorities:
```python
DEFAULT_PRIORITIES = [
    {"name": "Critical", "level": 1, "color": "#FF0000"},
    {"name": "High", "level": 2, "color": "#FF8C00"},
    {"name": "Medium", "level": 3, "color": "#FFD700"},
    {"name": "Low", "level": 4, "color": "#00AA00"},
]
```

---

## Terrantic Code to Remove

After the new domain is working and all tests pass:

### Source directories to delete
- `src/rcm/` (entire directory)
- All rcm-specific entries in `src/common/entities/base_entity.py` TableName enum

### Test directories to delete
- `tests/rcm/` (entire directory)
- `tests/integration/rcm/` (entire directory)

### Files to update
- `main.py` — remove all rcm router imports/registrations
- `src/organization/entities/tenant_entity.py` — remove rcm relationships
- `src/organization/entities/bu_entity.py` — remove rcm relationships
- `src/dev_tools/db/seed.py` — remove rcm seeding
- `src/dev_tools/db/fixed_data.py` — remove rcm fixed data
- `src/dev_tools/db/verify_seed.py` — update for project_mgmt
- `tests/seed_db.py` — remove rcm seed config
- `conftest.py` — update integration seed config if rcm-specific
- `src/dev_tools/planner_agent_iterations/` — keep or archive (this is agent eval infra, not domain code; remove only if it has rcm entity deps)
- `prompts/planner/` — remove rcm agent prompts
- `migrations/` — new migration for project_mgmt schema

### Files to keep
- `src/common/` — all base classes (already domain-agnostic)
- `src/organization/` — Tenant, BU (updated relationships)
- `src/shared/` — infra, config, utilities
- `src/utilities/` — LLM client, prompt manager (for Phase 6)
- `src/dev_tools/cli.py` — update commands
- All claude agent/skill files

---

## Execution Order (Sub-Phases)

### 3a: Scaffold module structure + enums
- Create all `__init__.py` files and directory structure
- Create `src/project_mgmt/enums.py`
- Verify: module imports work

### 3b: Label (L1) — full MVCS + tests
- Entity, repo, service, controller, schemas
- All 3 unit test files + integration test
- Wire into main.py (alongside rcm)
- Verify: `precommit-tests` passes

### 3c: Priority (L1) — full MVCS + tests
- Same pattern as Label
- Verify: `precommit-tests` passes

### 3d: Project (L2) — full MVCS + tests + status transitions
- Entity with richer fields
- Service with `update_project_status` orchestration method
- Controller with `/status` endpoint
- All tests including transition tests
- Verify: `precommit-tests` passes

### 3e: Task (L2) — full MVCS + tests + orchestration
- Entity with FKs to Project, Label, Priority
- Service with `transition_status` orchestration
- Controller with `/status` endpoint
- All tests including transition and side-effect tests
- Verify: `precommit-tests` passes

### 3f: ProjectSummary (L3) — read model + tests
- Service composing ProjectRepository + TaskRepository
- Controller with GET list and GET by id
- Tests with mocked repos
- Verify: `precommit-tests` passes

### 3g: Seed data and fixed data
- Update seed.py, fixed_data.py, verify_seed.py
- Update tests/seed_db.py for project_mgmt entities
- Update integration test conftest
- Verify: seeding works, integration tests pass

### 3h: Remove linkedout domain
- Delete `src/rcm/`
- Delete `tests/rcm/`, `tests/integration/rcm/`
- Update main.py, organization entities, TableName enum
- Clean up any remaining linkedout references
- Verify: `precommit-tests` passes with only project_mgmt tests

### 3i: Final cleanup
- Remove linkedout naming from any remaining files
- Update main.py description
- Verify Alembic migration for new schema
- Verify: `precommit-tests` passes — clean repo

---

## Pattern Coverage Summary

| Requirement | Entity | How |
|------------|--------|-----|
| Simple CRUD | Label, Priority | Generic BaseService/BaseRepository |
| Text search (ilike) | Label (name), Project (name), Task (title) | FilterSpec ilike |
| Exact match (eq) | Priority (name, level), Task (project_id, status, etc.) | FilterSpec eq |
| In-list (in) | Label (label_ids), Project (status_in, project_ids), Task (status_in, task_ids) | FilterSpec in |
| Range (gte/lte) | Priority (level), Project (start_date), Task (due_date) | FilterSpec gte/lte |
| Boolean filter | All entities via BaseEntity is_active | Already in base |
| Pagination | All entities | BaseRepository + PaginateResponseSchema |
| Sorting | All entities | SortByFields enum + BaseRepository |
| Bulk create | All entities | BaseService.create_entities_bulk |
| Parent-child | Project -> Task | FK + cascade delete |
| Service orchestration | Task.transition_status, Project.update_project_status | Custom service methods |
| Read model / aggregation | ProjectSummary | Compose from multiple repos |
| Status transitions | Project, Task | Validated state machine in service |
| Enum/config entity | Priority | Ordered levels |
