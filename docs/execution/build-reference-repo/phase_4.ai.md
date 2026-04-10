# Phase 4: Authentication & Authorization

## Execution Context
**Depends on**: Phase 3 (AppUser entities + endpoints to wire auth into)
**Blocks**: Phase 5b (auth mocking)
**Parallel with**: Phase 5a (basic test infra), Phase 6a (agent infra)

## Goal
Port and adapt the linkedout 3-layer dependency-based auth pattern. Firebase JWT as default, API key as secondary, config-driven local bypass.

## Critical Reconciliation Decisions (Baked In)
- **I6**: Auth config is a composed class `AuthConfig(BaseSettings)`, NOT added to a flat BaseConfig. Phase 7 composes: `AppConfig(AuthConfig, LLMConfig, ReliabilityConfig, BaseSettings)`.
- **I8**: `Principal` uses `auth_provider_id` field (NOT `id`). `BuRole` (NOT `WorkspaceRole`).

## Pre-Conditions
- Phase 3 DONE: `AppUserEntity`, `AppUserTenantRoleEntity`, `AppUserService`, `AppUserTenantRoleService` exist
- Endpoints exist to wire auth into (project_mgmt routers)
- `precommit-tests` passes

## Post-Conditions (Definition of Done)
- `precommit-tests` passes
- 3-layer auth chain works: `is_valid_user` -> `get_valid_user` -> `validate_role_access`
- Firebase JWT verification (mockable)
- API key auth via provider seam
- Service account tokens from config (not hardcoded)
- `AUTH_ENABLED=false` bypasses auth with explicit dev context
- Auth dependency injected into CRUDRouterFactory
- All auth tests pass with mocked providers

---

## Target Directory: `src/shared/auth/`

```
src/shared/auth/
  __init__.py                          # Public exports
  config.py                            # AuthConfig(BaseSettings)
  dependencies/
    __init__.py
    auth_dependencies.py               # 3-layer chain + init_auth()
    schemas/
      __init__.py
      auth_context.py                  # Principal, Actor, Subject, AuthContext
      role_enums.py                    # TenantRole, BuRole
  providers/
    __init__.py
    base_auth_provider.py              # Abstract interface
    firebase_auth_provider.py          # Firebase JWT (singleton)
    api_key_auth_provider.py           # Bcrypt prefix lookup
```

---

## Step 1: Role Enums

### File: `src/shared/auth/dependencies/schemas/role_enums.py`
```python
class TenantRole(StrEnum):
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"

class BuRole(StrEnum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    VIEWER = "VIEWER"
```

---

## Step 2: AuthContext Schemas

### File: `src/shared/auth/dependencies/schemas/auth_context.py`
- `Principal`: auth_provider_id (str), user_id (Optional), email (Optional), name (Optional)
- `Actor`: id, current_tenant_roles (List[TenantRole]), current_bu_roles (List[BuRole]), is_impersonating
  - Methods: has_tenant_role(), has_bu_role(), is_tenant_admin(), is_bu_admin(), is_admin()
- `Subject`: tenant_id, bu_id (Optional)
- `AuthContext`: principal, actor (Optional), subject (Optional)
  - Delegates role methods to actor
  - Properties: is_service_account, is_api_key_auth

---

## Step 3: Auth Config

### File: `src/shared/auth/config.py`
```python
class AuthConfig(BaseSettings):
    AUTH_ENABLED: bool = True
    FIREBASE_ENABLED: bool = True
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_CREDENTIALS_PATH: str = ""
    SERVICE_ACCOUNT_TOKENS: str = ""   # "token:name,token:name"
    API_KEY_AUTH_ENABLED: bool = False
    API_KEY_HEADER: str = "X-API-Key"
    DEV_BYPASS_USER_ID: str = "dev-user-001"
    DEV_BYPASS_USER_EMAIL: str = "dev@localhost"
    DEV_BYPASS_USER_NAME: str = "Local Developer"
    DEV_BYPASS_TENANT_ID: str = "dev-tenant-001"
    DEV_BYPASS_BU_ID: str = "dev-bu-001"

    def get_service_account_map(self) -> Dict[str, str]: ...
```

---

## Step 4: Auth Providers

### `base_auth_provider.py` — Abstract interface with: verify_token, create_user, delete_user, update_user, get_user_by_email, get_instance (singleton)

### `firebase_auth_provider.py` — Thread-safe singleton, Firebase JWT verification. `initialize_firebase_global(config)` at app startup.

### `api_key_auth_provider.py` — Bcrypt prefix lookup pattern:
1. Extract 8-char prefix from API key
2. Query `AppUserEntity` by `api_key_prefix`
3. bcrypt verify full key against `api_key_hash`
4. Return `{app_user_id, tenant_id}` or None

---

## Step 5: 3-Layer Dependency Chain

### File: `src/shared/auth/dependencies/auth_dependencies.py`

**Layer 1: `is_valid_user(request: Request) -> AuthContext`**
- `AUTH_ENABLED=false` -> dev bypass context (admin roles, configurable IDs)
- API key header present -> placeholder principal (deferred to Layer 2)
- Bearer token -> check service account map, then Firebase JWT
- Returns AuthContext with minimal Principal. Zero DB queries.

**Layer 2: `get_valid_user(tenant_id, bu_id, auth_ctx, session) -> AuthContext`**
- Dev bypass -> add Subject from path params
- Service account -> auto-admin roles
- Firebase users -> load AppUser by auth_provider_id, validate tenant access, load roles
- Uses `AppUserService`, `AppUserTenantRoleService` (deferred imports)

**Layer 3: `validate_role_access(tenant_id, bu_id, tenant_roles, bu_roles, require_both, auth_ctx) -> AuthContext`**
- Service accounts + dev bypass auto-pass
- AND/OR logic for role checks

**Convenience partials**: `require_tenant_admin`, `require_bu_admin`, `require_any_admin`

**Dedicated**: `api_key_auth(request, session) -> AuthContext` for API-key-only endpoints

---

## Step 6: Wire Auth into CRUDRouterFactory

Add `auth_dependency: Optional[Callable] = None` to `CRUDRouterConfig`. When set, router gets `dependencies=[Depends(config.auth_dependency)]`.

Update `BaseRequestSchema.auth_context` type from `Optional[object]` to `Optional[AuthContext]`.

---

## Step 7: App Startup Wiring

In `main.py`:
```python
from shared.auth.config import AuthConfig
from shared.auth.dependencies.auth_dependencies import init_auth
from shared.auth.providers.firebase_auth_provider import initialize_firebase_global

auth_config = AuthConfig()
init_auth(auth_config)
if auth_config.FIREBASE_ENABLED:
    initialize_firebase_global(auth_config)
```

---

## Step 8: Tests

### `tests/shared/auth/test_auth_context.py`
- Principal, Actor, AuthContext model tests
- Progressive enrichment, role checking, admin detection

### `tests/shared/auth/test_auth_dependencies.py`
- Layer 1: dev bypass, missing header 401, service account token, Firebase JWT (mocked), API key
- Layer 2: dev bypass subject, service account admin, Firebase user DB load, 403 scenarios
- Layer 3: role check pass/fail, AND/OR logic

### `tests/shared/auth/test_api_key_auth_provider.py`
- Valid key, invalid key, unknown prefix, short key, singleton pattern

### Auth Mock Fixture (for other phases)
```python
@pytest.fixture
def mock_auth_context():
    return AuthContext(
        principal=Principal(auth_provider_id="test-uid-001", user_id="test-user-001"),
        actor=Actor(id="test-user-001", current_tenant_roles=[TenantRole.ADMIN], current_bu_roles=[BuRole.ADMIN]),
        subject=Subject(tenant_id="test-tenant-001", bu_id="test-bu-001"),
    )

@pytest.fixture
def override_auth(mock_auth_context):
    from main import app
    app.dependency_overrides[is_valid_user] = lambda: mock_auth_context
    app.dependency_overrides[get_valid_user] = lambda: mock_auth_context
    yield
    app.dependency_overrides.clear()
```

---

## Files Summary

### Create (~12 files)
| File | Type |
|------|------|
| `src/shared/auth/__init__.py` | Exports |
| `src/shared/auth/config.py` | AuthConfig |
| `src/shared/auth/dependencies/__init__.py` | Empty |
| `src/shared/auth/dependencies/auth_dependencies.py` | 3-layer chain |
| `src/shared/auth/dependencies/schemas/__init__.py` | Empty |
| `src/shared/auth/dependencies/schemas/auth_context.py` | AuthContext models |
| `src/shared/auth/dependencies/schemas/role_enums.py` | Role enums |
| `src/shared/auth/providers/__init__.py` | Empty |
| `src/shared/auth/providers/base_auth_provider.py` | Abstract provider |
| `src/shared/auth/providers/firebase_auth_provider.py` | Firebase JWT |
| `src/shared/auth/providers/api_key_auth_provider.py` | API key bcrypt |
| `tests/shared/auth/test_*.py` | 4 test files |

### Modify (~3 files)
| File | Change |
|------|--------|
| `main.py` | Add auth startup wiring |
| `src/common/controllers/crud_router_factory.py` | Add auth_dependency to CRUDRouterConfig |
| `src/common/schemas/base_request_schema.py` | Type auth_context as Optional[AuthContext] |

### External References (read on demand)
- linkedout: `.-aragent/linkedout_backend/src/shared/auth/` — 3-layer chain pattern
- linkedout: `./src/middleware/auth.py` — API key bcrypt pattern
