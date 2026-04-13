# Concurrent Apify Batch Execution — Shared Context

**Plan:** `docs/plan/2026-04-13-concurrent-batches.collab.md`
**Project root:** `/data/workspace/linkedout-oss`
**Backend root:** `/data/workspace/linkedout-oss/backend`
**Source root:** `/data/workspace/linkedout-oss/backend/src`

## Goal

Parallelize Apify batch dispatch: send N batches concurrently, poll all in one loop, process each as it completes. Post-processing stays serialized. With N=5, wall-clock drops from ~5h to ~1-1.5h.

## Review Decisions (Binding)

These decisions were made during plan review on 2026-04-13. They are NOT negotiable — follow them exactly.

| # | Topic | Decision | Rationale |
|---|-------|----------|-----------|
| 1 | Dispatch-state-write gap | Document as known risk, defer fix | ~10ms window, pre-existing, ~$0.40 worst case |
| 2 | Poll key strategy | Use any healthy key via `_get_key()` | Decouples from dispatch key |
| 3 | Disk cache on fetch | Check `_load_results()` before `fetch_results()` | Prevents redundant Apify API calls on resume |
| 4 | Test scope | All 21 tests | Money-protection, crash recovery, error isolation, resume helper |
| 5 | Resume helper extraction | Extract `_check_batch_resume()` returning `BatchResumeResult` | Keeps main loop clean |
| 6 | `_poll_fetch_save()` | Delete (dead code after refactor) | One code path for all batch counts |
| 7 | Sync vs async | Synchronous `time.sleep()` polling | asyncio adds complexity for ~250ms savings |

## Key Files

| File | Relative Path | Role |
|------|--------------|------|
| `settings.py` | `backend/src/shared/config/settings.py` | `EnrichmentConfig` pydantic model — add `max_parallel_batches` |
| `apify_client.py` | `backend/src/linkedout/enrichment_pipeline/apify_client.py` | Apify HTTP client — add `check_run_status()` |
| `bulk_enrichment.py` | `backend/src/linkedout/enrichment_pipeline/bulk_enrichment.py` | Main pipeline — extract resume helper, rewrite loop, delete `_poll_fetch_save()` |
| `test_bulk_enrichment.py` | `backend/tests/unit/enrichment_pipeline/test_bulk_enrichment.py` | Pipeline tests |
| `test_apify_client.py` | `backend/tests/unit/enrichment_pipeline/test_apify_client.py` | Client tests |

## Key Classes and Methods (Current State)

### `EnrichmentConfig` (settings.py)
```python
class EnrichmentConfig(BaseModel):
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
    skip_embeddings: bool = False
```

### `LinkedOutApifyClient` (apify_client.py)
- `enrich_profiles_async(urls)` → starts async run, returns `run_id`
- `poll_run(run_id)` → blocking poll, raises on failure
- `poll_run_safe(run_id)` → blocking poll, returns `(status, dataset_id)` on any terminal state
- `fetch_results(dataset_id)` → returns `list[dict]`
- **Does NOT have `check_run_status()` yet** — SP1 adds it

### `enrich_profiles()` (bulk_enrichment.py)
Current loop (lines 374-557) is sequential: `for batch_idx, batch_profiles in enumerate(batches)` with inline 4-way resume check (completed / fetched-not-processed / started-not-fetched / not-started).

### Helper functions (bulk_enrichment.py)
- `_get_key(key_tracker)` → returns API key or None if all exhausted
- `_dispatch_batch(batch_idx, batch_urls, key_tracker, state_path)` → dispatches to Apify, returns run_id or None
- `_poll_fetch_save(client, run_id, results_dir, batch_idx, state_path)` → blocking poll+fetch+save, returns `(status, dataset_id, results)` — **will be deleted in SP3**
- `_process_batch_results(...)` → processes results for a batch, returns `(enriched, failed)` — **unchanged**
- `_save_results(results_dir, run_id, results)` → persists raw Apify data to disk
- `_load_results(results_dir, run_id)` → loads saved results, returns None if missing
- `_load_state(state_path)` → reads JSONL state, returns `{batch_idx: BatchState}`
- `_append_state(state_path, event)` → appends event to JSONL state

### Data types (bulk_enrichment.py)
- `EnrichmentResult` — summary of a pipeline run
- `BatchState` — reconstructed state of a single batch from state file

## Conventions

- All files get `# SPDX-License-Identifier: Apache-2.0` header
- Logger: `get_logger(__name__, component="enrichment")`
- Tests: `pytest` with `tmp_path` fixture, mocks via `unittest.mock`
- Imports use relative package paths: `from shared.config import get_config`
- State file is append-only JSONL with event types: `batch_started`, `batch_fetched`, `profile_processed`, `batch_completed`

## Dependency Chain

```
SP1 (Foundation) ──┐
                    ├── SP3 (Dispatch-Pool Loop) ── SP4 (Tests)
SP2 (Resume Helper) ┘
```

SP1 and SP2 are independent (different files / additive-only). SP3 depends on both. SP4 depends on all.

## Verification

```bash
uv run python -m pytest backend/tests/unit/enrichment_pipeline/ -v
uv run python -m pytest backend/tests/ -v --tb=short
```
