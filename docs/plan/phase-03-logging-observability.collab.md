# Phase 3: Logging, Observability & Reporting Infrastructure — Detailed Plan

**Version:** 1.0
**Date:** 2026-04-07
**Status:** Ready for implementation
**Depends on:** Phase 2 (Environment & Configuration System)
**Depended on by:** Phases 4–13 (all subsequent phases consume this infrastructure)

---

## Phase Overview

### Goal
Build the cross-cutting logging, metrics, and reporting layer that ALL subsequent phases consume. Every CLI command, API endpoint, and setup step must produce consistent, structured, diagnosable output. This is the nervous system — without it, debugging user issues is guesswork.

### What This Phase Delivers
1. **Enhanced loguru-based logging** — component-aware, correlation-tracked, writing to `~/linkedout-data/logs/`
2. **Per-component log files** — `backend.log`, `cli.log`, `setup.log`, `enrichment.log`, `import.log`, `queries.log`
3. **Operation result pattern** — every CLI command produces progress → summary → gaps → next steps → report path
4. **Readiness report framework** — `OperationReport` dataclass persisting JSON artifacts to `~/linkedout-data/reports/`
5. **Metrics collection** — append-only JSONL files in `~/linkedout-data/metrics/`
6. **`linkedout diagnostics` CLI command** — comprehensive shareable system health report
7. **Auto-repair hooks** — `--repair` flag to detect and fix common issues
8. **Extension logging enhancements** — structured dev logging + backend API call tracking

### Dependencies on Prior Phases
- **Phase 0 (decisions):** Logging strategy (`docs/decision/logging-observability-strategy.md`) — keep loguru, human-readable format, no JSON logs, JSONL metrics
- **Phase 2 (config):** `LINKEDOUT_LOG_DIR`, `LINKEDOUT_LOG_LEVEL`, `LINKEDOUT_METRICS_DIR`, `LINKEDOUT_REPORTS_DIR` env vars and `config.yaml` integration must exist

### Key Decision Doc Constraints
| Decision | Constraint on Phase 3 |
|----------|----------------------|
| `logging-observability-strategy.md` | Keep loguru (not structlog). Human-readable log files only. No JSON log format. Structured data → reports/metrics dirs. 50MB rotation, 30-day retention. |
| `env-config-design.md` | Logs under `~/linkedout-data/logs/`. Config via `LINKEDOUT_LOG_*` env vars. Three-layer config hierarchy. |
| `cli-surface.md` | `linkedout diagnostics` command with `--repair` and `--json` flags. All CLI commands follow operation result pattern. |
| `queue-strategy.md` | Enrichment runs synchronously — enrichment logging is inline, no worker logs. Extension errors go to `~/linkedout-data/logs/`. |

---

## Task Breakdown

### 3A. Logging Framework Enhancement (loguru)
**Complexity:** M
**Files to modify:**
- `backend/src/shared/utilities/logger.py` — main changes
- `backend/src/shared/utilities/__init__.py` — update exports

**What to do:**
1. **Migrate log file output** from `backend/logs/app_run_{RUN_ID}.log` (inside repo) to `~/linkedout-data/logs/` (user data dir). Read `LINKEDOUT_LOG_DIR` from config (Phase 2), falling back to `~/linkedout-data/logs/`.
2. **Add `component` and `operation` parameters** to `get_logger()`:
   ```python
   def get_logger(name: str = None, component: str = None, operation: str = None):
       LoggerSingleton.get_instance()
       bindings = {}
       if name: bindings['name'] = name
       if component: bindings['component'] = component
       if operation: bindings['operation'] = operation
       return logger.bind(**bindings) if bindings else logger
   ```
3. **Add per-component file sinks** via loguru's `filter` parameter. Each component (`backend`, `cli`, `setup`, `enrichment`, `import`, `queries`) gets its own log file. Use `filter=lambda record: record["extra"].get("component") == "cli"` pattern.
4. **Update rotation policy:** 50 MB rotation (down from 500 MB), 30-day retention (up from 10 days), gzip compression. Archive to `~/linkedout-data/logs/archive/`.
5. **Add correlation ID support** via `contextvars.ContextVar`. Create `correlation_id` context var module.
6. **Keep console format unchanged** — compact colorized output on stderr.

**Acceptance criteria:**
- `get_logger(__name__, component="cli", operation="import_csv")` works and routes to `cli.log`
- Log files appear in `~/linkedout-data/logs/`, not `backend/logs/`
- Old log location is no longer written to
- Rotation at 50 MB with gzip compression
- Correlation ID propagates through `contextvars`

---

### 3B. Correlation ID Infrastructure
**Complexity:** S
**Files to create:**
- `backend/src/shared/utilities/correlation.py`

**Files to modify:**
- `backend/src/shared/utilities/request_logging_middleware.py`
- `backend/src/shared/utilities/logger.py` — auto-bind correlation_id from contextvars

**What to do:**
1. **Create `correlation.py`** with:
   - `correlation_id_var: ContextVar[str]` 
   - `generate_correlation_id(prefix: str) -> str` — generates `{prefix}_{nanoid_12chars}` (e.g., `req_abc123def456`)
   - `get_correlation_id() -> str | None` — reads from contextvar
2. **Update `RequestLoggingMiddleware`** to:
   - Generate `correlation_id` per request (`req_` prefix)
   - Store in `correlation_id_var`
   - Return as `X-Correlation-ID` response header
   - Log the correlation_id in request log entries
3. **CLI correlation IDs:** Each CLI command invocation generates `cli_{command}_{timestamp}` and sets the contextvar at entry.
4. **Auto-bind in logger:** `LoggerSingleton._module_level_filter` reads `correlation_id_var` and injects into log record extras if present.

**Acceptance criteria:**
- Every backend request log line includes a `correlation_id`
- Response headers include `X-Correlation-ID`
- CLI commands log their correlation ID
- Downstream log entries within a request/command inherit the correlation ID

---

### 3C. Standardize Logger Usage Across Codebase
**Complexity:** M
**Files to modify:** ~20 files that use `import logging` / `logging.getLogger(__name__)` directly

**What to do:**
1. **Grep and replace** all direct `import logging` / `logging.getLogger(__name__)` with `from shared.utilities.logger import get_logger; logger = get_logger(__name__)`.
2. **Add `component` binding** to each call site based on its location:
   - `backend/src/linkedout/enrichment_pipeline/*` → `component="enrichment"`
   - `backend/src/linkedout/import_pipeline/*` → `component="import"`
   - `backend/src/linkedout/intelligence/*` → `component="backend"`
   - `backend/src/dev_tools/*` → `component="cli"`
   - `backend/src/utilities/llm_manager/*` → `component="backend"`
3. **Do NOT change log messages** — only change the import and logger instantiation pattern.

**Acceptance criteria:**
- Zero `import logging` or `logging.getLogger` calls remain in the codebase (except in `_StdlibIntercept` and test files)
- Every logger instance has a `component` binding
- Existing tests still pass — behavior unchanged

---

### 3D. Backend Request Logging Enhancement
**Complexity:** S
**Files to modify:**
- `backend/src/shared/utilities/request_logging_middleware.py`

**What to do:**
1. **Bind component** to logger: `logger = get_logger('http.access', component='backend')`
2. **Add correlation ID** to log entries (from 3B)
3. **Add request ID** to response headers
4. **Log additional context:** method, path, status, duration_ms, query params (redacted if sensitive)
5. **Keep the existing format** — just add correlation_id and component to extra fields

**Acceptance criteria:**
- Every API request produces a log entry in `backend.log` with correlation_id and duration_ms
- Response includes `X-Correlation-ID` header

---

### 3E. Metrics Collection Module
**Complexity:** S
**Files to create:**
- `backend/src/shared/utilities/metrics.py`

**What to do:**
1. **Create `record_metric(name, value, **context)` function** that appends a JSONL line to `~/linkedout-data/metrics/daily/YYYY-MM-DD.jsonl`.
2. **JSONL format:**
   ```json
   {"ts":"2026-04-07T14:23:05Z","metric":"profiles_imported","value":3847,"source":"csv","duration_ms":4521}
   ```
3. **Create `read_summary()` function** that reads/updates `~/linkedout-data/metrics/summary.json` (rolling summary updated by `linkedout status`).
4. **Directory creation:** Ensure `~/linkedout-data/metrics/daily/` exists on first write. Read `LINKEDOUT_METRICS_DIR` from config.
5. **Thread-safe:** Use file locking or atomic append for concurrent safety.

**Acceptance criteria:**
- `record_metric("profiles_imported", 3847, source="csv")` appends to daily JSONL
- JSONL file is human-readable and grep-able
- No external dependencies — just file I/O

---

### 3F. Operation Report Framework
**Complexity:** M
**Files to create:**
- `backend/src/shared/utilities/operation_report.py`

**What to do:**
1. **Create `OperationReport` dataclass:**
   ```python
   @dataclass
   class OperationReport:
       operation: str
       timestamp: str  # ISO 8601
       duration_ms: float
       counts: OperationCounts  # total, succeeded, skipped, failed
       coverage_gaps: list[CoverageGap]  # type, count, detail
       failures: list[OperationFailure]  # item, reason
       next_steps: list[str]
       
       def save(self, reports_dir: Path | None = None) -> Path:
           """Save to ~/linkedout-data/reports/{operation}-YYYYMMDD-HHMMSS.json"""
           
       def print_summary(self) -> None:
           """Print human-readable summary to stdout"""
           
       def to_dict(self) -> dict:
           """Serialize to dict for JSON output"""
   ```
2. **Create supporting dataclasses:** `OperationCounts`, `CoverageGap`, `OperationFailure`
3. **`print_summary()` follows the operation result pattern:**
   ```
   Results:
     Imported:  3,847 new connections
     Skipped:   23 (already in database)
     Failed:    0

   Coverage:
     Companies matched:  3,691 / 3,847 (95.9%)
     Missing companies:  156

   Next steps:
     → Run `linkedout compute-affinity` to calculate affinity scores

   Report saved: ~/linkedout-data/reports/import-csv-20260407-142305.json
   ```
4. **Reports directory:** Read `LINKEDOUT_REPORTS_DIR` from config, default `~/linkedout-data/reports/`. Create on first write.

**Acceptance criteria:**
- `OperationReport` can be instantiated, saved as JSON, and printed as human-readable summary
- JSON output includes all fields: operation, timestamp, duration_ms, counts, coverage_gaps, failures, next_steps
- `print_summary()` follows the exact output pattern from `docs/decision/cli-surface.md`
- Reports are saved to `~/linkedout-data/reports/` with timestamp-based filenames

---

### 3G. CLI Operation Logging
**Complexity:** S
**Files to modify:**
- `backend/src/dev_tools/cli.py` — add logging hooks to existing commands
- Each command file (`load_linkedin_csv.py`, `compute_affinity.py`, `generate_embeddings.py`, etc.)

**What to do:**
1. **Add CLI entry-point decorator/wrapper** that:
   - Generates a correlation ID (`cli_{command}_{timestamp}`)
   - Logs command start with parameters
   - Logs command completion with duration
   - On failure, produces a diagnostic snippet
2. **Update existing commands** to use `get_logger(__name__, component="cli")` where they don't already
3. **Do NOT refactor commands into the new `linkedout` CLI yet** — that's Phase 6. Just add logging to existing commands.

**Acceptance criteria:**
- Every CLI command invocation produces start/end log entries in `cli.log`
- Failed commands log the error with enough context to diagnose remotely
- Correlation ID is set for the duration of command execution

---

### 3H. Enrichment & Import Audit Trail
**Complexity:** S
**Files to modify:**
- `backend/src/linkedout/enrichment_pipeline/controller.py`
- `backend/src/linkedout/enrichment_pipeline/post_enrichment.py`
- `backend/src/linkedout/import_pipeline/service.py`
- `backend/src/dev_tools/load_linkedin_csv.py`
- `backend/src/dev_tools/compute_affinity.py`
- `backend/src/dev_tools/generate_embeddings.py`

**What to do:**
1. **Enrichment logging:** Add `component="enrichment"` binding to all enrichment pipeline loggers. Log: profiles enriched count, cost (if Apify), duration, errors.
2. **Import logging:** Add `component="import"` binding to import pipeline. Log: rows parsed, matched, skipped, failed with reasons.
3. **Metrics recording:** Call `record_metric()` at the end of each enrichment/import operation.
4. **Do NOT restructure enrichment pipeline** — just add logging and metrics calls to existing code.

**Acceptance criteria:**
- Enrichment operations produce entries in `enrichment.log`
- Import operations produce entries in `import.log`
- Metrics JSONL records are appended for each operation

---

### 3I. Diagnostic Report Generator (`linkedout diagnostics`)
**Complexity:** L
**Files to create:**
- `backend/src/dev_tools/diagnostics.py`

**Files to modify:**
- `backend/src/dev_tools/cli.py` — add `diagnostics` command (under existing `rcv2` CLI for now; Phase 6 creates the `linkedout` CLI)

**What to do:**
1. **Implement `linkedout diagnostics` command** (registered as `rcv2 db diagnostics` temporarily until Phase 6 CLI refactor) that collects:
   - **System info:** OS, Python version, PostgreSQL version, disk space, data dir size
   - **Config summary:** embedding provider, log level, API key status (configured/not — never the value), data dir path
   - **Database stats:** profiles total, profiles with embeddings, profiles without embeddings, companies total, connections total, last enrichment date, schema version (Alembic head)
   - **Health checks:** DB connectivity, embedding model status, API key validity (test a lightweight call), disk space adequacy
   - **Recent errors:** Parse last 50 lines of each log file for ERROR/CRITICAL entries
2. **Output format:**
   - Default: human-readable summary to stdout
   - `--json`: structured JSON to stdout
   - Always write to `~/linkedout-data/reports/diagnostic-YYYYMMDD-HHMMSS.json`
3. **Secret redaction:** API keys show only "configured" / "not configured". File paths with usernames are NOT redacted in diagnostics (only in `report-issue`).
4. **Design for shareable bug reports:** Output should be directly pasteable into a GitHub issue.

**Acceptance criteria:**
- `rcv2 db diagnostics` produces a comprehensive report covering system, config, database, health
- `--json` flag outputs valid JSON
- Report is saved to `~/linkedout-data/reports/`
- No secrets appear in the output
- Running on a healthy system shows all health checks as "pass"

---

### 3J. Auto-Repair Hooks
**Complexity:** M
**Files to create:**
- `backend/src/shared/utilities/repair.py`

**Files to modify:**
- `backend/src/dev_tools/diagnostics.py` — integrate `--repair` flag

**What to do:**
1. **Create `RepairHook` abstraction:**
   ```python
   @dataclass
   class RepairHook:
       name: str
       description: str
       detect: Callable[[], RepairDetection]  # returns count of items needing repair
       repair: Callable[[], OperationReport]   # performs the repair
   ```
2. **Register initial repair hooks:**
   - `missing_embeddings` — profiles without embeddings → offer to run embedding generation
   - `missing_affinity` — connections without affinity scores → offer to run compute-affinity
   - `stale_enrichment` — profiles with enrichment older than TTL → offer re-enrichment
3. **`--repair` flow:**
   - Run all detection hooks
   - For each detected gap: print description and count, ask "Fix N items? [Y/n]"
   - On confirm, run repair function
   - Print repair result using `OperationReport.print_summary()`
4. **Pattern for future hooks:** Framework must be extensible — other phases add their own repair hooks.

**Acceptance criteria:**
- `rcv2 db diagnostics --repair` detects and offers to fix common issues
- Each repair is interactive (asks before acting)
- Repairs produce `OperationReport` artifacts
- Framework is extensible (adding a new hook = registering one `RepairHook` instance)

---

### 3K. Setup Flow Logging
**Complexity:** S
**Files to create:**
- `backend/src/shared/utilities/setup_logger.py` (thin wrapper for setup-specific logging)

**What to do:**
1. **Setup-specific log file:** Route `component="setup"` logs to `~/linkedout-data/logs/setup.log`
2. **Setup diagnostic on failure:** When a setup step fails, generate `~/linkedout-data/logs/setup-diagnostic-YYYYMMDD-HHMMSS.txt` containing:
   - All setup log entries for the current session
   - System info snapshot
   - The step that failed and the error
3. **Step-level logging pattern:** Each setup step logs start, success/failure, and timing:
   ```
   14:23:05 I setup Step 3/9: Installing Python dependencies...
   14:23:15 I setup Step 3/9: Complete (10.2s) — 47 packages installed
   ```
4. **Note:** The actual setup flow is implemented in Phase 9. This task only creates the logging infrastructure that Phase 9 will use.

**Acceptance criteria:**
- Setup log entries route to `setup.log`
- A `SetupStepLogger` context manager or decorator is available for Phase 9 to use
- Failed setup produces a diagnostic file with enough context to file a bug report

---

### 3L. Extension Logging Enhancements
**Complexity:** S
**Files to create:**
- `extension/lib/devLog.ts`

**Files to modify:**
- `extension/lib/log.ts` — add backend API call logging to activity log entries

**What to do:**
1. **Create `devLog(level, component, message, data?)` utility:**
   ```typescript
   export function devLog(level: 'debug' | 'info' | 'warn' | 'error', component: string, message: string, data?: unknown): void {
     // Only output in dev mode or when LINKEDOUT_DEBUG=true in extension storage
     if (!isDebugEnabled) return;
     console[level](`[LinkedOut:${component}] ${message}`, data ?? '');
   }
   ```
2. **Add backend API call logging** to activity log: when the extension makes a fetch call to the backend, log the request method, path, status, duration, and any errors to the existing activity log.
3. **Add rate limit event details:** Ensure rate limit log entries include the limit that was hit and the retry-after time.
4. **Do NOT add cross-boundary correlation** in v1 (per decision doc — deferred).

**Acceptance criteria:**
- `devLog('info', 'voyager', 'Fetching profile', { url })` outputs only in debug mode
- Backend API calls logged in activity log with status and duration
- Rate limit entries include limit details

---

### 3M. Setup Report Data Layer
**Complexity:** S
**Files to create:**
- `backend/src/shared/utilities/health_checks.py`

**What to do:**
1. **Create health check functions** reusable by both `linkedout diagnostics` (3I) and the future `/linkedout-setup-report` skill (Phase 11):
   - `check_db_connection() -> HealthCheckResult`
   - `check_embedding_model() -> HealthCheckResult`
   - `check_api_keys() -> HealthCheckResult`
   - `check_disk_space() -> HealthCheckResult`
   - `get_db_stats() -> dict` — profile count, company count, embedding coverage %, etc.
2. **`HealthCheckResult` dataclass:**
   ```python
   @dataclass
   class HealthCheckResult:
       check: str
       status: Literal["pass", "fail", "skip"]
       detail: str = ""
   ```
3. **Share between diagnostics command and future skills** — diagnostics (3I) calls these functions.

**Acceptance criteria:**
- Health check functions are independently callable
- Each returns a structured result with check name, status, and detail
- `get_db_stats()` returns profile count, company count, embedding coverage %, connection count

---

## Implementation Order

```
3A (logging framework)  ──→  3B (correlation IDs)  ──→  3C (standardize usage)
      │                                                        │
      ↓                                                        ↓
3E (metrics module)                                     3D (request logging)
      │                                                        │
      ↓                                                        ↓
3F (operation report)  ──→  3G (CLI logging)  ──→  3H (enrichment/import audit)
      │
      ↓
3M (health checks)  ──→  3I (diagnostics command)  ──→  3J (auto-repair)
      
3K (setup logging) — independent, can start after 3A
3L (extension logging) — independent, can start anytime
```

**Parallelizable groups:**
- Group 1: 3A → 3B → 3C → 3D (sequential — each depends on prior)
- Group 2: 3E (can start after 3A)
- Group 3: 3F (can start after 3A)
- Group 4: 3K, 3L (independent, start after 3A)
- Group 5: 3G, 3H (after 3C + 3E + 3F)
- Group 6: 3M → 3I → 3J (after 3F)

---

## Testing Strategy

### Unit Tests
| Module | Test File | What to Test |
|--------|-----------|-------------|
| `logger.py` | `tests/unit/shared/test_logger.py` | Component routing to correct log files, correlation ID injection, rotation config |
| `correlation.py` | `tests/unit/shared/test_correlation.py` | ID generation format, contextvar propagation |
| `metrics.py` | `tests/unit/shared/test_metrics.py` | JSONL append format, daily file naming, summary read/update |
| `operation_report.py` | `tests/unit/shared/test_operation_report.py` | JSON serialization, `print_summary()` output format, file naming |
| `health_checks.py` | `tests/unit/shared/test_health_checks.py` | Health check result format, DB stats query |
| `repair.py` | `tests/unit/shared/test_repair.py` | Hook registration, detection, repair flow |

### Integration Tests
| Test | What It Verifies |
|------|-----------------|
| Log routing | CLI command produces entries in `cli.log`, not just `backend.log` |
| Diagnostics | `rcv2 db diagnostics` against real PostgreSQL produces valid JSON report |
| Metrics file | Metrics JSONL written after import operation |
| Report persistence | `OperationReport.save()` creates correct file in reports dir |

### What NOT to Test
- Don't test loguru internals (rotation, compression — those are loguru's responsibility)
- Don't test file I/O mechanics (use real tmp dirs in tests)
- Don't mock the logger itself — test that the right files get the right entries

---

## Exit Criteria Verification Checklist

- [ ] `linkedout diagnostics` (or `rcv2 db diagnostics`) produces a comprehensive shareable report
- [ ] Every CLI command and API request produces structured log output with component and correlation_id
- [ ] `~/linkedout-data/logs/` is populated after any operation, with per-component files
- [ ] Metrics are collected as JSONL in `~/linkedout-data/metrics/daily/`
- [ ] Every CLI command that modifies data produces a quantified result summary (OperationReport)
- [ ] Readiness reports are persisted JSON artifacts with precise counts and coverage gaps
- [ ] `--repair` flag on diagnostics detects and fixes common issues interactively
- [ ] Extension has `devLog()` utility and backend API call logging in activity log
- [ ] No log files are written inside the repo directory (all go to `~/linkedout-data/logs/`)
- [ ] Log rotation at 50 MB with gzip compression and 30-day retention

---

## File Summary

### New Files (to create)
| File | Task | Description |
|------|------|-------------|
| `backend/src/shared/utilities/correlation.py` | 3B | Correlation ID generation + contextvars |
| `backend/src/shared/utilities/metrics.py` | 3E | JSONL metrics recording |
| `backend/src/shared/utilities/operation_report.py` | 3F | OperationReport dataclass + print/save |
| `backend/src/shared/utilities/health_checks.py` | 3M | Reusable health check functions |
| `backend/src/shared/utilities/repair.py` | 3J | Auto-repair hook framework |
| `backend/src/shared/utilities/setup_logger.py` | 3K | Setup-specific logging utilities |
| `backend/src/dev_tools/diagnostics.py` | 3I | `linkedout diagnostics` command implementation |
| `extension/lib/devLog.ts` | 3L | Structured dev logging for extension |
| `tests/unit/shared/test_logger.py` | 3A | Logger unit tests |
| `tests/unit/shared/test_correlation.py` | 3B | Correlation ID tests |
| `tests/unit/shared/test_metrics.py` | 3E | Metrics module tests |
| `tests/unit/shared/test_operation_report.py` | 3F | Operation report tests |
| `tests/unit/shared/test_health_checks.py` | 3M | Health check tests |
| `tests/unit/shared/test_repair.py` | 3J | Repair hook tests |

### Existing Files (to modify)
| File | Task | Changes |
|------|------|---------|
| `backend/src/shared/utilities/logger.py` | 3A | Migrate log dir, add component/operation params, per-component sinks, rotation policy |
| `backend/src/shared/utilities/request_logging_middleware.py` | 3B, 3D | Add correlation ID generation + response header, component binding |
| `backend/src/shared/utilities/__init__.py` | 3A | Update exports |
| `backend/src/dev_tools/cli.py` | 3G, 3I | Add logging wrapper, register diagnostics command |
| `backend/src/linkedout/enrichment_pipeline/controller.py` | 3H | Add component binding + metrics call |
| `backend/src/linkedout/enrichment_pipeline/post_enrichment.py` | 3H | Add component binding |
| `backend/src/linkedout/import_pipeline/service.py` | 3H | Add component binding + metrics call |
| `backend/src/dev_tools/load_linkedin_csv.py` | 3H | Add component binding + metrics call |
| `backend/src/dev_tools/compute_affinity.py` | 3H | Add component binding + metrics call |
| `backend/src/dev_tools/generate_embeddings.py` | 3H | Add component binding + metrics call |
| `extension/lib/log.ts` | 3L | Add backend API call entries to activity log |
| ~20 files with `import logging` | 3C | Replace with `get_logger()` + component binding |

---

## Open Questions

1. **Metrics retention policy:** The decision doc doesn't specify how long JSONL metric files are kept. Suggest: keep forever (they're small, append-only, ~1KB/day for typical usage). Users can delete manually. Should we add a `LINKEDOUT_METRICS_RETENTION` config?

2. **Extension debug mode activation:** `devLog()` checks `LINKEDOUT_DEBUG` in extension storage. How should users toggle this? Options: (a) `browser.storage.local` key set via devtools console, (b) options page toggle (Phase 12), (c) URL param on extension pages. Suggest: (a) for now, (b) in Phase 12.

3. **Log file permissions:** Should log files be created with restricted permissions (e.g., `0640`)? Logs may contain profile names and LinkedIn URLs. The decision doc doesn't specify. Suggest: default OS permissions since it's a single-user local tool, but document that logs may contain PII.

4. **Diagnostics without DB:** What should `linkedout diagnostics` output when the database isn't set up yet (first-time user running diagnostics before setup)? Suggest: system info + config summary succeed, database section shows "not configured" or "connection failed" with guidance to run setup.

5. **Backfill existing log calls:** Task 3C targets ~20 files with direct `logging.getLogger`. The stdlib intercept already routes these through loguru, so they work today. Should 3C be deferred if it's not blocking? It adds component binding (useful for routing) but is non-critical. Suggest: include in Phase 3 for cleanliness, but it's the lowest-priority task.
