# Decision: Change RLS policies from FOR SELECT to FOR ALL

**Date:** 2026-04-04
**Status:** Accepted
**Context:** LinkedOut stub reconciliation and affinity scoring

## Question
Should RLS policies on `connection` and `crawled_profile` tables use `FOR SELECT` (read-only isolation) or `FOR ALL` (full CRUD isolation)?

## Key Findings
- Original `FOR SELECT` policies correctly isolated reads by `app_user_id`
- With `FORCE ROW LEVEL SECURITY = true`, `FOR SELECT` silently blocks all INSERT/UPDATE/DELETE -- writes return 0 rows affected with no error
- This silently broke `compute-affinity` CLI (returned "0 connections updated") and `reconcile-stubs` merge operations
- The `linkedout_user` DB role is used by both the application and CLI tools, so it must support writes through RLS

## Decision
Recreate RLS policies as `FOR ALL` on `connection` and `crawled_profile` tables. The policy expression remains the same (`app_user_id = current_setting('app.current_user_id')`), but now applies to all operations.

This is the correct choice because:
1. The application legitimately writes to these tables under the same user context
2. `FOR SELECT` + `FORCE ROW LEVEL SECURITY` creates a silent-failure mode that violates Principle of Least Surprise
3. `FOR ALL` still enforces tenant isolation -- users can only write to their own rows

## Implications
- All CLI scripts touching RLS-protected tables must pass `app_user_id` via `get_session(DbSessionType.WRITE, app_user_id=uid)`
- These policy changes should be captured in an Alembic migration (not yet done)
- Other RLS-protected tables should be audited for the same `FOR SELECT` vs `FOR ALL` issue
- The `compute-affinity` CLI needs the same `app_user_id` fix applied

## References
- `src/dev_tools/reconcile_stubs.py` -- first script to hit this issue
- `src/linkedout/intelligence/scoring/affinity_scorer.py` -- affinity computation also affected
- `plan_and_progress/LEARNINGS.md` -- 2026-04-04 entries
