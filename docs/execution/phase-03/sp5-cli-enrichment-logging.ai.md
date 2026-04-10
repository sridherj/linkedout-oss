# SP5: CLI Operation Logging + Enrichment/Import Audit Trail

**Sub-Phase:** 5 of 7
**Tasks:** 3G (CLI Operation Logging) + 3H (Enrichment & Import Audit Trail)
**Complexity:** S + S = M
**Depends on:** SP2 (metrics), SP3 (operation report), SP4 (standardized loggers)
**Blocks:** None

---

## Objective

Instrument all existing CLI commands with structured entry/exit logging and correlation IDs. Add metrics recording and component-specific logging to the enrichment and import pipelines. This is the "apply the framework" sub-phase — use the infrastructure from SP1-SP4.

---

## Context

Read `_shared_context.md` for project-level context.

**Key constraint:** Do NOT refactor commands into the new `linkedout` CLI — that's Phase 6. Just add logging to existing commands. Do NOT restructure the enrichment pipeline — just add logging and metrics calls.

---

## Tasks

### 1. CLI Entry-Point Logging Wrapper (3G.1)

**File:** `backend/src/dev_tools/cli.py`

Create a decorator or context manager that wraps CLI command execution:

```python
import functools
from shared.utilities.correlation import generate_correlation_id, set_correlation_id
from shared.utilities.logger import get_logger

def cli_logged(command_name: str):
    """Decorator for CLI commands that adds correlation ID and entry/exit logging."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cid = generate_correlation_id(f"cli_{command_name}")
            set_correlation_id(cid)
            logger = get_logger(__name__, component="cli", operation=command_name)
            logger.info(f"Starting {command_name}", params=kwargs)
            start = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start) * 1000
                logger.info(f"Completed {command_name}", duration_ms=duration_ms)
                return result
            except Exception as e:
                duration_ms = (time.time() - start) * 1000
                logger.error(f"Failed {command_name}: {e}", 
                           duration_ms=duration_ms, error_type=type(e).__name__)
                raise
        return wrapper
    return decorator
```

### 2. Apply Logging Wrapper to Existing Commands (3G.2)

Apply `@cli_logged("command_name")` to each existing CLI command function:

| Command File | Command Name |
|---|---|
| `backend/src/dev_tools/load_linkedin_csv.py` | `"load_linkedin_csv"` |
| `backend/src/dev_tools/compute_affinity.py` | `"compute_affinity"` |
| `backend/src/dev_tools/generate_embeddings.py` | `"generate_embeddings"` |

Verify each command file uses `get_logger(__name__, component="cli")` (should already be done by SP4).

### 3. Enrichment Pipeline Logging (3H.1)

**Files to modify:**
- `backend/src/linkedout/enrichment_pipeline/controller.py`
- `backend/src/linkedout/enrichment_pipeline/post_enrichment.py`

Changes:
- Ensure loggers use `component="enrichment"` binding (verify SP4 did this)
- Add structured logging at key points:
  - Enrichment batch start: log batch size, provider
  - Enrichment batch complete: log profiles enriched count, duration, cost (if Apify)
  - Individual profile errors: log profile identifier and error reason
- Call `record_metric("enrichment_batch", profiles_count, provider=provider, duration_ms=duration, cost_usd=cost)` at batch completion

### 4. Import Pipeline Logging (3H.2)

**Files to modify:**
- `backend/src/linkedout/import_pipeline/service.py`
- `backend/src/dev_tools/load_linkedin_csv.py`

Changes:
- Ensure loggers use `component="import"` binding (verify SP4 did this)
- Add structured logging:
  - Import start: log source, row count
  - Import complete: log rows parsed, matched, skipped, failed with reasons
- Call `record_metric("profiles_imported", count, source=source, duration_ms=duration)` at completion

### 5. Affinity & Embedding Metrics (3H.3)

**Files to modify:**
- `backend/src/dev_tools/compute_affinity.py`
- `backend/src/dev_tools/generate_embeddings.py`

Add `record_metric()` calls at the end of each operation:
- `record_metric("affinity_computed", count, duration_ms=duration)`
- `record_metric("embedding_generated", count, model=model, duration_ms=duration)`

---

## Files to Modify

| File | Changes |
|------|---------|
| `backend/src/dev_tools/cli.py` | Add `cli_logged` decorator/wrapper |
| `backend/src/dev_tools/load_linkedin_csv.py` | Apply logging wrapper + metrics call |
| `backend/src/dev_tools/compute_affinity.py` | Apply logging wrapper + metrics call |
| `backend/src/dev_tools/generate_embeddings.py` | Apply logging wrapper + metrics call |
| `backend/src/linkedout/enrichment_pipeline/controller.py` | Add structured logging + metrics call |
| `backend/src/linkedout/enrichment_pipeline/post_enrichment.py` | Add component binding verification |
| `backend/src/linkedout/import_pipeline/service.py` | Add structured logging + metrics call |

---

## Verification

### Automated Checks

- Run existing tests — all must pass
- Start backend, trigger an import/enrichment, verify:
  - CLI log entries appear in `cli.log` with correlation_id
  - Enrichment entries appear in `enrichment.log`
  - Import entries appear in `import.log`
  - Metrics JSONL file is created/appended in `~/linkedout-data/metrics/daily/`

### Manual Checks

- Run a CLI command and check `~/linkedout-data/logs/cli.log` for start/end entries
- Check that failed commands log the error with enough context to diagnose remotely
- Verify correlation ID is consistent across all log entries for one command invocation

---

## Acceptance Criteria

- [ ] Every CLI command invocation produces start/end log entries in `cli.log`
- [ ] Failed commands log the error with enough context to diagnose remotely
- [ ] Correlation ID is set for the duration of command execution
- [ ] Enrichment operations produce entries in `enrichment.log`
- [ ] Import operations produce entries in `import.log`
- [ ] Metrics JSONL records are appended for each operation
- [ ] Existing tests still pass
