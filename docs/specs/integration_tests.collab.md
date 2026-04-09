---
feature: integration-tests
module: backend/tests/integration
linked_files:
  - backend/tests/integration/conftest.py
  - backend/tests/integration/organization/
  - backend/tests/integration/linkedout/
  - backend/tests/integration/linkedout/intelligence/conftest.py
  - backend/tests/integration/linkedout/intelligence/test_rls_isolation.py
  - backend/tests/integration/linkedout/dashboard/
  - backend/tests/integration/linkedout/enrichment_pipeline/
  - backend/tests/integration/linkedout/import_pipeline/
  - backend/tests/integration/query_history/
  - backend/tests/integration/test_agent_run_integration.py
  - backend/tests/integration/test_embed_command.py
  - backend/src/shared/test_utils/entity_factories.py
  - backend/src/shared/test_utils/seeders/base_seeder.py
  - backend/src/shared/test_utils/seeders/seed_config.py
  - backend/src/dev_tools/db/fixed_data.py
version: 1
last_verified: "2026-04-09"
---

# Integration Tests

**Created:** 2026-04-09 — Adapted from internal spec for LinkedOut OSS

## Intent

Provide full-stack integration tests that run against a real PostgreSQL database. Tests exercise the complete HTTP request path: FastAPI endpoint -> controller -> service -> repository -> PostgreSQL. Per-worker schema isolation enables parallel execution via pytest-xdist.

## Behaviors

### PostgreSQL Schema Isolation

- **Per-worker schema**: Each pytest-xdist worker gets its own schema named `integration_test_{worker_id}` (e.g., `integration_test_gw0`). The worker ID is read from `PYTEST_XDIST_WORKER` env var (defaults to `gw0` for single-worker runs).

- **Schema lifecycle**: An admin engine (without schema search path) creates the schema at session start (`DROP SCHEMA IF EXISTS ... CASCADE` then `CREATE SCHEMA`). Tables are created via `Base.metadata.create_all(engine, checkfirst=False)`. The schema is dropped at session end in a `finally` block.

- **Search path routing**: The test engine URL appends `options=-csearch_path%3D{schema}%2Cpublic` to include both the test schema and `public`. The `public` schema is included so pgvector types (installed there) are resolvable. `checkfirst=False` in `create_all` prevents SQLAlchemy from seeing `public.*` tables and skipping creation in the test schema.

### Test Infrastructure

- **PostgreSQL requirement**: Integration tests require `DATABASE_URL` pointing to a PostgreSQL database. SQLite URLs cause tests to skip with a clear message. Missing or non-PostgreSQL URLs also trigger `pytest.skip`. Connection failures are caught and skip gracefully.

- **Environment loading**: `.env` and `.env.local` are loaded via `python-dotenv` (`.env.local` takes precedence). `LINKEDOUT_ENVIRONMENT` is set to `integration_test`.

- **Session-scoped fixtures**: `integration_db_engine`, `integration_db_session`, `seeded_data`, `test_client`, `test_tenant_id`, `test_bu_id` are all session-scoped for efficiency. Setup runs only once per test session.

- **Entity seeding**: Uses `BaseSeeder` with `EntityFactory` and `SeedConfig(tables=['*'])` to populate all tables with deterministic test data. Fixed data from `dev_tools.db.fixed_data` provides the primary tenant/BU/user IDs. Covers organization entities (Tenant, BU, AppUser, AppUserTenantRole, EnrichmentConfig), agent infrastructure (AgentRun), and LinkedOut domain entities (Company, CompanyAlias, RoleAlias, CrawledProfile, Experience, Education, ProfileSkill, Connection, ImportJob, ContactSource, EnrichmentEvent).

- **TestClient**: FastAPI `TestClient` is configured by setting `db_session_manager.set_engine()` to the integration test engine. The app is imported after DB configuration to ensure middleware uses the test engine.

- **Fixed data IDs**: `test_tenant_id` returns `fixed_data.FIXED_TENANT['id']` and `test_bu_id` returns `fixed_data.FIXED_BUS[0]['id']`. These are used in URL path parameters for scoped entity requests.

### Test Patterns

- **Full CRUD verification**: Integration tests exercise list, create, get-by-id, update, and delete for each entity via HTTP. Verify correct HTTP status codes (200, 201, 204, 404).

- **URL path scoping**: Scoped entity requests use the `/tenants/{tid}/bus/{bid}/...` path pattern. Verify tenant and BU IDs from fixed_data are used in URLs.

- **Shared entity integration tests**: Shared entities (Company, CrawledProfile, CompanyAlias, RoleAlias) are tested at root-level paths without tenant/BU scoping (e.g., `/companies`, `/crawled-profiles`). Verify CRUD operations work without tenant/BU path parameters.

- **Response schema validation**: Responses are validated against the expected JSON structure including pagination metadata (total, limit, offset, page_count, links) and wrapped entity keys (e.g., `{'company': {...}}` for single, `{'companies': [...]}` for list).

### Intelligence Tests

The intelligence test suite (`backend/tests/integration/linkedout/intelligence/`) tests search, SQL tool, vector search, affinity scoring, best-hop, multi-turn conversations, web search, and RLS isolation.

- **Intelligence test data**: The `intelligence_test_data` fixture (session-scoped, in `tests/integration/linkedout/intelligence/conftest.py`) creates two app users with separate connections (20 for user A, 5 for user B), profiles, experiences across 3 companies (Google, Stripe, Acme), contact sources, and an import job. This provides isolation test data on top of the base `seeded_data`.

- **pgvector fixtures**: `pgvector_available` checks and creates the vector extension. `vector_column_ready` alters the `embedding` column to `vector(1536)` type within the same session transaction to avoid deadlocks with prior ACCESS SHARE locks.

### RLS Isolation Tests

The RLS tests (`test_rls_isolation.py`) verify that PostgreSQL Row-Level Security policies correctly enforce per-user data isolation.

- **Module-scoped RLS fixture**: `rls_policies_applied` is **module-scoped** (not session-scoped). This is critical: `FORCE ROW LEVEL SECURITY` makes even the table owner subject to RLS, so if it were session-scoped it would break every other test that queries RLS-protected tables.

- **Same-session DDL**: `rls_policies_applied` runs DDL (ALTER TABLE, CREATE POLICY) on `integration_db_session` rather than opening a new connection. A separate connection would deadlock waiting for `AccessExclusive` locks held by the session-scoped session's open transaction.

- **RLS policy coverage**: Policies are created for `connection` (direct `app_user_id` match) and 4 profile-linked tables (`crawled_profile`, `experience`, `education`, `profile_skill`) using EXISTS subquery via `connection.crawled_profile_id`. A composite index `idx_connection_user_profile` is created for subquery performance.

- **Teardown contract**: On module teardown, `rls_policies_applied` drops all policies and disables RLS. Other test modules see no RLS side effects.

- **RLS context via `get_session(app_user_id=...)`**: Tests set the RLS session variable by passing `app_user_id` to `db_session_manager.get_session()`, which calls `set_config('app.current_user_id', ...)` on the transaction. This matches production behavior.

- **Test categories**: Cross-user isolation (two users see only their own data), fail-closed (unset session variable returns 0 rows), reference data (company/company_alias not RLS-protected), complex queries (RLS across JOINs and CTEs).

### Additional Test Suites

- **Dashboard tests**: `tests/integration/linkedout/dashboard/` with its own conftest creating dashboard-specific test data. Tests the dashboard aggregation endpoint.

- **Enrichment pipeline tests**: `tests/integration/linkedout/enrichment_pipeline/` covers BYOK key management, import history, and enrichment stats endpoints.

- **Import pipeline tests**: `tests/integration/linkedout/import_pipeline/` covers the full import flow.

- **Query history tests**: `tests/integration/query_history/` covers query history flow and report data aggregation.

- **CLI integration tests**: `tests/integration/cli/` and `tests/integration/test_embed_command.py` test CLI commands that require a database.

### Marker Configuration

- **pytest.mark.integration**: All integration tests are marked with `@pytest.mark.integration` (either via `pytestmark` module-level assignment or individual decorators). They are excluded from default unit test runs via `addopts` in pytest.ini (`-m "not ... integration ..."`).

- **Running integration tests**: Use `pytest -m integration` to run only integration tests. This requires `DATABASE_URL` pointing to a live PostgreSQL database.

### Separate Test Directories

- **Top-level tests**: `/data/workspace/linkedout-oss/tests/` contains installation tests (`tests/installation/`) and skills tests (`tests/skills/`). These are separate from backend tests and have their own conftest with PostgreSQL availability checks.

- **Live LLM tests**: `backend/tests/live_llm/` contains tests that make real LLM calls, marked with `@pytest.mark.live_llm`. These require API keys.

- **Live services tests**: `backend/tests/live_services/` contains tests calling external services (e.g., Apify), marked with `@pytest.mark.live_services`.

- **Eval tests**: `backend/tests/eval/` contains search quality evaluation tests, marked with `@pytest.mark.eval`.

## Decisions

| Date | Decision | Chose | Over | Because |
|------|----------|-------|------|---------|
| 2026-04-09 | Isolation strategy | Per-worker PostgreSQL schema | Per-test transaction rollback | Schema isolation is cleaner for session-scoped fixtures and prevents FK constraint issues |
| 2026-04-09 | Skip behavior | `pytest.skip` when PostgreSQL unavailable | Hard failure | Developers without PostgreSQL can still run unit tests |
| 2026-04-09 | Fixture scope | Session-scoped | Function-scoped | One DB setup per session is much faster; tests should be additive, not destructive |
| 2026-04-09 | Search path includes public | Yes | Test schema only | pgvector extension types must be visible from the test schema |
| 2026-04-09 | checkfirst=False | Yes | Default checkfirst=True | Prevents SQLAlchemy from seeing public.* tables and skipping test schema creation |
| 2026-04-09 | RLS fixture scope | Module-scoped | Session-scoped | FORCE RLS affects the table owner too -- session scope would break all other tests that query RLS-protected tables |
| 2026-04-09 | RLS DDL execution | Same session (`integration_db_session`) | New connection | Avoids AccessExclusive lock deadlock with the session-scoped transaction |
| 2026-04-09 | RLS context mechanism | `get_session(app_user_id=...)` | Separate search engine | Single engine, RLS set per-session via `set_config`. Simpler, no second connection pool |

## Not Included

- Docker-compose for PostgreSQL setup (assumes pre-existing database)
- Migration testing (Alembic up/down verification)
- Performance benchmarks
- Load testing or concurrent request testing
- API contract testing against OpenAPI spec
- Project management entity tests (Label, Priority, Project, Task) -- removed from OSS
