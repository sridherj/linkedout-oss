# Sub-phase 2: Execution-Layer Security — PostgreSQL RLS Implementation

## Prerequisites
- **SP1 complete** (benchmark needed to measure impact of RLS change)
- Manual prereq done: `linkedout_search_role` created in PostgreSQL

## Outcome
All search SQL queries are tenant-scoped at the database level via RLS. The LLM no longer adds WHERE clauses for scoping. The system prompt is stripped of scoping instructions.

## Estimated Effort
2-3 sessions (spike completed, implementation is mechanical)

## Verification Criteria
- [ ] Run full benchmark, compare scores -- equal or better vs SP1 baseline (no regression)
- [ ] Raw SQL without `app_user_id` WHERE clause via `psql` with search role -- returns only scoped data
- [ ] SQL with unset session variable -- returns 0 rows (fail-closed)
- [ ] Integration test: two different `app_user_id` values see different result sets for the same query
- [ ] System prompt no longer mentions `app_user_id` scoping

---

## Activities

### 2.1 Create Non-Superuser DB Role
- Script: `scripts/create_search_role.sh` -- creates `linkedout_search_role` with SELECT-only on all tables
- **Already done** as manual prereq. Verify the role exists and has correct permissions.
- Role must NOT be table owner (owner bypasses RLS)

### 2.2 RLS Policies (Alembic Migration)
- Single Alembic migration with raw SQL `op.execute()`:
  - `ALTER TABLE connection ENABLE ROW LEVEL SECURITY`
  - Policy on `connection`: `USING (app_user_id = current_setting('app.current_user_id')::uuid)`
  - `ALTER TABLE crawled_profile ENABLE ROW LEVEL SECURITY`
  - Policy on `crawled_profile`: `USING (id IN (SELECT crawled_profile_id FROM connection WHERE app_user_id = current_setting('app.current_user_id')::uuid))`
  - Same subquery policy on `experience`, `education`, `profile_skill` (all JOIN via `crawled_profile_id`)
  - `company` and `company_alias`: **NO RLS** (reference data shared across users)
  - `FORCE ROW LEVEL SECURITY` on all tables with policies
- Add composite index: `CREATE INDEX idx_connection_user_profile ON connection(app_user_id, crawled_profile_id)` -- optimizes subquery policies
- **Spike reference:** `rls-spike-report.md` has the exact policy SQL and edge case results. RLS Option B verified: zero correctness issues across JOINs, CTEs, window functions, correlated subqueries, UNIONs, EXISTS, LEFT JOINs.

### 2.3 Session Variable Injection (Two-Engine Approach)
- Add a second engine to `DbSessionManager` connected as `linkedout_search_role`
- Expose via `get_search_session()` method that:
  1. Creates a session on the search engine
  2. Calls `session.execute(text("SELECT set_config('app.current_user_id', :uid, true)"), {"uid": str(app_user_id)})` before returning
- Main engine remains for writes; search engine is RLS-enforced reads only
- This must happen BEFORE any LLM-generated SQL executes in the same transaction
- **Key file:** `src/linkedout/shared/infra/db_session_manager.py`

### 2.4 Strip Scoping from Prompt
- Remove all `app_user_id` scoping instructions from `search_system.md`
- Remove the advisory "always include WHERE app_user_id" from `execute_sql` tool description
- Remove few-shot examples that include `app_user_id` in SQL WHERE clauses
- The LLM should now write SQL as if querying a single-user database

### 2.5 Validate
- Run full benchmark. Compare against SP1 baseline
- Run targeted queries that previously included `app_user_id` -- verify still correct
- Run same query with two different `app_user_id` session vars -- verify different results
- **Fail-closed test:** If `set_config` is not called, session variable defaults to empty string. `::uuid` cast will fail. Verify this returns 0 rows, not an error visible to the user.

### 2.6 Spec Update
- `/update-spec` for `linkedout_intelligence.collab.md`:
  - Current spec says "The SQL tool warns but does not block queries missing :app_user_id binding" -- replaced by RLS enforcement
  - Decision record says "Rejected: row-level security" -- reversed, RLS is now chosen
  - The advisory scoping model is replaced by database-level enforcement

---

## Design Review Notes

| ID | Issue | Resolution |
|----|-------|------------|
| A2 | Spec conflict: `linkedout_intelligence.collab.md` > Decisions > "Over: row-level security" | Decision reversed. RLS is now chosen. `/update-spec` in 2.6 |
| A2 | Spec conflict: edge note about advisory scoping | Replaced by RLS enforcement. `/update-spec` in 2.6 |
| A2 | Two DB engines in `DbSessionManager` | Main for writes, `linkedout_search_role` for RLS reads. `get_search_session()` method |
| Security | Fail-closed verification critical | Integration test: unset session variable returns 0 rows |
| Architecture | Separate connection pool for search | `get_search_session()` factory isolates connection management |

## Key Files to Read First
- `src/linkedout/shared/infra/db_session_manager.py` -- needs second engine
- `src/linkedout/intelligence/tools/sql_tool.py` -- needs to use search session
- `src/linkedout/intelligence/prompts/search_system.md` -- strip scoping instructions
- `docs/specs/linkedout_intelligence.collab.md` -- spec to update
- `.taskos/rls-spike-report.md` (in goal dir) -- RLS policy SQL and edge case results
