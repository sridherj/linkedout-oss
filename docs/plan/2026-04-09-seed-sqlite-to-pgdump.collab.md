# Seed Pipeline: SQLite to pg_dump Migration

**Date:** 2026-04-09
**Status:** Draft
**Scope:** Seed export, import, test fixtures, demo fixture

---

## Context

The seed data pipeline uses SQLite as an intermediate format between PostgreSQL
export and PostgreSQL import. This creates an "impedance mismatch" bug class:
boolean casting (INTEGER 0/1 vs BOOLEAN), array serialization (JSON text vs
ARRAY), column naming differences (`active` vs `is_active`). We just fixed
several of these in the CI green effort, but they'll recur with any schema change.

**Goal:** Replace SQLite with pg_dump/pg_restore. Eliminate ~640 lines of type
conversion code and the entire bug class.

**Non-goal:** Change what seed data contains (still 6 company/reference tables).

---

## Current Pipeline (what exists today)

### Seed data scale
- **Core tier:** ~47K companies (companies with experience data from crawled profiles)
- **Full tier:** ~218K companies (companies with employee count, funding, or size tier)
- 6 tables: `company`, `company_alias`, `role_alias`, `funding_round`, `startup_tracking`, `growth_signal`
- Released as `seed-v0.1.0` on GitHub Releases

### Export (`backend/src/dev_tools/seed_export.py`) — 361 lines
Maintainer-only script. Connects to production PG, exports to SQLite:

1. Opens session with `SYSTEM_USER_ID` (for RLS bypass) via `db_session_manager`
2. Uses `SQLAlchemy inspect()` to dynamically read column metadata per table
3. Applies **tier filters** per table:
   - `CORE_COMPANY_FILTER`: `SELECT DISTINCT c.id FROM company c JOIN experience e ... JOIN crawled_profile cp ...`
   - `FULL_COMPANY_FILTER`: `SELECT DISTINCT c.id FROM company c WHERE estimated_employee_count > 0 OR EXISTS(funding_round) OR size_tier IS NOT NULL`
   - Each child table has `TABLE_FILTER_COLUMN` mapping (e.g., `company_alias` → `company_id`, `role_alias` → `None` = export all)
4. `_build_export_query()` builds `SELECT ... FROM {table} WHERE {fk_col} IN ({tier_subquery}) ORDER BY id`
5. `_build_select()` supports PII NULLing (currently empty — no PII in seed tables)
6. `_convert_row()` converts PG types → SQLite types (arrays → JSON strings, bools → 0/1, timestamps → ISO strings)
7. `_create_sqlite_table()` maps PG types to SQLite types via `_sqlite_type_for()`
8. Writes `_metadata` table (version, deterministic timestamp from `MAX(updated_at)`, source hash, table counts)
9. Generates `seed-manifest.json` (version, created_at, per-file: name, tier, size, sha256, table_counts)
10. Uses `PRAGMA journal_mode=DELETE` + `VACUUM` for deterministic output

**Key functions to keep:** `SEED_TABLES`, `TIER_COMPANY_FILTER`, `TABLE_FILTER_COLUMN`, `_build_export_query()`, `_build_select()`, `_get_columns()`, `_get_deterministic_timestamp()`, `_generate_manifest()`, CLI
**Key functions to delete:** `_sqlite_type_for()`, `_is_array()`, `_is_bool()`, `_is_temporal()`, `_create_sqlite_table()`, `_convert_row()`

### Import (`backend/src/linkedout/commands/import_seed.py`) — 402 lines
User-facing CLI command. Reads SQLite, upserts to PG:

1. `_locate_seed_file()` auto-detects `seed-core.sqlite` or `seed-full.sqlite` in `~/linkedout-data/seed/`
2. `_validate_seed_file()` reads `_metadata` table, checks all 6 tables exist
3. `read_seed_table()` reads all rows as dicts via `sqlite3.Row`
4. `_convert_row()` converts SQLite types → PG types:
   - `ARRAY_COLUMNS`: `company.enrichment_sources`, `funding_round.lead_investors`, `funding_round.all_investors` — JSON string → Python list
   - `BOOL_COLUMNS`: `is_active` on all tables, `startup_tracking.watching` — INTEGER → bool
5. `_build_upsert_sql()` generates parameterized INSERT ... ON CONFLICT: `VALUES (:col1, :col2, ...)` with `IS DISTINCT FROM` change detection and `RETURNING (xmax = 0)` for insert/update counting
6. `_import_table()` processes rows in `BATCH_SIZE=1000` batches, executing upsert **per row** (not bulk)
7. Dry-run mode: reads SQLite, compares IDs against PG, reports would-insert/would-skip counts
8. `_write_report()` generates JSON report + `OperationReport` + `record_metric()`

**Key functions to keep:** `IMPORT_ORDER`, `_locate_seed_file()` (updated), `_write_report()`, `OperationReport`, CLI interface, metric recording
**Key functions to delete:** `ARRAY_COLUMNS`, `BOOL_COLUMNS`, `_COMMON_BOOL`, `_convert_row()`, `read_seed_table()`, `read_seed_metadata()`, `get_sqlite_tables()`, `get_sqlite_columns()`, `_validate_seed_file()`, `_build_upsert_sql()`, `_import_table()`

### Download (`backend/src/linkedout/commands/download_seed.py`) — 330 lines
Downloads seed files from GitHub Releases. **Format-agnostic** — downloads binary + checksums.
Only changes needed: filename extensions in `_locate_seed_file()` and error messages.

### Demo fixture (`backend/tests/fixtures/generate_test_demo_dump.py`) — 422 lines
Generates a synthetic demo `.dump` for CI. Currently has **schema bugs**:
- Uses `active` instead of `is_active` (column renamed in entities)
- Hand-written DDL missing many columns (`deleted_at`, `created_by`, `updated_by`, `version`, `estimated_employee_count`, etc.)
- `demo-seed-test.dump` was **never generated** — `TestDemoRestoreCycle` tests always skip
- Connection table schema wrong: uses `profile_id`/`connected_profile_id` instead of actual entity FK structure

### Test fixture (`backend/tests/fixtures/generate_test_seed.py`) — 644 lines
Generates synthetic SQLite fixture for unit/integration tests. Same impedance mismatch:
- Hand-written DDL (270 lines) duplicates and may drift from entity metadata
- Writes booleans as INTEGER 0/1, arrays as JSON strings, timestamps as ISO strings
- Creates 10 tables (6 seed + crawled_profile, experience, education, profile_skill)
- Data counts: 10 companies, 15 aliases, 10 role aliases, 8 funding rounds, 5 tracking, 12 signals, 20 profiles, 40 experiences, 25 educations, 30 skills

---

## Decisions

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | Import approach | Staging schema + SQL upsert | pg_restore into `_seed_staging`, single SQL upsert per table into public. All-SQL, no Python type conversion. |
| 2 | Export approach | Staging schema per tier | pg_dump doesn't support WHERE. Populate staging via filtered SELECT, then pg_dump the schema. |
| 3 | Test fixture | Require PG to generate, commit `.dump` | Fixture is committed; CI doesn't regenerate. Developers regenerate only on schema change. |
| 4 | Demo fixture | Fix alongside seed (Phase 1) | Same pg_dump pattern. No reason to gate one on the other. |
| 5 | Backward compat | None | Pre-1.0 OSS. Users re-run `download-seed`. |
| 6 | db_url for subprocess | `get_config().database_url` | Matches codebase convention (`db_utils.py` pattern). Don't use `session.get_bind().url`. (Plan review 2026-04-09) |
| 7 | Manual CREATE SCHEMA in import | Remove — let pg_restore handle it | Dump already contains `CREATE SCHEMA`; `--clean --if-exists` handles idempotency. Keep only `DROP SCHEMA IF EXISTS` for cleanup. (Plan review 2026-04-09) |

---

## Architecture: Staging Schema Pattern

Both export and import use the same `_seed_staging` schema as a staging area.
This is the core pattern that eliminates the impedance mismatch.

### Export flow (maintainer-only)
```
PostgreSQL (production, ~218K companies full / ~47K core)
  |
  | Session opened with SYSTEM_USER_ID (RLS bypass)
  | inspect() reads column metadata dynamically
  |
  | DROP SCHEMA IF EXISTS _seed_staging CASCADE
  | CREATE SCHEMA _seed_staging
  |
  | For each table in SEED_TABLES:
  |   CREATE TABLE _seed_staging.{table} AS
  |     SELECT {_build_select(columns)} FROM public.{table}
  |     WHERE {fk_col} IN ({TIER_COMPANY_FILTER[tier]})
  |     ORDER BY id
  |   (role_alias has no filter — exports all rows)
  |
  v
_seed_staging schema (6 tables, filtered data, native PG types)
  |
  | pg_dump -Fc --schema=_seed_staging --no-owner {db_url}
  |
  v
seed-core.dump / seed-full.dump
  |
  | DROP SCHEMA _seed_staging CASCADE
  | Generate seed-manifest.json (version, sha256, table_counts, format: "pgdump")
  v
Output files ready for GitHub Release
```

### Import flow (user-facing)
```
seed-core.dump (downloaded file)
  |
  | _check_pg_restore() — verify pg_restore on PATH
  | _read_manifest() — read seed-manifest.json from same directory
  |
  | DROP SCHEMA IF EXISTS _seed_staging CASCADE  (clean start)
  | CREATE SCHEMA _seed_staging
  | pg_restore --dbname=... --no-owner --clean --if-exists
  | (exit code 0 or 1 = OK, >= 2 = failure)
  |
  v
_seed_staging schema (6 tables, all data from dump)
  |
  | For each table in IMPORT_ORDER:
  |   _get_intersected_columns() — columns in BOTH staging and public
  |   WITH upserted AS (
  |     INSERT INTO public.{table} ({intersected_cols})
  |     SELECT {intersected_cols} FROM _seed_staging.{table}
  |     ON CONFLICT (id) DO UPDATE SET {non_pk_cols}
  |     WHERE {IS DISTINCT FROM check}
  |     RETURNING (xmax = 0) AS was_insert
  |   )
  |   SELECT COUNT(*) FILTER (WHERE was_insert),
  |          COUNT(*) FILTER (WHERE NOT was_insert) FROM upserted
  |   skipped = staging_count - inserted - updated
  |
  v
public schema (upserted data)
  |
  | DROP SCHEMA _seed_staging CASCADE
  | _write_report() + OperationReport + record_metric()
  v
Done. Report: N inserted, N updated, N skipped per table.
```

### Column intersection (schema version safety)

The upsert uses the **intersection** of staging and public columns — columns
present in BOTH schemas. This handles version skew:
- User ran a migration adding a column → public has it, staging doesn't → column excluded from upsert (gets its DEFAULT)
- Seed dump has a column removed in user's newer migration → staging has it, public doesn't → column excluded

```sql
SELECT column_name FROM information_schema.columns
WHERE table_schema = '_seed_staging' AND table_name = :table
INTERSECT
SELECT column_name FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = :table
```

### Error handling for pg_restore

pg_restore exit codes: 0 = success, 1 = warnings (expected with `--clean --if-exists`
when tables don't exist yet). Only exit code >= 2 is a real failure. This matches
the pattern already proven in `linkedout.demo.db_utils.restore_demo_dump()`.

---

## Phase 1: Export Rewrite + Demo Fixture

**Goal:** Export produces `.dump` files. Demo fixture is fixed and generated.

### 1a. Fix demo fixture: `backend/tests/fixtures/generate_test_demo_dump.py`

**Current bugs:**
- Uses `active` instead of `is_active` in all 6 hand-written CREATE TABLE statements
- Missing columns: `deleted_at`, `created_by`, `updated_by`, `version`, `estimated_employee_count`, `universal_name`, `employee_count_range`, `parent_company_id`, `enrichment_sources`, `enriched_at`, `pdl_id`, `wikidata_id`, etc.
- Connection table uses wrong schema (`profile_id`/`connected_profile_id` instead of entity FK structure with `tenant_id`, `bu_id`, `app_user_id`, `crawled_profile_id`, `sources[]`)
- `demo-seed-test.dump` was never generated — file doesn't exist

**Fix approach:**
- Replace all hand-written DDL (`_create_schema()`) with `Base.metadata.create_all(engine, tables=[...])` using a filtered table list. Import the entity classes to register their metadata, then filter `Base.metadata.sorted_tables` to only demo-relevant tables: `company`, `crawled_profile`, `experience`, `education`, `profile_skill`, `connection`.
- This automatically gets correct column names, types, defaults, and constraints from the entity definitions.
- Keep `_insert_data()` but fix column names in INSERT statements to match entity metadata (e.g., `active` → `is_active`).
- Connection INSERTs need full rewrite to match actual entity schema.
- Generate `backend/tests/fixtures/demo-seed-test.dump` and commit it.
- Add `!backend/tests/fixtures/demo-seed-test.dump` to `.gitignore`.
- Verify: `pytest tests/integration/cli/test_demo_db_integration.py -m integration -v` — `TestDemoRestoreCycle` tests pass (no longer skipped).

### 1b. Rewrite seed export: `backend/src/dev_tools/seed_export.py`

**Delete (~120 lines):**
- `_sqlite_type_for()` (lines 83-102) — SQLite type mapping
- `_is_array()` (lines 105-107) — array detection
- `_is_bool()` (lines 110-111) — bool detection
- `_is_temporal()` (lines 114-115) — temporal detection
- `_create_sqlite_table()` (lines 171-182) — SQLite DDL generation
- `_convert_row()` (lines 153-166) — PG → SQLite type conversion
- All `sqlite3` imports
- SQLite-specific PRAGMA and VACUUM logic in `_export_tier()`

**Add (~80 lines):**
- `_create_staging_schema(session, tier)`:
  1. `DROP SCHEMA IF EXISTS _seed_staging CASCADE`
  2. `CREATE SCHEMA _seed_staging`
  3. For each table in `SEED_TABLES`:
     - `columns = _get_columns(inspector, table_name)` — reuse existing
     - `query = _build_export_query(table_name, columns, tier)` — reuse existing
     - `session.execute(text(f"CREATE TABLE _seed_staging.{table_name} AS {query}"))`
  4. `session.commit()`
- `_pg_dump_staging(db_url, output_path)`:
  - `subprocess.run(["pg_dump", "-Fc", "--schema=_seed_staging", "--no-owner", db_url], capture_output=True, timeout=300)`
  - Write `result.stdout` to `output_path`
  - Exit code 0 = ok, otherwise raise RuntimeError
- `_drop_staging_schema(session)`:
  - `session.execute(text("DROP SCHEMA IF EXISTS _seed_staging CASCADE"))`
  - `session.commit()`

**Keep unchanged:**
- `SEED_TABLES` (line 33-40) — same 6 tables
- `PII_NULL_COLUMNS`, `EXCLUDE_COLUMNS` (lines 43-46) — keep mechanism even though currently empty
- `CORE_COMPANY_FILTER`, `FULL_COMPANY_FILTER`, `TIER_COMPANY_FILTER`, `TABLE_FILTER_COLUMN` (lines 50-78) — all tier filtering logic
- `_build_select()` (lines 122-128) — PII NULLing in SELECT clause
- `_build_export_query()` (lines 131-142) — builds filtered SELECT with tier subquery
- `_get_columns()` (lines 147-150) — column metadata via inspect()
- `_get_deterministic_timestamp()` (lines 185-193) — for manifest

**Modify:**
- `_export_tier()` — replace SQLite file creation with: `_create_staging_schema()`, count rows per staging table, `_pg_dump_staging()`, `_drop_staging_schema()`. Keep dry-run counting logic (use existing `_build_export_query` + `SELECT COUNT(*)`).
- `_generate_manifest()` (lines 289-307) — `.dump` filenames, add `"format": "pgdump"` field
- `VERSION` — bump to `"0.2.0"`

**New `_export_tier()` flow:**
```python
def _export_tier(session, inspector, tier, output_dir, dry_run):
    # Count qualifying companies (unchanged)
    company_count = session.execute(text(f"SELECT COUNT(*) FROM ({TIER_COMPANY_FILTER[tier]}) _sub")).scalar()
    if company_count == 0: return None

    if dry_run:
        # Same as today: count rows per table using _build_export_query
        for table in SEED_TABLES:
            columns = _get_columns(inspector, table)
            query = _build_export_query(table, columns, tier)
            count = session.execute(text(f"SELECT COUNT(*) FROM ({query}) _sub")).scalar()
            table_counts[table] = count
        return None

    # NEW: staging schema approach
    _create_staging_schema(session, inspector, tier)  # CREATE TABLE AS SELECT per table

    # Count rows in staging tables (for manifest)
    table_counts = {}
    for table in SEED_TABLES:
        count = session.execute(text(f"SELECT COUNT(*) FROM _seed_staging.{table}")).scalar()
        table_counts[table] = count

    # pg_dump the staging schema
    filepath = output_dir / f"seed-{tier}.dump"
    _pg_dump_staging(db_url, filepath)

    # Cleanup
    _drop_staging_schema(session)

    # Compute checksum (reuse existing compute_sha256)
    sha256 = compute_sha256(filepath)
    return {"name": filepath.name, "tier": tier, "path": filepath, ...}
```

**Note on db_url for pg_dump subprocess:** The export currently gets its session via `db_session_manager.get_session()`. For the `pg_dump` subprocess call, we need the raw DATABASE_URL. Use `get_config().database_url` (not `session.get_bind().url`) — this matches the codebase convention used by `db_utils.py` and avoids potential credential-format differences. **[Decision A — plan review 2026-04-09]**

**Output:**
- `seed-core.dump`, `seed-full.dump` (replace `.sqlite`)
- `seed-manifest.json` with `"format": "pgdump"` field

### Verify Phase 1
- Run export against a test database → `.dump` files produced
- `pg_restore --list seed-core.dump` shows 6 tables in `_seed_staging` schema
- Demo integration tests pass

---

## Phase 2: Import Rewrite

**Goal:** Import reads `.dump` files via pg_restore + staging schema upsert.

### `backend/src/linkedout/commands/import_seed.py` — major rewrite

**Delete (~200 lines):**
- `ARRAY_COLUMNS` (lines 43-46) — SQLite → PG array mappings
- `BOOL_COLUMNS`, `_COMMON_BOOL` (lines 50-58) — SQLite → PG bool mappings
- `BATCH_SIZE` (line 60) — no longer needed (bulk upsert)
- `read_seed_metadata()` (lines 66-73) — SQLite metadata reader
- `read_seed_table()` (lines 76-87) — SQLite row reader
- `get_sqlite_tables()` (lines 90-99) — SQLite table lister
- `get_sqlite_columns()` (lines 102-109) — SQLite column reader
- `_convert_row()` (lines 115-128) — Python type conversion
- `_build_upsert_sql()` (lines 134-155) — parameterized VALUES upsert
- `_import_table()` (lines 158-187) — per-row batch import loop
- `_validate_seed_file()` (lines 215-235) — SQLite structure validation
- All `sqlite3` and `json` (for type conversion) imports

**Add (~150 lines):**

- `_check_pg_restore()` — verify pg_restore on PATH:
  ```python
  def _check_pg_restore():
      if not shutil.which("pg_restore"):
          raise click.ClickException(
              "pg_restore not found. Install the PostgreSQL client package.\n"
              "  Ubuntu/Debian: sudo apt-get install postgresql-client\n"
              "  macOS: brew install libpq"
          )
  ```

- `_get_db_url()` — get DATABASE_URL from config (matches codebase convention) **[Decision A — plan review 2026-04-09]**:
  ```python
  def _get_db_url():
      return get_config().database_url
  ```

- `_restore_to_staging(session, db_url, dump_path)`:
  ```python
  def _restore_to_staging(session, db_url, dump_path):
      # Clean start — handles prior failed imports
      session.execute(text("DROP SCHEMA IF EXISTS _seed_staging CASCADE"))
      session.commit()
      # pg_restore creates the _seed_staging schema from the dump (--clean --if-exists handles idempotency)
      # **[Decision B — plan review 2026-04-09]**: no manual CREATE SCHEMA; pg_restore handles it

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

- `_get_intersected_columns(session, table)`:
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

- `_build_staging_upsert_sql(table, columns)` — **new function** (NOT a modification of old `_build_upsert_sql`):
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
  Key difference from old `_build_upsert_sql`: source is `SELECT FROM _seed_staging.{table}` not `VALUES (:params)`. Entire table upserted in one SQL statement — no batch loop needed.

- `_count_staging_rows(session, table)`:
  ```python
  def _count_staging_rows(session, table):
      return session.execute(
          text(f"SELECT COUNT(*) FROM _seed_staging.{table}")
      ).scalar()
  ```

- `_drop_staging_schema(session)`:
  ```python
  def _drop_staging_schema(session):
      session.execute(text("DROP SCHEMA IF EXISTS _seed_staging CASCADE"))
      session.commit()
  ```

- `_read_manifest(dump_path)` — read `seed-manifest.json` from same directory as dump file:
  ```python
  def _read_manifest(dump_path):
      manifest_path = dump_path.parent / "seed-manifest.json"
      if not manifest_path.exists():
          return None
      return json.loads(manifest_path.read_text())
  ```

**Keep (modified):**
- `IMPORT_ORDER` — unchanged
- `_locate_seed_file()` — updated: look for `.dump` instead of `.sqlite`
- `_write_report()`, `OperationReport` — unchanged
- CLI interface (`--seed-file`, `--dry-run`) — unchanged
- `record_metric()` call — unchanged

**New `import_seed_command()` flow:**
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
            for table in IMPORT_ORDER:
                staging_count = _count_staging_rows(session, table)
                columns = _get_intersected_columns(session, table)
                sql = _build_staging_upsert_sql(table, columns)
                row = session.execute(text(sql)).fetchone()
                inserted, updated = row[0], row[1]
                skipped = staging_count - inserted - updated
                results[table] = {inserted, updated, skipped, total: staging_count}

            _drop_staging_schema(session)

    # 3. Report (unchanged)
    _write_report(results, ...)
    OperationReport(...)
    record_metric(...)
```

### `backend/src/linkedout/commands/download_seed.py` — minor updates
- `_locate_seed_file()` (if shared) — look for `.dump` instead of `.sqlite`
- Error messages referencing `.sqlite` → `.dump`
- Everything else is format-agnostic (downloads binary + checksums)
- No change to `_select_tier_file()`, `_download_file()`, `_fetch_manifest()`, `get_release_url()` — they work with filenames from the manifest

### CI workflow: `.github/workflows/ci.yml`
- Verify `pg_restore` is available on `ubuntu-latest` runner. The `pgvector/pgvector:pg16` service container has it, but the runner needs `postgresql-client` package. Add step if needed:
  ```yaml
  - name: Install PostgreSQL client
    run: sudo apt-get install -y postgresql-client
  ```
  (May already be present — check first before adding.)

### Verify Phase 2
- `linkedout import-seed --seed-file test-seed-core.dump` against clean PG → row counts match manifest
- `linkedout import-seed --seed-file test-seed-core.dump --dry-run` → no data written, counts displayed
- Run import twice → second run shows all "skipped"

---

## Phase 3: Test Fixtures + Tests

### 3a. Seed test fixture: `backend/tests/fixtures/generate_test_seed.py` — complete rewrite

**Current:** 644 lines of hand-written SQLite DDL + synthetic data. Creates 10 tables (6 seed + 4 profile) in SQLite.

**New:** Uses PostgreSQL + pg_dump, mirrors Phase 1 export pattern. Only creates 6 seed tables (profile tables are not part of seed pipeline).

**New flow:**
1. Create temp database `linkedout_seed_test_fixture` (same pattern as demo fixture)
2. `CREATE SCHEMA _seed_staging`
3. Create 6 seed tables in staging using `Base.metadata.create_all(engine, tables=[...])` — filtered to only seed-relevant entities. This prevents DDL drift.
4. Insert same synthetic data as current fixture — but in native PG types:
   - Booleans: `TRUE`/`FALSE` (not INTEGER 0/1)
   - Arrays: `ARRAY['linkedin', 'pdl']` (not JSON strings)
   - Timestamps: `TIMESTAMPTZ` (not ISO text strings)
   - Same counts: 10 companies, 15 aliases, 10 role aliases, 8 funding rounds, 5 tracking, 12 signals
   - Same IDs: `co_test_001` through `co_test_010`, etc.
   - **No profile/experience/education/skill data** — those tables are not part of seed pipeline
5. `pg_dump -Fc --schema=_seed_staging --no-owner` → `test-seed-core.dump`
6. Generate `seed-manifest.json` alongside (table counts, version `"0.0.1-test"`, format `"pgdump"`)
7. Drop temp database

**Data details preserved from current fixture:**
- 10 companies across industries (Technology, Finance, Healthcare, ...), split SF/NY
- 15 company aliases cycling across companies, alternating linkedin/manual source
- 10 role aliases: SWE, Sr SWE, PM, Sr PM, DS, ML Eng, VP Eng, CTO, Designer, DevOps
- 8 funding rounds across 4 companies (co_test_001-004), Seed + Series A each
- 5 startup tracking records (co_test_001-005), 3 watching + 2 not
- 12 growth signals cycling across 5 companies, alternating headcount/revenue

**Note:** This script requires PostgreSQL + pg_dump locally. The fixture is committed — regeneration is rare (only on schema change). The rewrite uses the same `_psql()` helper pattern as `generate_test_demo_dump.py`.

### 3b. File changes
- **Delete:** `backend/tests/fixtures/test-seed-core.sqlite`
- **Add:** `backend/tests/fixtures/test-seed-core.dump` (committed)
- **Add:** `backend/tests/fixtures/seed-manifest.json` (committed)
- **Update `.gitignore`:** swap `!backend/tests/fixtures/test-seed-core.sqlite` → `!backend/tests/fixtures/test-seed-core.dump`

### 3c. Unit tests: `backend/tests/unit/cli/test_import_seed.py`

**Delete (14 tests):**
- `TestSQLiteReading` class (7 tests) — no more SQLite reading functions
- `TestTypeConversion` class (7 tests) — no more type conversion functions

**Keep (modified):**
- `TestAutoDetect` (5 tests) — update `.sqlite` → `.dump` in filenames and assertions
- `TestFKOrdering` (5 tests) — unchanged (tests `IMPORT_ORDER` constant)
- `TestUpsertSQL` (5 tests) — update to test `_build_staging_upsert_sql()`:
  - Still pure string building (no PG needed)
  - Assert `ON CONFLICT (id) DO UPDATE`, `IS DISTINCT FROM`, `RETURNING`
  - Assert `SELECT {cols} FROM _seed_staging.{table}` (not `VALUES :params`)
  - Assert `id` not in SET clause
- `TestValidateSeedFile` (2 tests) — delete (no more SQLite validation)

**Add (~5 tests):**
- `TestManifestReading` — test `_read_manifest()`:
  - Valid JSON with all fields → returns dict
  - Missing manifest file → returns None
  - Malformed JSON → appropriate error
- `TestStagingUpsertSQL` — test `_build_staging_upsert_sql()`:
  - SQL contains `_seed_staging.{table}` as source
  - Uses CTE with `WITH upserted AS (...)`

**Coverage note:** Unit test count drops from 29 to ~20. The new staging/restore logic (schema creation, column intersection, pg_restore subprocess) is inherently integration-level — it needs PostgreSQL. Integration tests in `test_seed_pipeline.py` cover this gap. This is acceptable: the SQLite tests were testing SQLite, not business logic.

### 3d. Unit tests: `backend/tests/unit/cli/test_download_seed.py`
- Update fixture filenames: `seed-core.sqlite` → `seed-core.dump`
- Rest is format-agnostic

### 3e. Integration tests: `backend/tests/integration/cli/test_seed_pipeline.py`

**Current state:**
- `FIXTURE_PATH` points to `test-seed-core.sqlite`
- `expected_counts` reads from SQLite `_metadata` table via `read_seed_metadata()`
- `TestUpdateDetection` copies the SQLite file, modifies it with `sqlite3`, re-imports
- Uses `sqlite3` imports

**Changes:**
- `FIXTURE_PATH` → `test-seed-core.dump`
- `expected_counts` → read from `seed-manifest.json` fixture file (JSON, not SQLite metadata)
- Remove `sqlite3` imports, `read_seed_metadata` import
- `TestUpdateDetection.test_modified_row_detected` — **simplify**: first import from dump, then `UPDATE company SET canonical_name = 'MODIFIED' WHERE id = 'co_test_001'` directly in PG, then re-import the original dump and verify the row is "updated" back. No need to copy/modify a dump file.
- Add test: `test_import_with_pg_restore_unavailable` — mock `shutil.which` to return None, verify clear error message.

### 3f. Setup tests: `backend/tests/linkedout/setup/test_seed_data.py`
- Update any `.sqlite` references to `.dump`

### Verify Phase 3
```bash
pytest tests/unit/cli/test_import_seed.py -v
pytest tests/unit/cli/test_download_seed.py -v
pytest tests/integration/cli/test_seed_pipeline.py -m integration -v
pytest tests/integration/cli/test_demo_db_integration.py -m integration -v
```

---

## Phase 4: Docs, Specs, and Cleanup

### 4a. Specs (update SQLite → pg_dump references)

- **`docs/specs/seed_data.collab.md`** — **major update** (~20 SQLite references):
  - File names: `seed-core.sqlite` → `seed-core.dump`, `seed-full.sqlite` → `seed-full.dump`
  - Data format section: SQLite transport → pg_dump format, staging schema pattern
  - Manifest section: add `"format": "pgdump"` field
  - Import behavior: remove SQLite `_metadata` table, type conversion, `_convert_row()` references
  - Export section: staging schema pattern, `pg_dump` instead of SQLite
  - Design decision: update "SQLite as transport format" rationale to explain pg_dump choice
  - Non-features: remove "export user's data back to SQLite"
- **`docs/specs/cli_commands.collab.md`** — update seed-related command descriptions:
  - `import-seed`: `.sqlite` → `.dump` in auto-detect, file references
  - `download-seed`: mention `.dump` format
  - Design decision table: update seed data format row
- **`docs/specs/linkedout_import_pipeline.collab.md`** — **major update** (~10 references):
  - Seed import section: remove SQLite source format, type conversion, `_metadata` references
  - Add staging schema pattern, pg_restore, column intersection
  - Design decision: update "SQLite as seed distribution format" → "pg_dump as seed distribution format"
  - Edge case: remove "validates 6 tables exist in SQLite file"

**NOT affected** (SQLite references are about unit test infrastructure, not seed pipeline):
- `docs/specs/unit_tests.collab.md` — SQLite in-memory for unit tests (stays)
- `docs/specs/database_session_management.collab.md` — SQLite dialect handling (stays)
- `docs/specs/database_indexing.collab.md` — SQLite compatibility for indexes (stays)
- `docs/specs/linkedout_crud.collab.md` — SQLite-compatible column types for unit tests (stays)
- `docs/specs/integration_tests.collab.md` — SQLite skip logic (stays, still valid)
- `docs/specs/linkedout_dashboard.collab.md` — unnest() SQLite note (stays)
- `docs/specs/linkedout_data_model.collab.md` — SQLite compat notes (stays)

### 4b. Documentation

- **`seed-data/README.md`** — **major rewrite** (~30 SQLite references):
  - All file references: `.sqlite` → `.dump`
  - Regenerating section: staging schema + pg_dump instead of SQLite
  - Publishing section: `seed-core.dump` / `seed-full.dump` in `gh release create`
  - Verification: `pg_restore --list` instead of `sqlite3 ... "SELECT count(*)"`
  - Remove "SQLite provides a portable single-file format" rationale
- **`docs/getting-started.md`** — minor:
  - Line 141: "SQLite files" → "dump files" in directory tree
- **`tests/README.md`** — **no change needed**:
  - SQLite references are about unit test infrastructure (in-memory SQLite for unit tests), not seed pipeline

### 4c. Other files

- **`backend/src/dev_tools/import_pdl_companies.py`** — **NOT affected**: reads PDL's own SQLite DB (People Data Labs), completely unrelated to seed pipeline
- **`backend/conftest.py`** — **NOT affected**: SQLite in-memory engine for unit tests, unrelated to seed pipeline
- **`backend/src/shared/infra/db/db_session_manager.py`** — **NOT affected**: SQLite dialect handling for unit tests
- **`plan_and_progress/LEARNINGS.md`** — **no change**: historical references, not actionable
- **`skills/linkedout-dev/SKILL.md`** — minor: one reference to "not SQLite stubs" — no change needed (describes integration tests vs unit tests)

### 4d. Final sweep
- Grep for remaining `.sqlite` references in seed-related code (exclude unit test infrastructure)
- Verify `seed-manifest.json` format field is `"pgdump"` in all generated manifests
- Push, CI green

---

## Files Summary

| File | Change | Phase |
|------|--------|-------|
| `backend/tests/fixtures/generate_test_demo_dump.py` | Fix schema (use Base.metadata), fix column names, fix connection schema | 1 |
| `backend/tests/fixtures/demo-seed-test.dump` | Generate + commit | 1 |
| `backend/src/dev_tools/seed_export.py` | Major rewrite: delete ~120 lines SQLite code, add ~80 lines staging schema code | 1 |
| `backend/src/linkedout/commands/import_seed.py` | Major rewrite: delete ~200 lines SQLite/conversion, add ~150 lines staging/upsert | 2 |
| `backend/src/linkedout/commands/download_seed.py` | Update `.sqlite` → `.dump` in locate + error messages | 2 |
| `.github/workflows/ci.yml` | Add postgresql-client if needed | 2 |
| `backend/tests/fixtures/generate_test_seed.py` | Complete rewrite: SQLite → PG + pg_dump, drop profile tables | 3 |
| `backend/tests/fixtures/test-seed-core.sqlite` | Delete | 3 |
| `backend/tests/fixtures/test-seed-core.dump` | New, committed | 3 |
| `backend/tests/fixtures/seed-manifest.json` | New, committed | 3 |
| `backend/tests/unit/cli/test_import_seed.py` | Delete 14 tests, modify 5, add ~5 | 3 |
| `backend/tests/unit/cli/test_download_seed.py` | Filename updates | 3 |
| `backend/tests/integration/cli/test_seed_pipeline.py` | Moderate rewrite: remove sqlite3, simplify update detection | 3 |
| `backend/tests/linkedout/setup/test_seed_data.py` | Minor `.sqlite` → `.dump` updates | 3 |
| `.gitignore` | Update fixture exclusions | 3 |
| `docs/specs/seed_data.collab.md` | Major update: SQLite → pg_dump throughout | 4 |
| `docs/specs/cli_commands.collab.md` | Update seed command descriptions | 4 |
| `docs/specs/linkedout_import_pipeline.collab.md` | Major update: SQLite → staging schema + pg_restore | 4 |
| `seed-data/README.md` | Major rewrite: all SQLite refs → pg_dump | 4 |
| `docs/getting-started.md` | Minor: "SQLite files" → "dump files" | 4 |

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| pg_restore not on CI runner | Check ubuntu-latest; add `postgresql-client` install step if needed |
| Staging schema left behind on crash | `DROP SCHEMA IF EXISTS _seed_staging CASCADE` at start of both export and import |
| Column mismatch (seed version vs user migration) | Column intersection query — only upsert columns present in both schemas |
| pg_restore exit code 1 (warnings) | Match demo pattern: treat 0 and 1 as success, >= 2 as failure |
| Test fixture requires PG to regenerate | Fixture is committed; devs only regenerate on schema change |
| Unit test coverage drops (14 deleted) | Integration tests cover the staging/restore logic; deleted tests were testing SQLite, not business logic |
| Demo fixture connection schema wrong | Use Base.metadata.create_all() to get correct schema from entity definitions |
| db_url extraction for subprocess | Use `str(session.get_bind().url)` to get connection URL from SQLAlchemy engine |
| Large staging schema during import (~218K companies) | Staging is temporary; dropped immediately after upsert. Disk usage is transient. |
