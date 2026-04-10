# SP2: Rewrite Seed Export

**Phase:** 1b — Export Rewrite + Demo Fixture
**Sub-phase:** 2 of 6
**Dependencies:** None (parallelizable with SP1)
**Estimated effort:** ~45 minutes
**Shared context:** `_shared_context.md`

---

## Scope

Rewrite the seed export script to use the staging schema + pg_dump pattern instead of SQLite. Delete ~120 lines of SQLite type conversion code, add ~80 lines of staging schema code.

**Plan section:** Phase 1, task 1b

---

## Inputs

- `backend/src/dev_tools/seed_export.py` (current: 361 lines)

## Outputs

- `backend/src/dev_tools/seed_export.py` — rewritten
- Export produces `seed-core.dump` / `seed-full.dump` instead of `.sqlite`
- `seed-manifest.json` includes `"format": "pgdump"` field

---

## Task 1: Delete SQLite Code (~120 lines)

**File:** `backend/src/dev_tools/seed_export.py`

Delete these functions/code blocks:
- `_sqlite_type_for()` (lines ~83-102) — SQLite type mapping
- `_is_array()` (lines ~105-107) — array detection helper
- `_is_bool()` (lines ~110-111) — bool detection helper
- `_is_temporal()` (lines ~114-115) — temporal detection helper
- `_create_sqlite_table()` (lines ~171-182) — SQLite DDL generation
- `_convert_row()` (lines ~153-166) — PG → SQLite type conversion
- All `sqlite3` imports
- SQLite-specific PRAGMA and VACUUM logic in `_export_tier()`

---

## Task 2: Add Staging Schema Functions (~80 lines)

Add these new functions:

### `_create_staging_schema(session, inspector, tier)`
```python
def _create_staging_schema(session, inspector, tier):
    session.execute(text("DROP SCHEMA IF EXISTS _seed_staging CASCADE"))
    session.execute(text("CREATE SCHEMA _seed_staging"))
    for table_name in SEED_TABLES:
        columns = _get_columns(inspector, table_name)
        query = _build_export_query(table_name, columns, tier)
        session.execute(text(f"CREATE TABLE _seed_staging.{table_name} AS {query}"))
    session.commit()
```

### `_pg_dump_staging(db_url, output_path)`
```python
def _pg_dump_staging(db_url, output_path):
    result = subprocess.run(
        ["pg_dump", "-Fc", "--schema=_seed_staging", "--no-owner", str(db_url)],
        capture_output=True, timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed (exit {result.returncode}): {result.stderr.decode()[:500]}")
    output_path.write_bytes(result.stdout)
```

### `_drop_staging_schema(session)`
```python
def _drop_staging_schema(session):
    session.execute(text("DROP SCHEMA IF EXISTS _seed_staging CASCADE"))
    session.commit()
```

---

## Task 3: Modify `_export_tier()`

Replace the SQLite file creation logic with the staging schema pattern:

```python
def _export_tier(session, inspector, tier, output_dir, dry_run):
    # Count qualifying companies (unchanged from current code)
    company_count = session.execute(
        text(f"SELECT COUNT(*) FROM ({TIER_COMPANY_FILTER[tier]}) _sub")
    ).scalar()
    if company_count == 0:
        return None

    if dry_run:
        # Same as today: count rows per table using _build_export_query
        for table in SEED_TABLES:
            columns = _get_columns(inspector, table)
            query = _build_export_query(table, columns, tier)
            count = session.execute(text(f"SELECT COUNT(*) FROM ({query}) _sub")).scalar()
            table_counts[table] = count
        return None

    # NEW: staging schema approach
    _create_staging_schema(session, inspector, tier)

    # Count rows in staging tables (for manifest)
    table_counts = {}
    for table in SEED_TABLES:
        count = session.execute(text(f"SELECT COUNT(*) FROM _seed_staging.{table}")).scalar()
        table_counts[table] = count

    # pg_dump the staging schema
    filepath = output_dir / f"seed-{tier}.dump"
    db_url = get_config().database_url  # Decision #6: use get_config(), not session.get_bind().url
    _pg_dump_staging(db_url, filepath)

    # Cleanup
    _drop_staging_schema(session)

    # Compute checksum (reuse existing compute_sha256)
    sha256 = compute_sha256(filepath)
    return {"name": filepath.name, "tier": tier, "path": filepath, "sha256": sha256, "table_counts": table_counts}
```

**Important:** For db_url, use `get_config().database_url` — this is Decision #6 from plan review. Do NOT use `session.get_bind().url`.

---

## Task 4: Update `_generate_manifest()`

- Change filenames from `.sqlite` to `.dump`
- Add `"format": "pgdump"` field to the manifest JSON
- Bump `VERSION` to `"0.2.0"`

---

## Task 5: Add `subprocess` import

Add `import subprocess` at the top of the file if not already present.

---

## Verification Checklist

- [ ] No `sqlite3` imports remain in `seed_export.py`
- [ ] No SQLite type conversion functions remain (`_sqlite_type_for`, `_is_array`, `_is_bool`, `_is_temporal`, `_create_sqlite_table`, `_convert_row`)
- [ ] `_create_staging_schema()`, `_pg_dump_staging()`, `_drop_staging_schema()` added
- [ ] `_export_tier()` uses staging schema pattern
- [ ] db_url obtained via `get_config().database_url` (not `session.get_bind().url`)
- [ ] `VERSION` bumped to `"0.2.0"`
- [ ] `_generate_manifest()` produces `.dump` filenames and `"format": "pgdump"`
- [ ] `SEED_TABLES`, `TIER_COMPANY_FILTER`, `TABLE_FILTER_COLUMN`, `_build_select()`, `_build_export_query()`, `_get_columns()`, `_get_deterministic_timestamp()` all preserved unchanged
- [ ] `PII_NULL_COLUMNS`, `EXCLUDE_COLUMNS` preserved (mechanism kept even though currently empty)
- [ ] Run export against a test database → `.dump` files produced
- [ ] `pg_restore --list seed-core.dump` shows 6 tables in `_seed_staging` schema
