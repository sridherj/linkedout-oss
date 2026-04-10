# SP6: Docs, Specs, and Cleanup

**Phase:** 4 — Docs, Specs, and Cleanup
**Sub-phase:** 6 of 6
**Dependencies:** SP5 (all tests must pass before updating docs/specs)
**Estimated effort:** ~30 minutes
**Shared context:** `_shared_context.md`

---

## Scope

Update all documentation and specs to reflect the SQLite → pg_dump migration. Final sweep for stale references. Push and verify CI green.

**Plan section:** Phase 4

---

## Inputs

- All code changes from SP1-SP5 (complete)
- Documentation and spec files with SQLite references

## Outputs

- 3 spec files updated
- 2 documentation files updated
- Final grep confirms no stale `.sqlite` references in seed-related code

---

## Task 1: Update Specs

### `docs/specs/seed_data.collab.md` — Major update (~20 SQLite references)

- File names: `seed-core.sqlite` → `seed-core.dump`, `seed-full.sqlite` → `seed-full.dump`
- Data format section: SQLite transport → pg_dump format, staging schema pattern
- Manifest section: add `"format": "pgdump"` field description
- Import behavior: remove SQLite `_metadata` table, type conversion, `_convert_row()` references
- Export section: staging schema pattern, `pg_dump` instead of SQLite
- Design decision: update "SQLite as transport format" rationale to explain pg_dump choice
- Non-features: remove "export user's data back to SQLite" if present

### `docs/specs/cli_commands.collab.md` — Moderate update

- `import-seed` command: `.sqlite` → `.dump` in auto-detect, file references
- `download-seed` command: mention `.dump` format
- Design decision table: update seed data format row

### `docs/specs/linkedout_import_pipeline.collab.md` — Major update (~10 references)

- Seed import section: remove SQLite source format, type conversion, `_metadata` references
- Add staging schema pattern, pg_restore, column intersection description
- Design decision: update "SQLite as seed distribution format" → "pg_dump as seed distribution format"
- Edge case: remove "validates 6 tables exist in SQLite file"

### Files NOT affected (SQLite references are about unit test infrastructure, not seed pipeline)
Do NOT modify these — their SQLite references are about the unit test in-memory database, not the seed pipeline:
- `docs/specs/unit_tests.collab.md`
- `docs/specs/database_session_management.collab.md`
- `docs/specs/database_indexing.collab.md`
- `docs/specs/linkedout_crud.collab.md`
- `docs/specs/integration_tests.collab.md`
- `docs/specs/linkedout_dashboard.collab.md`
- `docs/specs/linkedout_data_model.collab.md`

---

## Task 2: Update Documentation

### `seed-data/README.md` — Major rewrite (~30 SQLite references)

- All file references: `.sqlite` → `.dump`
- Regenerating section: staging schema + pg_dump instead of SQLite
- Publishing section: `seed-core.dump` / `seed-full.dump` in `gh release create`
- Verification: `pg_restore --list` instead of `sqlite3 ... "SELECT count(*)"`
- Remove "SQLite provides a portable single-file format" rationale
- Add brief explanation of pg_dump format advantages

### `docs/getting-started.md` — Minor

- Line ~141: "SQLite files" → "dump files" in directory tree description
- Any other seed-related `.sqlite` references

---

## Task 3: Verify No Changes Needed

Confirm these files do NOT need changes (SQLite references are about unrelated systems):
- `backend/src/dev_tools/import_pdl_companies.py` — reads PDL's own SQLite DB (People Data Labs), completely unrelated to seed pipeline
- `backend/conftest.py` — SQLite in-memory engine for unit tests
- `backend/src/shared/infra/db/db_session_manager.py` — SQLite dialect handling for unit tests
- `plan_and_progress/LEARNINGS.md` — historical references, not actionable
- `skills/linkedout-dev/SKILL.md` — "not SQLite stubs" description (integration tests vs unit tests)

---

## Task 4: Final Sweep

1. **Grep for stale references:**
   ```bash
   grep -rn "\.sqlite" backend/src/ backend/tests/ --include="*.py" | grep -i seed
   grep -rn "\.sqlite" docs/ seed-data/ --include="*.md" | grep -i seed
   ```
   Only hits should be in files explicitly noted as NOT affected (PDL, unit test infrastructure).

2. **Verify manifest format:**
   Check all generated `seed-manifest.json` files contain `"format": "pgdump"`.

3. **Push and verify CI green:**
   ```bash
   git push
   ```
   Wait for CI to complete. All tests should pass.

---

## Verification Checklist

- [ ] `docs/specs/seed_data.collab.md` — all SQLite references updated to pg_dump
- [ ] `docs/specs/cli_commands.collab.md` — seed command descriptions updated
- [ ] `docs/specs/linkedout_import_pipeline.collab.md` — staging schema pattern documented
- [ ] `seed-data/README.md` — all `.sqlite` → `.dump`, regeneration instructions updated
- [ ] `docs/getting-started.md` — directory tree updated
- [ ] Grep confirms no stale `.sqlite` references in seed-related code/docs
- [ ] Files confirmed NOT needing changes: `import_pdl_companies.py`, `conftest.py`, `db_session_manager.py`
- [ ] CI green after push
