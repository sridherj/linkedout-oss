# Fix: RLS gap in shared controllers (tags page broken)

## Context

The `/tags` page shows raw `crawled_profile_id` instead of person names. The frontend calls `GET /crawled-profiles?crawled_profile_ids=...` which returns 200 with 0 results.

**Root cause:** RLS is enabled on 5 tables (`crawled_profile`, `connection`, `experience`, `education`, `profile_skill`). All 5 controllers use `create_service_dependency()` which opens sessions **without** `app_user_id` — so RLS filters out all rows. The `db_session_manager.get_session(app_user_id=uid)` infrastructure already exists but isn't wired up.

**Scope:** All 5 affected controllers use custom controllers (not CRUDRouterFactory), so the fix is contained to `create_service_dependency` + the 5 controller files.

## Plan

### Step 1: Add `app_user_id` to `create_service_dependency`

**File:** `src/common/controllers/base_controller_utils.py`

```python
def create_service_dependency(
    service_class: Type[TService],
    session_type: DbSessionType = DbSessionType.READ,
    app_user_id: str | None = None,
) -> Generator[TService, None, None]:
    with db_session_manager.get_session(session_type, app_user_id=app_user_id) as session:
        yield service_class(session)
```

### Step 2: Update 5 controllers — read endpoints only

For each controller, update the read dependency to accept `X-App-User-Id` header and pass it through. Write endpoints stay as-is (RLS policies are `FOR SELECT` only).

| Controller | File |
|-----------|------|
| crawled_profile | `src/linkedout/crawled_profile/controllers/crawled_profile_controller.py` |
| connection | `src/linkedout/connection/controllers/connection_controller.py` |
| experience | `src/linkedout/experience/controllers/experience_controller.py` |
| education | `src/linkedout/education/controllers/education_controller.py` |
| profile_skill | `src/linkedout/profile_skill/controllers/profile_skill_controller.py` |

Pattern for each — change `_get_*_service`:
```python
def _get_X_service(
    app_user_id: str = Header(..., alias="X-App-User-Id"),
) -> Generator[XService, None, None]:
    yield from create_service_dependency(XService, DbSessionType.READ, app_user_id=app_user_id)
```

### Step 3: Update spec

**File:** `docs/specs/database_session_management.collab.md` — note `create_service_dependency` now supports `app_user_id` passthrough.

## Verification

1. `curl -H "X-App-User-Id: usr_sys_001" "http://localhost:8000/crawled-profiles?crawled_profile_ids=cp_qKf9WGcpQnJ5a_GGHVTfo&limit=10"` — should return profile data
2. Check `/tags` page in browser — should show person's name
3. `precommit-tests`
