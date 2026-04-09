---
feature: linkedout-crud
module: backend/src/linkedout
linked_files:
  - backend/src/linkedout/company/
  - backend/src/linkedout/company_alias/
  - backend/src/linkedout/crawled_profile/
  - backend/src/linkedout/role_alias/
  - backend/src/linkedout/experience/
  - backend/src/linkedout/education/
  - backend/src/linkedout/profile_skill/
  - backend/src/linkedout/connection/
  - backend/src/linkedout/contact_source/
  - backend/src/linkedout/import_job/
  - backend/src/linkedout/enrichment_event/
  - backend/src/linkedout/search_session/
  - backend/src/linkedout/search_tag/
  - backend/src/linkedout/funding/
  - backend/src/organization/enrichment_config/
version: 1
last_verified: "2026-04-09"
---

# LinkedOut CRUD Layer

**Created:** 2026-04-09 — Adapted from internal spec for LinkedOut OSS

## Intent

Provide full CRUD stacks (entity, repository, service, controller, schemas) for all LinkedOut domain entities plus EnrichmentConfig. All entities use BaseEntity for ID generation, timestamps, soft delete, audit fields, active flag, and version. Scoped entities additionally use TenantBuMixin for tenant/BU isolation. Shared entities (global data) inherit BaseEntity only.

## Entity Inventory

### Scoped Entities (TenantBuMixin + BaseEntity)

These entities have `tenant_id` and `bu_id` columns and route at `/tenants/{tenant_id}/bus/{bu_id}/...`:

| Entity | Module Path | Files |
|--------|-------------|-------|
| Connection | `backend/src/linkedout/connection/` | entity, repository, service, controller, schemas |
| ContactSource | `backend/src/linkedout/contact_source/` | entity, repository, service, controller, schemas |
| ImportJob | `backend/src/linkedout/import_job/` | entity, repository, service, controller, schemas |
| EnrichmentEvent | `backend/src/linkedout/enrichment_event/` | entity, repository, service, controller, schemas |
| SearchSession | `backend/src/linkedout/search_session/` | entity, repository, service, controller, schemas |
| SearchTurn | `backend/src/linkedout/search_session/` | entity, repository, service, controller, schemas (shares module with SearchSession) |
| SearchTag | `backend/src/linkedout/search_tag/` | entity, repository, service, controller, schemas |

### Shared Entities (BaseEntity only)

These entities are global data with no tenant/BU scoping and route at `/<entities>`:

| Entity | Module Path | Files |
|--------|-------------|-------|
| Company | `backend/src/linkedout/company/` | entity, repository, service, controller, schemas |
| CompanyAlias | `backend/src/linkedout/company_alias/` | entity, repository, service, controller, schemas |
| CrawledProfile | `backend/src/linkedout/crawled_profile/` | entity, repository, service, controller, schemas |
| RoleAlias | `backend/src/linkedout/role_alias/` | entity, repository, service, controller, schemas |
| Experience | `backend/src/linkedout/experience/` | entity, repository, service, controller, schemas |
| Education | `backend/src/linkedout/education/` | entity, repository, service, controller, schemas |
| ProfileSkill | `backend/src/linkedout/profile_skill/` | entity, repository, service, controller, schemas |
| FundingRound | `backend/src/linkedout/funding/` | entity, repository, service, controller, schemas |
| GrowthSignal | `backend/src/linkedout/funding/` | entity, repository, service, controller, schemas (shares module with FundingRound) |
| StartupTracking | `backend/src/linkedout/funding/` | entity, repository, service, controller, schemas (shares module with FundingRound) |

### Organization Entity (BaseEntity only, separate module)

| Entity | Module Path | Notes |
|--------|-------------|-------|
| EnrichmentConfig | `backend/src/organization/enrichment_config/` | Organization-level entity with `app_user_id` FK, not a LinkedOut domain entity |

### Non-CRUD Modules

These LinkedOut modules do not follow the standard CRUD pattern:

| Module | Path | Purpose |
|--------|------|---------|
| query_history | `backend/src/linkedout/query_history/` | Query logging and session management (formatters.py, query_logger.py, session_manager.py) — no entity/repo/service/controller |
| dashboard | `backend/src/linkedout/dashboard/` | Dashboard controller only |
| intelligence | `backend/src/linkedout/intelligence/` | Search and best-hop controllers |
| import_pipeline | `backend/src/linkedout/import_pipeline/` | Import orchestration controller |
| enrichment_pipeline | `backend/src/linkedout/enrichment_pipeline/` | Enrichment orchestration controller |

## Behaviors

### Entity Layer

- **Scoped entities inherit TenantBuMixin + BaseEntity**: Connection, ContactSource, ImportJob, EnrichmentEvent, SearchSession, SearchTurn, and SearchTag use TenantBuMixin for tenant/BU scoping. Each defines an `id_prefix` for nanoid generation and uses `Mapped`/`mapped_column` (SQLAlchemy 2.0). Verify all scoped entities have tenant_id and bu_id columns.

- **Shared entities inherit BaseEntity only**: Company, CompanyAlias, CrawledProfile, RoleAlias, Experience, Education, ProfileSkill, FundingRound, GrowthSignal, and StartupTracking are global data with no tenant/BU scoping. They inherit BaseEntity without TenantBuMixin. Verify shared entities have no tenant_id or bu_id columns.

- **Column conventions**: All columns have `comment` parameter. All datetime fields use `DateTime(timezone=True)`. JSON fields use `JSONB` (auto-compiled to SQLite JSON by the test compiler). Fields are organized into logical groups with descriptive comment headers. Verify field grouping matches the entity-creation-agent conventions.

- **Relationship naming**: Relationship attribute names and `back_populates` values match the target table name (singular or plural as appropriate). Verify all relationships follow this convention.

> Edge: EnrichmentConfig sits in `backend/src/organization/enrichment_config/`, not `backend/src/linkedout/`. It is an organization-level entity with an `app_user_id` FK, not a LinkedOut domain entity.

### Repository Layer

- **Scoped entities extend BaseRepository**: Connection, ContactSource, ImportJob, EnrichmentEvent, SearchSession, SearchTurn, and SearchTag extend `BaseRepository[TEntity, TSortEnum]` and define `_entity_class`, `_default_sort_field`, `_entity_name`, and `_get_filter_specs()`. No manual CRUD methods. Verify repositories are minimal configuration classes.

- **Shared entities use custom repositories**: Company, CompanyAlias, CrawledProfile, RoleAlias, Experience, Education, ProfileSkill, FundingRound, GrowthSignal, StartupTracking, and EnrichmentConfig use fully custom hand-written repositories that do NOT extend BaseRepository. Root cause: `BaseRepository._get_base_query()` requires `tenant_id` and `bu_id` parameters which shared entities lack.

- **FilterSpec-based filtering** (scoped entities): Repositories define filters declaratively using FilterSpec with types: `eq`, `in`, `ilike`, `bool`, `gte`, `lte`. Filter field names match API schema query parameter names. Verify all filterable fields have corresponding FilterSpecs.

### Service Layer

- **Scoped entities extend BaseService**: Connection, ContactSource, ImportJob, EnrichmentEvent, SearchSession, SearchTurn, and SearchTag extend `BaseService[TEntity, TSchema, TRepository]` and implement three abstract methods: `_extract_filter_kwargs()`, `_create_entity_from_request()`, `_update_entity_from_request()`. No manual CRUD methods. Services never call `commit()`. Verify services are minimal configuration classes.

- **Shared entities use custom services**: Company, CompanyAlias, CrawledProfile, RoleAlias, Experience, Education, ProfileSkill, FundingRound, GrowthSignal, StartupTracking, and EnrichmentConfig use fully custom hand-written services that do NOT extend BaseService. Same root cause as repositories: BaseService delegates to BaseRepository which requires tenant/BU.

### Controller Layer

- **CRUDRouterFactory usage**: RoleAlias, SearchSession, SearchTurn, and SearchTag use `CRUDRouterFactory` / `create_crud_router()`. The factory generates standard CRUD endpoints, handles error-to-HTTP-status mapping, and builds HATEOAS pagination links.

- **Custom controllers for remaining entities**: Company, CompanyAlias, CrawledProfile, Experience, Education, ProfileSkill, Connection, ContactSource, ImportJob, EnrichmentEvent, FundingRound, GrowthSignal, StartupTracking, and EnrichmentConfig use hand-written custom controllers.

- **Shared entity routes at root level**: Shared entities route at `/<entities>` (e.g., `/companies`, `/crawled-profiles`) without tenant/BU path parameters. Verify shared entity endpoints are accessible at root-level URLs.

- **Scoped entity routes with tenant/BU**: Scoped entities route at `/tenants/{tenant_id}/bus/{bu_id}/<entities>`. Verify scoped entity endpoints require tenant_id and bu_id path parameters.

- **Standard endpoints**: Most entities expose up to six endpoints: list (GET), create (POST), bulk create (POST /bulk), get-by-id (GET /{id}), update (PATCH /{id}), and delete (DELETE /{id}). Exception: funding entities (FundingRound, GrowthSignal, StartupTracking) have 5 endpoints (no bulk create) due to their hand-written controller pattern.

- **Read/write session separation**: Controllers use `create_service_dependency(Service, DbSessionType.READ)` for GET endpoints and `DbSessionType.WRITE` for POST/PATCH/DELETE. Verify read endpoints use read sessions and write endpoints use write sessions.

- **META_FIELDS for pagination links**: Each controller defines `_META_FIELDS` listing all filter query parameters (excluding tenant_id, bu_id, limit, offset). These are echoed in the response meta and forwarded into pagination link generation. Verify pagination links preserve filter parameters.

### Schema Layer

- **Two-file schema pattern**: Each entity has `<entity>_schema.py` (core schema with `ConfigDict(from_attributes=True)`) and `<entities>_api_schema.py` (all request/response schemas). Enum types are defined inline or in the core schema file. Verify both files exist per entity.

- **API schema conventions**: All CRUD request/response schemas present. `SortByFields` enum defines allowed sort columns. List filters use `Query()` for multi-value params. Path params are Optional with None default. Fields use `Annotated[type, Field(description=...)]`. Verify all fields have descriptions.

- **Field grouping**: Schema fields organized into logical groups with comment headers matching entity structure (Identifiers, Basic Information, Status, etc.). Verify grouping follows schema-creation-agent conventions.

## Decisions

### Custom stack for shared entities — 2026-03-27
**Chose:** Hand-written repositories and services for shared entities
**Over:** Extending BaseRepository/BaseService
**Because:** BaseRepository requires tenant_id and bu_id on all queries via `_get_base_query()`. Shared entities are global with no tenant scoping. This is a known deviation from the agent-defined standard. Resolution requires a tenant-agnostic base variant.

### CRUDRouterFactory for newer entities — 2026-04-09
**Chose:** CRUDRouterFactory for RoleAlias, SearchSession, SearchTurn, SearchTag
**Over:** Custom controllers for all entities
**Because:** These entities were added later and adopted the factory pattern. Older entities retain custom controllers for backward compatibility.

### SQLite-compatible column types — 2026-03-27
**Chose:** Text placeholders for ARRAY, TSVECTOR, vector columns on entities
**Over:** PostgreSQL-specific types directly on entity classes
**Because:** Unit tests use SQLite in-memory databases. PostgreSQL-specific types are applied in Alembic migrations only. JSONB is the exception — the codebase has a custom SQLAlchemy compiler that translates JSONB to JSON for SQLite.

### SearchSession/SearchTurn replace SearchHistory — 2026-04-09
**Chose:** Two entities (SearchSession + SearchTurn) in `search_session/` module
**Over:** Single SearchHistory entity
**Because:** Conversational search requires session-level grouping of individual turns with their own lifecycle. SearchHistory was split into the session/turn pair.

## Not Included

- Business logic beyond CRUD (affinity computation, dedup pipeline, import orchestration)
- Search endpoints (vector search, full-text search — these live in `backend/src/linkedout/intelligence/`)
- Bulk import/export endpoints
- Rate limiting or throttling
- Field-level authorization (all fields readable/writable by any authenticated user)
- Tenant-agnostic BaseRepository/BaseService variants (needed to close the shared entity deviation)
- CRUDRouterFactory variant for root-level routes (needed for shared entity controllers that still use custom controllers)
