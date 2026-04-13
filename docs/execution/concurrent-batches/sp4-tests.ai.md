# SP4: Tests

**Depends on:** SP1 (config + client), SP2 (resume helper), SP3 (dispatch-pool loop)
**Produces:** 21 new tests across 6 categories
**Estimated scope:** ~500 lines of test code

## Overview

Implement all 21 tests from the plan's test matrix. Tests cover concurrency, the new client method, money protection, crash recovery, error isolation, and the resume helper unit tests.

All tests mock Apify HTTP calls — no real API calls. Use the existing test patterns in `test_bulk_enrichment.py` and `test_apify_client.py` as reference.

---

## Test file locations

| Category | File | Tests |
|----------|------|-------|
| Core concurrency (T-concurrent-1 through 6) | `test_bulk_enrichment.py` | 6 tests |
| Client (T-concurrent-7) | `test_apify_client.py` | 1 test |
| Money protection (T-M1 through 4) | `test_bulk_enrichment.py` | 4 tests |
| Crash recovery (T-R1 through 3) | `test_bulk_enrichment.py` | 3 tests |
| Error isolation (T-E1 through 3) | `test_bulk_enrichment.py` | 3 tests |
| Resume helper (T-BH1 through 5) | `test_bulk_enrichment.py` | 5 tests |

**Total: 21 tests** (1 in `test_apify_client.py`, 20 in `test_bulk_enrichment.py`)

---

## Imports needed

In `test_bulk_enrichment.py`, add these imports:

```python
from linkedout.enrichment_pipeline.bulk_enrichment import (
    _check_batch_resume,
    BatchResumeResult,
    BatchState,
)
```

In `test_apify_client.py`, no new imports needed — `LinkedOutApifyClient` is already imported.

---

## Test category 1: Core concurrency (`test_bulk_enrichment.py`)

### T-concurrent-1: Sequential behavior preserved (`max_parallel_batches=1`)

```
Setup:
  - 3 batches of 2 profiles each
  - max_parallel_batches=1 (default)
  - Mock check_run_status to return SUCCEEDED immediately
  - Mock fetch_results to return matching profiles

Assert:
  - Batches dispatched one at a time (dispatch counts: batch 0 dispatched, processed before batch 1 starts)
  - All 6 profiles enriched
  - EnrichmentResult.batches_completed == 3
  - State file has events in sequential order (batch_started 0 before batch_started 1)
```

### T-concurrent-2: Parallel dispatch with `max_parallel_batches=3`

```
Setup:
  - 5 batches of 2 profiles each
  - max_parallel_batches=3
  - Mock check_run_status: returns None first call, then SUCCEEDED on second call for each batch
  - Mock fetch_results to return matching profiles

Assert:
  - First 3 batches dispatched before any completes (3 batch_started events before any batch_fetched)
  - As batches complete, remaining 2 fill freed slots
  - All 10 profiles enriched
  - EnrichmentResult.batches_completed == 5
```

### T-concurrent-3: Out-of-order completion

```
Setup:
  - 3 batches, max_parallel_batches=3
  - Mock check_run_status: batch 2 returns SUCCEEDED first, then batch 0, then batch 1

Assert:
  - All 3 batches processed correctly regardless of completion order
  - State file has batch_completed events (order doesn't matter, all 3 present)
  - on_progress called 3 times with increasing cumulative totals
```

### T-concurrent-4: One batch fails mid-flight

```
Setup:
  - 3 batches, max_parallel_batches=3
  - Mock check_run_status: batch 0 SUCCEEDED, batch 1 FAILED, batch 2 SUCCEEDED
  - Mock fetch_results: returns partial results for batch 1 (1 of 2 profiles)

Assert:
  - Batch 0 and 2 fully processed
  - Batch 1 partially processed (whatever Apify returned)
  - Other batches unaffected by batch 1's failure
  - EnrichmentResult.batches_completed == 3
  - Failure logged but not raised
```

### T-concurrent-5: Key exhaustion mid-flight

```
Setup:
  - 5 batches, max_parallel_batches=3
  - First 3 batches dispatch successfully
  - Key tracker raises AllKeysExhaustedError on 4th dispatch attempt
  - Mock check_run_status: first 3 batches complete normally

Assert:
  - First 3 batches dispatched and processed
  - Batches 4-5 not dispatched
  - stopped_reason == 'all_keys_exhausted'
  - EnrichmentResult.batches_completed == 3
```

### T-concurrent-6: Resume with in-flight batches

```
Setup:
  - 4 batches total, state file shows:
    - Batch 0: completed
    - Batch 1: batch_started (run_id set, no dataset_id — was in-flight when crashed)
    - Batch 2: batch_started (run_id set, no dataset_id — was in-flight when crashed)
    - Batch 3: no state (not started)
  - max_parallel_batches=3
  - Mock check_run_status: batch 1 and 2 return SUCCEEDED

Assert:
  - Batch 0 skipped (already completed)
  - Batch 1 and 2 resume polling (NOT re-dispatched) — verify enrich_profiles_async NOT called for these
  - Batch 3 dispatched normally
  - All batches complete
```

---

## Test category 2: Client (`test_apify_client.py`)

### T-concurrent-7: `check_run_status()` returns correctly

```
Setup:
  - Mock requests.get for the actor-runs endpoint

Test cases (parameterize):
  - status='RUNNING' → returns None
  - status='READY' → returns None
  - status='SUCCEEDED', defaultDatasetId='ds1' → returns ('SUCCEEDED', 'ds1')
  - status='FAILED', defaultDatasetId='ds2' → returns ('FAILED', 'ds2')
  - status='ABORTED', defaultDatasetId='ds3' → returns ('ABORTED', 'ds3')
  - status='TIMED-OUT', defaultDatasetId='ds4' → returns ('TIMED-OUT', 'ds4')

Assert:
  - Correct return value for each status
  - HTTP GET called with correct URL and token
  - No sleep/retry — single call per invocation
```

---

## Test category 3: Money protection (`test_bulk_enrichment.py`)

### T-M1: FAILED run fetches partial results, no re-dispatch

```
Setup:
  - 1 batch, check_run_status returns ('FAILED', 'ds1')
  - fetch_results returns 1 of 2 expected profiles

Assert:
  - Partial results processed (1 enriched, 1 failed)
  - enrich_profiles_async called exactly once (no re-dispatch)
  - State file has batch_fetched with run_status='FAILED'
```

### T-M2: TIMED-OUT run fetches partial results, no re-dispatch

```
Setup:
  - Same as T-M1 but with TIMED-OUT status

Assert:
  - Same assertions as T-M1 but with run_status='TIMED-OUT'
```

### T-M3: Resume finds all batches completed on Apify

```
Setup:
  - 3 batches, state file shows all 3 as batch_started (in-flight when we crashed)
  - check_run_status returns SUCCEEDED for all 3 immediately
  - fetch_results returns full results for all 3

Assert:
  - enrich_profiles_async NOT called (zero dispatches)
  - All 3 batches processed from existing Apify runs
  - Money saved: no re-dispatch
```

### T-M4: Resume with results already on disk

```
Setup:
  - 1 batch, state file shows batch_started (run_id set)
  - Results file exists on disk (from prior fetch before crash)
  - check_run_status returns SUCCEEDED

Assert:
  - _load_results returns data (from disk)
  - fetch_results NOT called (mock not invoked)
  - Results processed from disk cache
```

---

## Test category 4: Crash recovery (`test_bulk_enrichment.py`)

### T-R1: Mixed resume states

```
Setup:
  - 7 batches, max_parallel_batches=3
  - State file shows:
    - Batch 0, 1: completed
    - Batch 2, 3: batch_started (in-flight)
    - Batch 4, 5, 6: no state (pending)
  - check_run_status: batch 2, 3 return SUCCEEDED

Assert:
  - Batch 0, 1: skipped (counted)
  - Batch 2, 3: resume polling, add to inflight
  - Batch 4 fills 1 remaining slot (max_parallel=3, 2 in inflight)
  - After batch 2 or 3 completes, batch 5 fills slot
  - All 7 batches eventually complete
```

### T-R2: Crash during post-processing

```
Setup:
  - 2 batches, max_parallel_batches=2
  - State file shows:
    - Batch 0: batch_started + batch_fetched + 3 of 5 profile_processed events
    - Batch 1: batch_started (in-flight)
  - Results file for batch 0 exists on disk (5 results)
  - check_run_status: batch 1 returns SUCCEEDED

Assert:
  - Batch 0: resume processing from disk, skip 3 already-processed profiles, process remaining 2
  - Batch 1: resume polling, fetch, process all
  - _process_batch_results called with already_processed={3 urls} for batch 0
```

### T-R3: Back-to-back resumes, no state growth

```
Setup:
  - 2 batches, both completed in state file
  - Run enrich_profiles twice

Assert:
  - State file size unchanged after second run (no duplicate events appended)
  - No dispatches (enrich_profiles_async not called)
  - Both runs return same EnrichmentResult
```

---

## Test category 5: Error isolation (`test_bulk_enrichment.py`)

### T-E1: Poll error for one batch, another succeeds in same cycle

```
Setup:
  - 2 batches in-flight, max_parallel_batches=2
  - check_run_status: raises Exception for batch 0, returns SUCCEEDED for batch 1
  - On next poll cycle: batch 0 returns SUCCEEDED

Assert:
  - Batch 1 processed immediately (not blocked by batch 0's error)
  - Batch 0 processed on retry (second poll cycle)
  - Warning logged for batch 0's initial failure
```

### T-E2: fetch_results fails, batch stays in-flight

```
Setup:
  - 1 batch in-flight
  - check_run_status returns SUCCEEDED
  - fetch_results raises Exception on first call, succeeds on second

Assert:
  - Batch stays in inflight after first fetch failure
  - Batch processed on second poll cycle (fetch succeeds)
  - Other hypothetical batches would be unaffected
```

### T-E3: All keys invalid mid-flight

```
Setup:
  - 3 batches in-flight
  - _get_key returns None (all keys exhausted) during poll phase

Assert:
  - stopped_reason == 'all_keys_exhausted'
  - State file has batch_started events for all 3 (recoverable on resume)
  - No batch_completed events (processing stopped)
```

---

## Test category 6: Resume helper unit tests (`test_bulk_enrichment.py`)

These test `_check_batch_resume()` directly as a pure function.

### T-BH1: Completed batch → skip

```python
def test_check_batch_resume_completed(self, tmp_path):
    results_dir = tmp_path / 'results'
    results_dir.mkdir()
    existing_state = {
        0: BatchState(batch_idx=0, urls=['u1', 'u2'], completed=True,
                      processed_urls={'u1', 'u2'}),
    }
    result = _check_batch_resume(0, ['u1', 'u2'], existing_state, results_dir)
    assert result.action == 'skip'
    assert result.already_processed == {'u1', 'u2'}
```

### T-BH2: Fetched, results on disk, partially processed → process

```python
def test_check_batch_resume_partial_process(self, tmp_path):
    results_dir = tmp_path / 'results'
    results_dir.mkdir()
    _save_results(results_dir, 'run1', [{'linkedinUrl': 'u1'}, ...])
    existing_state = {
        0: BatchState(batch_idx=0, urls=['u1', 'u2', 'u3', 'u4', 'u5'],
                      run_id='run1', dataset_id='ds1',
                      processed_urls={'u1', 'u2', 'u3'}),
    }
    result = _check_batch_resume(0, ['u1', 'u2', 'u3', 'u4', 'u5'], existing_state, results_dir)
    assert result.action == 'process'
    assert result.run_id == 'run1'
    assert result.results is not None
    assert result.already_processed == {'u1', 'u2', 'u3'}
```

### T-BH3: dataset_id set but results file missing → poll

```python
def test_check_batch_resume_results_missing(self, tmp_path):
    results_dir = tmp_path / 'results'
    results_dir.mkdir()
    # No results file on disk
    existing_state = {
        0: BatchState(batch_idx=0, urls=['u1'], run_id='run1', dataset_id='ds1'),
    }
    result = _check_batch_resume(0, ['u1'], existing_state, results_dir)
    assert result.action == 'poll'
    assert result.run_id == 'run1'
```

### T-BH4: run_id set, no dataset_id → poll

```python
def test_check_batch_resume_started_not_fetched(self, tmp_path):
    results_dir = tmp_path / 'results'
    results_dir.mkdir()
    existing_state = {
        0: BatchState(batch_idx=0, urls=['u1'], run_id='run1'),
    }
    result = _check_batch_resume(0, ['u1'], existing_state, results_dir)
    assert result.action == 'poll'
    assert result.run_id == 'run1'
```

### T-BH5: No state → dispatch

```python
def test_check_batch_resume_no_state(self, tmp_path):
    results_dir = tmp_path / 'results'
    results_dir.mkdir()
    existing_state = {}  # No entry for batch 0
    result = _check_batch_resume(0, ['u1'], existing_state, results_dir)
    assert result.action == 'dispatch'
    assert result.run_id is None
```

---

## Test infrastructure

### Mocking pattern for concurrent tests

The concurrent tests need to mock `check_run_status()` with per-batch behavior. Use `side_effect` to control per-call responses:

```python
# Example: batch 0 finishes first, batch 1 finishes second
call_count = {'0': 0, '1': 0}
def mock_check_status(run_id):
    if run_id == 'run_0':
        call_count['0'] += 1
        if call_count['0'] >= 2:
            return ('SUCCEEDED', 'ds_0')
        return None
    elif run_id == 'run_1':
        call_count['1'] += 1
        if call_count['1'] >= 3:
            return ('SUCCEEDED', 'ds_1')
        return None
```

### Mocking pattern for config

```python
mock_config = MagicMock()
mock_config.enrichment.max_batch_size = 2
mock_config.enrichment.max_parallel_batches = 3
mock_config.enrichment.run_poll_timeout_seconds = 60
mock_config.enrichment.run_poll_interval_seconds = 0.01  # fast for tests
```

### Assertions on dispatch count

Use `enrich_profiles_async` mock call count to verify no re-dispatches:

```python
assert mock_async.call_count == expected_dispatch_count
```

### Assertions on state file

Read the state file and parse events:

```python
events = [json.loads(line) for line in state_path.read_text().strip().split('\n')]
started_events = [e for e in events if e['type'] == 'batch_started']
assert len(started_events) == expected_count
```

---

## Verification

```bash
# Run new tests
uv run python -m pytest backend/tests/unit/enrichment_pipeline/test_bulk_enrichment.py -v -k "concurrent or money or recovery or isolation or resume_helper"
uv run python -m pytest backend/tests/unit/enrichment_pipeline/test_apify_client.py -v -k "check_run_status"

# Run all enrichment tests (no regressions)
uv run python -m pytest backend/tests/unit/enrichment_pipeline/ -v

# Full suite
uv run python -m pytest backend/tests/ -v --tb=short
```
