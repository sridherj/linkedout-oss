# Plan: Company CRUD Implementation

## Key Architectural Decision

Company is a **SHARED entity** -- it does NOT use TenantBuMixin. This has major implications:

1. **BaseRepository** hardcodes `tenant_id`/`bu_id` in _get_base_query, list_with_filters, count_with_filters, create, get_by_id, update (all with asserts). Company repository must **override** these methods to remove tenant/bu scoping.
2. **BaseService** hardcodes `tenant_id`/`bu_id` asserts in list_entities, create_entity, create_entities_bulk, update_entity, get_entity_by_id, delete_entity_by_id. Company service must **override** these methods.
3. **CRUDRouterFactory** hardcodes `tenant_id`/`bu_id` path params in all endpoints. **Cannot use it.** Must use **custom controller** pattern (like project_controller.py).
4. **ARRAY(String) for enrichment_sources** -- PostgreSQL-specific type. Need SQLite compatibility in conftest.py (similar to existing JSONB->JSON pattern).

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /companies | List with filters and pagination |
| POST | /companies | Create single company |
| POST | /companies/bulk | Create multiple companies |
| GET | /companies/{company_id} | Get company by ID |
| PATCH | /companies/{company_id} | Update company |
| DELETE | /companies/{company_id} | Delete company |

## Filters (for List endpoint)

| Filter | Type | Description |
|--------|------|-------------|
| canonical_name | ilike | Search in canonical_name |
| domain | ilike | Search in domain |
| industry | eq | Filter by industry |
| size_tier | eq | Filter by size_tier |
| hq_country | eq | Filter by hq_country |
| company_ids | in | Filter by list of IDs |

## Sort Fields

| Field | Description |
|-------|-------------|
| canonical_name | Sort by canonical name (default) |
| created_at | Sort by creation date |
| industry | Sort by industry |
| size_tier | Sort by size tier |

## Entity Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (co_*) | auto | Unique identifier |
| canonical_name | str | required | UNIQUE canonical name |
| normalized_name | str | required | Normalized name |
| linkedin_url | str | nullable | LinkedIn company URL |
| universal_name | str | nullable | LinkedIn universal name |
| website | str | nullable | Company website |
| domain | str | nullable | Company domain |
| industry | str | nullable | Industry |
| founded_year | int | nullable | Year founded |
| hq_city | str | nullable | HQ city |
| hq_country | str | nullable | HQ country |
| employee_count_range | str | nullable | Employee count range |
| estimated_employee_count | int | nullable | Estimated employee count |
| size_tier | str | nullable | tiny/small/mid/large/enterprise |
| network_connection_count | int | default 0 | Network connection count |
| parent_company_id | str | nullable | Self-referential FK to company.id |
| enrichment_sources | list[str] | nullable | PostgreSQL ARRAY of TEXT |
| enriched_at | datetime | nullable | Enrichment timestamp |

## Indexes

- ix_co_canonical UNIQUE on canonical_name
- ix_co_domain on domain
- ix_co_industry on industry
- ix_co_size_tier on size_tier

## Files to Create

### Source Files
- src/linkedout/company/__init__.py
- src/linkedout/company/entities/__init__.py
- src/linkedout/company/entities/company_entity.py
- src/linkedout/company/schemas/__init__.py
- src/linkedout/company/schemas/company_schema.py
- src/linkedout/company/schemas/company_api_schema.py
- src/linkedout/company/repositories/__init__.py
- src/linkedout/company/repositories/company_repository.py
- src/linkedout/company/services/__init__.py
- src/linkedout/company/services/company_service.py
- src/linkedout/company/controllers/__init__.py
- src/linkedout/company/controllers/company_controller.py

### Files to Modify
- migrations/env.py (add entity import)
- src/dev_tools/db/validate_orm.py (add entity import)
- conftest.py (add entity import + ARRAY->JSON compile for SQLite)
- src/common/entities/base_entity.py (add COMPANY to TableName)
- src/shared/test_utils/entity_factories.py (add create_company)
- src/shared/test_utils/seeders/base_seeder.py (add _seed_company)
- src/dev_tools/db/fixed_data.py (add FIXED_COMPANIES)
- tests/seed_db.py (add COMPANY to TableName)
- main.py (register companies_router)

### Test Files
- tests/linkedout/__init__.py
- tests/linkedout/company/__init__.py
- tests/linkedout/company/repositories/__init__.py
- tests/linkedout/company/repositories/test_company_repository.py
- tests/linkedout/company/services/__init__.py
- tests/linkedout/company/services/test_company_service.py
- tests/linkedout/company/controllers/__init__.py
- tests/linkedout/company/controllers/test_company_controller.py

## Execution Phases

- [ ] Phase 1: Entity creation
- [ ] Phase 2: Schemas (core + API)
- [ ] Phase 3: Repository + Tests
- [ ] Phase 4: Service + Tests
- [ ] Phase 5: Controller (Custom) + Tests
- [ ] Phase 6: Infrastructure (seeding, registrations)
- [ ] Phase 7: Compliance check
