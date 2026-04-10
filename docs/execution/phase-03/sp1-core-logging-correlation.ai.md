# SP1: Core Logging Framework + Correlation IDs

**Sub-Phase:** 1 of 7
**Tasks:** 3A (Logging Framework Enhancement) + 3B (Correlation ID Infrastructure)
**Complexity:** M + S = M
**Depends on:** None (first sub-phase)
**Blocks:** SP2, SP3, SP4, SP5, SP6, SP7

---

## Objective

Enhance the existing loguru-based `LoggerSingleton` to support component-aware routing, per-component log files, updated rotation policy, and correlation ID propagation via contextvars. This is the foundation every other sub-phase builds on.

---

## Context

Read `_shared_context.md` for project-level context, architecture decisions, and naming conventions.

**Key constraint:** Keep loguru. Human-readable log files only. No JSON log format.

---

## Tasks

### 1. Migrate Log File Output (3A.1)

**File:** `backend/src/shared/utilities/logger.py`

Change `LoggerSingleton` to write logs to `~/linkedout-data/logs/` instead of `backend/logs/app_run_{RUN_ID}.log`.

- Read `LINKEDOUT_LOG_DIR` from environment, falling back to `~/linkedout-data/logs/`
- Ensure the directory exists on logger initialization
- Remove the old per-run log file pattern (`app_run_{RUN_ID}.log`)
- Replace with a single `backend.log` as the default file sink

### 2. Add Component & Operation Parameters (3A.2)

**File:** `backend/src/shared/utilities/logger.py`

Update `get_logger()` to accept `component` and `operation`:

```python
def get_logger(name: str = None, component: str = None, operation: str = None):
    LoggerSingleton.get_instance()
    bindings = {}
    if name: bindings['name'] = name
    if component: bindings['component'] = component
    if operation: bindings['operation'] = operation
    return logger.bind(**bindings) if bindings else logger
```

### 3. Add Per-Component File Sinks (3A.3)

**File:** `backend/src/shared/utilities/logger.py`

Add separate loguru sinks for each component using the `filter` parameter:

```python
# Components and their log files
COMPONENT_LOG_FILES = {
    "backend": "backend.log",
    "cli": "cli.log",
    "setup": "setup.log",
    "enrichment": "enrichment.log",
    "import": "import.log",
    "queries": "queries.log",
}
```

Each sink filters by `record["extra"].get("component") == component_name`. Logs without a component binding go to `backend.log` (the default).

### 4. Update Rotation Policy (3A.4)

**File:** `backend/src/shared/utilities/logger.py`

Update all file sinks:
- Rotation: 50 MB (read `LINKEDOUT_LOG_ROTATION`, default `"50 MB"`)
- Retention: 30 days (read `LINKEDOUT_LOG_RETENTION`, default `"30 days"`)
- Compression: `"gz"`
- Keep the archive in `{log_dir}/archive/` if loguru supports custom archive paths, otherwise use loguru's default rotation naming

### 5. Keep Console Format Unchanged (3A.5)

The existing compact colorized output on stderr must not change. Only file sinks change.

### 6. Update Exports (3A.6)

**File:** `backend/src/shared/utilities/__init__.py`

Update exports to include new correlation module items.

### 7. Create Correlation ID Module (3B.1)

**File:** `backend/src/shared/utilities/correlation.py` (NEW)

```python
import contextvars
from nanoid import generate  # or use secrets.token_urlsafe

correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default=None)

def generate_correlation_id(prefix: str = "req") -> str:
    """Generate a correlation ID: {prefix}_{12_char_id}"""
    # Use nanoid if available, otherwise secrets.token_urlsafe(9) for 12 base64 chars
    ...

def get_correlation_id() -> str | None:
    """Read correlation ID from contextvar."""
    return correlation_id_var.get(None)

def set_correlation_id(cid: str) -> None:
    """Set correlation ID in contextvar."""
    correlation_id_var.set(cid)
```

Check if `nanoid` is already a dependency. If not, use `secrets.token_urlsafe(9)` to produce a 12-character ID. Do NOT add new dependencies unless absolutely necessary.

### 8. Auto-Bind Correlation ID in Logger (3B.2)

**File:** `backend/src/shared/utilities/logger.py`

In `LoggerSingleton._module_level_filter` (or equivalent patcher), read `correlation_id_var` from contextvars and inject it into the log record's extras if present:

```python
def _patcher(record):
    cid = get_correlation_id()
    if cid:
        record["extra"]["correlation_id"] = cid
```

### 9. Update Request Logging Middleware (3B.3)

**File:** `backend/src/shared/utilities/request_logging_middleware.py`

- Generate `correlation_id` per request using `generate_correlation_id("req")`
- Store in `correlation_id_var` via `set_correlation_id()`
- Return as `X-Correlation-ID` response header
- Log the correlation_id in request log entries

---

## Files to Modify

| File | Action |
|------|--------|
| `backend/src/shared/utilities/logger.py` | Major changes: log dir, component params, per-component sinks, rotation, correlation auto-bind |
| `backend/src/shared/utilities/__init__.py` | Update exports |
| `backend/src/shared/utilities/request_logging_middleware.py` | Add correlation ID generation + response header |

## Files to Create

| File | Description |
|------|-------------|
| `backend/src/shared/utilities/correlation.py` | Correlation ID module |
| `tests/unit/shared/test_logger.py` | Logger unit tests |
| `tests/unit/shared/test_correlation.py` | Correlation ID unit tests |

---

## Verification

### Unit Tests (`tests/unit/shared/test_logger.py`)
- `get_logger(__name__, component="cli")` returns a bound logger
- Log entries with `component="cli"` appear in `cli.log` (use tmp dir)
- Log entries without component appear in `backend.log`
- Rotation config is set to 50 MB
- Log files are created in the configured log directory, not `backend/logs/`

### Unit Tests (`tests/unit/shared/test_correlation.py`)
- `generate_correlation_id("req")` produces `req_<12chars>` format
- `set_correlation_id()` / `get_correlation_id()` roundtrip via contextvars
- Correlation ID auto-binds into log records when set

### Manual Checks
- Run the backend and verify logs appear in `~/linkedout-data/logs/backend.log`
- Verify old `backend/logs/` directory is no longer written to
- Check `X-Correlation-ID` header in API response

---

## Acceptance Criteria

- [ ] `get_logger(__name__, component="cli", operation="import_csv")` works and routes to `cli.log`
- [ ] Log files appear in `~/linkedout-data/logs/`, not `backend/logs/`
- [ ] Old log location is no longer written to
- [ ] Rotation at 50 MB with gzip compression
- [ ] Correlation ID propagates through contextvars
- [ ] Every backend request log line includes a `correlation_id`
- [ ] Response headers include `X-Correlation-ID`
- [ ] Existing tests still pass
