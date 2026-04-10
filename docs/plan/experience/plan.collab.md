# Plan: Experience CRUD Implementation

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /experiences | List with filters and pagination |
| POST | /experiences | Create single experience |
| POST | /experiences/bulk | Create multiple experiences |
| GET | /experiences/{experience_id} | Get experience by ID |
| PATCH | /experiences/{experience_id} | Update experience |
| DELETE | /experiences/{experience_id} | Delete experience |

## Filters (for List endpoint)

| Filter | Type | Description |
|--------|------|-------------|
| crawled_profile_id | eq | Filter by profile |
| company_id | eq | Filter by company |
| is_current | eq | Filter by current job flag |
| employment_type | eq | Filter by employment type |

## Sort Fields
- created_at (default)
- start_date
- position

## Entity Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| crawled_profile_id | str (FK) | yes | FK to crawled_profile |
| position | Optional[str] | no | |
| position_normalized | Optional[str] | no | |
| company_name | Optional[str] | no | |
| company_id | Optional[str] (FK) | no | FK to company |
| company_linkedin_url | Optional[str] | no | |
| employment_type | Optional[str] | no | |
| start_date | Optional[date] | no | |
| start_year | Optional[int] | no | |
| start_month | Optional[int] | no | |
| end_date | Optional[date] | no | |
| end_year | Optional[int] | no | |
| end_month | Optional[int] | no | |
| end_date_text | Optional[str] | no | |
| is_current | Optional[bool] | no | READ-ONLY, excluded from create/update |
| seniority_level | Optional[str] | no | |
| function_area | Optional[str] | no | |
| location | Optional[str] | no | |
| description | Optional[str] | no | |
| raw_experience | Optional[str] | no | Text placeholder for JSONB |

## Files to Create

### Source Files
- src/linkedout/experience/__init__.py
- src/linkedout/experience/entities/__init__.py
- src/linkedout/experience/entities/experience_entity.py
- src/linkedout/experience/schemas/__init__.py
- src/linkedout/experience/schemas/experience_schema.py
- src/linkedout/experience/schemas/experience_api_schema.py
- src/linkedout/experience/repositories/__init__.py
- src/linkedout/experience/repositories/experience_repository.py
- src/linkedout/experience/services/__init__.py
- src/linkedout/experience/services/experience_service.py
- src/linkedout/experience/controllers/__init__.py
- src/linkedout/experience/controllers/experience_controller.py

### Test Files
- tests/linkedout/experience/__init__.py
- tests/linkedout/experience/repositories/__init__.py
- tests/linkedout/experience/repositories/test_experience_repository.py
- tests/linkedout/experience/services/__init__.py
- tests/linkedout/experience/services/test_experience_service.py
- tests/linkedout/experience/controllers/__init__.py
- tests/linkedout/experience/controllers/test_experience_controller.py

### Modified Files
- main.py (add router import + include)
- migrations/env.py (add entity import)
- src/dev_tools/db/validate_orm.py (add entity import)

## Execution Checklist
- [ ] Entity created
- [ ] Schemas created
- [ ] Repository created
- [ ] Service created
- [ ] Controller created
- [ ] Test files created
- [ ] main.py updated
- [ ] migrations/env.py updated
- [ ] validate_orm.py updated
