# Sub-Phase 3: Enrichment Pipeline (Trigger + Worker + Apify + Post-Enrichment)

**Goal:** linkedin-ai-production
**Phase:** 3 — Import Pipeline + User-Triggered Enrichment
**Depends on:** SP-2 (Import Pipeline — connections and crawled_profiles must exist)
**Estimated effort:** 4-5h
**Source plan sections:** 3.3.1, 3.3.2, 3.3.3, 3.3.4

---

## Objective

Build the user-triggered enrichment flow: an endpoint to trigger enrichment for selected profiles, a Procrastinate worker task, an Apify client with key rotation, and a post-enrichment service that updates crawled profiles with rich data + embeddings.

## Context

- Procrastinate POC validated in S6 spike (`src/shared/queue/` — config.py, tasks.py)
- Apify API integration validated in S7 spike (`spikes/s7_apify_spike.py`)
- Apify field mapping: `docs/reference/apify_field_mapping.md`
- Apify sample response: `docs/reference/apify_sample_response.json`
- Actor ID: `LpVuK3Zozwuipa5bp`
- Existing entity services: CrawledProfileService, EnrichmentEventService, EnrichmentConfigService, ExperienceService, EducationService, CompanyService
- `CompanyMatcher` from Phase 2 shared utilities (reconciliation C11) — reuse for company dedup

## Pre-Flight Checks

```bash
# Verify Procrastinate config exists
python -c "from src.shared.queue.config import app; print('OK')"

# Verify enrichment entities exist
python -c "from src.linkedout.enrichment_event.entities.enrichment_event_entity import EnrichmentEventEntity; print('OK')"
python -c "from src.linkedout.enrichment_config.entities.enrichment_config_entity import EnrichmentConfigEntity; print('OK')"

# Verify reference docs
head -5 docs/reference/apify_field_mapping.md
head -5 docs/reference/apify_sample_response.json

# Verify CompanyMatcher exists (reconciliation C11)
python -c "from src.shared.utils.company_matcher import CompanyMatcher; print('OK')" 2>/dev/null || echo "CompanyMatcher not found — may need to create or check location"
```

---

## Step 1: Enrichment Trigger Endpoint (3.3.1)

### File

`src/linkedout/enrichment_pipeline/controller.py`

### Endpoint

`POST /tenants/{tenant_id}/bus/{bu_id}/enrichment/enrich`

### Request Body

```json
{
  "profile_ids": ["cp_xxx", "cp_yyy"],
  "connection_ids": ["conn_xxx"],
  "all_unenriched": true,
  "max_count": 100
}
```

### Flow

1. **Resolve target profiles:**
   - `profile_ids`: directly enrich those crawled_profiles
   - `connection_ids`: find connections → get linked linkedin_urls (skip those without)
   - `all_unenriched`: find all connections where `crawled_profile.has_enriched_data=False` AND `crawled_profile.linkedin_url IS NOT NULL`
2. **For each target linkedin_url:**
   - **Cache check:** If crawled_profile exists AND `last_crawled_at > NOW() - 90 days` → skip (cache hit), create enrichment_event with `event_type='cache_hit'`, `cost_estimate_usd=0`
   - **Cache miss:** Defer enrichment task to Procrastinate queue
3. Create enrichment_event rows: `event_type='queued'`, `enrichment_mode=<platform|byok>`
4. Return summary: `{"queued": 45, "cached": 30, "skipped_no_url": 25, "estimated_cost_usd": 0.18}`

### Cost Estimation

`queued_count * 0.004` (Apify $4/1K profiles)

---

## Step 2: Enrichment Worker Task — Thin Procrastinate Task (3.3.2)

### File

`src/linkedout/enrichment_pipeline/tasks.py`

**Important (Decision #4):** Task lives next to domain code, NOT in `shared/queue/`.

Update `src/shared/queue/config.py` to add `'linkedout.enrichment_pipeline.tasks'` to `import_paths`.

### Task (Thin — ~20 lines, Decision #3)

```python
@app.task(name='enrich_profile', retry=3)
def enrich_profile(
    linkedin_url: str,
    enrichment_event_id: str,
    enrichment_mode: str,       # 'platform' or 'byok'
    app_user_id: str,
) -> None:
    """Thin task — delegates to PostEnrichmentService."""
    # 1. Get Apify client (platform round-robin or BYOK decrypt)
    # 2. Call Apify API
    # 3. Delegate to PostEnrichmentService.process_enrichment_result()
```

---

## Step 3: Apify Client Abstraction (3.3.3)

### File

`src/linkedout/enrichment_pipeline/apify_client.py`

### LinkedOutApifyClient

```python
class LinkedOutApifyClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.actor_id = "LpVuK3Zozwuipa5bp"
        self.base_url = "https://api.apify.com/v2"

    def enrich_profile_sync(self, linkedin_url: str) -> dict | None:
        """Sync enrichment. Returns raw Apify response or None on failure."""

    def enrich_profiles_async(self, linkedin_urls: list[str]) -> str:
        """Start async run. Returns run_id."""

    def poll_run(self, run_id: str, timeout: int = 300) -> str:
        """Poll until complete. Returns dataset_id."""

    def fetch_results(self, dataset_id: str) -> list[dict]:
        """Fetch results from dataset."""
```

### Platform Key Rotation (Decision #6 — itertools.cycle)

```python
import itertools

_key_cycle = None

def get_platform_apify_key() -> str:
    """True round-robin across APIFY_API_KEY_{N} env vars using itertools.cycle."""
    global _key_cycle
    if _key_cycle is None:
        keys = [os.environ[f"APIFY_API_KEY_{i}"] for i in range(1, 10) if os.environ.get(f"APIFY_API_KEY_{i}")]
        if not keys:
            raise ValueError("No APIFY_API_KEY_{N} env vars configured")
        _key_cycle = itertools.cycle(keys)
    return next(_key_cycle)
```

### BYOK Key Decryption

```python
def get_byok_apify_key(app_user_id: str, db_session) -> str:
    """Decrypt BYOK key from enrichment_config."""
    config = db_session.query(EnrichmentConfigEntity).filter_by(app_user_id=app_user_id).first()
    if not config or not config.apify_key_encrypted:
        raise ValueError("No BYOK key configured for this user")
    fernet = Fernet(os.environ["TENANT_SECRET_ENCRYPTION_KEY"].encode())
    return fernet.decrypt(config.apify_key_encrypted.encode()).decode()
```

---

## Step 4: PostEnrichmentService (3.3.4)

### File

`src/linkedout/enrichment_pipeline/post_enrichment.py`

### PostEnrichmentService

A service class that delegates to existing entity services (Decision #3). Called by the thin Procrastinate task after Apify returns data.

### Responsibilities

1. **Race condition guard:** Re-check cache (another user may have enriched while queued)
2. **Update existing stub CrawledProfile** (upsert by linkedin_url):
   - Map fields per `docs/reference/apify_field_mapping.md`
   - Store raw JSON as `raw_profile`
   - Set `has_enriched_data=True`, `last_crawled_at=now()`, `data_source='apify'`
3. **Extract relational data** via existing entity services:
   - `ExperienceEntity` rows from `experience` array
   - `EducationEntity` rows from `education` array
   - `ProfileSkillEntity` rows from `skills`/`topSkills`
   - Create/link `CompanyEntity` from experience company data
4. **Company extraction from experience:**
   - For entries with `companyLinkedinUrl`: check existing CompanyEntity by linkedin_url → link or create
   - For entries without: match by `companyName` (exact, case-insensitive)
   - **Reuse `CompanyMatcher` from shared utilities (reconciliation C11)**
5. **Generate embedding:**
   - Text format: `"{full_name} | {headline} | {about} | Experience: {company1} - {title1}, {company2} - {title2}..."`
   - Call OpenAI `text-embedding-3-small` → 1536-dim vector
   - Store in `crawled_profile.embedding`
6. **Populate `search_vector`** (tsvector) from name + headline + about + experience companies
7. **Update enrichment_event:** `event_type='completed'`, `cost_estimate_usd=0.004`

### Error Handling

- Transient (429, 503, timeout): Procrastinate retry handles
- Profile not found: `event_type='failed'`, no retry
- 3 retries exhausted: `event_type='failed'`, log error

---

## Unit Tests

| Test File | What's Tested |
|-----------|---------------|
| `tests/unit/enrichment_pipeline/test_enrich_task.py` | Thin task delegation to PostEnrichmentService |
| `tests/unit/enrichment_pipeline/test_apify_client.py` | API calls mocked, itertools.cycle key rotation |
| `tests/unit/enrichment_pipeline/test_post_enrichment.py` | Relational data extraction, embedding text format, company dedup |

## Integration Tests

| Test | What's Validated |
|------|-----------------|
| `test_enrich_trigger` | Trigger enrichment → enrichment_events created → task queued. `all_unenriched` uses `crawled_profile.has_enriched_data=False`. |
| `test_enrich_cache_hit` | Recent crawled_profile → no Apify call, cache hit event |
| Full round-trip (mark `live_llm`) | Live Apify call → crawled_profile updated + experiences + education + skills created |

---

## Completion Criteria

- [ ] Enrichment trigger endpoint resolves profiles/connections/all_unenriched
- [ ] 90-day cache check working (skip recently crawled)
- [ ] Thin Procrastinate task (~20 lines) delegates to PostEnrichmentService
- [ ] `import_paths` in Procrastinate config updated
- [ ] Apify client with true round-robin key rotation (itertools.cycle)
- [ ] BYOK key decryption working
- [ ] PostEnrichmentService creates experiences, education, skills, companies
- [ ] CompanyMatcher reused from shared utilities (reconciliation C11)
- [ ] Embedding generation working (OpenAI text-embedding-3-small)
- [ ] search_vector populated
- [ ] Error handling: retry on transient, fail on not-found
- [ ] All unit tests pass
- [ ] Integration tests pass
- [ ] `precommit-tests` all green

## Verification

```bash
# Run unit tests
pytest tests/unit/enrichment_pipeline/ -v

# Run integration tests
pytest tests/integration/test_enrichment_pipeline.py -v

# Full test suite
precommit-tests
```
