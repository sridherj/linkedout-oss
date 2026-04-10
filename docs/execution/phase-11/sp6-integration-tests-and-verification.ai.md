# Sub-Phase 6: Integration Tests & Final Verification

**Phase:** 11 — Query History & Reporting
**Plan tasks:** Testing Strategy (from phase plan), Exit Criteria Verification
**Dependencies:** sp1, sp2, sp3, sp4, sp5
**Blocks:** —
**Can run in parallel with:** —

## Objective
Write integration tests that verify the end-to-end query logging flow, report data aggregation, and skill output correctness. Run the full exit criteria checklist and ensure everything works together.

## Context
- Read shared context: `docs/execution/phase-11/_shared_context.md`
- Read plan (Testing Strategy + Exit Criteria sections): `docs/plan/phase-11-query-history.md`
- Read all sub-phase deliverables for what needs to be tested

## Deliverables

### 1. `backend/tests/integration/query_history/test_query_history_flow.py` (NEW)

End-to-end query logging and readback test.

**Test cases:**
- `test_log_and_readback`: Log 5 queries via `log_query()`, read back the JSONL file, verify all 5 entries are present with correct fields
- `test_session_grouping`: Log 3 queries in same session (within timeout), verify all share same `session_id`. Then wait/simulate timeout, log another query, verify new `session_id`
- `test_date_based_file_routing`: Log queries on two different dates (mock `datetime.now()`), verify entries go to separate JSONL files
- `test_metrics_integration`: Log a query, verify a corresponding metric was recorded in `{data_dir}/metrics/daily/YYYY-MM-DD.jsonl` (if Phase 3I metrics module exists)
- `test_concurrent_writes`: Use `concurrent.futures.ThreadPoolExecutor` to log 20 queries simultaneously, verify JSONL file has exactly 20 valid JSON lines with no corruption

**Test setup:**
- Use `tmp_path` fixture to create isolated `LINKEDOUT_DATA_DIR`
- Set env var `LINKEDOUT_DATA_DIR` to `tmp_path` for test isolation
- Clean up after tests

### 2. `backend/tests/integration/query_history/test_report_data_aggregation.py` (NEW)

Test that the report skill's data aggregation logic works correctly across multiple data sources.

**Test cases:**
- `test_query_activity_aggregation`: Create sample JSONL files spanning 30 days, verify query count aggregation (total, weekly, monthly, daily averages) matches expected values
- `test_top_searches_extraction`: Create JSONL with known query patterns, verify top companies/topics extraction is correct
- `test_network_growth_from_import_reports`: Create sample `import-csv-*.json` report files, verify network growth calculations
- `test_graceful_degradation_missing_data`: Run aggregation with empty/missing directories, verify no errors and correct "no data" messages
- `test_report_persistence`: Generate a setup report, verify it's persisted to correct path, then verify historical comparison works against it

**Test setup:**
- Use `tmp_path` fixture for isolated data directory
- Create sample data files (JSONL, JSON reports) with known content
- For DB-dependent tests (network stats, profile freshness), either:
  - Use the real test DB if available (integration test context)
  - Or skip those sections with a note (if DB not available in test env)

### 3. `backend/tests/integration/query_history/__init__.py` (NEW)
Package init for integration test directory.

### 4. `backend/tests/unit/query_history/__init__.py` (NEW)
Package init for unit test directory (may already exist from sp1/sp2).

### 5. Exit Criteria Verification Script

Create a verification checklist that the runner can execute:

```bash
#!/bin/bash
# Phase 11 Exit Criteria Verification
set -e

echo "=== Phase 11: Query History & Reporting — Exit Criteria ==="

echo "1. Checking query_logger.py exists..."
test -f backend/src/linkedout/query_history/query_logger.py && echo "  PASS" || echo "  FAIL"

echo "2. Checking session_manager.py exists..."
test -f backend/src/linkedout/query_history/session_manager.py && echo "  PASS" || echo "  FAIL"

echo "3. Checking formatters.py exists..."
test -f backend/src/linkedout/query_history/formatters.py && echo "  PASS" || echo "  FAIL"

echo "4. Checking /linkedout-history skill exists..."
(test -f skills/linkedout-history/SKILL.md.tmpl || test -f skills/claude-code/linkedout-history/SKILL.md) && echo "  PASS" || echo "  FAIL"

echo "5. Checking /linkedout-report skill exists..."
(test -f skills/linkedout-report/SKILL.md.tmpl || test -f skills/claude-code/linkedout-report/SKILL.md) && echo "  PASS" || echo "  FAIL"

echo "6. Checking /linkedout-setup-report skill exists..."
(test -f skills/linkedout-setup-report/SKILL.md.tmpl || test -f skills/claude-code/linkedout-setup-report/SKILL.md) && echo "  PASS" || echo "  FAIL"

echo "7. Running unit tests..."
cd backend && uv run pytest tests/unit/query_history/ -v

echo "8. Running integration tests..."
uv run pytest tests/integration/query_history/ -v

echo "=== All checks complete ==="
```

This script is for the runner's reference — it does not need to be committed as a file unless the runner decides to.

## Verification
After completing all deliverables:
1. All unit tests from sp1 and sp2 pass: `cd backend && uv run pytest tests/unit/query_history/ -v`
2. All integration tests pass: `cd backend && uv run pytest tests/integration/query_history/ -v`
3. Walk the exit criteria checklist from the phase plan — every box should be checkable
4. Verify the three skills produce correct output with sample data
