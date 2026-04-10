# Sub-Phase 4: DB Layer Updates + Integration Tests

**Goal:** linkedin-ai-production
**Phase:** 2b — Startup Pipeline Compatibility
**Depends on:** SP-3 (Alembic Migration + Nanoid — tables must exist, nanoid util available)
**Estimated effort:** 4-6h
**Source plan steps:** Steps 5, 5.5

---

## Objective

Update the shared pipeline DB layer (`db.py`, `company_ops.py`) to target LinkedOut's schema — new table names, nanoid PKs, split company/startup_tracking writes. Then write integration tests to verify before any pipeline stage changes.

## Context

All three agents (`startup-pipeline`, `startup-enrich`, `startup-discover`) share this DB layer. Fixing it once covers the core path for all agents.

**Working directory:** `<prior-project>/agents/pipeline/`
**Files to modify:** `db.py`, `company_ops.py`
**Test file to create:** `tests/test_db_layer.py`

---

## Part A: DB Layer Updates (Step 5)

### 5a: Connection string (`db.py`)

```python
# OLD
dsn = os.environ.get("LINKEDIN_INTEL_DSN") or os.environ.get("DATABASE_URL")
dbname = os.environ.get("PGDATABASE", "linkedin_intel")

# NEW
dsn = os.environ.get("LINKEDOUT_DSN") or os.environ.get("DATABASE_URL")
dbname = os.environ.get("PGDATABASE", "linkedout")
```

### 5b: Table name updates (plural → singular)

All SQL queries across `db.py`, `company_ops.py`, and any other files found in SP-1 audit:

| Old Table Name | New Table Name |
|----------------|----------------|
| `companies` | `company` |
| `funding_rounds` | `funding_round` |
| `growth_signals` | `growth_signal` |
| `pipeline_state` | `pipeline_state` (unchanged) |
| `raw_feed_items` | `raw_feed_item` |
| `extracted_companies` | `extracted_company` |
| `discovery_signals` | `discovery_signal` |
| `pipeline_failed_items` | `pipeline_failed_item` |
| `news_articles` | `news_article` |
| `news_company_mentions` | `news_company_mention` |

### 5c: PK type updates (INTEGER → TEXT nanoid)

Every query that:
- Returns `company_id` as int → now returns str
- Uses `SERIAL` for new row IDs → must generate nanoid in Python and pass as param
- Type hints: `int | None` → `str | None` for all ID returns

### 5d: `insert_or_match_company()` — structural rewrite

This function is the central company creation path. Post-migration it must split writes across two tables:

```python
# Step 1: INSERT into company (core fields only)
INSERT INTO company (id, name, canonical_name, normalized_name, website, ...)
VALUES (generate_nanoid('co'), %s, %s, %s, %s, ...)
ON CONFLICT (canonical_name) DO NOTHING
RETURNING id

# Step 2: UPSERT into startup_tracking
INSERT INTO startup_tracking (id, company_id, watching, vertical, sub_category)
VALUES (generate_nanoid('st'), %s, true, %s, %s)
ON CONFLICT (company_id) DO UPDATE SET
    watching = true,
    vertical = COALESCE(EXCLUDED.vertical, startup_tracking.vertical),
    sub_category = COALESCE(EXCLUDED.sub_category, startup_tracking.sub_category)
```

### 5d continued: Column mapping updates

Queries referencing columns that moved to `startup_tracking`:

| Old Query Pattern | New Query Pattern |
|-------------------|-------------------|
| `SELECT ... watching FROM companies` | `SELECT ... st.watching FROM company c JOIN startup_tracking st ON st.company_id = c.id` |
| `UPDATE companies SET watching = true` | `INSERT INTO startup_tracking ... ON CONFLICT (company_id) DO UPDATE SET watching = true` |
| `UPDATE companies SET vertical = %s` | `UPDATE startup_tracking SET vertical = %s WHERE company_id = %s` |
| `UPDATE companies SET description = %s` | `UPDATE startup_tracking SET description = %s WHERE company_id = %s` |
| `UPDATE companies SET funding_stage = %s, total_raised_usd = %s, ...` | `UPDATE startup_tracking SET funding_stage = %s, total_raised_usd = %s, ... WHERE company_id = %s` |

### 5d continued: Split `update_company_metadata()`

Split into two functions:

```python
# Company-native fields
_COMPANY_METADATA_COLUMNS = frozenset({
    'website', 'hq_city', 'hq_country', 'founded_year', 'estimated_employee_count'
})

# Startup tracking fields
_TRACKING_METADATA_COLUMNS = frozenset({
    'vertical', 'description', 'estimated_arr_usd', 'arr_signal_date', 'arr_confidence'
})

def update_company_metadata(conn, company_id: str, **kwargs) -> None:
    """Update company-native fields only."""
    # UPDATE company SET col1=%s, col2=%s WHERE id=%s

def update_tracking_metadata(conn, company_id: str, **kwargs) -> None:
    """Update startup_tracking fields. Uses WHERE company_id=%s."""
    # UPDATE startup_tracking SET col1=%s WHERE company_id=%s
```

Also update `helpers.py cmd_update_company` to call both functions, routing kwargs to the correct one.

### 5d continued: `enrichment_report()` rewrite

```sql
-- OLD
SELECT ... FROM companies WHERE watching = true
JOIN funding_rounds fr ON fr.company_id = c.id
... c.estimated_arr_usd ...

-- NEW
SELECT ... FROM company c
JOIN startup_tracking st ON st.company_id = c.id WHERE st.watching = true
JOIN funding_round fr ON fr.company_id = c.id
... st.estimated_arr_usd ...
```

### 5e: Remove REFRESH MATERIALIZED VIEW

Remove any `REFRESH MATERIALIZED VIEW CONCURRENTLY company_growth_metrics` calls from `db.py` or `run.py`.

---

## Part B: Integration Tests (Step 5.5)

**File:** `<prior-project>/agents/pipeline/tests/test_db_layer.py`

Tests to write:

1. `test_db_connection()` — connect to LinkedOut DB via `LINKEDOUT_DSN`, verify all 10 expected tables exist
2. `test_nanoid_generation()` — verify `generate_nanoid('co')` returns `co_<12chars>`, correct alphabet
3. `test_insert_or_match_company_new()` — insert a new company, verify rows in both `company` + `startup_tracking` with correct nanoid PKs
4. `test_insert_or_match_company_existing()` — re-insert same company, verify UPSERT into `startup_tracking` without duplicates
5. `test_insert_funding_round()` — verify `fr_xxx` nanoid, FK constraint enforced
6. `test_insert_growth_signal()` — verify `gs_xxx` nanoid, FK constraint enforced
7. `test_update_company_metadata()` — verify writes go to `company` table only
8. `test_update_tracking_metadata()` — verify writes go to `startup_tracking` via `WHERE company_id=%s`
9. `test_enrichment_report()` — seed data, call `enrichment_report()`, verify counters
10. `test_orm_coexistence()` — insert via raw SQL, read via ORM; insert via ORM, read via raw SQL

---

## Completion Criteria

- [ ] All pipeline `.py` files reference only new table names (in `db.py` and `company_ops.py`)
- [ ] All ID params/returns are `str` type
- [ ] Connection uses `LINKEDOUT_DSN`
- [ ] No references to `linkedin_intel`
- [ ] No materialized view refresh calls remain
- [ ] `insert_or_match_company()` writes to both `company` and `startup_tracking`
- [ ] `update_company_metadata()` and `update_tracking_metadata()` are separate functions
- [ ] All 10 integration tests pass

## Verification

```bash
pytest agents/pipeline/tests/test_db_layer.py -v
# All tests green — GATE: do not proceed to SP-5/6/7 until this passes
```
