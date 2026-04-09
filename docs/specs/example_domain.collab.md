---
feature: example-domain-project-management
module: src/project_mgmt, src/organization
linked_files:
  - src/project_mgmt/label/
  - src/project_mgmt/priority/
  - src/project_mgmt/project/
  - src/project_mgmt/task/
  - src/organization/entities/app_user_entity.py
  - src/organization/entities/app_user_tenant_role_entity.py
last_verified: 2026-03-27
version: 3
---

# Example Domain — Project Management

**Created:** 2026-03-25 — Backfilled from existing implementation
**Updated:** 2026-03-27 — Added EnrichmentConfigEntity behavior

## Intent

Demonstrate the MVCS architectural patterns through a coherent project-management domain. The domain exists to teach the patterns, not because the domain itself is important. It covers simple CRUD (Label, Priority), parent-child relationships (Project, Task), and organization entities (AppUser, roles).

## Behaviors

### L1 Entities — Generic CRUD via CRUDRouterFactory

- **Label CRUD**: Label entity uses `CRUDRouterFactory` for all six endpoints (list, create, bulk create, get, update, delete). Labels are scoped to tenant+BU. Verify all endpoints are accessible at `/tenants/{tid}/bus/{bid}/labels`.

- **Priority CRUD**: Priority entity uses `CRUDRouterFactory` for all six endpoints. Priorities have a numeric `level` field for ordering. Verify priorities can be listed with sorting by level.

### L2 Entities — Custom Controllers

- **Project as parent entity**: Project has a full MVCS stack with custom controller. Projects are scoped to tenant+BU. Verify project CRUD works at `/tenants/{tid}/bus/{bid}/projects`.

- **Task as child entity**: Task belongs to a Project via `project_id` FK. Task has a custom controller with service-to-service orchestration. Verify tasks can be listed filtered by project_id.

- **Task status transitions**: Task has a status field. Verify task status can be updated via the update endpoint.

- **Task date and ID filtering**: Task controller exposes `due_date_gte`, `due_date_lte`, and `task_ids` as meta fields for list filtering. Verify tasks can be filtered by due date range and specific IDs.

- **Project date and ID filtering**: Project controller exposes `start_date_gte`, `start_date_lte`, and `project_ids` as meta fields for list filtering. Verify projects can be filtered by start date range and specific IDs.

### Organization Entities

- **AppUserEntity**: Represents an authenticated identity. Has `auth_provider_id` for linking to external auth (Firebase UID). Always exists regardless of tenancy mode. Verify app users can be created and looked up by auth_provider_id.

- **AppUserTenantRoleEntity**: Maps an app user to a tenant with a role. Verify that a user can have different roles in different tenants.

- **EnrichmentConfigEntity**: Per-user enrichment settings for LinkedOut data enrichment. Sits in the organization module with a direct `app_user_id` FK. Has its own MVCS stack with a custom controller at `/enrichment-configs`. Unique constraint on `app_user_id` ensures one config per user. Verify enrichment configs can be created and listed without tenant/BU path parameters.

### MVCS Pattern Coverage

- **Entity layer**: All domain entities extend BaseEntity with TenantBuMixin. Each defines `id_prefix` for prefixed nanoid generation. Verify entity table names follow snake_case convention.

- **Repository layer**: Each entity has a repository extending BaseRepository with entity-specific FilterSpecs. Verify filter specs cover the entity's queryable fields.

- **Service layer**: Each entity has a service extending BaseService with the three required abstract methods implemented. Verify entity-to-schema conversion works for all entities.

- **Controller layer**: Label and Priority use CRUDRouterFactory. Project and Task use custom controllers. Verify both patterns produce functional endpoints.

## Decisions

| Date | Decision | Chose | Over | Because |
|------|----------|-------|------|---------|
| 2026-03-25 | Module name | `project_mgmt` | `project_management` | Shorter, consistent with existing convention |
| 2026-03-25 | Router naming | Plural (`labels_router`, `tasks_router`) | Singular | REST convention for collection endpoints |
| 2026-03-25 | L1 vs L2 split | Label/Priority via factory, Project/Task via custom | All via factory | Shows both patterns — factory for simple CRUD, custom for orchestration |

## Not Included

- ProjectSummary read model (placeholder for future L3 pattern)
- Task-to-Task dependencies or subtasks
- Label or Priority assignment to Tasks (relation exists conceptually but is simple)
- Workflow engine or state machine for task transitions
