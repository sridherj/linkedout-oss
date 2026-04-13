# SP2: Resume Helper

**Depends on:** Nothing (parallel with SP1)
**Produces:** `BatchResumeResult` dataclass + `_check_batch_resume()` function in bulk_enrichment.py
**Estimated scope:** ~80 lines of production code

## Overview

Extract the inline 4-way resume logic from `enrich_profiles()` (lines 378-508) into a standalone helper function. This is **additive only** — the helper and dataclass are added to the file but the existing loop is NOT modified. SP3 will rewrite the loop to call the helper.

The current code has clear comment blocks that map 1:1 to the four resume actions:
- `# ── Already completed ──` → action `skip`
- `# ── Fetched but not fully processed ──` → action `process`
- `# ── Started but not fetched ──` → action `poll`
- `# ── Not started ──` → action `dispatch`

---

## Change 1: `BatchResumeResult` dataclass

**File:** `backend/src/linkedout/enrichment_pipeline/bulk_enrichment.py`
**Location:** In the "Data types" section (after `BatchState`, around line 72)

```python
@dataclass
class BatchResumeResult:
    """What to do with a batch based on its state file history."""

    action: str  # 'skip' | 'process' | 'poll' | 'dispatch'
    run_id: str | None = None
    results: list[dict] | None = None
    already_processed: set[str] = field(default_factory=set)
```

### Field semantics

| action | run_id | results | already_processed | Meaning |
|--------|--------|---------|-------------------|---------|
| `skip` | — | — | — | Batch fully completed in prior run. Count and continue. |
| `process` | set | loaded from disk | set of already-processed URLs | Fetched but not fully processed. Process from disk, skip already-processed profiles. |
| `poll` | set | None | possibly set | Dispatched but not fetched. Add to inflight for polling (NO re-dispatch). |
| `dispatch` | None | None | empty | Not started. Dispatch to Apify. |

---

## Change 2: `_check_batch_resume()` function

**File:** `backend/src/linkedout/enrichment_pipeline/bulk_enrichment.py`
**Location:** In the "Internal helpers" section (after `_get_key()`, before `_dispatch_batch()`)

```python
def _check_batch_resume(
    batch_idx: int,
    batch_urls: list[str],
    existing_state: dict[int, BatchState],
    results_dir: Path,
) -> BatchResumeResult:
    """Determine what action to take for a batch based on prior state.

    Checks state file history and disk cache to classify the batch into one of:
    - skip: fully completed in a prior run
    - process: results fetched and on disk, but not all profiles processed
    - poll: dispatched to Apify but results not fetched yet
    - dispatch: not started, needs fresh Apify dispatch
    """
    batch_state = existing_state.get(batch_idx)

    # ── Not started ──
    if batch_state is None:
        return BatchResumeResult(action='dispatch')

    # ── Already completed ──
    if batch_state.completed:
        return BatchResumeResult(
            action='skip',
            already_processed=batch_state.processed_urls,
        )

    # ── Fetched but not fully processed ──
    if batch_state.dataset_id and batch_state.run_id:
        saved_results = _load_results(results_dir, batch_state.run_id)
        if saved_results is not None:
            return BatchResumeResult(
                action='process',
                run_id=batch_state.run_id,
                results=saved_results,
                already_processed=batch_state.processed_urls,
            )
        else:
            # Results file missing — need to re-fetch via polling
            # (dataset_id is set, so Apify completed, but we lost the file)
            return BatchResumeResult(
                action='poll',
                run_id=batch_state.run_id,
                already_processed=batch_state.processed_urls,
            )

    # ── Started but not fetched ──
    if batch_state.run_id:
        return BatchResumeResult(
            action='poll',
            run_id=batch_state.run_id,
            already_processed=batch_state.processed_urls,
        )

    # ── Defensive: state exists but no run_id (shouldn't happen) ──
    return BatchResumeResult(action='dispatch')
```

### Key details

- **Pure function**: reads state and disk, returns a value. No side effects.
- **Does NOT dispatch, poll, or modify state** — caller decides what to do based on the action.
- The "fetched but results file missing" case returns `poll` (not `dispatch`) because the run already exists in Apify — re-dispatching would waste money. Re-polling will get the terminal status and re-fetch.
- `already_processed` is always set from `batch_state.processed_urls` when state exists, enabling callers to skip profiles that were already written to DB.
- Defensive fallback at the end handles corrupt state (has batch entry but no run_id).

### Important: This is additive only

Do NOT modify the existing `enrich_profiles()` loop. The helper is added alongside the existing code. SP3 will rewrite the loop to call `_check_batch_resume()`. Until SP3 runs, the existing sequential loop continues to work as-is.

---

## Exports

Add `BatchResumeResult` and `_check_batch_resume` to the module's logical interface. They don't need to be in `__all__` (they're internal helpers), but test imports will reference them:

```python
from linkedout.enrichment_pipeline.bulk_enrichment import (
    _check_batch_resume,
    BatchResumeResult,
)
```

---

## Verification

```bash
# Existing tests still pass (no behavioral changes — only additive code)
uv run python -m pytest backend/tests/unit/enrichment_pipeline/test_bulk_enrichment.py -v

# Quick import check
cd backend && uv run python -c "from linkedout.enrichment_pipeline.bulk_enrichment import BatchResumeResult, _check_batch_resume; print('OK')"
```

No existing behavior is modified. The helper is dead code until SP3 calls it.
