# SP6: Integration Testing

**Sub-Phase:** 6 of 6
**Tasks:** 7G (Integration Testing)
**Complexity:** M
**Depends on:** SP3 (download-seed command), SP4 (import-seed command)
**Blocks:** None (final sub-phase)

---

## Objective

Write unit and integration tests for the seed data pipeline: download command, import command, checksum verification, upsert idempotency, FK ordering, and the full end-to-end flow.

---

## Context

Read `_shared_context.md` for project-level context and testing approach.

**Agent references:**
- `.claude/agents/integration-test-creator-agent.md` — Follow this agent's patterns for test fixtures (`test_client`, `seeded_data`, `integration_db_session`), session-scoped DB setup, and test organization
- `.claude/agents/seed-test-db-creator-agent.md` — Reference for `SeedDb`, `TableName` enum, `SeedConfig` patterns when creating test seed fixtures

**Key constraints:**
- Unit tests run in CI with no external dependencies
- Integration tests require a test PostgreSQL database
- Test fixture is a small SQLite file (~10 rows per table) committed to the repo
- Do NOT test against real GitHub Releases in CI — mock HTTP calls

---

## Tasks

### 1. Create Test Fixture SQLite

**File:** `backend/tests/fixtures/test-seed-core.sqlite` (NEW)

Create a small SQLite database with the same schema as production seed files but with ~10 rows per table. Use synthetic/fake data (not real profiles).

Include:
- 10 companies with varied attributes (some with funding, some without)
- 15 company aliases
- 10 role aliases
- 8 funding rounds across 4 companies
- 5 startup tracking records
- 12 growth signals
- 20 crawled profiles linked to the 10 companies
- 40 experience records
- 25 education records
- 30 profile skills
- `_metadata` table with version "0.0.1-test", timestamps, and row counts

Write a Python script to generate this fixture: `backend/tests/fixtures/generate_test_seed.py`. This script should be runnable to regenerate the fixture if the schema changes.

### 2. Unit Tests for Download Command

**File:** `backend/tests/unit/cli/test_download_seed.py` (NEW)

Test cases:

**Manifest parsing and validation:**
- Parse a valid manifest JSON → correct structure
- Invalid manifest (missing fields) → raises clear error
- Manifest with unknown tier → graceful handling

**Checksum verification:**
- Correct checksum → returns True
- Incorrect checksum → returns False
- Empty file → valid checksum (of empty content)

**URL construction:**
- Default URL → `https://github.com/sridherj/linkedout-oss/releases/download/<version>/`
- `LINKEDOUT_SEED_URL` env var overrides base URL
- Version parsing (with and without `seed-v` prefix)

**Skip-if-exists logic:**
- File exists + checksum matches + no --force → skip
- File exists + checksum matches + --force → download
- File exists + checksum mismatch → download
- File doesn't exist → download

**Tier selection:**
- Default → selects "core" file from manifest
- `--full` → selects "full" file from manifest

### 3. Unit Tests for Import Command

**File:** `backend/tests/unit/cli/test_import_seed.py` (NEW)

Test cases:

**SQLite reading:**
- Read all rows from a table in the test fixture → correct count and data
- Read `_metadata` table → correct version and row counts
- Missing table → clear error

**Auto-detect logic:**
- `seed-core.sqlite` in seed dir → found
- `seed-full.sqlite` in seed dir (no core) → found
- No SQLite files → error pointing to `linkedout download-seed`
- Multiple files → prefers core

**FK ordering:**
- Import tables in correct order → no errors
- Verify the hardcoded order matches expected dependencies

**Upsert logic (using test fixture + in-memory SQLite as mock target, or test DB):**
- Insert new row → counted as "inserted"
- Insert duplicate row with same data → counted as "skipped"
- Insert duplicate row with changed data → counted as "updated"

### 4. Integration Tests

**File:** `backend/tests/integration/cli/test_seed_pipeline.py` (NEW)

These tests require a test PostgreSQL database. Use whatever test DB setup the project already uses (check existing integration tests for patterns).

Test cases:

**Full import pipeline:**
- Import test fixture into empty PostgreSQL → all rows inserted
- Verify row counts per table match fixture metadata
- Verify FK relationships are intact (e.g., experience records point to valid profiles)

**Idempotency:**
- Import test fixture twice → second run shows all "skipped"
- Verify row counts unchanged after second import

**Update detection:**
- Import test fixture → modify a company name in the SQLite → re-import → one "updated" for company table

**Dry-run mode:**
- Import with `--dry-run` → verify no rows in PostgreSQL
- Output shows correct counts of what would be imported

**Report generation:**
- After import, verify JSON report exists at expected path
- Report contains correct per-table counts and duration

**Error handling:**
- Import with missing table in SQLite → clear error, no partial import
- Import with invalid data type → clear error identifying the problem row

### 5. Test for Operation Result Pattern

Both commands should produce output matching the Operation Result Pattern. Test this by capturing CLI output:

```python
from click.testing import CliRunner

def test_import_seed_output_format():
    runner = CliRunner()
    result = runner.invoke(import_seed, ["--seed-file", str(fixture_path)])
    assert "Results:" in result.output
    assert "Next steps:" in result.output
    assert "Report saved:" in result.output
```

---

## Files to Create

| File | Description |
|------|-------------|
| `backend/tests/fixtures/generate_test_seed.py` | Script to generate test fixture |
| `backend/tests/fixtures/test-seed-core.sqlite` | Test fixture (generated by script) |
| `backend/tests/unit/cli/test_download_seed.py` | Download command unit tests |
| `backend/tests/unit/cli/test_import_seed.py` | Import command unit tests |
| `backend/tests/integration/cli/test_seed_pipeline.py` | Integration tests |

---

## Verification

### Run Unit Tests
```bash
cd backend
pytest tests/unit/cli/test_download_seed.py -v
pytest tests/unit/cli/test_import_seed.py -v
```

### Run Integration Tests
```bash
cd backend
pytest tests/integration/cli/test_seed_pipeline.py -v
```

### Check Coverage
- All public functions in `download_seed.py` and `import_seed.py` should be covered
- Upsert logic has insert/update/skip paths tested
- Error paths tested (missing file, bad checksum, bad data)

---

## Acceptance Criteria

- [ ] Test fixture SQLite exists with ~10 rows per table and correct schema
- [ ] Fixture generation script is runnable (`python generate_test_seed.py`)
- [ ] Unit tests for download: manifest parsing, checksum, URL construction, skip logic, tier selection
- [ ] Unit tests for import: SQLite reading, auto-detect, FK ordering, upsert logic
- [ ] Integration test: full import into PostgreSQL, correct row counts
- [ ] Integration test: idempotency (import twice → all skips)
- [ ] Integration test: dry-run produces no writes
- [ ] Integration test: report generation with correct structure
- [ ] Operation Result Pattern verified in CLI output
- [ ] All unit tests pass without external dependencies
- [ ] All integration tests pass with test PostgreSQL
