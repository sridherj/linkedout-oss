# SP4: `linkedout import-seed` CLI Command

**Sub-Phase:** 4 of 6
**Tasks:** 7D (import-seed command)
**Complexity:** L
**Depends on:** SP1 (manifest schema)
**Blocks:** SP6 (integration testing)

---

## Objective

Implement the `linkedout import-seed` CLI command that reads a downloaded SQLite seed file and imports all 10 tables into the local PostgreSQL database. Must be idempotent — running twice with the same data is safe.

---

## Context

Read `_shared_context.md` for project-level context, import order, entity schemas, and CLI conventions.

**Key constraints:**
- Import runs synchronously (no queue/workers)
- Upsert strategy: check by PK/unique constraint, update if exists, insert if not
- Must respect FK ordering (see shared context for the 10-table order)
- CLI follows Operation Result Pattern
- Uses `db_session_manager` for PostgreSQL access

---

## Tasks

### 1. Create Import Seed Command

**File:** `backend/src/linkedout/cli/commands/import_seed.py` (NEW)

#### CLI Interface

```python
@click.command("import-seed")
@click.option("--seed-file", type=click.Path(exists=True), default=None,
              help="Path to seed SQLite file (default: auto-detect in ~/linkedout-data/seed/)")
@click.option("--dry-run", is_flag=True, help="Report what would be imported, do not write")
def import_seed(seed_file, dry_run):
    """Import seed company data from SQLite into PostgreSQL."""
```

#### Import Flow

1. **Locate seed file:**
   - If `--seed-file` provided, use that path
   - Otherwise, look in `~/linkedout-data/seed/` (respect `LINKEDOUT_DATA_DIR`)
   - Auto-detect: prefer `seed-core.sqlite`, fall back to `seed-full.sqlite`
   - If no file found: clear error with guidance to run `linkedout download-seed`

2. **Validate seed file:**
   - Open SQLite, read `_metadata` table
   - Log seed version, creation date, table counts
   - Verify all 10 expected tables exist

3. **Import tables in FK order:**

   For each table in order (see shared context for the 10-table sequence):

   a. Read all rows from SQLite table
   b. Upsert into PostgreSQL in **batches of 1000 rows** using `INSERT ... ON CONFLICT DO UPDATE` or `executemany`. Row-by-row insertion is too slow for the full seed (~100K+ rows). Target: < 5 minutes for the full seed tier. If batch inserts are still too slow, use `psycopg2.copy_expert()` with `COPY FROM STDIN`.
      - Track per-row outcome: "inserted", "updated", or "skipped" (data matches)
   c. Show per-table progress: `Importing company... 4,521/4,521`
   d. Track counts: inserted, updated, skipped per table

4. **Dry-run mode:**
   - Parse and read all SQLite data
   - Report per-table counts (total rows, how many would be inserted/updated/skipped)
   - Do NOT open a write transaction to PostgreSQL
   - Print: `DRY RUN — no data written. Remove --dry-run to import.`

5. **Generate report:**
   - Write JSON report to `~/linkedout-data/reports/seed-import-YYYYMMDD-HHMMSS.json`
   - Include: seed version, tier, per-table counts (inserted/updated/skipped), duration, dry_run flag

6. **Print summary (Operation Result Pattern):**
   ```
   Results:
     company:          4,521 inserted, 0 updated, 0 skipped
     company_alias:    8,432 inserted, 0 updated, 0 skipped
     role_alias:       1,205 inserted, 0 updated, 0 skipped
     ...
     profile_skill:   31,847 inserted, 0 updated, 0 skipped

   Total: 127,543 rows imported across 10 tables

   Next steps:
     → Run `linkedout embed` to generate profile embeddings
     → Run `linkedout status` to verify database state

   Report saved: ~/linkedout-data/reports/seed-import-20260407-143012.json
   ```

   On second run:
   ```
   Results:
     company:          0 inserted, 0 updated, 4,521 skipped
     ...

   Total: 0 rows imported (127,543 already up to date)
   ```

#### Upsert Strategy

**Option A: ORM-based (safer, slower)**
```python
for row in sqlite_rows:
    existing = session.query(Entity).filter_by(id=row["id"]).first()
    if existing:
        if has_changes(existing, row):
            update_entity(existing, row)
            updated += 1
        else:
            skipped += 1
    else:
        session.add(Entity(**row))
        inserted += 1
session.commit()
```

**Option B: Raw SQL with ON CONFLICT (faster, recommended for large datasets)**
```sql
INSERT INTO company (id, name, domain, ...)
VALUES (%(id)s, %(name)s, %(domain)s, ...)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  domain = EXCLUDED.domain,
  ...
WHERE company.name != EXCLUDED.name
   OR company.domain != EXCLUDED.domain
   -- etc.
RETURNING (xmax = 0) AS inserted
```

The RETURNING clause tells us if the row was inserted (xmax=0) or updated. Rows that match the ON CONFLICT but don't satisfy the WHERE clause are skipped.

**Recommendation:** Use Option B (raw SQL) for tables with >1000 rows, Option A for smaller tables. Or use Option B consistently for simplicity. The sub-phase runner should decide based on what's simpler to implement correctly.

### 2. SQLite Reader

```python
def read_seed_table(sqlite_path: Path, table_name: str) -> list[dict]:
    """Read all rows from a SQLite table as list of dicts."""
    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(f"SELECT * FROM {table_name}")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def read_seed_metadata(sqlite_path: Path) -> dict:
    """Read the _metadata table from a seed SQLite file."""
```

Note: `table_name` comes from a hardcoded list (the 10 known tables), not from user input — no SQL injection risk.

### 3. Table-to-Entity Mapping

Define the mapping between SQLite table names and PostgreSQL handling:

```python
IMPORT_ORDER = [
    {"table": "company", "pk": "id"},
    {"table": "company_alias", "pk": "id"},
    {"table": "role_alias", "pk": "id"},
    {"table": "funding_round", "pk": "id"},
    {"table": "startup_tracking", "pk": "id"},
    {"table": "growth_signal", "pk": "id"},
    {"table": "crawled_profile", "pk": "id"},
    {"table": "experience", "pk": "id"},
    {"table": "education", "pk": "id"},
    {"table": "profile_skill", "pk": "id"},
]
```

Read entity files to determine actual PK and unique constraint column names. The list above is illustrative — check each entity for the real PK field name.

### 4. Register Command

**File:** `backend/src/linkedout/cli/cli.py`

Add `import_seed` to the CLI group:
```python
from linkedout.cli.commands.import_seed import import_seed
cli.add_command(import_seed)
```

---

## Files to Create

| File | Description |
|------|-------------|
| `backend/src/linkedout/cli/commands/import_seed.py` | Import seed command |

## Files to Modify

| File | Changes |
|------|---------|
| `backend/src/linkedout/cli/cli.py` | Register `import-seed` command |

## Files to Reference (Read-Only)

| File | Why |
|------|-----|
| All 10 entity files (see `_shared_context.md`) | Column names, PKs, FKs, types |
| `backend/src/shared/infra/db/db_session_manager.py` | DB session setup |

---

## Verification

### Unit Tests (for SP6 to implement, but design for testability)

Ensure the following are independently testable:
- `read_seed_table()` reads SQLite rows correctly
- `read_seed_metadata()` parses metadata
- FK ordering is correct (import in wrong order → predictable error)
- Upsert logic: insert new row, update changed row, skip identical row
- Dry-run mode: no PostgreSQL writes
- Auto-detect logic: finds correct file in seed directory

### Manual Checks
- Create a small test SQLite with ~10 rows per table
- `linkedout import-seed --seed-file test.sqlite` imports all rows
- Running again: all rows show as "skipped"
- `--dry-run`: reports counts without writing
- Missing seed file → clear error pointing to `linkedout download-seed`

---

## Acceptance Criteria

- [ ] `linkedout import-seed` imports all 10 tables from SQLite into PostgreSQL
- [ ] Tables imported in correct FK order
- [ ] Upsert: new rows inserted, changed rows updated, identical rows skipped
- [ ] Running twice with same data → all skips (idempotent)
- [ ] `--dry-run` reports without writing to PostgreSQL
- [ ] `--seed-file` accepts explicit path
- [ ] Auto-detect finds seed file in `~/linkedout-data/seed/`
- [ ] Per-table progress display during import
- [ ] Follows Operation Result Pattern in output
- [ ] Produces JSON report in `~/linkedout-data/reports/`
- [ ] Logs to `~/linkedout-data/logs/cli.log`
- [ ] Missing seed file → clear error with guidance
- [ ] Command registered in CLI entry point
