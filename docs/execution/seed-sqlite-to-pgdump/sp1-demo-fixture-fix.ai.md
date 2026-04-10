# SP1: Fix Demo Fixture

**Phase:** 1a — Export Rewrite + Demo Fixture
**Sub-phase:** 1 of 6
**Dependencies:** None (parallelizable with SP2)
**Estimated effort:** ~30 minutes
**Shared context:** `_shared_context.md`

---

## Scope

Fix the demo fixture generator so it produces a valid `.dump` file using entity metadata instead of hand-written DDL. This eliminates schema drift bugs.

**Plan section:** Phase 1, task 1a

---

## Inputs

- `backend/tests/fixtures/generate_test_demo_dump.py` (current: 422 lines, buggy hand-written DDL)
- Entity classes for schema metadata (company, crawled_profile, experience, education, profile_skill, connection)
- Existing `_psql()` helper pattern used in the file

## Outputs

- `backend/tests/fixtures/generate_test_demo_dump.py` — fixed
- `backend/tests/fixtures/demo-seed-test.dump` — newly generated and committed
- `.gitignore` — add `!backend/tests/fixtures/demo-seed-test.dump`

---

## Task 1: Replace Hand-Written DDL with Entity Metadata

**File:** `backend/tests/fixtures/generate_test_demo_dump.py`

### Current bugs
- Uses `active` instead of `is_active` in all 6 hand-written CREATE TABLE statements
- Missing columns: `deleted_at`, `created_by`, `updated_by`, `version`, `estimated_employee_count`, `universal_name`, `employee_count_range`, `parent_company_id`, `enrichment_sources`, `enriched_at`, `pdl_id`, `wikidata_id`, etc.
- Connection table uses wrong schema (`profile_id`/`connected_profile_id` instead of entity FK structure with `tenant_id`, `bu_id`, `app_user_id`, `crawled_profile_id`, `sources[]`)
- `demo-seed-test.dump` was never generated — file doesn't exist

### Fix approach
1. **Replace all hand-written DDL** (`_create_schema()`) with `Base.metadata.create_all(engine, tables=[...])` using a filtered table list
2. Import the entity classes to register their metadata, then filter `Base.metadata.sorted_tables` to only demo-relevant tables: `company`, `crawled_profile`, `experience`, `education`, `profile_skill`, `connection`
3. This automatically gets correct column names, types, defaults, and constraints from entity definitions

### Specific changes
- Delete `_create_schema()` function and all hand-written CREATE TABLE statements
- Add entity imports to register metadata
- Replace `_create_schema()` call with `Base.metadata.create_all(engine, tables=[filtered_list])`
- Keep `_insert_data()` but fix column names in INSERT statements to match entity metadata (e.g., `active` → `is_active`)
- Connection INSERTs need full rewrite to match actual entity schema (with `tenant_id`, `bu_id`, `app_user_id`, `crawled_profile_id`, `sources[]`)

---

## Task 2: Generate and Commit Demo Dump

1. Run the fixed generator to produce `backend/tests/fixtures/demo-seed-test.dump`
2. Commit the dump file
3. Add `!backend/tests/fixtures/demo-seed-test.dump` to `.gitignore` (so it's tracked despite being a binary-ish file)

---

## Task 3: Verify Demo Integration Tests

Run:
```bash
pytest tests/integration/cli/test_demo_db_integration.py -m integration -v
```

**Expected:** `TestDemoRestoreCycle` tests pass (no longer skipped because the dump file now exists).

---

## Verification Checklist

- [ ] `generate_test_demo_dump.py` uses `Base.metadata.create_all()` instead of hand-written DDL
- [ ] No hand-written CREATE TABLE statements remain in the file
- [ ] Column names match entity definitions (especially `is_active`, not `active`)
- [ ] Connection table INSERTs match actual entity schema
- [ ] `demo-seed-test.dump` exists in `backend/tests/fixtures/`
- [ ] `.gitignore` has `!backend/tests/fixtures/demo-seed-test.dump`
- [ ] `pytest tests/integration/cli/test_demo_db_integration.py -m integration -v` — TestDemoRestoreCycle passes
