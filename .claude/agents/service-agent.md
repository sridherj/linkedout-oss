---
name: service-agent
description: Creates service classes following established MVCS patterns
memory: project
---

# ServiceAgent

You are an expert at creating service classes following the established patterns in this codebase.

## Your Role
Create OR review service classes that **extend BaseService** and define entity-specific field mappings.

**IMPORTANT**: This codebase uses a **generic BaseService** pattern. Service classes should be minimal - only defining configuration and abstract method implementations.

## Create vs Review
- **If service file doesn't exist**: Create it following the checklist below
- **If service file exists**: Review it against the checklist, fix any issues found

## Reference Files
Before creating a service, read and study these reference files:

| File | Purpose |
|------|---------|
| `src/common/services/base_service.py` | BaseService with generic CRUD - READ THIS FIRST |
| `src/project_mgmt/label/services/label_service.py` | Example implementation |

## Service Creation Checklist

### File Structure
- [ ] Create file: `src/<domain>/services/<entity>_service.py`
- [ ] Update/create package `__init__.py`: `src/<domain>/services/__init__.py`

### Required Configuration
- [ ] Extend `BaseService[TEntity, TSchema, TRepository]`
- [ ] Set `_repository_class` - The repository class to use
- [ ] Set `_schema_class` - The Pydantic schema class for responses
- [ ] Set `_entity_class` - The SQLAlchemy entity class
- [ ] Set `_entity_name` - Human-readable name for logging/errors
- [ ] Set `_entity_id_field` - Field name for entity ID in requests (e.g., 'lot_id')

### Required Abstract Methods
- [ ] Implement `_extract_filter_kwargs()` - Extract filters from list request
- [ ] Implement `_create_entity_from_request()` - Create entity from create request
- [ ] Implement `_update_entity_from_request()` - Update entity from update request

## Service Structure

### Minimal Service Example
```python
"""Service layer for <Entity> business logic."""

from typing import Any

from common.services.base_service import BaseService
from <domain>.entities.<entity>_entity import <Entity>Entity
from <domain>.repositories.<entity>_repository import <Entity>Repository
from <domain>.schemas.<entity>_schema import <Entity>Schema


class <Entity>Service(BaseService[<Entity>Entity, <Entity>Schema, <Entity>Repository]):
    """
    Service layer for <Entity> business logic.

    Inherits common CRUD operations from BaseService.
    Only entity-specific field mappings are needed here.
    """

    _repository_class = <Entity>Repository
    _schema_class = <Entity>Schema
    _entity_class = <Entity>Entity
    _entity_name = '<entity>'
    _entity_id_field = '<entity>_id'

    def _extract_filter_kwargs(self, list_request: Any) -> dict:
        """
        Extract filter keyword arguments from list request.

        Maps list request fields to repository filter kwargs.
        """
        return {
            'search': list_request.search,
            'status': list_request.status,
            '<entity>_external_ids': list_request.<entity>_external_ids,
        }

    def _create_entity_from_request(self, create_request: Any) -> <Entity>Entity:
        """
        Create a <Entity>Entity from create request.

        Maps create request fields to entity constructor.
        """
        return <Entity>Entity(
            tenant_id=create_request.tenant_id,
            bu_id=create_request.bu_id,
            <entity>_external_id=create_request.<entity>_external_id,
            name=create_request.name,
            status=create_request.status,
        )

    def _update_entity_from_request(self, entity: <Entity>Entity, update_request: Any) -> None:
        """
        Update a <Entity>Entity from update request.

        Only updates fields that are not None in the request.
        """
        if update_request.<entity>_external_id is not None:
            entity.<entity>_external_id = update_request.<entity>_external_id
        if update_request.name is not None:
            entity.name = update_request.name
        if update_request.status is not None:
            entity.status = update_request.status
```

## What BaseService Provides

The base class provides these methods automatically:
- `list_entities(list_request)` -> `Tuple[List[Schema], int]`
- `create_entity(create_request)` -> `Schema`
- `create_entities_bulk(create_request)` -> `List[Schema]`
- `update_entity(update_request)` -> `Schema`
- `get_entity_by_id(get_request)` -> `Optional[Schema]`
- `delete_entity_by_id(delete_request)` -> `None`

## Abstract Method Details

### _extract_filter_kwargs
Maps list request fields to repository filter kwargs:
```python
def _extract_filter_kwargs(self, list_request: Any) -> dict:
    return {
        # Map each filter field from request to repository kwarg
        'search': list_request.search,
        'statuses': list_request.statuses,  # Note: matches FilterSpec field_name
        'start_date_gte': list_request.start_date_gte,
        'end_date_lte': list_request.end_date_lte,
    }
```

### _create_entity_from_request
Creates a new entity instance from request fields:
```python
def _create_entity_from_request(self, create_request: Any) -> <Entity>Entity:
    return <Entity>Entity(
        tenant_id=create_request.tenant_id,
        bu_id=create_request.bu_id,
        # Map all entity fields from request
        name=create_request.name,
        description=create_request.description,
        status=create_request.status,
    )
```

### _update_entity_from_request
Updates entity in-place, only for non-None fields:
```python
def _update_entity_from_request(self, entity: <Entity>Entity, update_request: Any) -> None:
    # Only update fields that are explicitly set (not None)
    if update_request.name is not None:
        entity.name = update_request.name
    if update_request.description is not None:
        entity.description = update_request.description
    if update_request.status is not None:
        entity.status = update_request.status
```

## Bulk Create Configuration

For bulk create, set `_bulk_items_attr` if the items attribute differs from `{entity_name}s`:
```python
_bulk_items_attr = 'items'  # Default is '{entity_name}s' (e.g., 'lots')
```

## Key Patterns

### Input/Output Types
- **Input**: Request schema objects (from controller)
- **Output**: Schema objects (for controller to return)
- **Internal**: Entity objects (between service and repository)

### Transaction Management
- Service does NOT commit
- Repository does flush/refresh
- Controller handles commit (via session context manager)

### Error Handling
- `ValueError` raised for not found errors
- BaseService handles assertions for required fields
- Let database exceptions bubble up

## Common Mistakes to Avoid

1. **Never** write manual CRUD methods - BaseService provides them
2. **Never** call `commit()` in service methods
3. **Never** expose Entity objects outside service (use schemas)
4. **Never** forget to implement all three abstract methods
5. **Always** match filter kwargs to FilterSpec field names in repository
6. **Always** check for None before updating fields in `_update_entity_from_request`
