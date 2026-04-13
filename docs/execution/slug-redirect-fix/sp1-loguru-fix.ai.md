# SP1: Loguru Format Fix

**Depends on:** Nothing (independent)
**Produces:** Clean loguru formatting across enrichment pipeline files
**Estimated scope:** ~17 line changes, no new code

## Overview

Fix 17 logger calls that use stdlib `%s`/`%d` formatting but run through loguru (which uses `{}` style). Logs currently show literal `%d`, `%s` instead of interpolated values.

These changes are already in the working tree (staged or unstaged). This sub-phase verifies the changes are correct and commits them.

## What to Do

### Step 1: Verify working tree changes

Check `git diff` and `git diff --cached` for changes in:
- `backend/src/linkedout/enrichment_pipeline/bulk_enrichment.py` (14 calls)
- `backend/src/linkedout/enrichment_pipeline/post_enrichment.py` (3 calls)

### Step 2: Verify correctness

Every logger call should use `{}` placeholders, not `%s` or `%d`. Examples of correct patterns:

```python
# WRONG (stdlib style)
logger.info('Processed %d profiles in batch %d', count, batch_idx)
logger.warning('Failed to process %s: %s', url, error)

# RIGHT (loguru style)
logger.info('Processed {} profiles in batch {}', count, batch_idx)
logger.warning('Failed to process {}: {}', url, error)
```

If any `%s`/`%d` calls remain in these two files, fix them.

### Step 3: Run existing tests

```bash
cd /data/workspace/linkedout-oss && uv run python -m pytest backend/tests/unit/enrichment_pipeline/ -v --tb=short
```

All existing tests must pass. The format changes are log-only — no behavior change.

### Step 4: Commit

Stage the two files and commit with message:
```
Fix loguru format strings: replace %s/%d with {} in enrichment pipeline

17 logger calls across bulk_enrichment.py (14) and post_enrichment.py (3)
used stdlib %s/%d formatting but the logger is loguru ({} style).
Logs showed literal %d, %s instead of interpolated values.
```

## Files Changed

| File | Change |
|------|--------|
| `backend/src/linkedout/enrichment_pipeline/bulk_enrichment.py` | 14 logger calls: `%s`/`%d` → `{}` |
| `backend/src/linkedout/enrichment_pipeline/post_enrichment.py` | 3 logger calls: `%s`/`%d` → `{}` |

## Verification

- [ ] No `%s` or `%d` in logger calls in either file
- [ ] `uv run python -m pytest backend/tests/unit/enrichment_pipeline/ -v` passes
- [ ] Changes committed
