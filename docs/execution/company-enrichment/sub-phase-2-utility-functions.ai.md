# Sub-Phase 2: Utility Functions — company_utils and wikidata_utils

**Goal:** linkedin-ai-production
**Phase:** 2 — Company Enrichment
**Depends on:** Nothing (can run in parallel with SP-1)
**Estimated effort:** 2-3h
**Source plan section:** Sub-phase 2

---

## Objective

Port `company_utils.py` and `wikidata_utils.py` from the old second-brain enrichment scripts into linkedout's `dev_tools` module. Add `cleanco` dependency. Write unit tests and a live service test for Wikidata.

## Context

- **Code directory:** `./`
- **Reference scripts (old):** `<prior-project>/agents/startup_enrichment/enrich_companies.py`, `company_utils.py`, `wikidata_utils.py`
- These are pure utility modules with no DB dependencies.
- `cleanco` is needed for `normalize_company_name()` — not currently in the project.
- `size_tier` uses 5 tiers: `tiny, small, mid, large, enterprise` (resolved from old script's 4 tiers).

## Pre-Flight Checks

Before starting, verify:
- [ ] Reference scripts exist at `<prior-project>/agents/startup_enrichment/`
- [ ] `pip install cleanco` works in the project virtualenv
- [ ] `tests/dev_tools/` directory exists (or create it)

## Files to Create/Modify

```
./
├── src/dev_tools/company_utils.py                 # NEW: size tier, name normalization, subsidiary resolution
├── src/dev_tools/wikidata_utils.py                # NEW: Wikidata search and SPARQL metadata fetch
├── requirements.txt                               # ADD: cleanco
├── tests/dev_tools/test_company_utils.py          # NEW: unit tests
├── tests/dev_tools/test_wikidata_utils.py         # NEW: unit tests (mocked httpx)
└── tests/live_services/test_wikidata_live.py      # NEW: live API test
```

---

## Step 1: Add `cleanco` Dependency

**Tasks:**
1. Add `cleanco` to `requirements.txt`
2. Install: `pip install cleanco`
3. Verify: `python -c "import cleanco; print(cleanco.__version__)"`

## Step 2: Port company_utils.py

**Tasks:**
1. Read the old reference scripts to understand the exact functions:
   - Check `<prior-project>/agents/startup_enrichment/` for `company_utils.py` or equivalent functions in `enrich_companies.py`
2. Create `src/dev_tools/company_utils.py` with:

   **`SUBSIDIARY_MAP`** — hardcoded dict mapping subsidiary names to parent companies. Copy verbatim from old script.

   **`_REGIONAL_SUFFIX_RE`** — regex for regional suffixes (e.g., "India", "UK"). Copy verbatim.

   **`normalize_company_name(name: str) -> Optional[str]`**
   - Returns None if name is None or empty
   - Wraps `cleanco.basename()` to strip legal suffixes (LLC, Inc, Ltd, etc.)

   **`resolve_subsidiary(name: str) -> Optional[str]`**
   - Checks `SUBSIDIARY_MAP` for exact match
   - Falls back to `_REGIONAL_SUFFIX_RE` pattern match
   - Returns parent company name or None

   **`compute_size_tier(employee_count: Optional[int]) -> Optional[str]`**
   - Returns None if employee_count is None
   - Uses 5 tiers:
     - ≤ 10: `'tiny'`
     - ≤ 50: `'small'`
     - ≤ 200: `'mid'`
     - ≤ 1000: `'large'`
     - > 1000: `'enterprise'`
   - NOTE: These breakpoints differ from the old 4-tier script. The 5-tier version aligns with the data model spec. Verify existing DB values: `SELECT DISTINCT size_tier FROM company WHERE size_tier IS NOT NULL` — if existing values use the old 4-tier scheme, reconcile before proceeding.

**Verify:**
```python
from dev_tools.company_utils import compute_size_tier, normalize_company_name, resolve_subsidiary
assert compute_size_tier(5) == 'tiny'
assert normalize_company_name('Google LLC') == 'Google'
```

## Step 3: Port wikidata_utils.py

**Tasks:**
1. Read the old reference scripts for Wikidata utility functions.
2. Create `src/dev_tools/wikidata_utils.py` with:

   **Constants:**
   - `WIKIDATA_API = 'https://www.wikidata.org/w/api.php'`
   - `SPARQL_ENDPOINT = 'https://query.wikidata.org/sparql'`
   - `SEARCH_DELAY = 0.3` (seconds between API calls)
   - `USER_AGENT = 'LinkedOut/1.0 (sridherj@gmail.com)'` (updated from old script)
   - `HTTP_HEADERS` — dict with User-Agent

   **`wikidata_search(client: httpx.Client, name: str) -> Optional[dict]`**
   - Searches Wikidata `wbsearchentities` API
   - Returns `{qid, label, description}` for best match, or None
   - Returns None on HTTP errors (graceful degradation)

   **`sparql_query(client: httpx.Client, query: str) -> list[dict]`**
   - Executes SPARQL query against Wikidata endpoint
   - Returns list of result bindings

   **`batch_sparql_metadata(client: httpx.Client, qids: list[str]) -> dict`**
   - Fetches properties for batches of 80 QIDs:
     - P1128 (employees), P452 (industry), P571 (founded), P159 (HQ), P856 (website)
   - Returns `{qid: {employees, industry, founded, hq, website}}`
   - Returns empty dict on SPARQL failure

**Verify:**
```python
from dev_tools.wikidata_utils import wikidata_search, batch_sparql_metadata
# Imports succeed
```

## Step 4: Write Unit Tests for company_utils

**Tasks:**
Create `tests/dev_tools/test_company_utils.py`:

1. **`test_compute_size_tier`** — parametrized:
   - `None` → `None`
   - `1` → `'tiny'`
   - `10` → `'tiny'`
   - `11` → `'small'`
   - `50` → `'small'`
   - `51` → `'mid'`
   - `200` → `'mid'`
   - `201` → `'large'`
   - `1000` → `'large'`
   - `1001` → `'enterprise'`

2. **`test_normalize_company_name`** — parametrized:
   - `'Google LLC'` → `'Google'`
   - `'Tata Consultancy Services Limited'` → `'Tata Consultancy Services'`
   - `None` → `None`
   - `''` → `None`

3. **`test_resolve_subsidiary`** — parametrized:
   - `'Amazon Web Services'` → parent `'Amazon'` (or whatever SUBSIDIARY_MAP says)
   - `'Google'` → `None` (no parent)
   - Test a regional suffix case (e.g., `'Deloitte India'` → `'Deloitte'`)

**Verify:**
```bash
pytest tests/dev_tools/test_company_utils.py -v
```

## Step 5: Write Unit Tests for wikidata_utils

**Tasks:**
Create `tests/dev_tools/test_wikidata_utils.py`:

1. **`test_wikidata_search_success`** — mock `httpx.Client` response with valid search results. Assert QID returned.
2. **`test_wikidata_search_empty`** — mock empty search results. Assert None returned.
3. **`test_wikidata_search_http_error`** — mock HTTP error. Assert None returned (graceful degradation).
4. **`test_batch_sparql_metadata`** — mock SPARQL response with properties. Assert correct field extraction.
5. **`test_batch_sparql_metadata_batching`** — mock with >80 QIDs. Assert multiple SPARQL calls made.

**Verify:**
```bash
pytest tests/dev_tools/test_wikidata_utils.py -v
```

## Step 6: Write Live Service Test for Wikidata

**Tasks:**
Create `tests/live_services/test_wikidata_live.py`:

1. Mark with `@pytest.mark.live_services` to exclude from default runs
2. **`test_search_google`** — search for "Google", expect QID Q95
3. **`test_metadata_google`** — fetch metadata for Q95, expect non-empty industry and employee count

**Verify:**
```bash
pytest tests/live_services/test_wikidata_live.py -v -m live_services
```

---

## Verification Checklist

- [ ] `pip install cleanco` succeeds; `import cleanco` works
- [ ] `from dev_tools.company_utils import compute_size_tier, normalize_company_name, resolve_subsidiary` succeeds
- [ ] `from dev_tools.wikidata_utils import wikidata_search, batch_sparql_metadata` succeeds
- [ ] `pytest tests/dev_tools/test_company_utils.py -v` — all pass
- [ ] `pytest tests/dev_tools/test_wikidata_utils.py -v` — all pass
- [ ] `pytest tests/live_services/test_wikidata_live.py -v` — passes against real Wikidata API
- [ ] Existing DB `size_tier` values checked and reconciled with 5-tier scheme
