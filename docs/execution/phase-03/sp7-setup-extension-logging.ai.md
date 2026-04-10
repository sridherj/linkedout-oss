# SP7: Setup Flow Logging + Extension Logging Enhancements

**Sub-Phase:** 7 of 7
**Tasks:** 3K (Setup Flow Logging) + 3L (Extension Logging Enhancements)
**Complexity:** S + S = S
**Depends on:** SP1 (setup logging uses component routing from core framework)
**Blocks:** None

---

## Objective

Create setup-specific logging infrastructure for Phase 9 to consume, and add structured dev logging + backend API call tracking to the Chrome extension. These are two independent tasks grouped together because they're both small and don't affect the main dependency chain.

---

## Context

Read `_shared_context.md` for project-level context.

**Key decisions:**
- 3K creates logging infrastructure only — the actual setup flow is Phase 9
- 3L: `devLog()` only outputs in debug mode (`LINKEDOUT_DEBUG=true` in extension storage)
- No cross-boundary extension→backend correlation in v1 (deferred)

---

## Tasks

### Part A: Setup Flow Logging (3K)

#### 1. Create Setup Logger Module

**File:** `backend/src/shared/utilities/setup_logger.py` (NEW)

Thin wrapper for setup-specific logging using the SP1 framework:

```python
from shared.utilities.logger import get_logger

def get_setup_logger(step: str = None) -> loguru.Logger:
    """Get a logger bound to component='setup'."""
    bindings = {"component": "setup"}
    if step:
        bindings["operation"] = step
    return get_logger("setup", **bindings)
```

#### 2. Create SetupStepLogger Context Manager

```python
import time
from contextlib import contextmanager

@contextmanager
def setup_step(step_number: int, total_steps: int, description: str):
    """Context manager for setup step logging.
    
    Usage:
        with setup_step(3, 9, "Installing Python dependencies") as step:
            # do work
            step.detail("47 packages installed")
    
    Logs:
        14:23:05 I setup Step 3/9: Installing Python dependencies...
        14:23:15 I setup Step 3/9: Complete (10.2s) — 47 packages installed
    
    On failure:
        14:23:12 E setup Step 3/9: FAILED (7.1s) — pip install returned exit code 1
        + generates ~/linkedout-data/logs/setup-diagnostic-YYYYMMDD-HHMMSS.txt
    """
```

#### 3. Setup Diagnostic on Failure

When a setup step fails, generate `~/linkedout-data/logs/setup-diagnostic-YYYYMMDD-HHMMSS.txt` containing:
- All setup log entries for the current session (filter by correlation_id)
- System info snapshot (OS, Python version, disk space)
- The step that failed and the error traceback
- This file should be self-contained enough to file as a bug report

---

### Part B: Extension Logging Enhancements (3L)

#### 4. Create devLog Utility

**File:** `extension/lib/devLog.ts` (NEW)

```typescript
let debugEnabled: boolean | null = null;

async function isDebugEnabled(): Promise<boolean> {
    if (debugEnabled !== null) return debugEnabled;
    const result = await browser.storage.local.get('LINKEDOUT_DEBUG');
    debugEnabled = result.LINKEDOUT_DEBUG === true || result.LINKEDOUT_DEBUG === 'true';
    return debugEnabled;
}

export async function devLog(
    level: 'debug' | 'info' | 'warn' | 'error',
    component: string,
    message: string,
    data?: unknown
): Promise<void> {
    if (!await isDebugEnabled()) return;
    const prefix = `[LinkedOut:${component}]`;
    const args = data !== undefined ? [prefix, message, data] : [prefix, message];
    console[level](...args);
}
```

Notes:
- Only outputs when `LINKEDOUT_DEBUG=true` in `browser.storage.local`
- Users toggle via devtools console: `browser.storage.local.set({ LINKEDOUT_DEBUG: true })`
- Options page toggle will come in Phase 12

#### 5. Add Backend API Call Logging

**File:** `extension/lib/log.ts` (MODIFY)

When the extension makes a fetch call to the backend API, log to the existing activity log:
- Request: method, path
- Response: status code, duration_ms
- Errors: error message, status code

Add a new log type to the existing `LogEntry` types (or use existing `error` type):
```typescript
type LogType = 'fetched' | 'saved' | 'updated' | 'skipped' | 'rate_limited' | 'error' | 'best_hop' | 'api_call';
```

#### 6. Enhance Rate Limit Log Entries

**File:** `extension/lib/log.ts` (MODIFY)

Ensure `rate_limited` log entries include:
- The limit that was hit (e.g., "LinkedIn API rate limit")
- The retry-after time (if available from response headers)
- Current count vs. limit (if known)

---

## Files to Create

| File | Description |
|------|-------------|
| `backend/src/shared/utilities/setup_logger.py` | Setup-specific logging utilities |
| `extension/lib/devLog.ts` | Structured dev logging for extension |

## Files to Modify

| File | Changes |
|------|---------|
| `extension/lib/log.ts` | Add backend API call logging, enhance rate limit entries |

---

## Verification

### Part A: Setup Logging

- `get_setup_logger()` returns a logger bound to `component="setup"`
- `setup_step(3, 9, "Installing Python dependencies")` context manager:
  - Logs step start with step number
  - Logs step completion with duration
  - On exception, logs failure and generates diagnostic file
- Setup log entries route to `~/linkedout-data/logs/setup.log`
- Diagnostic file contains system info + error + log entries

### Part B: Extension Logging

- `devLog('info', 'voyager', 'Fetching profile', { url })` outputs only when `LINKEDOUT_DEBUG=true`
- When `LINKEDOUT_DEBUG` is not set or false, `devLog` produces no console output
- Backend API calls are logged in the activity log with status and duration
- Rate limit entries include limit details and retry-after

---

## Acceptance Criteria

- [ ] Setup log entries route to `setup.log`
- [ ] `SetupStepLogger` context manager (or decorator) is available for Phase 9
- [ ] Failed setup produces a diagnostic file with enough context for a bug report
- [ ] `devLog('info', 'voyager', 'Fetching profile', { url })` outputs only in debug mode
- [ ] Backend API calls logged in activity log with status and duration
- [ ] Rate limit entries include limit details
