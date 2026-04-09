---
feature: unit-tests
module: backend/tests/, backend/conftest.py
linked_files:
  - backend/conftest.py
  - backend/tests/seed_db.py
  - backend/src/shared/test_utils/entity_factories.py
  - backend/src/shared/test_utils/seeders/base_seeder.py
  - backend/src/shared/test_utils/seeders/seed_config.py
  - backend/tests/common/
  - backend/tests/linkedout/
  - backend/tests/dev_tools/
  - backend/pytest.ini
version: 1
last_verified: "2026-04-09"
---

# Unit Tests

**Created:** 2026-04-09 — Adapted from internal spec for LinkedOut OSS

## Intent

Provide fast, isolated unit tests for the repository, service, and controller layers using SQLite in-memory databases (repository) and mocks (service, controller). Tests run without PostgreSQL and cover filtering, pagination, CRUD operations, and business logic.

## Behaviors

### Repository Tests (SQLite)

- **Shared DB for read-only tests**: Read-only tests use `shared_db_session` fixture backed by a session-scoped SQLite engine. The DB is seeded once and shared across all read-only tests. The session auto-rolls back changes at the end.

- **Isolated DB for mutation tests**: Tests that create/update/delete use `class_scoped_isolated_db_session` or `function_scoped_isolated_db_session`. Each gets a fresh SQLite database with its own engine. Verify mutations in one test class do not affect another.

- **Custom seed config**: `@pytest.mark.seed_config(SeedDb.SeedConfig(...))` on a test class customizes what data is seeded for isolated DBs. The marker is extracted from class-level first, then node-level. Default `SeedConfig()` is used when no marker is present.

- **Pre-seeded data access**: `all_seeded_data_for_shared_db` provides a dict of `{TableName: [entities]}` with detached copies. Entities are merged into a fresh session, all column attributes are force-loaded, then expunged to prevent `DetachedInstanceError` across tests.

### Service Tests (Mocked Repository)

- **Repository mocking**: Service tests mock the repository layer via `create_autospec(Repository, instance=True, spec_set=True)` and inject it as `svc._repository`. The service is tested in isolation with controlled repository responses.

- **Wiring checks**: Service test suites include `test_can_instantiate` to verify service-entity wiring. Additional wiring checks verify the service can be constructed with a mocked session.

- **None-handling tests**: Service tests verify that updating with None values does not overwrite existing entity fields. Verify that partial updates preserve untouched fields.

- **Error handling**: Service tests verify that `ValueError` is raised when entities are not found on update/delete. Verify the error message includes the entity identifier.

### Controller Tests (Mocked Service)

- **Service mocking via dependency overrides**: Controller tests mock the service layer using `create_autospec` and inject via FastAPI's `app.dependency_overrides[_get_<entity>_service]`. This replaces the service factory dependency. Tests use FastAPI's `TestClient`. Verify HTTP status codes, response schemas, and error handling.

- **Shared entity endpoints**: Shared entities (Company, CrawledProfile, CompanyAlias, RoleAlias) use root-level paths (e.g., `/companies`). Tests verify CRUD without tenant/BU URL parameters.

- **Scoped entity endpoints**: Tenant/BU-scoped entities (Connection, ContactSource, ImportJob, etc.) use `/tenants/{tid}/bus/{bid}/...` paths. Tests verify tenant and BU IDs are included in request URLs.

- **Auth override**: Controller tests clear `dependency_overrides` in fixture teardown. The `override_auth` fixture (in `conftest.py`) bypasses `is_valid_user` and `get_valid_user` dependencies with a pre-built `AuthContext` for tenant `tenant-test-001` and BU `bu-test-001`.

### Test Fixtures

- **JSONB compatibility**: A custom SQLAlchemy compiler translates PostgreSQL `JSONB` to SQLite `JSON` for unit tests. Registered via `@compiles(_pg_jsonb, 'sqlite')`.

- **ARRAY compatibility**: A second compiler translates PostgreSQL `ARRAY` to SQLite `JSON`. This is required because OSS entities use ARRAY columns (e.g., `connection.sources`).

- **Foreign key enforcement**: SQLite test engines enable `PRAGMA foreign_keys=ON` via a `connect` event listener. Verify FK constraints are enforced in unit tests.

- **DateTimeComparator**: Utility class for comparing timestamps with tolerance (default 2 seconds). Supports `compare_le` and `compare_ge` static methods for timezone-aware and naive datetime comparison. Available via `datetime_comparator` fixture.

- **mock_auth_context**: Pre-built `AuthContext` fixture with admin roles for tenant `tenant-test-001` and BU `bu-test-001`. Uses `Principal`, `Actor`, `Subject` schemas from `shared.auth.dependencies.schemas`.

- **reset_config**: Autouse fixture that resets the `_settings_instance` singleton between every test to prevent config bleed.

- **data_dir**: Fixture that sets `LINKEDOUT_DATA_DIR` to a temp path so tests never write to `~/linkedout-data/`.

### Seeding Infrastructure

- **Two-layer seeding**: Unit tests use `SeedDb` (in `tests/seed_db.py`) which wraps the shared `BaseSeeder` for backward compatibility. `SeedDb.SeedConfig` maps legacy count parameters (e.g., `tenant_count`, `company_count`) to the shared `SeedConfig` format.

- **Shared BaseSeeder**: `BaseSeeder` (in `shared/test_utils/seeders/base_seeder.py`) uses dependency-ordered seeding (17 entity types). Fixed data from `dev_tools.db.fixed_data` is seeded first (system tenant, system BU, system user), followed by configurable random entities.

- **Entity factories**: `EntityFactory` (in `shared/test_utils/entity_factories.py`) creates entity instances with deterministic defaults. Covers organization entities (Tenant, BU, AppUser, AppUserTenantRole, EnrichmentConfig), common infrastructure (AgentRun), and LinkedOut domain entities (Company, CompanyAlias, RoleAlias, CrawledProfile, Experience, Education, ProfileSkill, Connection, ImportJob, ContactSource, EnrichmentEvent) -- 17 entity types total.

- **Entity coverage**: Unit test suites exist for Company, CompanyAlias, RoleAlias, CrawledProfile, Experience, Education, ProfileSkill, Connection, ImportJob, ContactSource, EnrichmentEvent, FundingRound, GrowthSignal, SearchSession, SearchTurn, and AgentRun -- each with repository, service, and controller test files.

### Test Configuration (pytest.ini)

- **Default addopts**: Tests run with `pytest-xdist` (`-n auto --dist=loadfile`) and exclude markers: `live_llm`, `live_langfuse`, `live_services`, `integration`, `eval`.

- **Custom markers**: `unit`, `integration`, `live_llm`, `live_langfuse`, `live_services`, `eval` are registered in `pytest.ini`. The `smoke` and `seed_config` markers are registered in `conftest.py`'s `pytest_configure`.

- **Auto-marker hook**: `pytest_collection_modifyitems` adds `unit` marker to files under `repositories/` or `services/` paths, and `integration` marker to files under `controllers/` paths. Note: this auto-marker labels unit controller tests as "integration" which is misleading but is the current behavior.

- **Environment**: `LINKEDOUT_ENVIRONMENT=test` is set both in pytest.ini (`env` section) and in conftest.py.

## Decisions

| Date | Decision | Chose | Over | Because |
|------|----------|-------|------|---------|
| 2026-04-09 | Unit test DB | SQLite in-memory | Mocked DB / PostgreSQL | Fast, real SQL execution, no external dependency |
| 2026-04-09 | Shared vs isolated | Session-scoped shared for reads, class-scoped isolated for mutations | All isolated | Shared DB is faster for read-only tests; isolation prevents mutation interference |
| 2026-04-09 | Seeding approach | Two-layer: legacy SeedDb wrapping shared BaseSeeder | Single seeder | Backward compat with existing tests while sharing factory code with integration tests |
| 2026-04-09 | Controller mock injection | FastAPI dependency_overrides | unittest.mock.patch | Direct dependency override is cleaner for FastAPI and avoids import-path coupling |

## Not Included

- Property-based testing (hypothesis)
- Snapshot testing
- Coverage enforcement thresholds
- Test data generation from production schemas
- Project management entities (Label, Priority, Project, Task) -- removed from OSS
