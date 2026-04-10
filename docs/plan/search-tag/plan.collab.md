# Plan: SearchTag CRUD Implementation

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /tenants/{t}/bus/{b}/search-tags | List with filters and pagination |
| POST | /tenants/{t}/bus/{b}/search-tags | Create single search tag |
| POST | /tenants/{t}/bus/{b}/search-tags/bulk | Create multiple search tags |
| GET | /tenants/{t}/bus/{b}/search-tags/{id} | Get search tag by ID |
| PATCH | /tenants/{t}/bus/{b}/search-tags/{id} | Update search tag |
| DELETE | /tenants/{t}/bus/{b}/search-tags/{id} | Delete search tag |

## Filters (for List endpoint)

| Filter | Type | Description |
|--------|------|-------------|
| app_user_id | eq | Filter by user who created the tag |
| session_id | eq | Filter by search session |
| crawled_profile_id | eq | Filter by tagged profile |
| tag_name | eq, ilike | Filter/search by tag label |

## Sort Fields

| Field | Description |
|-------|-------------|
| created_at | Default sort field |
| tag_name | Sort alphabetically |

## Entity Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (stag_ prefix) | auto | Unique identifier |
| tenant_id | str | auto (from URL) | Tenant scope |
| bu_id | str | auto (from URL) | Business unit scope |
| app_user_id | str, FK app_user.id | yes | User who created the tag |
| session_id | str, FK search_session.id | yes | Session where the tag was created |
| crawled_profile_id | str, FK crawled_profile.id | yes | Tagged profile |
| tag_name | Text | yes | Tag label |
| created_at | datetime | auto | Creation timestamp |
| updated_at | datetime | auto | Last updated timestamp |

**Note:** `session_id` has FK to `search_session.id` -- that table is being created by another agent in the same batch.

## Indexes

| Name | Columns | Purpose |
|------|---------|---------|
| ix_stag_app_user_tag | (app_user_id, tag_name) | Listing tags per user |
| ix_stag_app_user_profile | (app_user_id, crawled_profile_id) | Listing tags on a profile |
| ix_stag_session | (session_id) | Session-level tag queries |

## Files to Create

### Source Files
- `src/linkedout/search_tag/__init__.py`
- `src/linkedout/search_tag/entities/__init__.py`
- `src/linkedout/search_tag/entities/search_tag_entity.py`
- `src/linkedout/search_tag/schemas/__init__.py`
- `src/linkedout/search_tag/schemas/search_tag_schema.py`
- `src/linkedout/search_tag/schemas/search_tag_api_schema.py`
- `src/linkedout/search_tag/repositories/__init__.py`
- `src/linkedout/search_tag/repositories/search_tag_repository.py`
- `src/linkedout/search_tag/services/__init__.py`
- `src/linkedout/search_tag/services/search_tag_service.py`
- `src/linkedout/search_tag/controllers/__init__.py`
- `src/linkedout/search_tag/controllers/search_tag_controller.py`

### Registration Points (modify existing files)
- `migrations/env.py` -- import entity
- `src/dev_tools/db/validate_orm.py` -- import entity + add to modules list
- `main.py` -- import router + include_router

### Test Files
- `tests/linkedout/search_tag/__init__.py`
- `tests/linkedout/search_tag/repositories/__init__.py`
- `tests/linkedout/search_tag/repositories/test_search_tag_repository.py`
- `tests/linkedout/search_tag/services/__init__.py`
- `tests/linkedout/search_tag/services/test_search_tag_service.py`
- `tests/linkedout/search_tag/controllers/__init__.py`
- `tests/linkedout/search_tag/controllers/test_search_tag_controller.py`

## Pattern

Following `search_history` as the reference pattern for entity/schema/repo/service. Using CRUDRouterFactory for the controller (standard CRUD only).

## Execution Phases

- [ ] Phase 1: Entity (create entity + register in env.py, validate_orm.py)
- [ ] Phase 2: Schemas (core schema + API schema with sort enum)
- [ ] Phase 3: Repository + wiring tests
- [ ] Phase 4: Service + wiring tests
- [ ] Phase 5: Controller + wiring tests (register in main.py)
