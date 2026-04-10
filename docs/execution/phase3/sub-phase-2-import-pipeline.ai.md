# Sub-Phase 2: Import Pipeline (Endpoint + Dedup + Merge)

**Goal:** linkedin-ai-production
**Phase:** 3 — Import Pipeline + User-Triggered Enrichment
**Depends on:** SP-1 (Converter Framework)
**Estimated effort:** 4-5h
**Source plan sections:** 3.2.1, 3.2.2, 3.2.3, 3.2.4

---

## Objective

Build the import upload endpoint, normalization utilities, cascading dedup pipeline, and golden record merge. After this sub-phase, users can upload a CSV and get contacts parsed, deduped, and merged into the connection table.

## Context

- Converters from SP-1 produce `(parsed_contacts, failed_rows)` tuples
- URL normalization already exists in `shared/utils/` (reconciliation C1) — import from there, do NOT create a local duplicate
- `connection.sources` is already ARRAY(Text) (reconciliation C2)
- Existing entity services: ConnectionService, ContactSourceService, ImportJobService, CrawledProfileService

## Pre-Flight Checks

```bash
# Verify SP-1 converters are importable
python -c "from src.linkedout.import_pipeline.converters.registry import get_converter; print('OK')"

# Verify shared URL normalization exists
python -c "from src.shared.utils.url_normalize import normalize_linkedin_url; print('OK')"

# Verify ImportJobEntity and ContactSourceEntity exist
python -c "from src.linkedout.import_job.entities.import_job_entity import ImportJobEntity; print('OK')"
python -c "from src.linkedout.contact_source.entities.contact_source_entity import ContactSourceEntity; print('OK')"
```

## New Dependencies

Add to `pyproject.toml` (if not already present):
```toml
rapidfuzz = ">=3.0"           # Fuzzy name matching for dedup stage 3
python-multipart = ">=0.0.9"  # File upload support for FastAPI
```

---

## Step 1: Import Upload Endpoint + ImportService (3.2.1)

### Files to Create

- `src/linkedout/import_pipeline/service.py` — `ImportService` (orchestrates parse→dedup→merge, Decision #2)
- `src/linkedout/import_pipeline/controller.py` — Thin controller, delegates to ImportService

### Endpoint

`POST /tenants/{tenant_id}/bus/{bu_id}/import`

Request: `multipart/form-data` with `file` (CSV) and optional `source_type` (string).

### ImportService.process_import() Flow

1. **Concurrent import guard (Decision #10):** Check for active import_job (status='pending' or 'processing') for same `source_type + app_user_id`. If exists, reject with 409 Conflict.
2. Create `ImportJobEntity` with status='pending'
3. Get converter (by source_type or auto-detect)
4. Parse file → `(parsed_contacts, failed_rows)` (per-row error handling)
5. Update import_job: `total_records = len(parsed)`, `failed_count = len(failed_rows)`, status='parsing'
6. **Bulk insert** `ContactSourceEntity` rows (use `session.execute(insert(ContactSourceEntity), list_of_dicts)` — Decision #12)
7. Update import_job: `parsed_count`, status='deduplicating'
8. Run dedup pipeline (synchronous)
9. Merge into connections
10. Update import_job: status='complete', counters updated
11. Return import_job summary (including failed_rows details)

### Sync vs Async Decision Point

- Files <= 5,000 rows: process synchronously (sub-30s)
- Files > 5,000 rows: defer to Procrastinate, return `status='processing'` + job ID
- Threshold configurable via env var `IMPORT_SYNC_THRESHOLD` (default 5000)

### Progress Endpoint

`GET /tenants/{tenant_id}/bus/{bu_id}/import-jobs/{job_id}` — Returns current ImportJob status + counters.

### Response Format

```json
{
  "import_job_id": "ij_xxx",
  "status": "complete",
  "total_records": 24806,
  "parsed_count": 24806,
  "matched_count": 19500,
  "new_count": 5306,
  "failed_count": 0
}
```

---

## Step 2: Normalization Utilities (3.2.2)

### File

`src/linkedout/import_pipeline/normalize.py`

### Functions

```python
def normalize_email(email: str) -> str:
    """Lowercase, strip whitespace. Returns empty string if invalid."""

def normalize_phone(phone: str, default_country: str = 'IN') -> str | None:
    """E.164 format via phonenumbers library. Returns None if unparseable."""
```

**Important (Reconciliation C1):** URL normalization lives in `src/shared/utils/`. Do NOT create a local `normalize_linkedin_url`. Import from `shared/utils/` instead.

### Test File

`tests/unit/import_pipeline/test_normalize.py`

### Tests

- Email: whitespace, case, empty string
- Phone: Indian numbers (with/without country code), US formats, bare digits, unparseable → None

---

## Step 3: Cascading Dedup Pipeline (3.2.3)

### File

`src/linkedout/import_pipeline/dedup.py`

### Input/Output

- Input: List of `ContactSourceEntity` rows for a given import job
- Output: Each ContactSource gets `dedup_status`, `dedup_method`, `dedup_confidence`, and optionally `connection_id`

### Approach (Decision #5+7): Single In-Memory Load, Three Python Stages

Load ALL connections for the user in one DB query (~25K max). Build lookup dicts:
- `url_to_connection: dict[str, ConnectionEntity]` — normalized LinkedIn URL → connection
- `email_to_connection: dict[str, ConnectionEntity]` — normalized email → connection

**Stage 1 — Exact LinkedIn URL match (confidence 1.0):**
- Look up each ContactSource's normalized LinkedIn URL in `url_to_connection` dict
- Also match within-import dedup (other ContactSource rows in same import)
- Set `dedup_status='matched'`, `dedup_method='exact_url'`, `dedup_confidence=1.0`

**Stage 2 — Exact email match (confidence 0.95):**
- For remaining unmatched with non-null email
- Look up in `email_to_connection` dict (exact match, no LIKE)
- Set `dedup_status='matched'`, `dedup_method='exact_email'`, `dedup_confidence=0.95`

**Stage 3 — Fuzzy name+company match (RapidFuzz, threshold 0.85):**
- For remaining unmatched with non-null first_name + last_name
- Use `rapidfuzz.fuzz.token_sort_ratio` on full_name
- If name score >= 85 AND company matches (exact or token_sort >= 80): match
- Set `dedup_status='matched'`, `dedup_method='fuzzy_name_company'`, `dedup_confidence=score/100`

**Stage 4 — Flag unmatched:**
- Remaining: `dedup_status='new'`, `dedup_method=None`, `dedup_confidence=None`

### Performance Note

One DB round-trip to load all connections. All 3 stages run as pure Python against in-memory dicts.

### Test File

`tests/unit/import_pipeline/test_dedup.py`

### Tests

- 10 contacts: 3 exact URL matches, 2 email matches, 1 fuzzy match, 4 new → correct dedup_status on each
- Idempotency: re-import same CSV → all match existing connections → 0 new

---

## Step 4: Golden Record Merge (3.2.4)

### File

`src/linkedout/import_pipeline/merge.py`

### If Matched (connection exists)

- Append source_type to `connection.sources` (if not already present)
- Merge emails/phones: union, don't duplicate
- Survivorship rules:
  - `connected_at`: earliest date wins
  - Company/title: LinkedIn CSV wins over Google/phone sources
  - Email: any non-null source fills in missing
  - Phone: any non-null source fills in missing
- Update `connection.source_details` JSONB: append new source entry
- Link contact_source → connection

### If New (no match)

- Check if `crawled_profile` exists for this LinkedIn URL:
  - If yes: create connection linked to existing crawled_profile
  - If no: **always create a stub `crawled_profile`** with `has_enriched_data=False` and available data (name, linkedin_url from CSV, `data_source='csv_stub'`). **`connection.crawled_profile_id` is never NULL.**
- Set `sources = [source_type]`
- Copy relevant fields from ContactSource to Connection

### Tests (Integration)

- Import LinkedIn CSV → verify connection.sources contains 'linkedin_csv'
- Import Google contacts → verify matching connections gain email data + 'google_contacts_job' in sources
- Re-import same CSV → verify no duplicate connections, sources unchanged

---

## Unit Test: Import Service Orchestration (Decision #9)

### Test File

`tests/unit/import_pipeline/test_import_service.py`

### Tests

- Orchestration: converter called → contact_sources created → dedup called → merge called → counters updated
- Concurrent import rejection (409) — Decision #10
- Sync/async threshold behavior (Decision #11): test both paths
  - Sync: 10 rows, default threshold → sync path
  - Async: 10 rows with `IMPORT_SYNC_THRESHOLD=5` → async path

---

## Integration Tests

### Test File

`tests/integration/test_import_pipeline.py`

| Test | What's Validated |
|------|-----------------|
| `test_import_linkedin_csv_e2e` | Upload CSV → import_job + contact_sources + connections created. New contacts get stub crawled_profile with `has_enriched_data=False`. |
| `test_import_idempotent` | Re-upload same CSV → 0 new connections |
| `test_import_cross_source_merge` | Import LinkedIn then Google → emails merged onto connections |
| `test_import_concurrent_rejection` | Second import while first active → 409 Conflict |
| `test_import_sync_async_threshold` | 10 rows with threshold=5 → async path. 10 rows with threshold=5000 → sync path. |

---

## Completion Criteria

- [ ] `ImportService` orchestrates full import flow (parse→dedup→merge)
- [ ] Controller is thin — delegates to `ImportService.process_import()`
- [ ] Concurrent import guard returns 409 Conflict (Decision #10)
- [ ] Bulk insert for ContactSource rows (Decision #12)
- [ ] Sync/async threshold working (Decision #11)
- [ ] URL normalization imported from `shared/utils/` (reconciliation C1)
- [ ] Email and phone normalization working
- [ ] All 3 dedup stages working (URL, email, fuzzy name+company)
- [ ] Golden record merge with stub crawled_profile for new contacts
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] `precommit-tests` all green

## Verification

```bash
# Run unit tests
pytest tests/unit/import_pipeline/ -v

# Run integration tests
pytest tests/integration/test_import_pipeline.py -v

# Full test suite
precommit-tests
```
