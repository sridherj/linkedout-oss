# SP3: Rewrite Seed Import

**Phase:** 2 — Import Rewrite
**Sub-phase:** 3 of 6
**Dependencies:** SP1 (demo fixture), SP2 (export rewrite) — both must complete first
**Estimated effort:** ~60 minutes
**Shared context:** `_shared_context.md`

---

## Scope

Major rewrite of the seed import command: replace SQLite reading + Python type conversion with pg_restore + staging schema SQL upsert. Also update download command and CI workflow.

**Plan section:** Phase 2

---

## Inputs

- `backend/src/linkedout/commands/import_seed.py` (current: 402 lines)
- `backend/src/linkedout/commands/download_seed.py` (current: 330 lines)
- `.github/workflows/ci.yml`
- SP2 outputs: understanding of `.dump` file format and staging schema pattern

## Outputs

- `backend/src/linkedout/commands/import_seed.py` — major rewrite
- `backend/src/linkedout/commands/download_seed.py` — minor updates
- `.github/workflows/ci.yml` — postgresql-client step if needed

---

## Task 1: Delete SQLite Code from import_seed.py (~200 lines)

**File:** `backend/src/linkedout/commands/import_seed.py`

Delete these functions/constants:
- `ARRAY_COLUMNS` (lines ~43-46) — SQLite → PG array mappings
- `BOOL_COLUMNS`, `_COMMON_BOOL` (lines ~50-58) — SQLite → PG bool mappings
- `BATCH_SIZE` (line ~60) — no longer needed (bulk upsert replaces batch loop)
- `read_seed_metadata()` (lines ~66-73) — SQLite metadata reader
- `read_seed_table()` (lines ~76-87) — SQLite row reader
- `get_sqlite_tables()` (lines ~90-99) — SQLite table lister
- `get_sqlite_columns()` (lines ~102-109) — SQLite column reader
- `_convert_row()` (lines ~115-128) — Python type conversion
- `_build_upsert_sql()` (lines ~134-155) — parameterized VALUES upsert
- `_import_table()` (lines ~158-187) — per-row batch import loop
- `_validate_seed_file()` (lines ~215-235) — SQLite structure validation
- All `sqlite3` and `json` (for type conversion) imports

---

## Task 2: Add New Functions (~150 lines)

### `_check_pg_restore()`
```python
def _check_pg_restore():
    if not shutil.which("pg_restore"):
        raise click.ClickException(
            "pg_restore not found. Install the PostgreSQL client package.\n"
            "  Ubuntu/Debian: sudo apt-get install postgresql-client\n"
            "  macOS: brew install libpq"
        )
```

### `_get_db_url()`
```python
def _get_db_url():
    return get_config().database_url
```
**Decision #6:** Use `get_config().database_url`, not `session.get_bind().url`.

### `_restore_to_staging(session, db_url, dump_path)`
```python
def _restore_to_staging(session, db_url, dump_path):
    # Clean start — handles prior failed imports
    session.execute(text("DROP SCHEMA IF EXISTS _seed_staging CASCADE"))
    session.commit()
    # Decision #7: no manual CREATE SCHEMA; pg_restore creates it from the dump

    result = subprocess.run(
        ["pg_restore", f"--dbname={db_url}", "--no-owner",
         "--clean", "--if-exists", str(dump_path)],
        capture_output=True, text=True, timeout=300,
    )
    # Match demo pattern: 0 and 1 are OK, >= 2 is failure
    if result.returncode not in (0, 1):
        raise click.ClickException(
            f"pg_restore failed (exit {result.returncode}): {result.stderr[:500]}"
        )
    if result.returncode == 1 and result.stderr:
        logger.warning(f"pg_restore warnings: {result.stderr[:500]}")
```

### `_get_intersected_columns(session, table)`
```python
def _get_intersected_columns(session, table):
    rows = session.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = '_seed_staging' AND table_name = :table
        INTERSECT
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = :table
    """), {"table": table}).fetchall()
    return [r[0] for r in rows]
```

### `_build_staging_upsert_sql(table, columns)`
This is a **new function** (NOT a modification of old `_build_upsert_sql`):
```python
def _build_staging_upsert_sql(table, columns):
    col_list = ", ".join(columns)
    non_pk = [c for c in columns if c != "id"]
    set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in non_pk)
    where_parts = [f"public.{table}.{c} IS DISTINCT FROM EXCLUDED.{c}" for c in non_pk]
    where_clause = " OR ".join(where_parts)

    return f"""
    WITH upserted AS (
        INSERT INTO public.{table} ({col_list})
        SELECT {col_list} FROM _seed_staging.{table}
        ON CONFLICT (id) DO UPDATE SET {set_clause}
        WHERE {where_clause}
        RETURNING (xmax = 0) AS was_insert
    )
    SELECT
        COUNT(*) FILTER (WHERE was_insert) AS inserted,
        COUNT(*) FILTER (WHERE NOT was_insert) AS updated
    FROM upserted
    """
```
Key difference from old `_build_upsert_sql`: source is `SELECT FROM _seed_staging.{table}` not `VALUES (:params)`. Entire table upserted in one SQL statement.

### `_count_staging_rows(session, table)`
```python
def _count_staging_rows(session, table):
    return session.execute(
        text(f"SELECT COUNT(*) FROM _seed_staging.{table}")
    ).scalar()
```

### `_drop_staging_schema(session)`
```python
def _drop_staging_schema(session):
    session.execute(text("DROP SCHEMA IF EXISTS _seed_staging CASCADE"))
    session.commit()
```

### `_read_manifest(dump_path)`
```python
def _read_manifest(dump_path):
    manifest_path = dump_path.parent / "seed-manifest.json"
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text())
```

---

## Task 3: Rewrite `import_seed_command()` Flow

```python
@click.command('import-seed')
@click.option('--seed-file', ...)
@click.option('--dry-run', ...)
@cli_logged('import_seed')
def import_seed_command(seed_file, dry_run):
    start = time.time()

    # 1. Locate dump file, check pg_restore
    dump_path = _locate_seed_file(seed_file)
    _check_pg_restore()
    manifest = _read_manifest(dump_path)

    # Display version info from manifest (replaces _validate_seed_file)
    if manifest:
        click.echo(f"Seed version: {manifest.get('version', 'unknown')}")

    # 2. Restore to staging + upsert
    with db_session_manager.get_session(DbSessionType.WRITE, app_user_id=SYSTEM_USER_ID) as session:
        db_url = _get_db_url()  # from get_config(), not session
        _restore_to_staging(session, db_url, dump_path)

        if dry_run:
            # Count rows in staging, compare to public
            for table in IMPORT_ORDER:
                staging_count = _count_staging_rows(session, table)
                public_count = session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                # Report what would happen
            _drop_staging_schema(session)
        else:
            results = {}
            for table in IMPORT_ORDER:
                staging_count = _count_staging_rows(session, table)
                columns = _get_intersected_columns(session, table)
                sql = _build_staging_upsert_sql(table, columns)
                row = session.execute(text(sql)).fetchone()
                inserted, updated = row[0], row[1]
                skipped = staging_count - inserted - updated
                results[table] = {"inserted": inserted, "updated": updated, "skipped": skipped, "total": staging_count}

            _drop_staging_schema(session)

    # 3. Report (unchanged pattern)
    _write_report(results, ...)
    OperationReport(...)
    record_metric(...)
```

---

## Task 4: Update `_locate_seed_file()`

Both in `import_seed.py` and `download_seed.py` (if shared or duplicated):
- Look for `.dump` instead of `.sqlite`
- Update auto-detect logic: `seed-core.dump` or `seed-full.dump` in `~/linkedout-data/seed/`

---

## Task 5: Update download_seed.py (Minor)

**File:** `backend/src/linkedout/commands/download_seed.py`

- Update `_locate_seed_file()` if it exists here — look for `.dump` instead of `.sqlite`
- Update error messages referencing `.sqlite` → `.dump`
- Everything else is format-agnostic (downloads binary + checksums) — no changes needed to `_select_tier_file()`, `_download_file()`, `_fetch_manifest()`, `get_release_url()`

---

## Task 6: CI Workflow

**File:** `.github/workflows/ci.yml`

Check if `pg_restore` is available on `ubuntu-latest` runner. The `pgvector/pgvector:pg16` service container has it, but the runner itself needs `postgresql-client`. Add step if not already present:

```yaml
- name: Install PostgreSQL client
  run: sudo apt-get install -y postgresql-client
```

**Check first** — it may already be present. Only add if needed.

---

## Task 7: Add New Imports

Add to `import_seed.py`:
- `import subprocess`
- `import shutil`
- `from backend.src.shared.infra.config import get_config` (or wherever `get_config` lives)

Remove from `import_seed.py`:
- `import sqlite3`
- Any `json` imports used solely for type conversion

---

## Verification Checklist

- [ ] No `sqlite3` imports remain in `import_seed.py`
- [ ] No SQLite conversion constants remain (`ARRAY_COLUMNS`, `BOOL_COLUMNS`, `_COMMON_BOOL`, `BATCH_SIZE`)
- [ ] No SQLite reader functions remain (`read_seed_metadata`, `read_seed_table`, `get_sqlite_tables`, `get_sqlite_columns`, `_validate_seed_file`)
- [ ] No Python type conversion functions remain (`_convert_row`, old `_build_upsert_sql`, `_import_table`)
- [ ] New functions added: `_check_pg_restore`, `_get_db_url`, `_restore_to_staging`, `_get_intersected_columns`, `_build_staging_upsert_sql`, `_count_staging_rows`, `_drop_staging_schema`, `_read_manifest`
- [ ] `_locate_seed_file()` looks for `.dump` not `.sqlite`
- [ ] `import_seed_command()` uses staging schema pattern
- [ ] db_url via `get_config().database_url` (Decision #6)
- [ ] No manual `CREATE SCHEMA` in restore — pg_restore handles it (Decision #7)
- [ ] pg_restore exit codes: 0 and 1 OK, >= 2 failure
- [ ] `download_seed.py` updated (`.sqlite` → `.dump` in locate + error messages)
- [ ] CI workflow has `postgresql-client` if needed
- [ ] `linkedout import-seed --seed-file test-seed-core.dump` against clean PG → row counts match
- [ ] `linkedout import-seed --seed-file test-seed-core.dump --dry-run` → no data written, counts displayed
- [ ] Import twice → second run shows all "skipped"
