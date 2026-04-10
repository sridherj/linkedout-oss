# Sub-Phase 3: Core Enrichment Script — PDL Scan + Wikidata Gap-Fill

**Goal:** linkedin-ai-production
**Phase:** 2 — Company Enrichment
**Depends on:** SP-1 (pdl_id/wikidata_id columns), SP-2 (utility functions)
**Estimated effort:** 4-5h
**Source plan section:** Sub-phase 3

---

## Objective

Create `src/dev_tools/enrich_companies.py` implementing the full enrichment waterfall: Phase A (PDL CSV scan with slug match → name match fallback) then Phase B (Wikidata SPARQL gap-fill). The script enriches company rows with industry/website/HQ/size data using COALESCE semantics (never overwrite existing data). Idempotent via `enrichment_sources` array check.

## Context

- **Code directory:** `./`
- **Reference script (old):** `<prior-project>/agents/startup_enrichment/enrich_companies.py`
- **DB session pattern:** `db_session_manager.get_session(DbSessionType.WRITE)` — same as `classify_roles.py`
- **SQL style:** `sqlalchemy.text()` with `:param` named parameters (NOT psycopg `%s`)
- **Company IDs:** nanoid strings with `co_` prefix (NOT integers)
- **Transaction strategy:** Two separate transactions — PDL commits first, then Wikidata separately
- **CSV reading:** `csv.DictReader` + `itertools.islice` — no pandas dependency
- **PDL file:** Required via `--pdl-file` CLI flag, no default path

## Pre-Flight Checks

Before starting, verify:
- [ ] SP-1 completed: `psql $DATABASE_URL -c "\d company" | grep pdl_id` shows the column
- [ ] SP-2 completed: `from dev_tools.company_utils import compute_size_tier` works
- [ ] SP-2 completed: `from dev_tools.wikidata_utils import wikidata_search, batch_sparql_metadata` works
- [ ] Reference script exists at `<prior-project>/agents/startup_enrichment/enrich_companies.py`
- [ ] Understand `classify_roles.py` pattern: `grep -n "db_session_manager" src/dev_tools/classify_roles.py`

## Files to Create/Modify

```
./
└── src/dev_tools/enrich_companies.py    # NEW: Full enrichment waterfall
```

---

## Step 1: Study Reference Script and Existing Patterns

**Tasks:**
1. Read old `enrich_companies.py` in full — understand the PDL scan logic, Wikidata gap-fill, and SQL patterns
2. Read `src/dev_tools/classify_roles.py` — understand the `db_session_manager` + `sqlalchemy.text()` pattern used in linkedout
3. Note the key adaptations needed:
   - `psycopg.connect(get_dsn())` → `db_session_manager.get_session(DbSessionType.WRITE)`
   - `conn.execute(sql, (param,))` with `%s` → `session.execute(text(sql), {"param": param})` with `:param`
   - Integer `companies.id` → nanoid string `company.id`
   - `companies` table name → `company` table name

## Step 2: Create Constants and Helpers

**Tasks:**
Create `src/dev_tools/enrich_companies.py` with:

1. **Imports:** `csv`, `itertools`, `logging`, `time`, `pathlib`, `typing`, `sqlalchemy.text`, `httpx`, `db_session_manager`, `DbSessionType`
2. **`PDL_SIZE_MAP`** — dict mapping PDL size strings to midpoint employee estimates. Copy verbatim from old script.
3. **`PDL_COLUMNS`** — list of CSV columns to read. Copy verbatim.
4. **`_parse_founded(val: str) -> Optional[int]`** — extracts 4-digit year. Copy verbatim.
5. **`_extract_pdl_fields(row: dict) -> dict`** — builds enrichment dict from PDL CSV row. Imports `compute_size_tier` from `dev_tools.company_utils`.
6. **`_extract_slug(url: str) -> Optional[str]`** — extracts company slug from LinkedIn URL. Copy verbatim.

## Step 3: Implement PDL Phase (Phase A)

**Tasks:**

1. **`load_pdl_matches(pdl_path: str, target_slugs: set, target_names: dict) -> dict`**
   - Single-pass chunked CSV read using `csv.DictReader` + `itertools.islice`
   - For each row: extract slug from LinkedIn URL, check against `target_slugs`
   - Fallback: normalize company name, check against `target_names`
   - Return `{company_id: {pdl_fields...}}`
   - Log progress every 100K rows

2. **`apply_pdl_enrichment(session, company_id: str, fields: dict) -> bool`**
   - UPDATE company row using COALESCE for each field (never overwrite existing data)
   - Use `sqlalchemy.text()` with `:param` named parameters
   - Append `'pdl'` to `enrichment_sources` using `array_append` with NULL-to-empty-array guard:
     ```sql
     enrichment_sources = array_append(
       CASE WHEN enrichment_sources IS NULL THEN ARRAY[]::text[] ELSE enrichment_sources END,
       'pdl'
     )
     ```
   - Set `pdl_id` from PDL data
   - Set `enriched_at = NOW()`
   - Return True if row was updated

## Step 4: Implement Wikidata Phase (Phase B)

**Tasks:**

1. **`run_wikidata_gapfill(session, limit: int = 500) -> int`**
   - Query companies missing key fields AND not already Wikidata-enriched:
     ```sql
     SELECT id, canonical_name FROM company
     WHERE (industry IS NULL OR website IS NULL)
       AND (enrichment_sources IS NULL OR NOT ('wikidata' = ANY(enrichment_sources)))
     ORDER BY network_connection_count DESC NULLS LAST
     LIMIT :limit
     ```
   - For each company:
     - Search Wikidata for QID using `wikidata_search()`
     - Sleep `SEARCH_DELAY` between searches (rate limiting)
   - Batch-fetch metadata for all found QIDs using `batch_sparql_metadata()`
   - Apply COALESCE-based UPDATE for Wikidata fields (same pattern as PDL)
   - Set `wikidata_id` from QID
   - Append `'wikidata'` to `enrichment_sources`
   - Return count of Wikidata-enriched companies

2. Use `httpx.Client(timeout=30.0)` for all Wikidata API calls.

## Step 5: Implement main() Function

**Tasks:**

1. **`main(dry_run: bool, skip_wikidata: bool, pdl_file: Optional[str], wikidata_limit: int, force: bool) -> int`**

2. **Gather targets:**
   ```sql
   SELECT id, universal_name, canonical_name FROM company
   ```
   If not `--force`, filter: `WHERE enrichment_sources IS NULL OR NOT ('pdl' = ANY(enrichment_sources))`

3. **Build lookup maps:**
   - `slug_to_id: dict[str, str]` — universal_name → company ID
   - `name_to_id: dict[str, str]` — normalized canonical_name → company ID

4. **Dry-run mode:**
   - Print target count
   - Scan PDL file and count potential slug/name matches (without applying)
   - Skip Wikidata
   - Return 0

5. **Phase A (PDL) — separate transaction:**
   - Use `db_session_manager.get_session(DbSessionType.WRITE)` as context manager
   - Call `load_pdl_matches()` → get matches
   - Call `apply_pdl_enrichment()` for each match
   - Commit
   - Log: PDL-enriched count

6. **Phase B (Wikidata) — separate transaction:**
   - If `--skip-wikidata`, skip
   - Use `db_session_manager.get_session(DbSessionType.WRITE)` as context manager
   - Call `run_wikidata_gapfill(session, limit=wikidata_limit)`
   - Commit
   - Log: Wikidata-enriched count

7. **Print summary:**
   - Total companies processed
   - PDL-enriched count and percentage
   - Wikidata-enriched count and percentage
   - Industry/website/size_tier coverage totals

8. Return 0 on success, 1 on error.

## Step 6: Error Handling

**Tasks:**
1. PDL file not found → clear error message: `"PDL file not found: {path}. Download from People Data Labs free dataset."`
2. PDL phase fails → rollback PDL transaction, return 1
3. Wikidata API down → catch `httpx` exceptions per-company, log warning, continue. PDL enrichment already committed.
4. Wikidata phase fails mid-way → partial enrichment committed (any companies already updated in this transaction). Log count of successes vs failures.

---

## Verification Checklist

- [ ] `from dev_tools.enrich_companies import main` succeeds
- [ ] Dry-run works: `main(dry_run=True, skip_wikidata=True, pdl_file='path/to/pdl.csv', wikidata_limit=500, force=False)` prints stats without modifying DB
- [ ] PDL enrichment populates fields: industry, website, size_tier, pdl_id, enrichment_sources
- [ ] Wikidata gap-fill populates fields for companies missing data after PDL
- [ ] COALESCE semantics verified: existing data is NOT overwritten
- [ ] Idempotency verified: re-running produces 0 new enrichments
- [ ] Two-transaction model: PDL data persists even if Wikidata phase fails
- [ ] `enrichment_sources` correctly contains `'pdl'` and/or `'wikidata'`

## Key SQL Patterns

**COALESCE UPDATE (never overwrite):**
```sql
UPDATE company SET
  industry = COALESCE(industry, :industry),
  website = COALESCE(website, :website),
  domain = COALESCE(domain, :domain),
  founded_year = COALESCE(founded_year, :founded_year),
  hq_city = COALESCE(hq_city, :hq_city),
  hq_country = COALESCE(hq_country, :hq_country),
  employee_count_range = COALESCE(employee_count_range, :employee_count_range),
  estimated_employee_count = COALESCE(estimated_employee_count, :estimated_employee_count),
  size_tier = COALESCE(size_tier, :size_tier),
  pdl_id = COALESCE(pdl_id, :pdl_id),
  enrichment_sources = array_append(
    CASE WHEN enrichment_sources IS NULL THEN ARRAY[]::text[] ELSE enrichment_sources END,
    'pdl'
  ),
  enriched_at = NOW()
WHERE id = :company_id
  AND (enrichment_sources IS NULL OR NOT ('pdl' = ANY(enrichment_sources)))
```

**Target query (non-force):**
```sql
SELECT id, universal_name, canonical_name
FROM company
WHERE enrichment_sources IS NULL
   OR NOT ('pdl' = ANY(enrichment_sources))
```
