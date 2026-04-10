# SP2: Metrics Collection Module

**Sub-Phase:** 2 of 7
**Tasks:** 3E (Metrics Collection Module)
**Complexity:** S
**Depends on:** SP1 (core logging framework)
**Blocks:** SP5 (CLI + enrichment logging)

---

## Objective

Create a simple, file-based metrics collection module that records operational metrics as append-only JSONL files. No external dependencies — just file I/O.

---

## Context

Read `_shared_context.md` for project-level context.

**Key decisions:**
- Metrics go to `~/linkedout-data/metrics/daily/YYYY-MM-DD.jsonl`
- Rolling summary in `~/linkedout-data/metrics/summary.json`
- `LINKEDOUT_METRICS_DIR` env var overrides the path
- No external services, no background processes

---

## Tasks

### 1. Create Metrics Module

**File:** `backend/src/shared/utilities/metrics.py` (NEW)

```python
def record_metric(name: str, value: Any, **context) -> None:
    """Append a metric event to the daily JSONL file.
    
    Args:
        name: Metric name (e.g., "profiles_imported")
        value: Metric value (typically a count)
        **context: Additional context fields (source, duration_ms, provider, etc.)
    
    Writes to: ~/linkedout-data/metrics/daily/YYYY-MM-DD.jsonl
    Format: {"ts":"ISO8601","metric":"name","value":N,...context}
    """
```

Implementation details:
- Read `LINKEDOUT_METRICS_DIR` from environment, default `~/linkedout-data/metrics/`
- Ensure `{metrics_dir}/daily/` directory exists on first write
- Use atomic append (open in `"a"` mode, write single line, flush)
- Timestamp in ISO 8601 UTC format
- Thread-safe: file append is atomic on POSIX for lines under PIPE_BUF (4096 bytes); our JSONL lines will be well under this

### 2. Create Summary Reader

```python
def read_summary(metrics_dir: Path | None = None) -> dict:
    """Read the rolling summary from summary.json.
    
    Returns dict with keys like profiles_total, companies_total, etc.
    Returns empty dict if summary.json doesn't exist.
    """

def update_summary(updates: dict, metrics_dir: Path | None = None) -> dict:
    """Merge updates into summary.json and return the result.
    
    Reads existing summary, merges updates (overwriting keys), writes back.
    """
```

### 3. Helper: Get Metrics Directory

```python
def _get_metrics_dir() -> Path:
    """Get metrics directory from env or default."""
    metrics_dir = os.environ.get("LINKEDOUT_METRICS_DIR", 
                                  str(Path.home() / "linkedout-data" / "metrics"))
    return Path(metrics_dir)
```

---

## Files to Create

| File | Description |
|------|-------------|
| `backend/src/shared/utilities/metrics.py` | Metrics collection module |
| `tests/unit/shared/test_metrics.py` | Metrics unit tests |

---

## Verification

### Unit Tests (`tests/unit/shared/test_metrics.py`)

- `record_metric("profiles_imported", 3847, source="csv")` creates/appends to `YYYY-MM-DD.jsonl`
- JSONL line contains `ts`, `metric`, `value`, and all context keys
- `ts` is valid ISO 8601 UTC
- Multiple `record_metric()` calls append to the same daily file
- `read_summary()` returns empty dict when no summary exists
- `update_summary({"profiles_total": 100})` creates/updates summary.json
- Directory is created automatically on first write
- Use `tmp_path` and `LINKEDOUT_METRICS_DIR` env var override for isolation

### Manual Checks
- After running, verify `~/linkedout-data/metrics/daily/YYYY-MM-DD.jsonl` is human-readable
- Verify file is grep-able: `grep profiles_imported ~/linkedout-data/metrics/daily/*.jsonl`

---

## Acceptance Criteria

- [ ] `record_metric("profiles_imported", 3847, source="csv")` appends to daily JSONL
- [ ] JSONL file is human-readable and grep-able
- [ ] No external dependencies — just file I/O
- [ ] Directory auto-created on first write
- [ ] `read_summary()` and `update_summary()` work correctly
- [ ] Thread-safe append (atomic POSIX write)
