# Sub-Phase 5: Pipeline Discovery Path (Stages 1-4)

**Goal:** linkedin-ai-production
**Phase:** 2b — Startup Pipeline Compatibility
**Depends on:** SP-4 (DB Layer Updates — shared DB layer must be migrated first)
**Estimated effort:** 2h
**Source plan steps:** Step 6 (6a-6e)
**Parallel with:** SP-6 (News Path), SP-7 (Agent Updates)

---

## Objective

Update pipeline stages 1-4 (the discovery/ingestion path) to use LinkedOut schema — singular table names, nanoid PKs, and the updated DB layer from SP-4.

## Context

**Working directory:** `<prior-project>/agents/pipeline/`

These stages form the discovery path:
1. `collect.py` — RSS collection → `raw_feed_item`
2. `extract.py` — Company extraction → `extracted_company`
3. `dedup.py` — Deduplication → updates `extracted_company`
4. `promote.py` — Promotion → `discovery_signal`, `company`, `startup_tracking`
5. `company_matcher.py` — 3-layer matching (used by dedup and promote)

---

## Tasks

### 6a: `collect.py` (Stage 1)
- Update `INSERT INTO raw_feed_items` → `INSERT INTO raw_feed_item`
- Generate `rfi_xxx` nanoid for each row (use `generate_nanoid('rfi')` from `db.py`)
- Update `execute_values` batch insert to include nanoid IDs

### 6b: `extract.py` (Stage 2)
- Update `INSERT INTO extracted_companies` → `INSERT INTO extracted_company`
- Generate `ec_xxx` nanoid for each row
- Update `raw_item_id` FK references (now TEXT nanoid, not INTEGER)

### 6c: `dedup.py` (Stage 3)
- Update table references: `extracted_companies` → `extracted_company`
- Update `matched_company_id` type handling (now TEXT)

### 6d: `promote.py` (Stage 4)
- Update `INSERT INTO discovery_signals` → `INSERT INTO discovery_signal`
- Generate `ds_xxx` nanoid
- Update `promoted_company_id` type (TEXT nanoid)
- Update `sample_raw_item_ids` from INTEGER[] to TEXT[]
- Update calls to `company_ops.insert_or_match_company()` (now returns `str`)

**Critical rewrite — bulk watching flag:**

```sql
-- OLD
UPDATE companies SET watching = true
WHERE id IN (
    SELECT DISTINCT matched_company_id FROM extracted_companies
    WHERE dedup_status = 'matched'
)

-- NEW
INSERT INTO startup_tracking (id, company_id, watching)
SELECT generate_nanoid('st'), matched_company_id, true
FROM (
    SELECT DISTINCT matched_company_id FROM extracted_company
    WHERE dedup_status = 'matched' AND matched_company_id IS NOT NULL
) sub
ON CONFLICT (company_id) DO UPDATE SET watching = true;
```

Note: The `generate_nanoid('st')` in SQL must use the PostgreSQL function created in SP-3's migration, not the Python function.

### 6e: `company_matcher.py`
- Update `SELECT FROM companies` → `SELECT FROM company`
- Update ID type handling in match results

**CRITICAL — alias table rename (silent failure risk):**

Two specific lines reference `company_aliases` (plural) — LinkedOut uses `company_alias` (singular):
- `_load_aliases()` information_schema check: `WHERE table_name = 'company_aliases'` → `WHERE table_name = 'company_alias'`
- `_load_aliases()` data query: `SELECT alias_name, company_id FROM company_aliases` → `FROM company_alias`

**Warning:** If missed, the information_schema check returns `False` and alias matching is silently disabled — no error, just degraded dedup quality.

---

## Completion Criteria

- [ ] All table references updated to singular names
- [ ] All new rows use nanoid PKs (no SERIAL/INTEGER IDs)
- [ ] `company_matcher.py` references `company_alias` (singular)
- [ ] Bulk watching update uses `startup_tracking` UPSERT
- [ ] All `insert_or_match_company()` calls handle `str` return type

## Verification

```bash
# Run stages 1-4 against an empty LinkedOut DB with a test RSS feed
# Verify:
psql -d linkedout -c "SELECT id FROM raw_feed_item LIMIT 3"       # rfi_xxx format
psql -d linkedout -c "SELECT id FROM extracted_company LIMIT 3"    # ec_xxx format
psql -d linkedout -c "SELECT id FROM discovery_signal LIMIT 3"     # ds_xxx format
psql -d linkedout -c "SELECT id, watching FROM startup_tracking LIMIT 3"  # st_xxx, watching=true
```
