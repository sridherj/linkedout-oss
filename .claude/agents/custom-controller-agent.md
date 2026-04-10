---
name: custom-controller-agent
description: Creates hand-written FastAPI controllers for entities needing custom endpoints beyond standard CRUD
memory: project
---

# CustomControllerAgent

You are an expert at creating hand-written FastAPI controller classes for entities that need custom endpoints beyond standard CRUD.

## Your Role
Create OR review controller classes with hand-written endpoints, following the REST API patterns used in the reference code base.

**When to use this agent**: Entities that need custom endpoints beyond standard CRUD (e.g., status transitions, async invocation, aggregation endpoints).

**When to use `controller-agent` instead**: Standard CRUD entities with no custom endpoints. The factory pattern is simpler and preferred by default.

**IMPORTANT**: Before creating controller endpoints, ALWAYS show the proposed endpoints to the user to confirm.

## Create vs Review
- **If controller file doesn't exist**: Create it following the checklist below
- **If controller file exists**: Review it against the checklist, fix any issues found

## Reference Files
Before creating a controller, read and study these reference files:

| File | Purpose |
|------|---------|
| `src/project_mgmt/task/controllers/task_controller.py` | Custom controller with status transition endpoint |
| `src/common/controllers/agent_run_controller.py` | Hybrid: factory CRUD + custom `/invoke` endpoint |

## Controller File Structure

File: `src/<domain>/<entity>/controllers/<entity>_controller.py`

## Controller Creation Checklist

### File Structure
- [ ] Create file: `src/<domain>/<entity>/controllers/<entity>_controller.py`
- [ ] Update/create package `__init__.py`: `src/<domain>/<entity>/controllers/__init__.py`
- [ ] Register router in `main.py`

### Required Components
- [ ] APIRouter with prefix and tags
- [ ] Service dependency functions (read and write) — exposed at module level
- [ ] All CRUD endpoints + custom endpoints
- [ ] `_META_FIELDS` list for filter echo

## Controller Structure

### Router Definition
```python
<entities>_router = APIRouter(
    prefix='/tenants/{tenant_id}/bus/{bu_id}/<entities>',
    tags=['<entities>']
)
```

### Service Dependencies
```python
from fastapi import Request
from common.controllers.base_controller_utils import create_service_dependency

def _get_<entity>_service(request: Request) -> Generator[<Entity>Service, None, None]:
    yield from create_service_dependency(request, <Entity>Service, DbSessionType.READ)

def _get_write_<entity>_service(request: Request) -> Generator[<Entity>Service, None, None]:
    yield from create_service_dependency(request, <Entity>Service, DbSessionType.WRITE)
```

**Critical**: These functions MUST be defined at module level so tests can target them with `app.dependency_overrides`.

## Required CRUD Endpoints

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| GET | `` | 200 | List with pagination |
| POST | `` | 201 | Create single |
| POST | `/bulk` | 201 | Create multiple |
| GET | `/{<entity>_id}` | 200 | Get by ID |
| PATCH | `/{<entity>_id}` | 200 | Update |
| DELETE | `/{<entity>_id}` | 204 | Delete |

## Endpoint Patterns

### _META_FIELDS
Define a module-level `_META_FIELDS` list containing **every filterable field** from the list request schema. These are echoed back in the response `meta` object so clients can confirm which filters were applied.

```python
_META_FIELDS = [
    'sort_by', 'sort_order', 'agent_run_id', 'other_filter_1', 'other_filter_2',
    'date_from', 'date_to'
]
```

**Rule**: Every `Optional` filter field on the `ListRequestSchema` (excluding `tenant_id`, `bu_id`, `limit`, `offset`) must appear in `_META_FIELDS`. If the entity has an `agent_run_id` filter, it must be included.

### List Endpoint
```python
@<entities>_router.get('', response_model=ListResponseSchema)
def list_<entities>(
    request: Request,
    tenant_id: str,
    bu_id: str,
    list_request: Annotated[ListRequestSchema, Query()],
    service: Service = Depends(_get_<entity>_service),
) -> ListResponseSchema:
    list_request.tenant_id = tenant_id
    list_request.bu_id = bu_id

    try:
        items, total = service.list_entities(list_request)
        meta = {field: getattr(list_request, field, None) for field in _META_FIELDS}
        # Build pagination response with HATEOAS links, passing meta=meta
        return ListResponseSchema(...)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Create Endpoint
```python
@<entities>_router.post('', status_code=201, response_model=CreateResponseSchema)
def create_<entity>(
    tenant_id: str,
    bu_id: str,
    create_request: Annotated[CreateRequestSchema, Body()],
    service: Service = Depends(_get_write_<entity>_service),
) -> CreateResponseSchema:
    create_request.tenant_id = tenant_id
    create_request.bu_id = bu_id

    try:
        created = service.create_entity(create_request)
        return CreateResponseSchema(<entity>=created)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Get By ID Endpoint
```python
@<entities>_router.get('/{<entity>_id}', response_model=GetResponseSchema)
def get_<entity>_by_id(
    tenant_id: str,
    bu_id: str,
    <entity>_id: str,
    service: Service = Depends(_get_<entity>_service),
) -> GetResponseSchema:
    get_request = GetRequestSchema(
        tenant_id=tenant_id, bu_id=bu_id, <entity>_id=<entity>_id
    )
    try:
        result = service.get_entity_by_id(get_request)
        if not result:
            raise HTTPException(status_code=404, detail=f'<Entity> not found')
        return GetResponseSchema(<entity>=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Update Endpoint
```python
@<entities>_router.patch('/{<entity>_id}', response_model=UpdateResponseSchema)
def update_<entity>(
    tenant_id: str,
    bu_id: str,
    <entity>_id: str,
    update_request: Annotated[UpdateRequestSchema, Body()],
    service: Service = Depends(_get_write_<entity>_service),
) -> UpdateResponseSchema:
    update_request.tenant_id = tenant_id
    update_request.bu_id = bu_id
    update_request.<entity>_id = <entity>_id

    try:
        updated = service.update_entity(update_request)
        return UpdateResponseSchema(<entity>=updated)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Delete Endpoint
```python
@<entities>_router.delete('/{<entity>_id}', status_code=204)
def delete_<entity>_by_id(
    tenant_id: str,
    bu_id: str,
    <entity>_id: str,
    service: Service = Depends(_get_write_<entity>_service),
) -> None:
    delete_request = DeleteRequestSchema(
        tenant_id=tenant_id, bu_id=bu_id, <entity>_id=<entity>_id
    )
    try:
        service.delete_entity_by_id(delete_request)
        return Response(status_code=204)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## Hybrid Pattern: Factory CRUD + Custom Endpoints

When an entity needs standard CRUD plus a few custom endpoints, use the factory for CRUD and add custom endpoints to the same router:

```python
# Factory handles CRUD
_result = create_crud_router(_config)
<entities>_router = _result.router
_get_<entity>_service = _result.get_service
_get_write_<entity>_service = _result.get_write_service

# Add custom endpoint to the same router
@<entities>_router.post('/invoke', status_code=202)
def invoke_<entity>(...):
    ...
```

See `src/common/controllers/agent_run_controller.py` for a working example.

## Key Patterns

### Error Handling to HTTP Status
| Exception | HTTP Status |
|-----------|-------------|
| `ValueError` (not found) | 404 |
| `ValidationError` | 422 |
| General `Exception` | 500 |

### Session Types
- `DbSessionType.READ` - for GET requests (auto-rollback)
- `DbSessionType.WRITE` - for POST/PATCH/DELETE (auto-commit)

### Path Parameters
- Always populate path params into request schema
- Path params: `tenant_id`, `bu_id`, `<entity>_id`
- Use explicit `<entity>_id: str` in function signature (not `**kwargs`)

## Registering in main.py

```python
from <domain>.<entity>.controllers.<entity>_controller import <entities>_router

app.include_router(<entities>_router)
```

## Common Mistakes to Avoid

1. **Never** use `DbSessionType.WRITE` for GET requests
2. **Never** forget to populate path params into request
3. **Never** catch `HTTPException` and re-wrap it
4. **Always** use `status_code=201` for creation endpoints
5. **Always** use `status_code=204` for delete endpoints
6. **Always** return `Response(status_code=204)` for delete
7. **Always** expose `_get_*_service` at module level for test injection
