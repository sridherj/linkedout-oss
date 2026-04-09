---
feature: mvcs-base-stack
module: backend/src/common
linked_files:
  - backend/src/common/entities/base_entity.py
  - backend/src/common/entities/soft_delete_mixin.py
  - backend/src/common/entities/tenant_bu_mixin.py
  - backend/src/common/repositories/base_repository.py
  - backend/src/common/services/base_service.py
  - backend/src/common/controllers/crud_router_factory.py
  - backend/src/common/schemas/base_request_schema.py
  - backend/src/common/schemas/base_response_schema.py
  - backend/src/common/schemas/base_enums_schemas.py
  - backend/src/common/schemas/crud_schema_mixins.py
version: 1
last_verified: "2026-04-09"
---

# MVCS Base Stack

**Created:** 2026-04-09 — Adapted from internal spec for LinkedOut OSS

## Intent

Provide a generic, type-safe MVCS (Model-View-Controller-Service) base stack that makes adding new CRUD entities low-effort while allowing clean escape hatches for non-trivial orchestration. The base classes enforce consistent patterns for ID generation, timestamps, soft delete, filtering, pagination, sorting, and session management.

## Behaviors

### BaseEntity

- **Prefixed nanoid generation**: A subclass defines `id_prefix` as a class variable. When a new entity is created, the primary key is auto-generated as a nanoid with that prefix via `Nanoid.make_nanoid_with_prefix()`. If `id_prefix` is None, a plain nanoid is generated. Verify the ID starts with the prefix string.

- **Auto table name**: A subclass named `FooBarEntity` without an explicit `__tablename__` gets table name `foo_bar` (CamelCase to snake_case, Entity suffix stripped). Verify the generated table name matches the expected snake_case form.

- **Standard timestamp fields**: Every entity inherits `created_at` and `updated_at` columns defaulting to UTC now. On update, `updated_at` is automatically refreshed via SQLAlchemy `onupdate`. Verify both timestamps are populated after creation and `updated_at` changes after modification.

- **Soft delete fields**: Every entity inherits `deleted_at` (nullable datetime), `archived_at` (nullable datetime), and `is_active` (boolean, default True). These fields are always present but the base CRUD stack does not use them — default delete is a hard delete. Entities that need soft delete opt into `SoftDeleteMixin`, which adds `soft_delete()`, `restore()`, and `is_deleted`. The mixin sets `is_active = False` on soft delete and `is_active = True` on restore. Verify that a non-mixin entity is physically removed on delete.

- **Audit and metadata fields**: Every entity inherits `created_by`, `updated_by` (nullable strings), `version` (integer, default 1), `source` (nullable string), and `notes` (nullable text). Verify defaults are applied on creation.

### TenantBuMixin

- **Multi-tenancy scoping**: Entities that belong to a tenant and business unit use `TenantBuMixin`, which adds `tenant_id` (FK to `tenant.id`) and `bu_id` (FK to `bu.id`). Both are non-nullable. The mixin also creates SQLAlchemy relationships with backrefs to `TenantEntity` and `BuEntity`. Verify that creating an entity without `tenant_id` or `bu_id` raises an error.

### BaseRepository

- **Tenant-BU scoped queries**: All read operations (`list_with_filters`, `get_by_id`, `get_by_ids`, `count_with_filters`) require `tenant_id` and `bu_id` parameters. The base query always filters by both. Verify queries never return entities from other tenants or BUs.

- **FilterSpec-based filtering**: A subclass defines `_get_filter_specs()` returning a list of `FilterSpec` objects. Each spec maps a filter parameter to a filter type (`eq`, `in`, `ilike`, `bool`, `gte`, `lte`, `jsonb_overlap`). Verify that passing a filter value applies the correct SQL predicate.

- **Built-in is_active filter**: `list_with_filters` and `count_with_filters` accept `is_active` as a first-class parameter separate from FilterSpec. When provided, it adds a direct `is_active = value` predicate to the base query. When `None`, no active filter is applied. Verify passing `is_active=True` excludes soft-deleted entities and `is_active=None` returns all records regardless of active status.

- **Pagination and sorting**: `list_with_filters` accepts `limit`, `offset`, `sort_by` (enum), and `sort_order` (ASC/DESC). The subclass defines `_default_sort_field`. Verify results respect limit/offset and sort order.

- **Batch fetch by IDs**: `get_by_ids` accepts a list of entity IDs and returns all matching entities in a single query. An empty list returns an empty result. Verify the count of returned entities matches the number of existing IDs.

- **Create with flush**: `create()` adds the entity, flushes (to generate the ID), and refreshes. It does not commit — commit is the caller's responsibility. Asserts that `tenant_id` and `bu_id` are set. Verify the entity has an ID after create but the transaction is uncommitted.

- **Update with merge**: `update()` merges the entity, flushes, and refreshes. Verify changed fields are persisted after the caller commits.

- **Hard delete**: `delete()` removes the entity from the session. It does not flush or commit. Verify the entity is gone after commit.

### BaseService

- **Generic CRUD orchestration**: `BaseService[TEntity, TSchema, TRepository]` provides `list_entities`, `create_entity`, `update_entity`, `get_entity_by_id`, `delete_entity_by_id`, and `create_entities_bulk`. Each method delegates to the repository and converts results to Pydantic schemas via `model_validate`. Verify all operations produce correct schema outputs.

- **Subclass contract**: Subclasses must implement `_extract_filter_kwargs`, `_create_entity_from_request`, and `_update_entity_from_request`. The base class enforces this via `@abstractmethod`. Verify that instantiating a subclass without these methods raises TypeError.

- **Bulk create**: `create_entities_bulk` iterates over items in the request (attribute name defaults to `{entity_name}s`, overridable via `_bulk_items_attr`), sets `tenant_id` and `bu_id` from the parent request, creates each entity, and returns a list of schemas. Verify all items are created with the correct tenant/BU scoping.

- **Entity not found on update/delete**: When `update_entity` or `delete_entity_by_id` cannot find the entity, a `ValueError` is raised. Verify the error message includes the entity ID.

- **Explicit commit**: The service exposes a `commit()` method that calls `session.commit()`. The CRUD methods do not auto-commit — the controller layer (via write session context manager) handles commit.

### CRUDRouterFactory

- **Six standard endpoints**: `create_crud_router(config)` returns a `CRUDRouterResult` with `router`, `get_service`, and `get_write_service`. The router exposes GET (list), POST (create, 201), POST /bulk (bulk create, 201), GET /{id} (get by ID), PATCH /{id} (update), DELETE /{id} (delete, 204 No Content). Expose `get_service` / `get_write_service` in the controller module so tests can use `app.dependency_overrides`. Verify all six routes are registered and status codes are correct.

- **Session type routing**: List and get-by-id use READ sessions (via `_get_service`). Create, bulk create, update, and delete use WRITE sessions (via `_get_write_service`). The session is obtained from `db_session_manager.get_session()`. Verify read endpoints do not commit and write endpoints do commit.

- **Paginated list response**: The list endpoint returns items, total count, limit, offset, page_count, HATEOAS links, and meta fields. Verify pagination math is correct (page_count = ceil(total/limit)).

- **Auth dependency support**: `CRUDRouterConfig.auth_dependency` optionally wires a dependency at the router level. Verify that when set, all endpoints require the auth dependency.

- **404 on missing entity**: Get-by-id returns HTTP 404 when the entity is not found. Update returns 404 when `ValueError` is raised. Delete returns 404 when `ValueError` is raised. Verify the status code and error detail message.

- **Dynamic path parameter injection**: Update, get-by-id, and delete endpoints use `_inject_path_param()` to dynamically add the entity ID path parameter (e.g., `{lot_id}`) to the function signature, since the parameter name is only known at config time. The function body reads the value via `request.path_params[config.entity_id_param]`.

> Edge: Empty list returns 200 with an empty items array, total=0, page_count=1 (not 0), and `links=None`. Non-empty lists always include HATEOAS links.

### Base Schemas

- **PaginateRequestSchema**: Extends `BaseRequestSchema` with `limit` (1-100, default 20) and `offset` (>=0, default 0). Verify validation rejects limit=0 or limit=101.

- **BaseRequestSchema with auth context**: Every request schema can carry an optional `AuthContext`. Verify it defaults to None when auth is not injected.

- **CRUD schema mixins**: `TenantBuRequestMixin` provides optional `tenant_id`/`bu_id` fields (populated by the controller from path params). `SortableRequestMixin` provides `sort_order` (ASC/DESC). `ActiveFilterMixin` provides `is_active` filter. These are composed into entity-specific list request schemas.

## Decisions

| Date | Decision | Chose | Over | Because |
|------|----------|-------|------|---------|
| 2026-03-25 | Filter types | Dataclass FilterSpec with 7 filter types | Dynamic filter builder | Explicit specs are easier to audit and test |
| 2026-03-25 | Commit responsibility | Repository flushes, caller commits | Repository auto-commits | Allows service-level transaction boundaries |
| 2026-03-25 | Schema conversion | model_validate in service layer | Manual dict mapping | Pydantic v2 from_attributes handles ORM objects directly |

## Not Included

- Optimistic locking enforcement (version field exists but is not checked on update)
- Soft delete filtering in base query (callers must filter on is_active explicitly)
- Nested/join eager loading in base repository
- Async repository/service variants
