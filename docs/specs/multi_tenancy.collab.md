---
feature: multi-tenancy
module: backend/src/common/entities, backend/src/organization
linked_files:
  - backend/src/common/entities/tenant_bu_mixin.py
  - backend/src/organization/entities/tenant_entity.py
  - backend/src/organization/entities/bu_entity.py
  - backend/src/common/repositories/base_repository.py
  - backend/src/shared/infra/db/db_session_manager.py
  - backend/migrations/versions/001_baseline.py
version: 1
last_verified: "2026-04-09"
---

# Multi-Tenancy (TenantBu)

**Created:** 2026-04-09 — Adapted from internal spec for LinkedOut OSS

## Intent

Provide a consistent multi-tenancy layer where all domain entities are scoped to a Tenant and Business Unit (BU). Single-user default, multi-tenant capable: the default setup creates one tenant and one BU for the local user, but the data model supports multiple tenants and BUs without code changes.

The implementation uses a mixin pattern so tenancy columns are isolated, consistent, and replaceable with alternative scoping through localized changes. Row-Level Security (RLS) at the database level provides an additional isolation boundary for user-specific data (connections, profiles).

## Behaviors

### TenantBuMixin

- **Two FK columns**: Mixing in `TenantBuMixin` adds `tenant_id` (FK to tenant.id) and `bu_id` (FK to bu.id) as non-nullable string columns. Verify both columns exist on the entity's table and have foreign key constraints.

- **Auto backref relationships**: The mixin creates SQLAlchemy relationships to `TenantEntity` and `BuEntity` with `backref=cls.__tablename__`. Adding a new entity with the mixin does NOT require editing TenantEntity or BuEntity. Verify the reverse relationship is accessible on TenantEntity/BuEntity by the entity's table name.

- **URL path scoping**: All tenant-BU scoped endpoints use the URL pattern `/tenants/{tenant_id}/bus/{bu_id}/...`. Verify path parameters are extracted and passed through to service and repository layers.

### Organization Entities

- **TenantEntity**: Top-level organizational unit with `id_prefix='tenant'`, `name` (required), and `description` (optional). Has a cascade relationship to BuEntity. Verify it can be created and queried independently.

- **BuEntity**: Business unit scoped under a tenant with `id_prefix='bu'`, `tenant_id` FK (CASCADE on delete), `name` (required), and `description` (optional). Verify it has a `tenant_id` FK to the tenant table and a `back_populates` relationship to TenantEntity.

- **AppUserEntity**: Sits above tenant/BU scoping (no TenantBuMixin). Has `id_prefix='usr'`, `email` (unique, required), `name`, `auth_provider_id` (unique), `api_key_prefix`, `api_key_hash`, `own_crawled_profile_id` (FK to crawled_profile), and `network_preferences`. Tenant access is managed through AppUserTenantRole.

### Scoping Enforcement (Application Layer)

- **Repository base query**: `BaseRepository._get_base_query` always filters by both `tenant_id` and `bu_id`. Verify that queries never leak data across tenant or BU boundaries.

- **Create assertions**: `BaseRepository.create` asserts that `entity.tenant_id` and `entity.bu_id` are not None before persisting. Verify that attempting to create without tenant/BU raises an AssertionError.

- **List assertions**: `BaseRepository.list` asserts `tenant_id` and `bu_id` are not None before querying. Same for `count`.

> Edge: Entities that are NOT tenant-scoped (like TenantEntity, AppUserEntity) do not use TenantBuMixin and have their own query patterns.

### Row-Level Security (Database Layer)

- **RLS on connection table**: The `connection` table has `FORCE ROW LEVEL SECURITY` enabled (applies even to the table owner) with policies that filter by `app_user_id` matching `current_setting('app.current_user_id')`. Both SELECT and ALL (write) operations are policy-gated.

- **RLS on profile tables**: `crawled_profile`, `experience`, `education`, and `profile_skill` tables have `FORCE ROW LEVEL SECURITY` enabled and RLS policies that scope access to profiles connected to the current user (via an EXISTS subquery through the connection table).

- **Session-level RLS context**: `DbSessionManager._try_set_rls_user` calls `SELECT set_config('app.current_user_id', :uid, true)` to set the transaction-scoped user ID. Pass `app_user_id` to `get_session()` to activate RLS scoping.

### Default Single-User Setup

- **Setup process creates defaults**: The `linkedout setup` CLI creates one tenant, one BU, and one AppUser. Their IDs are written to `~/linkedout-data/config/agent-context.env` for CLI tools and AI agents.

- **Dev bypass uses defaults**: When `AUTH_ENABLED=false` (local dev default), auth bypasses to `DEV_BYPASS_TENANT_ID` and `DEV_BYPASS_BU_ID` from AuthConfig, avoiding the need for real auth in single-user mode.

## Decisions

| Date | Decision | Chose | Over | Because |
|------|----------|-------|------|---------|
| 2026-03-25 | Tenancy mode | TenantBu as default (Tenant -> Business Unit) | Building all three modes | One mode fully tested is better than three partially tested |
| 2026-03-25 | Mixin pattern | Declarative mixin with backref | Explicit relationships on each entity | Less boilerplate, adding entities doesn't touch organization code |
| 2026-03-25 | Naming | `bu_id` not `workspace_id` | Generic naming | Matches the chosen default mode; replacement is grep-driven |
| 2026-04-07 | RLS addition | Database-level RLS for user data | Application-only scoping | Defense in depth; prevents data leaks even if application code has bugs |

## Not Included

- TenantWorkspace or TenantAppUser modes (designed for easy replacement, not implemented)
- Automated tenancy mode switching script
- Cross-tenant queries or admin super-tenant access patterns
- AppUserBuRole entity (removed; BU roles are placeholder empty lists)
