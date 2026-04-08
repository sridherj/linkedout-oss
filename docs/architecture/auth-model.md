# Auth Model

LinkedOut OSS authentication and authorization reference.

## 1. Overview

LinkedOut OSS uses a **single-user model** with a system tenant, business unit, and user. Authentication is **disabled by default** (`AUTH_ENABLED=false`). When disabled, every request is automatically assigned the dev-bypass identity with full admin roles — no login, no tokens, no Firebase.

This design is intentional: LinkedOut OSS targets self-hosted single-user installs where auth overhead adds no value. The full auth pipeline is preserved for future multi-user support (see Phase 0B decision).

## 2. Key Entities

The `organization/` module provides the structural entities that underpin the auth model:

| Entity | Table | ID Prefix | Purpose |
|--------|-------|-----------|---------|
| `TenantEntity` | `tenant` | `tenant` | Top-level organizational unit |
| `BuEntity` | `bu` | `bu` | Business unit within a tenant |
| `AppUserEntity` | `app_user` | `usr` | Application user (email, auth provider link, API key) |
| `AppUserTenantRoleEntity` | `app_user_tenant_role` | — | Maps users to tenant roles (ADMIN, MEMBER, VIEWER) |
| `EnrichmentConfigEntity` | `enrichment_config` | `ec` | Per-user enrichment settings (Apify key, mode) |

**System defaults** (from `shared/config/agent_context.py`):

| Constant | Value | Description |
|----------|-------|-------------|
| `SYSTEM_TENANT_ID` | `tenant_sys_001` | Default tenant for single-user mode |
| `SYSTEM_BU_ID` | `bu_sys_001` | Default business unit |
| `SYSTEM_USER_ID` | `usr_sys_001` | Default user for CLI and agent operations |

These IDs are written to `~/linkedout-data/config/agent-context.env` by the setup process. CLI tools and AI agents source this file to get DB access with proper RLS context.

## 3. Row-Level Security (RLS)

PostgreSQL RLS policies enforce tenant isolation at the database level. The session variable `app.current_user_id` controls which rows are visible.

**How it works:**

1. `DbSessionManager.get_session(app_user_id=...)` calls `set_config('app.current_user_id', uid, true)` on the PostgreSQL session (transaction-scoped).
2. RLS policies on `connection` filter by `app_user_id = current_setting('app.current_user_id', TRUE)`.
3. Profile-linked tables (`crawled_profile`, `experience`, `education`, `profile_skill`) use subquery policies that join through `connection` to enforce the same isolation.
4. `company` and `company_alias` have no RLS — they are shared reference data.

**Migration:** `d1e2f3a4b5c6_enable_rls_policies.py` creates these policies. A composite index `idx_connection_user_profile` on `connection(app_user_id, crawled_profile_id)` optimizes the subquery lookups.

**RLS bypass:** When `app_user_id` is not passed to `get_session()`, no `app.current_user_id` is set, and superuser connections bypass RLS. SQLite (used in unit tests) skips the `set_config` call entirely.

## 4. Auth Middleware

The auth pipeline is a **3-layer FastAPI dependency chain** in `shared/auth/dependencies/auth_dependencies.py`:

**Layer 1 — `is_valid_user(request)`:** Validates credentials, returns minimal `AuthContext`. Zero DB queries.
- `AUTH_ENABLED=false` → returns dev-bypass context with admin roles
- Service account token → matches against `AuthConfig.SERVICE_ACCOUNT_TOKENS`
- API key header → creates pending principal (resolved in Layer 2)
- Bearer token → Firebase JWT verification

**Layer 2 — `get_valid_user(tenant_id, bu_id)`:** Enriches context with DB data, validates tenant/BU access.
- Dev bypass → populates `Subject` from URL path params, passes through
- Service accounts → auto-granted admin roles, no DB lookup
- Firebase users → loads `AppUser` by `auth_provider_id`, validates tenant access, loads roles

**Layer 3 — `validate_role_access(...)`:** Role-based access checks.
- Service accounts and dev bypass auto-pass
- Supports AND/OR logic for combined tenant + BU role requirements

**Auth context model** (`shared/auth/dependencies/schemas/auth_context.py`):
- `Principal` — WHO is authenticated (auth provider ID, user ID, email)
- `Actor` — WHAT roles in current context (tenant roles, BU roles)
- `Subject` — WHAT is being acted upon (tenant ID, BU ID)

## 5. Firebase Provider

The Firebase auth provider (`shared/auth/providers/firebase_auth_provider.py`) is a thread-safe singleton implementing `BaseAuthProvider`. It provides JWT verification, user CRUD, and email lookup via the `firebase-admin` SDK.

**Current state:** Preserved but disabled by default. Firebase initialization only runs when both `FIREBASE_ENABLED=true` and `FIREBASE_CREDENTIALS_PATH` is set (checked in `main.py` lifespan). No Firebase dependency is required for normal operation.

**Why it's kept:** Future multi-user support (Phase 12) will re-enable Firebase for proper user authentication. Removing it now would require re-implementing the same integration later.

## 6. Configuration

### Auth-specific env vars (`AuthConfig` in `shared/auth/config.py`)

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_ENABLED` | `true` | Master switch for the auth pipeline. Set `false` for single-user. |
| `FIREBASE_ENABLED` | `true` | Enable Firebase JWT verification (only matters if `AUTH_ENABLED=true`) |
| `FIREBASE_PROJECT_ID` | `""` | Firebase project ID |
| `FIREBASE_CREDENTIALS_PATH` | `""` | Path to Firebase service account JSON |
| `SERVICE_ACCOUNT_TOKENS` | `""` | Comma-separated `token:name` pairs for service accounts |
| `API_KEY_AUTH_ENABLED` | `false` | Enable API key authentication |
| `API_KEY_HEADER` | `X-API-Key` | Header name for API key auth |
| `DEV_BYPASS_USER_ID` | `dev-user-001` | User ID injected when auth is disabled |
| `DEV_BYPASS_TENANT_ID` | `dev-tenant-001` | Tenant ID injected when auth is disabled |
| `DEV_BYPASS_BU_ID` | `dev-bu-001` | BU ID injected when auth is disabled |

### How to enable/disable

**Disable auth (default for OSS):** Set `AUTH_ENABLED=false` in your environment or `.env` file. All requests get dev-bypass admin context.

**Enable Firebase auth:** Set `AUTH_ENABLED=true`, `FIREBASE_ENABLED=true`, and provide `FIREBASE_CREDENTIALS_PATH` pointing to a valid service account JSON.

## 7. The `organization/` Module

The `organization/` module is **NOT template scaffolding**. It provides core data model infrastructure:

- **`TenantEntity` / `BuEntity`** — structural hierarchy for multi-tenancy. All domain entities with `TenantBuMixin` reference these via foreign keys.
- **`AppUserEntity`** — user identity, email, auth provider link, API key hash, own profile link, network preferences.
- **`AppUserTenantRoleEntity`** — maps users to tenant roles. Used by Layer 2 auth to validate tenant access.
- **`EnrichmentConfigEntity`** — per-user enrichment settings (Apify key, mode). Controls how profile enrichment works for each user.

Each entity has a full MVCS stack (repository, service, controller, schemas) following the project's standard patterns. The tenant and BU controllers are registered in `main.py` and provide CRUD endpoints at `/tenants/{tenant_id}/...` paths.
