# Fix: Enrichment Pipeline — Recover Uncollected Apify Results

## Problem

Two bugs in the enrichment pipeline cause **paid Apify results to be silently lost**:

### Bug 1: No recovery sweep for incomplete batches

When `enrich_profiles()` exits with batches dispatched but results never fetched (process killed, timeout, etc.), those Apify results sit in datasets indefinitely. On re-run, the input profile list changes (some profiles got enriched), so index-based crash recovery silently matches the old run's state against different URLs and either produces mismatches or skips them entirely.

**Root cause:** The pipeline has no pre-run recovery step that processes incomplete batches from the state file using the URLs stored in `batch_started` events.

### Bug 2: `--dry-run` doesn't report recoverable batches

`enrich_command()` dry run just counts `has_enriched_data = false` rows and reports a cost estimate. It never checks the state file for `batch_started` without `batch_completed` — so the user sees "840 unenriched, est. $3.36" when 300 of those already have paid results sitting in Apify.

### Impact (2026-04-13 incident)

- 16 batches dispatched, 13 completed, **3 batches (9, 10, 11) dispatched but results never fetched**
- 300 profiles with SUCCEEDED Apify runs, results sitting in datasets
- Dry run reported 840 needing enrichment — would have paid ~$1.20 again for those 300
- Manual recovery required: fetch datasets by run_id, process through PostEnrichmentService

## Fix

### Step 1: Pre-run recovery sweep (`bulk_enrichment.py`)

New function `recover_incomplete_batches()`:

1. Load state file -> find batches with `batch_started` but no `batch_completed`
2. For each incomplete batch, use the URLs and run_id from the `batch_started` event:
   a. Check Apify run status via `check_run_status(run_id)`
   b. If SUCCEEDED -> fetch results from dataset, process through `_process_batch_results()`, mark completed
   c. If FAILED/ABORTED -> mark batch as failed in state, profiles remain unenriched for next dispatch
   d. If still RUNNING -> skip (report to caller)
3. Return `RecoverySummary(recovered, failed, still_running)`

```python
@dataclass
class RecoverySummary:
    recovered: int          # profiles successfully processed from prior Apify results
    failed: int             # profiles in batches that Apify reported FAILED/ABORTED
    still_running: int      # profiles in batches still running on Apify
    batches_recovered: int  # number of batches fully recovered
```

The function uses URLs from `batch_started` events (not the current input list), so it works regardless of how the input list changed between runs.

### Step 2: State file rotation (`bulk_enrichment.py`)

After recovery sweep, if all prior batches are resolved (completed or failed, none still running), rotate the state file:

```python
if all_resolved and state_path.exists():
    state_path.rename(state_path.with_suffix('.jsonl.prev'))
```

This ensures the new run starts with a clean state file, avoiding index collisions.

### Step 3: Integrate into `enrich_command()` (`enrich.py`)

**Full run:** Call `recover_incomplete_batches()` before querying unenriched profiles. If recovery found results, re-query the unenriched count.

**Dry run:** Call a read-only variant `check_recoverable_batches()` that checks Apify status without fetching/processing. Report recoverable count separately:

```
Dry run: 840 unenriched profiles found
  300 have completed Apify runs awaiting collection (no additional cost)
  540 need new Apify enrichment (~$2.16)
Run `linkedout enrich` to collect + enrich.
```

### Step 4: Timeout -> defer to recovery, not discard (`bulk_enrichment.py`)

Change timeout handling (lines 532-537) to remove from inflight but leave state as `batch_started` (already the case). Log a clear warning:

```python
logger.warning(
    'Batch {} poll timed out (run {}). Results may still arrive — '
    'will attempt recovery on next run.',
    batch_idx, run_id,
)
del inflight[batch_idx]  # stop polling this run, but state file retains batch_started
```

This is mostly a logging clarity change — the current behavior already leaves the batch recoverable.

## Files

| File | Change |
|------|--------|
| `backend/src/linkedout/enrichment_pipeline/bulk_enrichment.py` | Add `recover_incomplete_batches()`, `check_recoverable_batches()`, state rotation |
| `backend/src/linkedout/commands/enrich.py` | Integrate recovery into command + dry run |
| `backend/tests/unit/enrichment_pipeline/test_bulk_enrichment.py` | New recovery tests |
| `backend/tests/unit/cli/test_enrich_command.py` | Dry-run recovery reporting tests |

## Tests

### `test_bulk_enrichment.py` — new tests

| Test | What it verifies |
|------|-----------------|
| `test_recover_succeeded_batches` | Mocks 2 incomplete batches with SUCCEEDED Apify runs. Verifies results are fetched, `_process_batch_results` is called with correct URLs from state file, state file gets `batch_completed` events, returns correct `RecoverySummary`. |
| `test_recover_failed_batches` | Mocks incomplete batch where Apify returned FAILED. Verifies batch marked failed in state, profiles not processed, `RecoverySummary.failed` count correct. |
| `test_recover_still_running` | Mocks incomplete batch where `check_run_status` returns None (still running). Verifies batch skipped, `RecoverySummary.still_running` count correct, state file unchanged. |
| `test_recover_mixed` | One SUCCEEDED, one FAILED, one RUNNING. Verifies each handled correctly, counts add up. |
| `test_state_rotation_after_full_recovery` | All prior batches resolved. Verifies state file renamed to `.jsonl.prev`, new state file is clean. |
| `test_no_rotation_when_batches_still_running` | One batch still running. Verifies state file NOT rotated. |
| `test_check_recoverable_batches_readonly` | Read-only check. Verifies Apify status checked but no results fetched, no state file writes. |

### `test_enrich_command.py` — new tests

| Test | What it verifies |
|------|-----------------|
| `test_dry_run_reports_recoverable_batches` | State file has incomplete batches, Apify returns SUCCEEDED. Dry-run output includes "N have completed Apify runs awaiting collection". |
| `test_full_run_recovers_before_dispatching` | `recover_incomplete_batches` called before `enrich_profiles`. Recovery count reported. |

## Verification

```bash
cd backend && source .venv/bin/activate
pytest tests/unit/enrichment_pipeline/test_bulk_enrichment.py -k "recover" -v
pytest tests/unit/cli/test_enrich_command.py -k "recover" -v
```
