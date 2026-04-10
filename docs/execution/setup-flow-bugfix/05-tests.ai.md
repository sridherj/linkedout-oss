# Sub-phase 05: Tests

## Metadata
- **Depends on:** 01, 02a-d, 03 (tests verify code from those phases)
- **Blocks:** nothing
- **Estimated scope:** 3 test files (new or extended)
- **Plan section:** Phase 5 (5a-5d)

## Context

Read `_shared_context.md` for system record IDs, timestamp requirements, and fixed_data
imports.

## Task 5a: Unit tests for `bootstrap_system_records()`

**File:** `backend/tests/linkedout/setup/test_database.py` (extend existing)

Tests:
1. Bootstrap runs without error when tables exist and are empty
2. Idempotent — run twice, second run doesn't error or duplicate
3. FK ordering is correct (tenant before BU)
4. ON CONFLICT DO NOTHING when records already exist

Pattern: Mock `create_engine` and verify the 3 INSERT statements are executed in order.
Match existing test patterns in this file.

## Task 5b: Unit tests for `load_csv_batch()` counter correctness

**File:** `backend/tests/linkedout/commands/test_import_connections.py` (new or extend)

Tests:
1. Valid rows: counters sum to `total` (no double-counting)
2. `url_index` updated only after commit
3. Error on ConnectionEntity insert: `errors` increments, other counter does NOT
4. Duplicate URL in same batch: documented behavior (creates duplicate stub, caught by
   unique constraint)

Pattern: Use SQLAlchemy session with savepoint support. May need PostgreSQL integration
test if SQLite savepoint behavior differs.

## Task 5c: Regression test for `user_profile.py` timestamp fix

**File:** `backend/tests/linkedout/setup/test_user_profile.py` (new or extend)

Test: Mock SQLAlchemy session, verify INSERT statement text includes `created_at` and
`updated_at`. This is a known failure mode that warrants a regression test.

## Task 5d: Verify existing tests pass after `sys.executable` change

Run:
```bash
cd backend && python -m pytest tests/linkedout/setup/test_csv_import.py tests/linkedout/setup/test_contacts_import.py -v
```

Current tests use `"import-connections" in call_args` (not exact list equality), so they
should pass. Verify explicitly.

## Completion Criteria
- [ ] Bootstrap idempotency tests pass
- [ ] CSV counter correctness tests pass
- [ ] Timestamp regression test passes
- [ ] Existing tests still pass after sys.executable changes
- [ ] All new tests follow existing patterns in the test suite
