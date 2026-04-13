# Fix: Batch Enrichment Performance — Hoist CompanyMatcher Preload

## Problem

`process_batch()` processes 100 profiles at ~10s each (~17 min/batch). The dominant cost is **redundant company preloading**: `ProfileEnrichmentService` is instantiated per profile, and its `__init__` loads all 239K companies from the database every time.

### Architecture context

Two services participate in enrichment, each with its own `CompanyMatcher`:

- **`PostEnrichmentService`** (`post_enrichment.py:32`) — processes Apify results into the DB. Created once per batch. Owns URL normalization, redirect handling, archive writing, and batch embedding. Its `__init__` (line 44) calls `_preload_companies()` to build a `CompanyMatcher` for company dedup.

- **`ProfileEnrichmentService`** (`crawled_profile/services/profile_enrichment_service.py:31`) — the "make profile searchable" lifecycle. Owns structured row creation (experience, education, skills), company resolution, role alias lookup, search_vector rebuild, and per-profile embedding. Its `__init__` (line 50) **also** calls `_preload_companies()` to build its own independent `CompanyMatcher`.

Both services need company data for dedup/resolution, but they load it independently. `PostEnrichmentService` uses its matcher for company resolution during `_update_crawled_profile()`. `ProfileEnrichmentService` uses its matcher during `enrich()` to resolve company IDs for experience records.

### Call chain

```
PostEnrichmentService(session)                   # __init__ line 44: _preload_companies() — 239K rows (once)
  └─ process_batch()                             # post_enrichment.py:297
       └─ for each profile:
            └─ process_enrichment_result()        # post_enrichment.py:60
                 └─ ProfileEnrichmentService(session)  # LINE 135: created PER PROFILE
                      └─ __init__()
                           └─ _preload_companies()     # 239K rows AGAIN, per profile
                      └─ enrich(profile_id, request)   # DB writes: delete old, insert new, flush
```

For a batch of 100 profiles, `_preload_companies()` runs **101 times** total: 1 for `PostEnrichmentService` + 100 for `ProfileEnrichmentService` (one per profile at line 135).

### Estimated cost breakdown (per profile)

| Step | Time | Notes |
|------|------|-------|
| `_preload_companies()` (239K rows) | ~5-7s | `SELECT * FROM company` + iterate + matcher build |
| DB writes (delete + insert + flush) | ~1-2s | Experiences, education, skills via `enrich()` |
| `with_for_update()` lock | <0.1s | Row lock, minor |
| **Total** | **~7-9s** | Matches observed ~10s/profile |

### Impact

- 100-profile batch: ~17 min (should be ~2-3 min)
- 540 remaining profiles: ~1.5 hours (should be ~15-20 min)
- Future enrichment runs scale linearly with this overhead
- Note: embedding is already batched correctly — `process_batch()` disables embedding per-profile (line 316-317), then does one batch `embed()` call at the end (line 382). The preload is the only bottleneck.

## Fix

### Change 1: Hoist `ProfileEnrichmentService` in `process_batch()`

In `PostEnrichmentService.process_batch()`, create a single `ProfileEnrichmentService` **after** the embedding disable (line 317) and pass it to `process_enrichment_result()`.

**Ordering matters:** The service must be created after `self._embedding_provider = None` so it receives `None` as its embedding provider. If created before, it gets the real provider and does per-profile embedding — defeating the batch embedding optimization.

```python
# post_enrichment.py — process_batch()

# Disable per-profile embedding (existing lines 316-317)
original_provider = self._embedding_provider
self._embedding_provider = None

# AFTER embedding disable: create one shared service with shared CompanyMatcher
enrichment_service = ProfileEnrichmentService(
    self._session, self._embedding_provider,
    company_matcher=self._company_matcher,
    company_by_canonical=self._company_by_canonical,
)

for profile_id, linkedin_url, apify_data in results:
    ...
    self.process_enrichment_result(
        apify_data, event_id, linkedin_url,
        ...,
        enrichment_service=enrichment_service,  # pass through
    )
```

### Change 2: Accept optional `enrichment_service` in `process_enrichment_result()`

Add `enrichment_service: ProfileEnrichmentService | None = None` parameter. If provided, use it; otherwise create one (preserving backward compat for single-profile callers).

```python
# post_enrichment.py — process_enrichment_result()

def process_enrichment_result(
    self, ..., enrichment_service: ProfileEnrichmentService | None = None,
) -> None:
    ...
    # Line 135: use provided service or create new
    svc = enrichment_service or ProfileEnrichmentService(self._session, self._embedding_provider)
    svc.enrich(profile.id, enrich_request)
```

### Change 3: Accept optional `CompanyMatcher` in `ProfileEnrichmentService.__init__()`

Add optional `company_matcher` and `company_by_canonical` params. If provided, skip `_preload_companies()` and use the caller's instances. This lets `process_batch()` share one matcher across both services, eliminating the second 239K-row preload.

```python
# profile_enrichment_service.py — __init__()

def __init__(
    self, session: Session, embedding_provider: Optional[EmbeddingProvider] = None,
    company_matcher: CompanyMatcher | None = None,
    company_by_canonical: dict[str, CompanyEntity] | None = None,
):
    self._session = session
    self._repository = CrawledProfileRepository(session)
    self._embedding_provider = embedding_provider
    self._role_alias_repo = RoleAliasRepository(session)
    if company_matcher is not None:
        self._company_matcher = company_matcher
        self._company_by_canonical = company_by_canonical or {}
    else:
        self._company_matcher = CompanyMatcher()
        self._company_by_canonical = {}
        self._preload_companies()
```

### What this does NOT change

- Single-profile path (API controller calling `process_enrichment_result()` directly) — unchanged, still creates its own service and preloads companies
- `ProfileEnrichmentService.enrich()` internals — unchanged
- `with_for_update()` — keep for now (correctness > micro-optimization)
- `session.flush()` per profile — keep for now (savepoint rollback needs flushed state)

## Expected improvement

| Metric | Before | After |
|--------|--------|-------|
| Company preloads per batch | 101 (1 PostEnrich + 100 ProfileEnrich) | 1 (PostEnrich only, shared with ProfileEnrich) |
| Time per 100-profile batch | ~17 min | ~2-3 min |
| Time for 540 profiles | ~1.5 hr | ~15-20 min |

## Files

| File | Change |
|------|--------|
| `backend/src/linkedout/enrichment_pipeline/post_enrichment.py` | Hoist service in `process_batch()`, accept optional param in `process_enrichment_result()` |
| `backend/src/linkedout/crawled_profile/services/profile_enrichment_service.py` | Accept optional `company_matcher` + `company_by_canonical` in `__init__()` |

## Tests

### Existing tests (must still pass)

All existing `test_bulk_enrichment.py` and `test_enrich_command.py` tests — they mock `PostEnrichmentService` so they're unaffected by this internal change.

### New tests in `test_post_enrichment.py`

| Test | What it verifies |
|------|-----------------|
| `test_process_batch_creates_single_enrichment_service` | Mock `ProfileEnrichmentService` constructor, verify it's called once (not N times) during `process_batch()` with N profiles |
| `test_process_batch_passes_company_matcher_to_enrichment_service` | Verify the hoisted service receives `self._company_matcher` and `self._company_by_canonical` |
| `test_process_enrichment_result_uses_provided_service` | Pass an `enrichment_service` kwarg, verify it's used instead of creating a new one |
| `test_process_enrichment_result_creates_own_service_when_none` | Call without `enrichment_service`, verify a new one is created (backward compat) |

### New tests in `test_profile_enrichment_service.py`

| Test | What it verifies |
|------|-----------------|
| `test_init_with_provided_matcher_skips_preload` | Pass `company_matcher` + `company_by_canonical`, verify `_preload_companies()` is NOT called |
| `test_init_without_matcher_preloads` | Omit matcher args, verify `_preload_companies()` IS called (existing behavior) |

### Manual verification

```bash
# Before: time a batch enrichment
linkedout enrich --limit 100  # note wall-clock time

# After: same command, should be ~5x faster
linkedout enrich --limit 100
```

## Verification

```bash
cd backend && source .venv/bin/activate
pytest tests/unit/enrichment_pipeline/test_bulk_enrichment.py -v
pytest tests/unit/cli/test_enrich_command.py -v
pytest tests/unit/enrichment_pipeline/test_post_enrichment.py -v  # new + existing
pytest tests/unit/crawled_profile/test_profile_enrichment_service.py -v  # new
```
