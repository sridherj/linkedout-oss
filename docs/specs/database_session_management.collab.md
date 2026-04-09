---
feature: database-session-management
module: backend/src/shared/infra/db
linked_files:
  - backend/src/shared/infra/db/db_session_manager.py
  - backend/src/shared/config/settings.py
  - backend/src/common/controllers/base_controller_utils.py
version: 1
last_verified: "2026-04-09"
---

# Database & Session Management

**Created:** 2026-04-09 — Adapted from internal spec for LinkedOut OSS

## Intent

Provide a centralized database session manager (singleton) that enforces consistent session handling patterns: READ sessions auto-rollback, WRITE sessions auto-commit on success and rollback on error. Supports both PostgreSQL (production/integration) and SQLite (unit tests) with dialect-aware read-only enforcement.

## Behaviors

### DbSessionManager (Singleton)

- **Singleton pattern**: Only one `DbSessionManager` instance exists. Calling `DbSessionManager()` always returns the same instance. Verify multiple instantiations return the same object.

- **Auto initialization**: On first instantiation, the engine is created from `get_config().database_url` with echo controlled by `get_config().db_echo_log`. Verify the engine is ready after initialization.

- **Custom engine for tests**: `set_engine(engine)` replaces the engine and session factory. Used by tests to inject SQLite in-memory engines. Verify that after `set_engine`, sessions come from the new engine.

### Session Types

- **READ session**: `get_session(DbSessionType.READ)` provides a context-managed session that auto-rollbacks on exit. On PostgreSQL, sets `SET TRANSACTION READ ONLY`. On SQLite, sets `PRAGMA query_only = ON`. Verify no data is persisted after a READ session exits.

- **WRITE session**: `get_session(DbSessionType.WRITE)` provides a context-managed session that auto-commits on success and rollbacks on exception. On SQLite, resets `PRAGMA query_only = OFF`. Verify data is committed after a successful WRITE session.

- **Exception handling**: On any exception within the session context, the session is rolled back and the exception is re-raised. Verify partial writes are not persisted when an error occurs mid-transaction.

### RLS-Scoped Sessions

- **app_user_id parameter**: `get_session(app_user_id=uid)` sets `app.current_user_id` via PostgreSQL `set_config(..., true)` (transaction-scoped). RLS policies on `connection`, `crawled_profile`, `experience`, `education`, `profile_skill` and other tables use this session variable to enforce tenant isolation. On SQLite (unit tests), this is a no-op. Verify RLS scoping is applied when `app_user_id` is provided and ignored on SQLite.

- **Controller-level RLS wiring**: `create_service_dependency(service_class, session_type, app_user_id=)` in `common/controllers/base_controller_utils.py` passes `app_user_id` through to `get_session()`. Controllers for RLS-protected tables accept `X-App-User-Id` header and forward it via this parameter. Both read and write operations are RLS-gated — the migration creates `FOR SELECT` and `FOR ALL` policies on `connection`, `crawled_profile`, `experience`, `education`, and `profile_skill` tables. All endpoints that touch RLS-protected tables must pass `app_user_id`.

### Raw Session

- **Manual management**: `get_raw_session(session_type)` returns a session without context management. The caller is responsible for commit/rollback/close. Defaults to WRITE session type. Verify the session is functional but requires manual lifecycle management.

### Dialect-Aware Read-Only

- **PostgreSQL**: READ sessions execute `SET TRANSACTION READ ONLY`. Verify write operations within a READ session raise a database error on PostgreSQL.

- **SQLite**: READ sessions execute `PRAGMA query_only = ON`. If the pragma fails, a warning is logged but execution continues. Verify the fallback behavior does not crash.

### Entity Discovery

- **Import-based registration**: The session manager module imports all entity packages to ensure SQLAlchemy discovers all entity classes. Current entities: `organization`, `common`, `linkedout.company`, `linkedout.company_alias`, `linkedout.role_alias`, `linkedout.crawled_profile`, `linkedout.experience`, `linkedout.education`, `linkedout.profile_skill`, `linkedout.connection`, `linkedout.import_job`, `linkedout.contact_source`, `linkedout.enrichment_event`, `organization.enrichment_config`. Verify all entities appear in `Base.metadata.tables` after import.

## Decisions

| Date | Decision | Chose | Over | Because |
|------|----------|-------|------|---------|
| 2026-03-25 | Session pattern | Context manager with auto-commit/rollback | Manual session management everywhere | Prevents session leaks and ensures consistent transaction handling |
| 2026-03-25 | Read-only enforcement | Dialect-specific SQL commands | Application-level read-only flag | Database-level enforcement catches bugs that app-level checks miss |
| 2026-03-25 | Singleton | Module-level `db_session_manager` | Dependency injection | Simple, works well with FastAPI's dependency system |

## Not Included

- Connection pooling configuration (uses SQLAlchemy defaults)
- Read replica routing
- Async session support (uses sync SQLAlchemy)
- Database migration execution (handled by Alembic separately)
- Health check or connection validation
