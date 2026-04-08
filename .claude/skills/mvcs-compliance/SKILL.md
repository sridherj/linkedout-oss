---
name: mvcs-compliance
user_invocable: true
description: Apply MVCS architecture compliance rules when creating or reviewing service, repository, or controller code. Use when ensuring services return schemas (not entities), proper transaction management, and correct layer responsibilities.
---

# MVCSCompliance Skill

Apply these MVCS (Model-View-Controller-Service) architecture rules when writing or reviewing code.

## Reference Files
- `src/common/services/base_service.py` — BaseService with generic CRUD
- `src/common/repositories/base_repository.py` — BaseRepository with FilterSpec
- `src/common/controllers/crud_router_factory.py` — Generic CRUD endpoint generation

## Layer Responsibilities

### Model (Entity) Layer
- SQLAlchemy entity definitions
- Database schema representation
- **Internal to the application** - never exposed outside service layer
- **Naming Convention**: Relationship names and `back_populates` MUST match target table names (e.g., `project` or `task` from `reference_code`).

### View (Schema) Layer
- Pydantic request/response schemas
- API contract definitions
- What clients see and send

### Controller Layer
- FastAPI endpoint handlers
- HTTP request/response handling
- Transaction management (commit happens here)
- Converts between HTTP and service calls

### Service Layer
- Business logic
- Orchestration
- **Bridges controller (schemas) and repository (entities)**
- Returns schemas, never entities

### Repository Layer
- Data access
- Database queries
- Returns entities to service layer

## Critical Architecture Rules

### 1. Services MUST NOT Expose Entities
```python
# WRONG - Exposing entity
def get_project(self, request) -> ProjectEntity:
    return self._repository.get_by_id(...)

# CORRECT - Return schema
def get_project(self, request) -> Optional[ProjectSchema]:
    entity = self._repository.get_by_id(...)
    if entity is None:
        return None
    return ProjectSchema.model_validate(entity)
```

### 2. Services MUST Delegate to Other Services
When a service needs data from another module, it MUST call that module's service, not its repository.

```python
# WRONG - Directly accessing another module's repository
class TaskService:
    def create_task(self, request):
        # Don't do this!
        project = ProjectRepository(self._session).get_by_id(...)

# CORRECT - Delegate to project service
class TaskService:
    def __init__(self, session):
        self._project_service = ProjectService(session)

    def create_task(self, request):
        project = self._project_service.get_project_by_id(...)
```

### 3. Transaction Management at Controller Level
```python
# Repository - NO commit
def create(self, entity):
    self._session.add(entity)
    self._session.flush()
    self._session.refresh(entity)
    return entity  # NO commit!

# Service - NO commit
def create_project(self, request):
    entity = ProjectEntity(...)
    created = self._repository.create(entity)
    return ProjectSchema.model_validate(created)  # NO commit!

# Controller - Commit via context manager
def _get_write_service():
    with db_session_manager.get_session(DbSessionType.WRITE) as session:
        yield ProjectService(session)
        # Session commits automatically for WRITE type
```

### 4. All Queries Must Be Scoped
Every database query MUST include tenant_id and bu_id:
```python
# Repository query (TenantBu mode — default)
query = self._session.query(ProjectEntity).filter_by(
    tenant_id=tenant_id,
    bu_id=bu_id
)
```

## Data Flow

```
Request → Controller → Service → Repository → Database
                ↓          ↓           ↓
             Schema     Entity      Entity
                ↑          ↓           ↑
Response ← Controller ← Service ← Repository
                ↑
             Schema (converted from Entity)
```

## Questions to Ask Before Implementing

From `service-layer-architecture-compliance.mdc`:

1. "Should I use an existing service method for this operation?"
2. "What are the correct scoping parameters (tenant_id, bu_id) for this lookup?"
3. "Is there an updated service method that supports the functionality I need?"

## Never Assume

- That direct database queries are acceptable without confirmation
- That service methods don't exist or are insufficient without checking
- That bypassing service layers is the right approach

## Compliance Checklist

- [ ] Services never return Entity objects
- [ ] Services delegate to other services (not repositories) for cross-module data
- [ ] Only controllers manage transactions (via session context manager)
- [ ] All queries include tenant_id and bu_id (or sub-entity ID for the active tenancy mode)
- [ ] Repository methods never call commit()
- [ ] Service methods never call commit()
- [ ] Entity-to-schema conversion happens in service layer
