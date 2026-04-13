# SP1: Foundation

**Depends on:** Nothing (first sub-phase)
**Produces:** Three independent, small changes that SP2 and SP3 build on
**Estimated scope:** ~100 lines of production code + unit tests for each change

## Overview

Add the foundational building blocks that the core pipeline (SP2) and integration layer (SP3) need:

1. `poll_run_safe()` in `apify_client.py` — returns `(status, dataset_id)` without raising on failure
2. `max_batch_size` + `skip_embeddings` settings in `EnrichmentConfig`
3. `append_apify_archive_batch()` in `apify_archive.py` — batch-write multiple entries in one I/O cycle

These three changes are independent of each other and can be implemented in any order.

---

## Change 1: `poll_run_safe()` in apify_client.py

**File:** `backend/src/linkedout/enrichment_pipeline/apify_client.py`
**Class:** `LinkedOutApifyClient`

### What to Add

Add a new method `poll_run_safe()` to `LinkedOutApifyClient` that returns a `(status, dataset_id)` tuple instead of raising on non-SUCCEEDED statuses. The existing `poll_run()` must remain unchanged (no contract break).

### Implementation Details

```python
def poll_run_safe(self, run_id: str, timeout: int | None = None, poll_interval: int | None = None) -> tuple[str, str]:
    """Poll until run reaches a terminal state. Returns (status, dataset_id).

    Unlike poll_run(), this method does NOT raise on FAILED/ABORTED/TIMED-OUT.
    It always returns the dataset_id (which Apify allocates at run creation,
    regardless of outcome) so the caller can fetch partial results.

    Returns:
        Tuple of (status, dataset_id) where status is one of:
        SUCCEEDED, FAILED, ABORTED, TIMED-OUT

    Raises:
        TimeoutError: If the run does not reach a terminal state within timeout.
    """
```

Key behaviors:
- Same polling loop as `poll_run()` (GET `/actor-runs/{run_id}`, check status, sleep)
- Terminal states: `SUCCEEDED`, `FAILED`, `ABORTED`, `TIMED-OUT`
- On any terminal state: return `(status, data['defaultDatasetId'])`
- On timeout (no terminal state reached): raise `TimeoutError` (same as `poll_run()`)
- `defaultDatasetId` is always present in the Apify response regardless of run status (verified API fact)

### Existing `poll_run()` for Reference

Located at line ~237 of `apify_client.py`:

```python
def poll_run(self, run_id: str, timeout: int | None = None, poll_interval: int | None = None) -> str:
    """Poll until run completes. Returns dataset_id."""
    if timeout is None:
        timeout = self._cfg.run_poll_timeout_seconds
    if poll_interval is None:
        poll_interval = self._cfg.run_poll_interval_seconds
    url = f'{self.base_url}/actor-runs/{run_id}'
    elapsed = 0
    while elapsed < timeout:
        resp = requests.get(url, params={'token': self.api_key}, timeout=15)
        resp.raise_for_status()
        data = resp.json()['data']
        status = data['status']
        if status == 'SUCCEEDED':
            return data['defaultDatasetId']
        if status in ('FAILED', 'ABORTED', 'TIMED-OUT'):
            raise RuntimeError(f'Apify run {run_id} ended with status: {status}')
        time.sleep(poll_interval)
        elapsed += poll_interval
    raise TimeoutError(f'Apify run {run_id} did not complete within {timeout}s')
```

### Tests for poll_run_safe()

Add to `backend/tests/unit/enrichment_pipeline/test_apify_client.py`:

**Test A: SUCCEEDED returns (status, dataset_id)**
- Mock HTTP response: `status=SUCCEEDED`, `defaultDatasetId=ds_123`
- Assert: returns `("SUCCEEDED", "ds_123")`

**Test B: FAILED returns (status, dataset_id) without raising**
- Mock HTTP response: first poll `status=RUNNING`, second poll `status=FAILED`, `defaultDatasetId=ds_456`
- Assert: returns `("FAILED", "ds_456")` — no exception

**Test C: ABORTED returns (status, dataset_id)**
- Same pattern as Test B but with `ABORTED` status

**Test D: TIMED-OUT returns (status, dataset_id)**
- Same pattern but with `TIMED-OUT` status

**Test E: Polling timeout raises TimeoutError**
- Mock HTTP: always returns `status=RUNNING`
- Call with `timeout=2, poll_interval=1`
- Assert: raises `TimeoutError`

---

## Change 2: Settings Additions

**File:** `backend/src/shared/config/settings.py`
**Class:** `EnrichmentConfig`

### What to Add

Add two fields to the `EnrichmentConfig` pydantic model:

```python
class EnrichmentConfig(BaseModel):
    """Apify enrichment pipeline settings."""

    apify_base_url: str = 'https://api.apify.com/v2'
    cost_per_profile_usd: float = 0.004
    cache_ttl_days: int = 90
    sync_timeout_seconds: int = 60
    async_start_timeout_seconds: int = 30
    run_poll_timeout_seconds: int = 300
    run_poll_interval_seconds: int = 5
    fetch_results_timeout_seconds: int = 30
    key_validation_timeout_seconds: int = 15
    # NEW:
    max_batch_size: int = 100
    skip_embeddings: bool = False
```

- `max_batch_size: int = 100` — caps how many URLs go into a single Apify run. Not user-configurable via CLI (internal constant). Used by SP2's chunking logic.
- `skip_embeddings: bool = False` — when True, skip embedding generation after DB writes. Exposed as `--skip-embeddings` CLI flag in SP3.

### Tests

Add to `backend/tests/unit/` (e.g., in an existing settings test file or new `test_enrichment_config.py`):

**Test A: Default values**
- Create `EnrichmentConfig()` with no args
- Assert: `max_batch_size == 100`, `skip_embeddings == False`

**Test B: Custom values**
- Create `EnrichmentConfig(max_batch_size=50, skip_embeddings=True)`
- Assert values match

---

## Change 3: `append_apify_archive_batch()` in apify_archive.py

**File:** `backend/src/shared/utils/apify_archive.py`

### What to Add

Add a new function `append_apify_archive_batch()` that writes multiple archive entries in a single file open/write/close cycle, reducing I/O overhead for batch processing.

```python
def append_apify_archive_batch(
    entries: list[dict],
    source: str,
    data_dir: str | Path | None = None,
) -> None:
    """Append multiple raw Apify responses to the JSONL archive in one I/O cycle.

    Each entry in the list should be a dict with keys:
        - linkedin_url: str
        - apify_data: dict

    Fire-and-forget: failures are logged but never raised.

    Args:
        entries: List of dicts, each with 'linkedin_url' and 'apify_data' keys.
        source: Which flow triggered this (e.g. 'bulk_enrichment').
        data_dir: Override data directory. If None, resolved from settings.
    """
```

Key behaviors:
- Opens the archive file once, writes all entries, closes
- Same JSONL format as `append_apify_archive()`: `{"archived_at": ..., "linkedin_url": ..., "source": ..., "data": ...}`
- Fire-and-forget: catch all exceptions, log warning, never raise
- Empty `entries` list → no-op (don't even open file)
- Uses same archive path: `{data_dir}/crawled/apify-responses.jsonl`

### Existing `append_apify_archive()` for Reference

```python
def append_apify_archive(
    linkedin_url: str,
    apify_data: dict,
    source: str,
    data_dir: str | Path | None = None,
) -> None:
    try:
        if data_dir is None:
            from shared.config import get_config
            data_dir = get_config().data_dir

        archive_dir = Path(data_dir).expanduser() / 'crawled'
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / ARCHIVE_FILENAME

        line = json.dumps({
            'archived_at': datetime.now(timezone.utc).isoformat(),
            'linkedin_url': linkedin_url,
            'source': source,
            'data': apify_data,
        }, ensure_ascii=False, default=str)

        with open(archive_path, 'a', encoding='utf-8') as f:
            f.write(line + '\n')

    except Exception:
        logger.warning('Failed to archive Apify response for %s', linkedin_url, exc_info=True)
```

### Tests for append_apify_archive_batch()

Add to `backend/tests/unit/shared/utils/test_apify_archive.py`:

**Test A: Batch writes multiple entries in one call**
- Call with 3 entries
- Read JSONL file: assert 3 lines, each valid JSON with correct fields
- Each line has `archived_at`, `linkedin_url`, `source`, `data`

**Test B: Empty entries list is a no-op**
- Call with `entries=[]`
- Assert archive file does not exist (no file created)

**Test C: Fire-and-forget on failure**
- Mock `open()` to raise `PermissionError`
- Assert: no exception raised, warning logged

---

## Verification Checklist

After completing all three changes:

1. `pytest backend/tests/unit/enrichment_pipeline/test_apify_client.py -v` passes (including new poll_run_safe tests)
2. `pytest backend/tests/unit/shared/utils/test_apify_archive.py -v` passes (including new batch tests)
3. Settings tests pass
4. Existing tests still pass: `pytest backend/tests/unit/enrichment_pipeline/ -v`
5. No changes to existing method signatures — only additions
