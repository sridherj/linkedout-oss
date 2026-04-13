# SP1: Foundation

**Depends on:** Nothing (first sub-phase, parallel with SP2)
**Produces:** Two independent additions in separate files that SP3 builds on
**Estimated scope:** ~25 lines of production code

## Overview

Add two building blocks that the dispatch-pool loop (SP3) needs:

1. `max_parallel_batches` config field in `EnrichmentConfig`
2. `check_run_status()` method on `LinkedOutApifyClient`

Both changes are additive — they don't modify existing code, only add new fields/methods.

---

## Change 1: `max_parallel_batches` in settings.py

**File:** `backend/src/shared/config/settings.py`
**Class:** `EnrichmentConfig` (line ~70)

### What to Add

Add a single field to `EnrichmentConfig`:

```python
class EnrichmentConfig(BaseModel):
    """Apify enrichment pipeline settings."""

    apify_base_url: str = 'https://api.apify.com/v2'
    cost_per_profile_usd: float = 0.004
    cache_ttl_days: int = 90
    sync_timeout_seconds: int = 60
    async_start_timeout_seconds: int = 30
    run_poll_timeout_seconds: int = 900
    run_poll_interval_seconds: int = 5
    fetch_results_timeout_seconds: int = 30
    key_validation_timeout_seconds: int = 15
    max_batch_size: int = 100
    max_parallel_batches: int = 1  # 1 = sequential (current behavior)
    skip_embeddings: bool = False
```

### Key Details

- Default `1` preserves current behavior exactly — existing users see no change
- Set to 3-5 for production use (documented in config.yaml comments)
- Setting higher than number of API keys is fine — keys are round-robined for dispatch, but any key can poll any run
- Place between `max_batch_size` and `skip_embeddings` for logical grouping

---

## Change 2: `check_run_status()` in apify_client.py

**File:** `backend/src/linkedout/enrichment_pipeline/apify_client.py`
**Class:** `LinkedOutApifyClient`

### What to Add

Add a non-blocking single-check method. This is the non-blocking counterpart to `poll_run_safe()`. The dispatch-pool loop (SP3) calls this on each in-flight batch every poll interval, instead of blocking on one batch at a time.

```python
def check_run_status(self, run_id: str) -> tuple[str, str] | None:
    """Single non-blocking status check. Returns (status, dataset_id) if terminal, None if still running."""
    url = f'{self.base_url}/actor-runs/{run_id}'
    resp = requests.get(url, params={'token': self.api_key}, timeout=15)
    resp.raise_for_status()
    data = resp.json()['data']
    status = data['status']
    if status in ('SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED-OUT'):
        return (status, data['defaultDatasetId'])
    return None
```

### Key Details

- Uses the **same** GET endpoint as `poll_run()` and `poll_run_safe()`: `/actor-runs/{run_id}`
- Terminal states: `SUCCEEDED`, `FAILED`, `ABORTED`, `TIMED-OUT` — same set as `poll_run_safe()`
- Returns `None` for non-terminal states (READY, RUNNING, etc.)
- Returns `(status, dataset_id)` tuple for terminal states — same as `poll_run_safe()` return type
- `defaultDatasetId` is always present regardless of run status (verified Apify API fact)
- 15-second timeout on the HTTP request (same as `poll_run()`)
- **Does NOT sleep or loop** — caller controls polling cadence
- Place the method after `poll_run_safe()` in the class (logical grouping: poll_run, poll_run_safe, check_run_status)
- `poll_run()` and `poll_run_safe()` remain unchanged — they still work for external callers

---

## Verification

After both changes:

```bash
# Existing tests still pass (no behavioral changes)
uv run python -m pytest backend/tests/unit/enrichment_pipeline/test_apify_client.py -v
uv run python -m pytest backend/tests/unit/enrichment_pipeline/ -v

# Quick import check
cd backend && uv run python -c "from shared.config import get_config; c = get_config(); print(f'max_parallel_batches={c.enrichment.max_parallel_batches}')"
cd backend && uv run python -c "from linkedout.enrichment_pipeline.apify_client import LinkedOutApifyClient; print('check_run_status' in dir(LinkedOutApifyClient))"
```

Both changes are additive. No existing test should break.
