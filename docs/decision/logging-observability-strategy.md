# Logging & Observability Strategy

**Date:** 2026-04-07
**Status:** Approved by SJ (2026-04-07)
**Spike:** Phase 0H
**Implements:** Plan Phase 3 (Logging, Observability & Reporting Infrastructure)

---

## 1. Current State

### Backend (Python)
- **Framework:** loguru (adopted 2026-04-02, decision doc: `backend/docs/decision/2026-04-02-loguru-logging.md`)
- **Central module:** `backend/src/shared/utilities/logger.py` — `LoggerSingleton` with dual sinks (console + file)
- **Console format:** Compact colorized (`HH:mm:ss LEVEL module message`) on stderr
- **File format:** Verbose plain text (`YYYY-MM-DD HH:mm:ss.SSS | LEVEL | module:func:line | message`) in `backend/logs/app_run_{RUN_ID}.log`
- **Rotation:** 500 MB size, 10-day retention
- **Module-level filtering:** `LOG_LEVEL_<MODULE>=LEVEL` env vars with prefix matching
- **Stdlib intercept:** All `logging.getLogger()` calls route through loguru via `_StdlibIntercept`
- **Request logging:** `RequestLoggingMiddleware` logs HTTP method, path, status, duration
- **Inconsistency:** ~20 files still use `import logging` / `logging.getLogger(__name__)` directly (enrichment pipeline, intelligence tools, LLM manager, eval tests). These work via the stdlib intercept but bypass the `get_logger()` API, losing the `name` binding for filtering.

### Extension (TypeScript)
- **Activity log:** `extension/lib/log.ts` — append-only `LogEntry` records in `browser.storage.local`, capped at 200 entries
- **Log types:** fetched, saved, updated, skipped, rate_limited, error, best_hop
- **No structured dev logging** — uses `console.log` only

### CLI Commands
- No dedicated CLI logging infrastructure. CLI commands use the backend's `get_logger()` when running in-process but have no separate log file or consistent output pattern.

### Skills
- No logging infrastructure exists for skills (they run inside Claude Code / Codex).

---

## 2. Framework Decision

### Decision: Keep loguru. Do not switch to structlog.

**Rationale:**
1. loguru is already adopted, working, and tested. Switching costs are real, benefits are marginal for a single-user local tool.
2. loguru's built-in file rotation, colorized output, and stdlib intercept cover our needs.
3. structlog's main advantage (structured JSON for log aggregation) is less relevant — LinkedOut has no centralized log infrastructure.
4. loguru supports JSON serialization natively (`serialize=True`) when we need it.

**What we add on top of loguru:**
- A configurable JSON output mode (toggle via config, not a framework swap)
- Consistent field binding across all subsystems
- Correlation ID propagation

---

## 3. Log Format: Human-Readable Default, JSON Toggle

### Console (stderr) — human-readable, always
```
14:23:05 I cli.import Imported 3847 connections from CSV (23 skipped, 0 failed)
14:23:06 D backend.enrichment Starting enrichment batch [batch_id=abc123]
```

### File — human-readable only
```
2026-04-07 14:23:05.123 | INFO     | cli.import:run_import:45 | Imported 3847 connections from CSV (23 skipped, 0 failed)
```

**No JSON log format.** Structured data for programmatic consumption lives in `~/linkedout-data/reports/` (operation reports) and `~/linkedout-data/metrics/` (JSONL metrics). Log files are for humans reading with `tail -f` and `grep`.

---

## 4. Standard Log Fields

Every log entry (regardless of subsystem) must carry these fields via loguru's `bind()`:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `component` | str | Subsystem identifier | `backend`, `cli`, `extension`, `skill`, `setup` |
| `operation` | str | What's happening | `import_csv`, `enrich_profile`, `compute_affinity`, `search` |
| `correlation_id` | str | Request/session trace ID | `req_abc123`, `setup_20260407_1423` |

**Optional context fields** (bound per-operation):
- `duration_ms` — operation timing
- `profile_count`, `company_count` — batch operation counts
- `cost_usd` — for enrichment/embedding operations
- `error_type`, `error_detail` — on failures

**How to bind:** Wrap the existing `get_logger(name)` to accept component:
```python
logger = get_logger(__name__, component="cli", operation="import_csv")
# Internally: loguru.bind(name=name, component=component, operation=operation)
```

---

## 5. Log Levels Per Subsystem

| Subsystem | Default Level | Rationale |
|-----------|--------------|-----------|
| `backend.api` | INFO | Log requests, don't spam with route details |
| `backend.enrichment` | INFO | Track enrichment progress, errors |
| `backend.intelligence` | INFO | Log search/agent operations, not individual tool calls |
| `cli` | INFO | User-facing — show progress |
| `cli.import` | INFO | Show import progress and results |
| `cli.setup` | INFO | Show setup step progress |
| `http.access` | INFO | Request logging |
| `sqlalchemy.engine` | WARNING | Only on errors; DEBUG for query tracing |
| `apify` | INFO | Track API calls and costs |
| `openai` | WARNING | Suppress noisy SDK logs |
| `langfuse` | WARNING | Suppress unless debugging |

**Override:** `LOG_LEVEL_CLI_IMPORT=DEBUG` → sets `cli.import` to DEBUG.

---

## 6. Log File Layout

```
~/linkedout-data/logs/
├── backend.log          # Backend API server logs (when running)
├── cli.log              # All CLI command execution logs
├── setup.log            # Setup flow logs (appended across re-runs)
├── enrichment.log       # Enrichment pipeline (apify calls, costs, profile updates)
├── import.log           # CSV/contact import operations
├── queries.log          # Search queries and results summaries
└── archive/             # Rotated log files
```

**Key change from current state:** Logs move from `backend/logs/app_run_{RUN_ID}.log` (inside the repo) to `~/linkedout-data/logs/` (user data directory). The `LINKEDOUT_LOG_DIR` env var overrides.

### Routing
Each subsystem writes to its own log file via separate loguru sinks. The backend API also writes to `backend.log`. All sinks share the same format configuration.

**Implementation:** `LoggerSingleton` adds per-component file sinks with `filter=lambda record: record["extra"].get("component") == "cli"`.

---

## 7. Log Rotation Policy

| Setting | Value | Rationale |
|---------|-------|-----------|
| Rotation trigger | 50 MB per file | Smaller than current 500 MB — appropriate for single-user local tool |
| Retention | 30 days | Longer than current 10 days — users may not check logs frequently |
| Compression | gzip (`.gz`) | loguru supports `compression="gz"` natively |
| Archive location | `~/linkedout-data/logs/archive/` | Keep active logs clean |
| Naming | `backend.2026-04-07_14-23-05.log.gz` | Timestamp-based for easy sorting |

**Config env vars:**
- `LINKEDOUT_LOG_ROTATION=50 MB` (loguru rotation string)
- `LINKEDOUT_LOG_RETENTION=30 days` (loguru retention string)

---

## 8. Correlation IDs

### Backend API
- Generate a `correlation_id` per request in `RequestLoggingMiddleware` (nanoid, 12 chars, prefix `req_`).
- Store in `contextvars.ContextVar` so all downstream logging within that request inherits it.
- Return as `X-Correlation-ID` response header.

### CLI Commands
- Generate a `correlation_id` per CLI invocation: `cli_{command}_{timestamp}` (e.g., `cli_import_20260407_1423`).
- Bind to logger at command entry point.

### Extension → Backend
- Extension generates a `correlation_id` per user action and sends as `X-Correlation-ID` request header.
- Backend middleware reads it (or generates one if missing).
- Extension logs the correlation_id alongside its activity log entries.

### Skills
- Skills run inside Claude Code and don't produce traditional logs. Instead, skills log implicitly through the CLI commands they invoke (which carry correlation IDs). No additional logging infrastructure needed for skills.

---

## 9. Metrics Approach

### Simple JSONL Files — No External Service

```
~/linkedout-data/metrics/
├── daily/
│   └── 2026-04-07.jsonl     # One line per metric event
└── summary.json              # Rolling summary (updated by CLI commands)
```

**Metric events** (append-only JSONL):
```json
{"ts":"2026-04-07T14:23:05Z","metric":"profiles_imported","value":3847,"source":"csv","duration_ms":4521}
{"ts":"2026-04-07T14:23:06Z","metric":"enrichment_batch","profiles":50,"cost_usd":0.25,"provider":"apify","duration_ms":12000}
{"ts":"2026-04-07T14:25:00Z","metric":"embedding_generated","count":100,"model":"nomic-embed-text-v1.5","duration_ms":8500}
{"ts":"2026-04-07T15:00:00Z","metric":"query","query_type":"company_lookup","results":12,"duration_ms":230}
```

**Rolling summary** (`summary.json` — updated by `linkedout status`):
```json
{
  "profiles_total": 4012,
  "profiles_with_embeddings": 3847,
  "companies_total": 52000,
  "last_enrichment": "2026-04-07T14:23:06Z",
  "enrichment_cost_cumulative_usd": 12.50,
  "queries_today": 15,
  "queries_total": 234
}
```

**Implementation:** A thin `metrics.py` module with `record_metric(name, value, **context)` that appends to the daily JSONL file. No background processes, no aggregation daemons.

---

## 10. Diagnostic Report

`linkedout diagnostics` CLI command produces a comprehensive, shareable report.

### Contents

```json
{
  "generated_at": "2026-04-07T14:30:00Z",
  "system": {
    "os": "Ubuntu 24.04",
    "python": "3.12.3",
    "postgresql": "16.2",
    "linkedout_version": "0.1.0",
    "disk_free_gb": 45.2,
    "data_dir": "~/linkedout-data/",
    "data_dir_size_mb": 128.5
  },
  "config": {
    "embedding_provider": "local",
    "embedding_model": "nomic-embed-text-v1.5",
    "langfuse_enabled": false,
    "backend_url": "http://localhost:8001",
    "api_keys": {
      "openai": "configured",
      "apify": "not configured"
    }
  },
  "database": {
    "connected": true,
    "profiles_total": 4012,
    "profiles_with_embeddings": 3847,
    "profiles_without_embeddings": 165,
    "companies_total": 52000,
    "connections_total": 3870,
    "last_enrichment": "2026-04-07T14:23:06Z",
    "schema_version": "abc123def"
  },
  "health_checks": [
    {"check": "db_connection", "status": "pass"},
    {"check": "embedding_model", "status": "pass", "detail": "nomic-embed-text-v1.5 loaded"},
    {"check": "api_key_openai", "status": "skip", "detail": "not configured"},
    {"check": "api_key_apify", "status": "skip", "detail": "not configured"},
    {"check": "disk_space", "status": "pass", "detail": "45.2 GB free"}
  ],
  "recent_errors": [
    {"timestamp": "2026-04-07T14:20:00Z", "component": "enrichment", "message": "Apify rate limit exceeded", "count": 3}
  ]
}
```

### Output
- Written to `~/linkedout-data/reports/diagnostic-YYYYMMDD-HHMMSS.json`
- Also printed to stdout in a human-readable summary format
- Secrets are **never** included — only "configured" / "not configured"
- Designed to be pasted directly into a GitHub issue

### `--repair` flag
`linkedout diagnostics --repair` detects and offers to fix common issues:
- Profiles without embeddings → offer to run `linkedout embed`
- Stale enrichment data → offer to re-enrich
- Missing config values → prompt user to set them

---

## 11. Readiness Report Framework

Every major operation produces a structured report to `~/linkedout-data/reports/`:

```
~/linkedout-data/reports/
├── diagnostic-20260407-143000.json
├── import-csv-20260407-142305.json
├── compute-affinity-20260407-142400.json
├── re-embed-20260407-142500.json
├── seed-import-20260407-140000.json
└── setup-readiness-20260407-135500.json
```

### Report Format (standard for all operations)

```json
{
  "operation": "import-csv",
  "timestamp": "2026-04-07T14:23:05Z",
  "duration_ms": 4521,
  "counts": {
    "total": 3870,
    "succeeded": 3847,
    "skipped": 23,
    "failed": 0
  },
  "coverage_gaps": [
    {"type": "missing_company", "count": 156, "detail": "156 connections work at companies not in the database"},
    {"type": "missing_embedding", "count": 165, "detail": "165 profiles have no embedding vector"}
  ],
  "failures": [],
  "next_steps": [
    "Run `linkedout compute-affinity` to calculate affinity scores",
    "Run `linkedout embed` to generate embeddings for 165 profiles"
  ]
}
```

**Implementation:** A `OperationReport` dataclass with a `save()` method that writes to the reports directory. Every CLI command creates one at the end of execution.

---

## 12. Operation Result Pattern (CLI Output)

Every CLI command follows this output pattern:

```
$ linkedout load-linkedin-csv ~/Downloads/connections.csv

Loading connections from connections.csv...
  [============================] 3870/3870 profiles

Results:
  Imported:  3,847 new connections
  Skipped:   23 (already in database)
  Failed:    0

Coverage:
  Companies matched:  3,691 / 3,847 (95.9%)
  Missing companies:  156 (will resolve on next seed update)

Next steps:
  → Run `linkedout compute-affinity` to calculate affinity scores
  → Run `linkedout embed` to generate embeddings

Report saved: ~/linkedout-data/reports/import-csv-20260407-142305.json
```

**Pattern:** Progress → Summary → Coverage gaps → Next steps → Report path.

---

## 13. Extension Logging Enhancements

The existing `extension/lib/log.ts` activity log (200 entries in `browser.storage.local`) is sufficient for user-facing activity tracking.

### Additions for observability:
1. **Dev console logging:** Add a `devLog(level, component, message, data?)` utility that wraps `console.log` with structured format (only outputs in development mode or when `LINKEDOUT_DEBUG=true` in extension storage).
2. **Backend API call logging:** Log all fetch calls to backend in the activity log with status, duration, and error details.
3. **Rate limit events:** Already logged. Ensure they include the limit that was hit and the retry-after time.
4. **Error aggregation:** On extension popup/side-panel, show error count badge if recent errors exist.

### No cross-boundary correlation in v1
Extension → backend correlation via `X-Correlation-ID` header is a nice-to-have but not critical for single-user local use. Defer to Phase 3 implementation if time permits.

---

## 14. Implementation Plan (Phase 3 Mapping)

| Plan Task | Decision Applied |
|-----------|-----------------|
| 3A. Structured logging framework | Keep loguru + JSON toggle (not structlog) |
| 3B. Log file layout & rotation | `~/linkedout-data/logs/` with per-component files, 50MB rotation, 30-day retention |
| 3C. Backend request logging | Enhance `RequestLoggingMiddleware` with correlation IDs |
| 3D. CLI operation logging | Standard field binding + per-command log files |
| 3E. Enrichment audit trail | Enrichment-specific log file + metrics JSONL |
| 3F. Extension logging | `devLog()` utility + backend call logging |
| 3G. Diagnostic report | `linkedout diagnostics` command |
| 3H. Setup flow logging | Setup-specific log file + setup diagnostic report |
| 3I. Metrics collection | JSONL append files in `~/linkedout-data/metrics/` |
| 3J. Setup report data | Part of diagnostic report |
| 3K. Readiness report | `OperationReport` dataclass, JSON artifacts in `~/linkedout-data/reports/` |
| 3L. Operation result pattern | Progress → Summary → Gaps → Next steps → Report path |
| 3M. Auto-repair hooks | `--repair` flag on `linkedout diagnostics` |

---

## 15. Migration Steps

1. **Migrate log files:** Change `LoggerSingleton` to write to `~/linkedout-data/logs/` instead of `backend/logs/`. Support `LINKEDOUT_LOG_DIR` override.
2. **Standardize logger usage:** Replace all `import logging; logger = logging.getLogger(__name__)` with `from shared.utilities.logger import get_logger; logger = get_logger(__name__)`. (~20 files).
3. **Add component binding:** Update `get_logger()` to accept `component` parameter. Update all call sites.
4. **Add JSON mode:** Add `LINKEDOUT_LOG_FORMAT=json` support to `LoggerSingleton`.
5. **Add per-component sinks:** Route logs to separate files based on `component` field.
6. **Add correlation IDs:** `contextvars.ContextVar` + middleware integration.
7. **Build metrics module:** `record_metric()` function writing JSONL.
8. **Build report framework:** `OperationReport` dataclass.
9. **Build diagnostics command:** `linkedout diagnostics` CLI.

---

## 16. Config Summary

| Env Var | Default | Description |
|---------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Global default log level |
| `LOG_LEVEL_<MODULE>` | (none) | Per-module log level override |
| `LINKEDOUT_LOG_DIR` | `~/linkedout-data/logs/` | Log file directory |
| `LINKEDOUT_LOG_FORMAT` | `human` | Log format — human-readable only (no JSON mode, structured data goes to reports/metrics) |
| `LINKEDOUT_LOG_ROTATION` | `50 MB` | Log file rotation size |
| `LINKEDOUT_LOG_RETENTION` | `30 days` | Log file retention period |
| `LINKEDOUT_METRICS_DIR` | `~/linkedout-data/metrics/` | Metrics JSONL directory |
| `LINKEDOUT_REPORTS_DIR` | `~/linkedout-data/reports/` | Report output directory |
