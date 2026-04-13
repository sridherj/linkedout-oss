# SP3: Dispatch-Pool Loop

**Depends on:** SP1 (config + client method), SP2 (resume helper)
**Produces:** Rewritten `enrich_profiles()` with dispatch-pool pattern; `_poll_fetch_save()` deleted
**Estimated scope:** ~120 lines of production code (replaces ~180 lines)

## Overview

Replace the sequential `for batch_idx, batch_profiles in enumerate(batches)` loop in `enrich_profiles()` with a dispatch-pool pattern: maintain a pool of N in-flight batches, poll all concurrently, process each as it completes, fill freed slots from the pending queue.

This is the core change. After this sub-phase, `max_parallel_batches > 1` works.

---

## What changes

### 1. Add `collections.deque` import

Add to the imports at the top of `bulk_enrichment.py`:

```python
from collections import deque
```

### 2. Read `max_parallel_batches` from config

In `enrich_profiles()`, after reading `batch_size` from config (line ~357):

```python
cfg = get_config().enrichment
batch_size = cfg.max_batch_size
max_parallel_batches = cfg.max_parallel_batches
```

### 3. Replace the loop body (lines 374-557)

The current sequential loop:
```python
for batch_idx, batch_profiles in enumerate(batches):
    batch_urls = [url for _, url in batch_profiles]
    batch_state = existing_state.get(batch_idx)
    # ... 180 lines of inline resume + dispatch + poll + process ...
```

Replace with the dispatch-pool pattern:

```python
        pending = deque(enumerate(batches))  # [(batch_idx, batch_profiles), ...]
        inflight: dict[int, tuple[str, list[str], float]] = {}  # {batch_idx: (run_id, batch_urls, dispatch_time)}

        while pending or inflight:
            # ── Fill slots ──
            while len(inflight) < max_parallel_batches and pending:
                batch_idx, batch_profiles = pending.popleft()
                batch_urls = [url for _, url in batch_profiles]

                resume = _check_batch_resume(batch_idx, batch_urls, existing_state, results_dir)

                if resume.action == 'skip':
                    # Already completed — count and continue
                    logger.info('Batch {} already completed, skipping', batch_idx)
                    batches_completed += 1
                    total_enriched += len(resume.already_processed)
                    if on_progress:
                        on_progress(total_enriched, total_failed, len(profiles), batch_idx)
                    continue

                elif resume.action == 'process':
                    # Fetched but not fully processed — process from disk
                    logger.info(
                        'Batch %d fetched but not fully processed (%d/%d), resuming',
                        batch_idx, len(resume.already_processed), len(batch_urls),
                    )
                    enriched, failed = _process_batch_results(
                        batch_idx=batch_idx,
                        batch_urls=batch_urls,
                        apify_results=resume.results,
                        profile_id_by_url=profile_id_by_url,
                        already_processed=resume.already_processed,
                        state_path=state_path,
                        db_session_factory=db_session_factory,
                        post_enrichment_factory=post_enrichment_factory,
                        skip_embeddings=skip_embeddings,
                    )
                    total_enriched += enriched
                    total_failed += failed
                    _append_state(state_path, {
                        'type': 'batch_completed',
                        'batch_idx': batch_idx,
                        'enriched': enriched,
                        'failed': failed,
                    })
                    batches_completed += 1
                    if on_progress:
                        on_progress(total_enriched, total_failed, len(profiles), batch_idx)
                    continue

                elif resume.action == 'poll':
                    # Started but not fetched — add to inflight for polling (NO re-dispatch)
                    logger.info('Batch {} resuming poll (run {})', batch_idx, resume.run_id)
                    inflight[batch_idx] = (resume.run_id, batch_urls, time.time())

                else:  # 'dispatch'
                    run_id = _dispatch_batch(
                        batch_idx=batch_idx,
                        batch_urls=batch_urls,
                        key_tracker=key_tracker,
                        state_path=state_path,
                    )
                    if run_id is None:
                        stopped_reason = 'all_keys_exhausted'
                        break
                    inflight[batch_idx] = (run_id, batch_urls, time.time())

            # Break out of outer while if all keys exhausted during fill
            if stopped_reason:
                break

            # ── Poll all inflight ──
            if not inflight:
                continue

            # Any healthy key can poll any run (Decision #2)
            api_key = _get_key(key_tracker)
            if api_key is None and inflight:
                # All keys dead — can't poll. Inflight batches stay in state for resume.
                stopped_reason = 'all_keys_exhausted'
                break
            client = LinkedOutApifyClient(api_key)

            for batch_idx in list(inflight):
                run_id, batch_urls, dispatch_time = inflight[batch_idx]
                try:
                    result = client.check_run_status(run_id)
                except Exception:
                    # Per-batch error isolation — log, retry next poll cycle
                    logger.warning('Batch %d poll error for run %s, will retry', batch_idx, run_id)
                    continue

                if result is not None:
                    status, dataset_id = result
                    logger.info('Batch {} run {} finished: status={}', batch_idx, run_id, status)

                    # Disk cache before fetch (Decision #3)
                    results = _load_results(results_dir, run_id)
                    if results is None:
                        try:
                            results = client.fetch_results(dataset_id)
                        except Exception:
                            # Fetch failed — leave in inflight, retry next cycle
                            logger.warning('Batch %d fetch failed for run %s, will retry', batch_idx, run_id)
                            continue
                    _save_results(results_dir, run_id, results)

                    _append_state(state_path, {
                        'type': 'batch_fetched',
                        'batch_idx': batch_idx,
                        'run_id': run_id,
                        'dataset_id': dataset_id,
                        'run_status': status,
                        'result_count': len(results),
                    })

                    # Get already_processed from state (may have partial processing from prior crash)
                    batch_state = existing_state.get(batch_idx)
                    already_processed = batch_state.processed_urls if batch_state else set()

                    enriched, failed = _process_batch_results(
                        batch_idx=batch_idx,
                        batch_urls=batch_urls,
                        apify_results=results,
                        profile_id_by_url=profile_id_by_url,
                        already_processed=already_processed,
                        state_path=state_path,
                        db_session_factory=db_session_factory,
                        post_enrichment_factory=post_enrichment_factory,
                        skip_embeddings=skip_embeddings,
                    )
                    total_enriched += enriched
                    total_failed += failed
                    _append_state(state_path, {
                        'type': 'batch_completed',
                        'batch_idx': batch_idx,
                        'enriched': enriched,
                        'failed': failed,
                    })
                    batches_completed += 1
                    if on_progress:
                        on_progress(total_enriched, total_failed, len(profiles), batch_idx)

                    del inflight[batch_idx]

            # ── Timeout check ──
            poll_timeout = cfg.run_poll_timeout_seconds
            for batch_idx in list(inflight):
                run_id, batch_urls, dispatch_time = inflight[batch_idx]
                if time.time() - dispatch_time > poll_timeout:
                    logger.error('Batch %d timed out (run %s)', batch_idx, run_id)
                    del inflight[batch_idx]

            # ── Sleep before next poll cycle ──
            if inflight:
                time.sleep(cfg.run_poll_interval_seconds)
```

### Important behavioral notes

- **`skip` and `process` actions don't consume inflight slots.** They're resolved immediately in the fill loop via `continue`. Only `poll` and `dispatch` add to `inflight`.
- **`on_progress` fires per batch completion**, same as today. Batches may complete out of order — callback reports cumulative totals.
- **Post-processing is serialized.** `_process_batch_results()` runs in the main thread. No concurrent DB sessions.
- **Timeout removes from inflight but does NOT re-dispatch.** The batch is lost — recoverable on next resume if Apify eventually completes it.
- **`fetch_results()` failure leaves batch in inflight.** It'll be retried next poll cycle. This is per-batch error isolation.

### 4. Delete `_poll_fetch_save()`

Remove the entire `_poll_fetch_save()` function (lines 637-666 in the current file). It is dead code after this refactor — even `max_parallel_batches=1` uses the dispatch-pool pattern.

The function:
```python
def _poll_fetch_save(
    client: LinkedOutApifyClient,
    run_id: str,
    results_dir: Path,
    batch_idx: int,
    state_path: Path,
) -> tuple[str, str, list[dict]]:
    ...
```

**Confirm it has no other callers.** Search for `_poll_fetch_save` in the codebase — it should only appear in `bulk_enrichment.py` (the function definition + calls within the old loop that you just replaced).

---

## What does NOT change

- `_dispatch_batch()` — unchanged, still handles 402/401/429 rotation
- `_process_batch_results()` — unchanged, still handles matching + DB writes
- `_save_results()` / `_load_results()` — unchanged
- `_load_state()` / `_append_state()` — unchanged
- `_match_results()` — unchanged
- `_acquire_lock()` — unchanged
- `_chunk_profiles()` — unchanged
- `_get_key()` — unchanged
- `EnrichmentResult` / `BatchState` — unchanged
- State file format — unchanged (same event types, same structure)
- Lock file behavior — unchanged

---

## Verification

```bash
# Import check — code parses without errors
cd backend && uv run python -c "from linkedout.enrichment_pipeline.bulk_enrichment import enrich_profiles; print('OK')"

# Confirm _poll_fetch_save is gone
grep -r '_poll_fetch_save' backend/src/ && echo 'FAIL: still referenced' || echo 'PASS: deleted'

# Existing tests (some may need updating since internal APIs changed)
uv run python -m pytest backend/tests/unit/enrichment_pipeline/test_bulk_enrichment.py -v

# Full test suite
uv run python -m pytest backend/tests/ -v --tb=short
```

Note: Some existing tests may reference `_poll_fetch_save` in their imports or mocks. If so, update those imports/mocks to remove references. The tests themselves should still pass because the observable behavior (state file events, result processing) is unchanged.
