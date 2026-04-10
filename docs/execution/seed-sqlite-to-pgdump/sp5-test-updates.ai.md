# SP5: Update All Tests

**Phase:** 3c-3f — Test Fixtures + Tests
**Sub-phase:** 5 of 6
**Dependencies:** SP4 (test fixture must exist), SP3 (import code must be rewritten)
**Estimated effort:** ~45 minutes
**Shared context:** `_shared_context.md`

---

## Scope

Update all test files to work with the new pg_dump-based seed pipeline: delete obsolete SQLite tests, update remaining tests for new function signatures and file formats, add new tests for manifest reading and pg_restore error handling.

**Plan section:** Phase 3, tasks 3c through 3f

---

## Inputs

- `backend/tests/unit/cli/test_import_seed.py` (current unit tests for import)
- `backend/tests/unit/cli/test_download_seed.py` (current unit tests for download)
- `backend/tests/integration/cli/test_seed_pipeline.py` (current integration tests)
- `backend/tests/linkedout/setup/test_seed_data.py` (setup tests)
- SP3 outputs: new import functions (`_build_staging_upsert_sql`, `_read_manifest`, etc.)
- SP4 outputs: `test-seed-core.dump`, `seed-manifest.json`

## Outputs

- All 4 test files updated
- Tests pass: unit + integration

---

## Task 1: Unit Tests — test_import_seed.py

**File:** `backend/tests/unit/cli/test_import_seed.py`

### Delete (14 tests)
- `TestSQLiteReading` class (7 tests) — no more SQLite reading functions
- `TestTypeConversion` class (7 tests) — no more type conversion functions

### Delete (2 tests)
- `TestValidateSeedFile` class (2 tests) — no more SQLite validation

### Keep and modify
- **`TestAutoDetect` (5 tests):** Update `.sqlite` → `.dump` in filenames and assertions. The tests check `_locate_seed_file()` logic — same pattern, different file extension.
- **`TestFKOrdering` (5 tests):** Unchanged — tests `IMPORT_ORDER` constant, which didn't change.
- **`TestUpsertSQL` (5 tests):** Update to test `_build_staging_upsert_sql()`:
  - Still pure string building (no PG needed)
  - Assert SQL contains `ON CONFLICT (id) DO UPDATE`
  - Assert SQL contains `IS DISTINCT FROM`
  - Assert SQL contains `RETURNING (xmax = 0) AS was_insert`
  - Assert SQL contains `SELECT {cols} FROM _seed_staging.{table}` (not `VALUES :params`)
  - Assert `id` not in SET clause

### Add (~5 new tests)
- **`TestManifestReading`** — test `_read_manifest()`:
  - Valid JSON with all fields → returns dict
  - Missing manifest file → returns None
  - Malformed JSON → appropriate error
- **`TestStagingUpsertSQL`** — test `_build_staging_upsert_sql()`:
  - SQL contains `_seed_staging.{table}` as source
  - Uses CTE with `WITH upserted AS (...)`
  - Handles single-column table (only `id`) — no SET clause or WHERE clause in that edge case

### Coverage note
Unit test count drops from ~29 to ~20. This is acceptable: the deleted tests were testing SQLite operations, not business logic. The staging/restore logic (schema creation, column intersection, pg_restore subprocess) is inherently integration-level — it needs PostgreSQL. Integration tests cover this gap.

---

## Task 2: Unit Tests — test_download_seed.py

**File:** `backend/tests/unit/cli/test_download_seed.py`

- Update fixture filenames: `seed-core.sqlite` → `seed-core.dump` in any assertions or mock data
- Rest is format-agnostic — no other changes expected

---

## Task 3: Integration Tests — test_seed_pipeline.py

**File:** `backend/tests/integration/cli/test_seed_pipeline.py`

### Changes
1. **`FIXTURE_PATH`:** Update from `test-seed-core.sqlite` → `test-seed-core.dump`
2. **`expected_counts`:** Read from `seed-manifest.json` fixture file (JSON, not SQLite `_metadata` table via `read_seed_metadata()`)
3. **Remove imports:** `sqlite3`, `read_seed_metadata`
4. **`TestUpdateDetection.test_modified_row_detected`:** Simplify approach:
   - First import from dump (populates public schema)
   - Then `UPDATE company SET canonical_name = 'MODIFIED' WHERE id = 'co_test_001'` directly in PG
   - Then re-import the original dump
   - Verify the row is "updated" back (count shows 1 updated)
   - **No need to copy/modify a dump file** — modify public data, re-import staging data
5. **Add test:** `test_import_with_pg_restore_unavailable` — mock `shutil.which` to return None, verify `click.ClickException` with clear error message about installing postgresql-client

---

## Task 4: Setup Tests — test_seed_data.py

**File:** `backend/tests/linkedout/setup/test_seed_data.py`

- Update any `.sqlite` references to `.dump`
- Minimal changes expected — mostly file extension references

---

## Verification Checklist

- [ ] No `sqlite3` imports remain in any test file
- [ ] No references to `read_seed_metadata`, `read_seed_table`, `get_sqlite_tables`, `get_sqlite_columns` in tests
- [ ] `TestSQLiteReading` and `TestTypeConversion` classes deleted from `test_import_seed.py`
- [ ] `TestValidateSeedFile` class deleted from `test_import_seed.py`
- [ ] `TestAutoDetect` updated: `.sqlite` → `.dump`
- [ ] `TestUpsertSQL` updated: tests `_build_staging_upsert_sql()` with staging schema assertions
- [ ] New `TestManifestReading` tests added
- [ ] `test_download_seed.py` updated: `.sqlite` → `.dump`
- [ ] `test_seed_pipeline.py` reads expected counts from `seed-manifest.json` (not SQLite metadata)
- [ ] `TestUpdateDetection` simplified: modify PG directly, re-import dump
- [ ] `test_import_with_pg_restore_unavailable` added
- [ ] `test_seed_data.py` updated: `.sqlite` → `.dump`
- [ ] Run all tests:
  ```bash
  pytest tests/unit/cli/test_import_seed.py -v
  pytest tests/unit/cli/test_download_seed.py -v
  pytest tests/integration/cli/test_seed_pipeline.py -m integration -v
  pytest tests/integration/cli/test_demo_db_integration.py -m integration -v
  ```
