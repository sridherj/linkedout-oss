---
feature: authentication-authorization
module: backend/src/shared/auth
linked_files:
  - backend/src/shared/auth/dependencies/auth_dependencies.py
  - backend/src/shared/auth/dependencies/schemas/auth_context.py
  - backend/src/shared/auth/dependencies/schemas/role_enums.py
  - backend/src/shared/auth/providers/base_auth_provider.py
  - backend/src/shared/auth/providers/firebase_auth_provider.py
  - backend/src/shared/auth/providers/api_key_auth_provider.py
  - backend/src/shared/auth/config.py
version: 1
last_verified: "2026-04-09"
---

# Authentication & Authorization

**Created:** 2026-04-09 — Adapted from internal spec for LinkedOut OSS

## Intent

Provide a 3-layer dependency-based authentication and authorization chain for FastAPI. Layer 1 validates credentials without DB access. Layer 2 enriches the auth context with user data and validates tenant/BU access. Layer 3 checks role-based permissions. Single-user default, multi-tenant capable: the default local setup disables auth (`AUTH_ENABLED=false`), but the full auth stack (Firebase JWT, API key, service account) is preserved for multi-user deployments.

The system supports four auth modes: dev bypass (default for local), Firebase JWT, API key (bcrypt prefix lookup), and service account tokens.

## Behaviors

### Layer 1: is_valid_user

- **Dev bypass**: When `AUTH_ENABLED=false`, the dependency returns an AuthContext with a dev Principal (`dev_bypass:{DEV_BYPASS_USER_ID}`) and admin Actor with `ADMIN` in both tenant and BU roles. No credentials are checked. Verify the returned context has `dev_bypass:` prefix and admin roles.

- **API key detection**: When `API_KEY_AUTH_ENABLED=true` and the configured header (`X-API-Key` by default) is present, a pending Principal is returned with `api_key_pending:` prefix (first 8 chars of the key). Verify the principal is not yet enriched (no user_id, no actor roles).

- **Service account tokens**: When a Bearer token matches a `SERVICE_ACCOUNT_TOKENS` entry (comma-separated `token:name` pairs), a Principal with `service_account:{name}` prefix is returned. Verify the service name is extracted from the token map.

- **Firebase JWT verification**: When `FIREBASE_ENABLED=true` and a Bearer token does not match service accounts, it is verified via `FirebaseAuthProvider.verify_token` (delegates to `firebase_admin.auth.verify_id_token`). The decoded UID becomes the `auth_provider_id`. Verify that an invalid token returns HTTP 401.

- **Firebase not configured**: When `FIREBASE_ENABLED=false` and the token is not a service account, HTTP 401 is returned with detail "No auth provider configured".

- **Missing credentials**: When no Authorization header and no API key is present, HTTP 401 is returned with `WWW-Authenticate: Bearer realm="api"` header.

### Layer 2: get_valid_user

- **Dev bypass passthrough**: When the principal starts with `dev_bypass:`, the Subject is populated from path params (`tenant_id`, `bu_id`) and the Actor from Layer 1 is preserved. No DB queries are made.

- **Service account auto-admin**: Service accounts receive `ADMIN` tenant role and `ADMIN` BU role (only if `bu_id` is provided) without DB lookup. The actor ID is `service_account_{name}`.

- **API key pending rejection**: If an `api_key_pending:` principal reaches Layer 2, HTTP 401 is returned with "API key auth requires dedicated dependency". API key auth must use the standalone `api_key_auth` dependency instead.

- **Firebase user DB lookup**: For Firebase-authenticated users, `AppUserService.get_by_auth_provider_id` loads the user. If no AppUser exists, HTTP 403 is returned with "User account not found". Tenant access is validated via `AppUserTenantRoleService.has_tenant_access`. If the user lacks access, HTTP 403 is returned with "Access to tenant denied". Tenant roles are loaded via `AppUserTenantRoleService.get_roles`.

- **BU roles placeholder**: BU roles are always an empty list for Firebase users. The `AppUserBuRole` entity does not exist in OSS.

### Layer 3: validate_role_access

- **Auto-pass for privileged contexts**: Service accounts and dev bypass always pass role checks without validation.

- **OR logic (default)**: When `require_both=False` and `bu_id` is present, the user needs EITHER sufficient tenant roles OR BU roles.

- **AND logic**: When `require_both=True` and `bu_id` is present, the user needs BOTH tenant AND BU roles. Since BU roles are currently always empty for real users, AND logic will reject all non-privileged users with BU-scoped requests.

- **Tenant-only check**: When `bu_id` is None, only tenant roles are checked. BU roles are ignored.

### AuthContext Schema

- **Progressive enrichment**: AuthContext starts with just a Principal (Layer 1), gains an Actor and Subject (Layer 2). Each layer adds its expected fields.

- **Principal fields**: `auth_provider_id` (required), `user_id` (optional, populated Layer 2), `email` (optional), `name` (optional).

- **Actor fields**: `id` (required), `current_tenant_roles` (list of TenantRole), `current_bu_roles` (list of BuRole), `is_impersonating` (always False).

- **Subject fields**: `tenant_id` (required), `bu_id` (optional).

- **Role convenience methods**: `has_tenant_role`, `has_bu_role`, `is_admin`, `is_tenant_admin`, `is_bu_admin` on both Actor and AuthContext. `is_service_account` and `is_api_key_auth` are properties on AuthContext checking the `auth_provider_id` prefix.

### Role Enums

- **TenantRole**: `ADMIN`, `MEMBER`, `VIEWER` (StrEnum).

- **BuRole**: `ADMIN`, `MANAGER`, `VIEWER` (StrEnum).

### Convenience Partials

- **Pre-built dependencies**: `require_tenant_admin` (tenant_roles=[ADMIN]), `require_bu_admin` (bu_roles=[ADMIN]), `require_any_admin` (both tenant and BU ADMIN). These are `functools.partial` wrappers around `validate_role_access`.

### Standalone API Key Auth

- **Dedicated dependency**: `api_key_auth` is a standalone dependency for API-key-only endpoints. Requires `API_KEY_AUTH_ENABLED=true`. Verifies the key via `ApiKeyAuthProvider.verify_api_key` which does prefix lookup (first 8 chars) on `AppUserEntity.api_key_prefix`, then bcrypt verifies the full key against `api_key_hash`. Returns AuthContext with `MEMBER` tenant role. Invalid keys return HTTP 401.

### Auth Providers

- **BaseAuthProvider**: Abstract base with `verify_token`, `create_user`, `delete_user`, `update_user`, `get_user_by_email`, and `get_instance` (singleton). All providers must implement this interface.

- **FirebaseAuthProvider**: Thread-safe singleton. Requires `firebase_admin` initialization via `initialize_firebase_global` at startup. `verify_token` delegates to `firebase_admin.auth.verify_id_token`. Full user management methods (create, delete, update, get_by_email) are implemented. Comment notes: "Firebase auth preserved for potential multi-user support".

- **ApiKeyAuthProvider**: Thread-safe singleton. Only `verify_api_key(api_key, session)` is functional (needs DB session). All other BaseAuthProvider methods raise `NotImplementedError` with "API keys are managed through AppUser MVCS, not auth provider".

### AuthConfig

- **Environment-driven**: All config from env vars via pydantic-settings. Key settings: `AUTH_ENABLED` (default True), `FIREBASE_ENABLED` (default True), `FIREBASE_PROJECT_ID`, `FIREBASE_CREDENTIALS_PATH`, `SERVICE_ACCOUNT_TOKENS`, `API_KEY_AUTH_ENABLED` (default False), `API_KEY_HEADER` (default `X-API-Key`), dev bypass values (`DEV_BYPASS_USER_ID`, `DEV_BYPASS_USER_EMAIL`, `DEV_BYPASS_USER_NAME`, `DEV_BYPASS_TENANT_ID`, `DEV_BYPASS_BU_ID`).

- **Module-level initialization**: `init_auth(config)` must be called at app startup. Accessing auth before init raises `RuntimeError`.

## Decisions

| Date | Decision | Chose | Over | Because |
|------|----------|-------|------|---------|
| 2026-03-25 | Auth architecture | 3-layer dependency chain | Middleware-based auth | Dependency injection is more testable and composable in FastAPI |
| 2026-03-25 | Dev bypass | Config-driven AUTH_ENABLED flag | Hardcoded skip | Explicit and safe -- no risk of accidentally shipping disabled auth |
| 2026-03-25 | Role storage | AppUserTenantRole table (BU roles removed) | Embedded roles in user record | Single table for tenant roles; BU role entity removed as unnecessary |
| 2026-04-09 | OSS default | AUTH_ENABLED=false for local dev | Require Firebase setup on first run | Single-user local use should be zero-friction; Firebase is opt-in for multi-user |

## Not Included

- AppUserBuRole entity (removed; BU roles are placeholder empty lists)
- Impersonation (field exists on Actor but is always False)
- Token refresh or session management
- OAuth2 flows beyond JWT verification
- Rate limiting on auth endpoints
- Permission-level access control (only role-level)
- Firebase user management CLI (not in OSS)
