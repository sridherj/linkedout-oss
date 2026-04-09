---
feature: logging
module: backend/src/shared/utilities
linked_files:
  - backend/src/shared/utilities/logger.py
  - backend/src/shared/utilities/setup_logger.py
  - backend/src/shared/utilities/correlation.py
  - backend/src/shared/utilities/request_logging_middleware.py
version: 1
last_verified: "2026-04-09"
---

# Logging & Observability

**Created:** 2026-04-09 — Adapted from internal spec for LinkedOut OSS

## Intent

Provide a centralized, loguru-based logging system that replaces stdlib `logging` across the codebase. All output (console + per-component files) flows through a single pipeline with module-level filtering, colorized compact console output, verbose rotating file logs, and automatic correlation ID injection.

## Behaviors

### LoggerSingleton

- **Singleton pattern**: `LoggerSingleton.get_instance()` ensures only one logger configuration exists. Safe to call multiple times. Verify multiple calls return the same instance.

- **Dual output sinks**:
  - **Console** (stderr): Compact colorized format (`HH:mm:ss LEVEL module message`), `enqueue=True` for thread safety, `backtrace=True`, `diagnose=True`.
  - **File** (`{log_dir}/backend.log`): Verbose format with timestamp, level, full module path, function, line number, and correlation ID. Rotation and retention are configured via `LinkedOutSettings.log_rotation` (default `50 MB`) and `LinkedOutSettings.log_retention` (default `30 days`). Files are gzip-compressed on rotation.

- **Per-component file sinks**: Additional log files route specific subsystem output. Component log files: `cli.log`, `setup.log`, `enrichment.log`, `import.log`, `queries.log`. A log entry is routed to a component file only when the logger is bound with `component=<name>`. The default `backend.log` sink captures all logs regardless of component.

- **Correlation ID injection**: A patcher function injects the current correlation ID (from `correlation.get_correlation_id()`) into every log record's extras. This ensures file logs include the correlation ID for request tracing.

- **Stdlib logging intercept**: All `logging.getLogger()` calls are routed through loguru via `_StdlibIntercept` handler. `logging.basicConfig(handlers=[...], level=0, force=True)` ensures all stdlib loggers are captured. Verify third-party libraries using stdlib logging appear in loguru output.

### Module-Level Log Levels

- **Env-var configuration**: `LOG_LEVEL_<MODULE>=LEVEL` sets the log level for a specific module. Underscores in the env var name map to dots in the module path (e.g., `LOG_LEVEL_LINKEDOUT_INTELLIGENCE=DEBUG` maps to `linkedout.intelligence`). Supported levels: TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL.

- **Prefix matching**: If a module name isn't found exactly in the level map, prefix matching is used (e.g., `linkedout.intelligence` matches `linkedout.intelligence.agents.search_agent`).

- **Default level**: `LinkedOutSettings.log_level`, defaults to `INFO`.

### Correlation IDs (`correlation.py`)

- **Generation**: `generate_correlation_id(prefix)` produces IDs in the format `{prefix}_{12_char_nanoid}` (e.g., `req_V1StGXR8_Z5j`).

- **Propagation**: Stored in a `ContextVar`, automatically propagates through async call chains. Middleware sets it at request start; any downstream code reads it via `get_correlation_id()`.

### Request Logging Middleware (`request_logging_middleware.py`)

- **Per-request correlation ID**: Generates a correlation ID (prefix `req`) for each HTTP request and stores it in the contextvar.

- **Response header**: Injects `X-Correlation-ID` into every HTTP response.

- **Access log line**: Logs `{method} {path} {status_code} {duration_ms} [{correlation_id}]` for every HTTP request.

- **Sensitive parameter redaction**: Query parameters matching `api_key`, `token`, `password`, `secret`, `authorization`, and variants are redacted to `[REDACTED]` in log output.

### Setup Logger (`setup_logger.py`)

- **get_setup_logger(step)**: Returns a logger pre-bound to `component='setup'` for routing to `setup.log`.

- **setup_step() context manager**: Wraps setup steps with timing, logging step start/completion with duration. On failure, writes a self-contained diagnostic file to `{log_dir}/setup-diagnostic-{timestamp}.txt` with system info, correlation ID, error traceback, and disk usage.

### Public API

| Function | Purpose |
|----------|---------|
| `setup_logging(environment, log_level)` | Initialize the singleton. Safe to call multiple times. |
| `get_logger(name, component, operation)` | Return a loguru logger bound with module name, optional component for file routing, and optional operation context. |
| `set_level(level)` | Set the global default log level at runtime. |
| `set_module_log_level(module_name, level)` | Set a module-specific log level at runtime. |
| `get_module_log_level(module_name)` | Get the effective log level for a module. |

- **Backwards compatibility**: The module exports `logger` as a pre-bound instance, so existing `from shared.utilities.logger import logger` imports continue to work.

## Decisions

| Date | Decision | Chose | Over | Because |
|------|----------|-------|------|---------|
| 2026-04-02 | Logging framework | loguru | stdlib logging | Richer formatting, simpler API, built-in rotation, colorized output. Stdlib is intercepted for compatibility. |
| 2026-04-02 | Singleton vs module-level | LoggerSingleton class | Module-level global init | Parallels DbSessionManager pattern. Explicit initialization via `setup_logging()`. |
| 2026-04-02 | Thread safety | `enqueue=True` on all sinks | No enqueue | Prevents interleaved log lines from async/threaded code. |
| 2026-04-09 | Per-component log files | Component-based routing via `get_logger(component=...)` | Single log file | Separates noisy subsystems (imports, enrichment, CLI) into dedicated files for easier debugging. |
| 2026-04-09 | Log directory | `LinkedOutSettings.log_dir` (defaults to `~/linkedout-data/logs`) | Hardcoded path | Configurable via settings; consistent with data_dir pattern. |

## Not Included

- Structured JSON logging (for log aggregation services)
- Remote log shipping (Datadog, CloudWatch, etc.)
- Log sampling or rate limiting
