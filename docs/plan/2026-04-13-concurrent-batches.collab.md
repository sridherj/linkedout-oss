# Concurrent Apify Batch Execution

**Date:** 2026-04-13
**Status:** Reviewed
**Depends on:** v0.4.1 slug redirect fix (landed)
**Reviewed:** 2026-04-13 — architecture, code quality, tests, performance

## Problem

### Context

v0.4.0 moved from serial single-profile enrichment to batched Apify runs — the first major throughput win. But the batch loop itself is still sequential: dispatch one batch → block-wait for Apify to finish (up to 15 min) → fetch results → post-process into DB → dispatch next batch. We have 4 Apify API keys but only use one batch at a time.

### What's slow

A batch of 100 profiles has two phases:

1. **Apify scraping** (~5-13 min per batch) — we dispatch the run and block-wait, polling every 5s. The process is entirely idle during this time.
2. **Post-processing** (~10 sec/profile, ~17 min per batch) — DB writes, embeddings, archiving. This is CPU/IO-bound and must be serialized (single DB session).

For 1,759 profiles (18 batches), observed wall-clock is ~5 hours. The dominant cost is (1) — we're idle-waiting on Apify for ~70% of total time.

### What this changes

Parallelize (1) only: dispatch N batches to Apify concurrently, poll all of them in one loop, process each as it completes. Post-processing stays serialized — no concurrent DB sessions, no new complexity there.

With N=5 batches in flight, Apify wait time overlaps and total wall-clock drops to ~1-1.5 hours.

## Solution

### 1. Add `max_parallel_batches` config

**File:** `backend/src/shared/config/settings.py`

```python
class EnrichmentConfig(BaseModel):
    ...
    max_batch_size: int = 100
    max_parallel_batches: int = 1  # 1 = sequential (current behavior)
    ...
```

Default `1` preserves current behavior. Set to 3-5 for production use. Setting it higher than the number of API keys is fine — Apify keys are round-robined for dispatch, but any key can poll any run.

### 2. Add `check_run_status()` to `LinkedOutApifyClient`

**File:** `backend/src/linkedout/enrichment_pipeline/apify_client.py`

Non-blocking single check — returns status string or `None` if still running:

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

This is the non-blocking counterpart to `poll_run_safe()`. The concurrent loop calls this on each in-flight batch every poll interval, instead of blocking on one batch at a time.

**Note:** `poll_run_safe()` and `poll_run()` remain for external callers. `_poll_fetch_save()` in `bulk_enrichment.py` is deleted — the concurrent loop handles poll/fetch/save inline.

### 3. Restructure batch loop in `enrich_profiles()`

**File:** `backend/src/linkedout/enrichment_pipeline/bulk_enrichment.py`

Replace the sequential `for batch in batches` loop (lines 374-557) with a dispatch-pool pattern:

```
pending = deque(batches)         # batches not yet dispatched
inflight = {}                     # {batch_idx: (run_id, batch_urls, dispatch_time)}

while pending or inflight:
    # ── Fill slots ──
    while len(inflight) < max_parallel_batches and pending:
        batch_idx, batch_profiles = pending.popleft()
        batch_urls = [url for _, url in batch_profiles]
        resume = _check_batch_resume(batch_idx, batch_urls, existing_state, results_dir)
        if resume.action == 'skip':
            # Already completed — count and continue
            continue
        elif resume.action == 'process':
            # Fetched but not fully processed — process from disk, don't add to inflight
            _process_batch_results(..., already_processed=resume.already_processed)
            continue
        elif resume.action == 'poll':
            # Started but not fetched — add to inflight for polling (NO re-dispatch)
            inflight[batch_idx] = (resume.run_id, batch_urls, time.time())
        else:  # 'dispatch'
            run_id = _dispatch_batch(...)
            if run_id is None:
                stopped_reason = 'all_keys_exhausted'; break
            inflight[batch_idx] = (run_id, batch_urls, time.time())

    # ── Poll all inflight ──
    api_key = _get_key(key_tracker)  # any healthy key can poll any run
    if api_key is None and inflight:
        # All keys dead — can't poll, but don't lose track of inflight batches
        # They'll be recovered on resume from state file
        stopped_reason = 'all_keys_exhausted'; break
    client = LinkedOutApifyClient(api_key) if api_key else None

    for batch_idx in list(inflight):
        run_id, batch_urls, dispatch_time = inflight[batch_idx]
        try:
            result = client.check_run_status(run_id)
        except Exception:
            # Per-batch error isolation — log, retry next poll cycle
            logger.warning('Batch %d poll error, will retry', batch_idx)
            continue

        if result is not None:
            status, dataset_id = result
            # Check disk cache before fetching from Apify
            results = _load_results(results_dir, run_id)
            if results is None:
                results = client.fetch_results(dataset_id)
            _save_results(results_dir, run_id, results)
            _process_batch_results(...)
            del inflight[batch_idx]

    # ── Timeout check ──
    for batch_idx in list(inflight):
        run_id, batch_urls, dispatch_time = inflight[batch_idx]
        if time.time() - dispatch_time > run_poll_timeout_seconds:
            logger.error('Batch %d timed out (run %s)', batch_idx, run_id)
            del inflight[batch_idx]  # removed from inflight, NOT re-dispatched

    if inflight:
        time.sleep(poll_interval)  # existing run_poll_interval_seconds (5s)
```

**Key design points:**

- **Resume logic is unchanged.** The 4-way state check (completed / fetched-not-processed / started-not-fetched / not-started) still happens per batch via `_check_batch_resume()` helper. Batches that were dispatched but not fetched before a crash get added to `inflight` on resume, not re-dispatched.

- **State file stays append-only JSONL.** Each batch still gets `batch_started`, `batch_fetched`, `batch_completed` events in order. The only difference is events from different batches may interleave — `_load_state()` already indexes by `batch_idx` so this is fine.

- **Post-processing is serialized.** When a batch completes, its `_process_batch_results()` runs immediately in the main thread. This means DB writes don't overlap, avoiding concurrent session issues. The parallelism is only in the Apify wait time.

- **Poll key is decoupled from dispatch key.** Each poll iteration calls `_get_key()` for any healthy key. Any Apify key can poll any run (polling is a GET, not billable). This means a key revoked after dispatch doesn't block polling of in-flight batches.

- **Disk cache before fetch.** Before calling `fetch_results()`, check `_load_results()`. If results exist on disk (from a prior session that fetched but crashed before `batch_fetched` state write), skip the Apify API call.

- **Per-batch error isolation.** Each `check_run_status()` and `fetch_results()` call is wrapped in try/except. One batch's HTTP error doesn't take down the poll loop — the batch is retried next cycle, other batches proceed normally.

- **`_poll_fetch_save()` is deleted.** The concurrent loop handles poll/fetch/save inline. Even `max_parallel_batches=1` uses the dispatch-pool pattern (functionally equivalent to the old sequential loop).

- **`on_progress` callback fires per batch completion**, same as today. Batches may complete out of order — that's fine, the callback reports cumulative totals.

- **Known risk: dispatch-state-write gap (~10ms).** If the process dies after Apify accepts a run but before `batch_started` is written to state, the run is orphaned and the same URLs would be re-dispatched on resume (~$0.40 worst case). This is pre-existing in the sequential code and not worsened by this change. Documented for future hardening.

### 4. Extract resume logic into helper

The current 3-way resume check (lines 378-508) is ~130 lines of inline code. Extract it into a helper that returns one of:

```python
@dataclass
class BatchResumeResult:
    action: Literal['skip', 'process', 'poll', 'dispatch']
    run_id: str | None = None
    results: list[dict] | None = None
    already_processed: set[str] = field(default_factory=set)
```

This keeps the main loop clean and makes each case testable independently. The current code already has clear `# ── Already completed ──`, `# ── Fetched but not fully processed ──`, `# ── Started but not fetched ──`, `# ── Not started ──` blocks that map 1:1 to the four actions.

## Changes

| File | Change |
|------|--------|
| `shared/config/settings.py` | Add `max_parallel_batches: int = 1` to `EnrichmentConfig` |
| `enrichment_pipeline/apify_client.py` | Add `check_run_status()` method |
| `enrichment_pipeline/bulk_enrichment.py` | Restructure batch loop to dispatch-pool; extract `_check_batch_resume()` helper; delete `_poll_fetch_save()` |

## Test Plan (21 tests)

### Core concurrency (`test_bulk_enrichment.py`)

- **T-concurrent-1**: `max_parallel_batches=1` — sequential behavior preserved (regression)
- **T-concurrent-2**: `max_parallel_batches=3`, 5 batches — dispatches 3, waits, fills as slots free
- **T-concurrent-3**: Batch completes out of order (batch 2 finishes before batch 1) — both processed correctly
- **T-concurrent-4**: One batch fails mid-flight — other batches unaffected, failed batch logged
- **T-concurrent-5**: Key exhaustion mid-flight — pending batches stop dispatching, inflight batches finish normally
- **T-concurrent-6**: Resume with 2 batches in-flight (started, not fetched) — both resume polling without re-dispatch

### Client test (`test_apify_client.py`)

- **T-concurrent-7**: `check_run_status()` returns None for running, (status, dataset_id) for terminal

### Money-protection tests (`test_bulk_enrichment.py`)

- **T-M1**: Apify run FAILED → fetch partial results from dataset, do NOT re-dispatch same URLs
- **T-M2**: Apify run TIMED-OUT → fetch partial results, do NOT re-dispatch
- **T-M3**: Resume: 3 batches in-flight, Apify completed all while we were down → `check_run_status()` returns terminal for all 3, results fetched, zero re-dispatches
- **T-M4**: Resume: batch in-flight, results already on disk → `_load_results()` returns data, `fetch_results()` not called

### Crash recovery tests (`test_bulk_enrichment.py`)

- **T-R1**: Mixed resume: 2 completed + 2 in-flight + 3 pending, `max_parallel_batches=3` → skip 2, add 2 to inflight, fill 1 slot from pending
- **T-R2**: Crash during batch 2 post-processing (3 of 5 profiles processed), batch 3 still in-flight → resume: finish batch 2 from disk (skip 3 processed), continue polling batch 3
- **T-R3**: Two back-to-back resumes with no new progress → state file doesn't grow (no duplicate events), no re-dispatches

### Error isolation tests (`test_bulk_enrichment.py`)

- **T-E1**: `check_run_status()` HTTP error for batch 1, batch 2 returns SUCCEEDED in same poll → batch 2 processed, batch 1 retried next poll
- **T-E2**: `fetch_results()` fails for completed batch → batch stays in inflight, other batches unaffected, fetch retried next cycle
- **T-E3**: All keys become invalid mid-flight → stop dispatching, inflight batches tracked in state for resume recovery

### Resume helper unit tests (`test_bulk_enrichment.py`)

- **T-BH1**: `batch_state.completed = True` → action `skip`
- **T-BH2**: `dataset_id` set, results on disk, 3 of 5 processed → action `process`, results loaded, `already_processed={3 urls}`
- **T-BH3**: `dataset_id` set, results file missing → action `poll`, `run_id` set (re-fetch needed)
- **T-BH4**: `run_id` set, no `dataset_id` → action `poll`, `run_id` set
- **T-BH5**: No state at all → action `dispatch`

## Review Decisions (2026-04-13)

| # | Topic | Decision | Rationale |
|---|-------|----------|-----------|
| 1 | Dispatch-state-write gap | Document as known risk, defer fix | ~10ms window, pre-existing, ~$0.40 worst case. Don't over-engineer. |
| 2 | Poll key strategy | Use any healthy key via `_get_key()` | Decouples from dispatch key. Key revocation mid-flight doesn't block polling. |
| 3 | Disk cache on fetch | Check `_load_results()` before `fetch_results()` | Prevents redundant Apify API calls on resume. Cheap to implement. |
| 4 | Test scope | All 21 tests (7 original + 14 additions) | Money-protection, crash recovery, error isolation, resume helper coverage. |
| 5 | Resume helper extraction | Extract `_check_batch_resume()` returning `BatchResumeResult` | Keeps main loop clean, each resume case independently testable. |
| 6 | `_poll_fetch_save()` | Delete (dead code after refactor) | One code path. Even `max_parallel_batches=1` uses the dispatch-pool pattern. |
| 7 | Sync vs async | Synchronous `time.sleep()` polling | asyncio adds complexity for ~250ms savings per 5s cycle. Bottleneck is Apify time (minutes). |

## Verification

1. `uv run python -m pytest backend/tests/unit/enrichment_pipeline/ -v`
2. `uv run python -m pytest backend/tests/ -v --tb=short` — no regressions
3. Manual: `linkedout enrich` with `max_parallel_batches: 3` — observe 3 concurrent dispatches in logs
