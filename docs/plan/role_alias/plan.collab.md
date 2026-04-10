# Plan: RoleAlias CRUD Implementation

## Summary

Create a complete CRUD implementation for the `role_alias` entity in the LinkedOut module.
This is a **SHARED entity** (no tenant/BU scoping) -- uses only `BaseEntity`, not `TenantBuMixin`.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /role-aliases | List with filters and pagination |
| POST | /role-aliases | Create single role alias |
| POST | /role-aliases/bulk | Create multiple role aliases |
| GET | /role-aliases/{role_alias_id} | Get by ID |
| PATCH | /role-aliases/{role_alias_id} | Update |
| DELETE | /role-aliases/{role_alias_id} | Delete |

## Filters (for List endpoint)

| Filter | Type | Description |
|--------|------|-------------|
| alias_title | ilike | Search in alias_title |
| canonical_title | ilike | Search in canonical_title |
| seniority_level | eq | Filter by seniority level |
| function_area | eq | Filter by function area |

## Sort Fields

alias_title, canonical_title, created_at

## Entity Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str | auto (prefix: ra) | Unique identifier |
| alias_title | str | YES, UNIQUE | The alias job title |
| canonical_title | str | YES | The canonical/standard title |
| seniority_level | str | nullable | Seniority level |
| function_area | str | nullable | Functional area |

## Key Design Decisions

1. **No TenantBuMixin** -- entity extends only BaseEntity
2. **Custom controller** -- CRUDRouterFactory hardcodes tenant_id/bu_id path params, so we hand-write the controller
3. **Custom repository** -- overrides BaseRepository methods to remove tenant_id/bu_id assertions
4. **Custom service** -- overrides BaseService methods to remove tenant_id/bu_id assertions
5. **URL prefix**: /role-aliases (no tenant/BU in path)

## Files to Create

### Source Files
- src/linkedout/role_alias/__init__.py
- src/linkedout/role_alias/entities/__init__.py
- src/linkedout/role_alias/entities/role_alias_entity.py
- src/linkedout/role_alias/schemas/__init__.py
- src/linkedout/role_alias/schemas/role_alias_schema.py
- src/linkedout/role_alias/schemas/role_alias_api_schema.py
- src/linkedout/role_alias/repositories/__init__.py
- src/linkedout/role_alias/repositories/role_alias_repository.py
- src/linkedout/role_alias/services/__init__.py
- src/linkedout/role_alias/services/role_alias_service.py
- src/linkedout/role_alias/controllers/__init__.py
- src/linkedout/role_alias/controllers/role_alias_controller.py

### Files to Modify (Registrations)
- src/common/entities/base_entity.py (TableName enum)
- migrations/env.py (entity import)
- src/dev_tools/db/validate_orm.py (entity import + ALL_ENTITIES + ENTITY_PACKAGES)
- main.py (router import + include_router)
- conftest.py (entity import)
- tests/integration/conftest.py (entity import)
- src/shared/test_utils/entity_factories.py (factory method)
- src/shared/test_utils/seeders/base_seeder.py (seeder method)
- src/dev_tools/db/fixed_data.py (fixed seed data)

### Test Files
- tests/linkedout/__init__.py
- tests/linkedout/role_alias/__init__.py
- tests/linkedout/role_alias/repositories/__init__.py
- tests/linkedout/role_alias/repositories/test_role_alias_repository.py
- tests/linkedout/role_alias/services/__init__.py
- tests/linkedout/role_alias/services/test_role_alias_service.py
- tests/linkedout/role_alias/controllers/__init__.py
- tests/linkedout/role_alias/controllers/test_role_alias_controller.py
- tests/integration/linkedout/__init__.py
- tests/integration/linkedout/test_role_alias_controller.py

## Execution Phases

- [ ] Phase 1: Entity creation + registrations
- [ ] Phase 2: Schemas (core + API)
- [ ] Phase 3: Repository + repository tests
- [ ] Phase 4: Service + service tests
- [ ] Phase 5: Controller + controller tests
- [ ] Phase 6: Seeding + integration tests
