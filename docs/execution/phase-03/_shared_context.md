# Phase 03: Logging, Observability & Reporting — Shared Context

**Project:** LinkedOut OSS
**Phase:** 3 — Logging, Observability & Reporting Infrastructure
**Phase Plan:** `docs/plan/phase-03-logging-observability.md`
**Status:** Ready for implementation

---

## Project Overview

LinkedOut is a self-hosted, AI-native professional network intelligence tool. The user imports LinkedIn connections, enriches profiles, generates embeddings, and queries their network through CLI commands and a Chrome extension. The primary interface is a Claude Code / Codex / Copilot skill, with CLI commands as the underlying building blocks.

This phase builds the cross-cutting logging, metrics, and reporting layer that ALL subsequent phases (4-13) consume. Every CLI command, API endpoint, and setup step must produce consistent, structured, diagnosable output.

---

## Architecture Decisions (Binding Constraints)

### Logging Framework: loguru (NOT structlog)
- **Decision doc:** `docs/decision/logging-observability-strategy.md`
- loguru is already adopted and working. Do not switch.
- Human-readable log files only. **No JSON log format** — structured data goes to reports/metrics dirs.
- `serialize=True` available when needed, but default is human-readable.

### Log File Location
- **All logs → `~/linkedout-data/logs/`** (user data dir, not inside the repo)
- `LINKEDOUT_LOG_DIR` env var overrides this path
- Per-component files: `backend.log`, `cli.log`, `setup.log`, `enrichment.log`, `import.log`, `queries.log`
- Archive dir: `~/linkedout-data/logs/archive/`

### Log Rotation Policy
- 50 MB per file rotation (not 500 MB)
- 30-day retention
- gzip compression
- Archive to `~/linkedout-data/logs/archive/`

### Config Hierarchy (Phase 2)
- Env vars > `~/linkedout-data/config/config.yaml` > `~/linkedout-data/config/secrets.yaml` > code defaults
- Relevant env vars: `LINKEDOUT_LOG_DIR`, `LINKEDOUT_LOG_LEVEL`, `LINKEDOUT_LOG_ROTATION`, `LINKEDOUT_LOG_RETENTION`, `LINKEDOUT_METRICS_DIR`, `LINKEDOUT_REPORTS_DIR`
- **Decision doc:** `docs/decision/env-config-design.md`

### CLI Surface
- **Decision doc:** `docs/decision/cli-surface.md`
- `linkedout diagnostics` with `--repair` and `--json` flags
- All CLI commands follow operation result pattern: Progress → Summary → Gaps → Next steps → Report path
- Current CLI is `rcv2` namespace — Phase 6 creates the `linkedout` CLI. For now, register new commands under `rcv2`.

### Queue Strategy
- **Decision doc:** `docs/decision/queue-strategy.md`
- Enrichment runs synchronously (no Procrastinate). No worker logs needed.
- Extension errors go to `~/linkedout-data/logs/`

---

## Key Files & Paths

### Existing Files (to modify)
| File | Description |
|------|-------------|
| `backend/src/shared/utilities/logger.py` | `LoggerSingleton` — central logging module with dual sinks |
| `backend/src/shared/utilities/__init__.py` | Exports for shared utilities |
| `backend/src/shared/utilities/request_logging_middleware.py` | FastAPI request logging middleware |
| `backend/src/dev_tools/cli.py` | Main CLI entry point (Click-based `rcv2` commands) |
| `backend/src/dev_tools/load_linkedin_csv.py` | CSV import command |
| `backend/src/dev_tools/compute_affinity.py` | Affinity computation command |
| `backend/src/dev_tools/generate_embeddings.py` | Embedding generation command |
| `backend/src/linkedout/enrichment_pipeline/controller.py` | Enrichment pipeline controller |
| `backend/src/linkedout/enrichment_pipeline/post_enrichment.py` | Post-enrichment processing |
| `backend/src/linkedout/import_pipeline/service.py` | Import pipeline service |
| `extension/lib/log.ts` | Extension activity log |

### New Files (to create)
| File | Sub-Phase | Description |
|------|-----------|-------------|
| `backend/src/shared/utilities/correlation.py` | SP1 | Correlation ID generation + contextvars |
| `backend/src/shared/utilities/metrics.py` | SP2 | JSONL metrics recording |
| `backend/src/shared/utilities/operation_report.py` | SP3 | OperationReport dataclass + print/save |
| `backend/src/shared/utilities/health_checks.py` | SP6 | Reusable health check functions |
| `backend/src/shared/utilities/repair.py` | SP6 | Auto-repair hook framework |
| `backend/src/shared/utilities/setup_logger.py` | SP7 | Setup-specific logging utilities |
| `backend/src/dev_tools/diagnostics.py` | SP6 | Diagnostics command implementation |
| `extension/lib/devLog.ts` | SP7 | Structured dev logging for extension |

### Test Files (to create)
| File | Sub-Phase |
|------|-----------|
| `tests/unit/shared/test_logger.py` | SP1 |
| `tests/unit/shared/test_correlation.py` | SP1 |
| `tests/unit/shared/test_metrics.py` | SP2 |
| `tests/unit/shared/test_operation_report.py` | SP3 |
| `tests/unit/shared/test_health_checks.py` | SP6 |
| `tests/unit/shared/test_repair.py` | SP6 |

---

## Naming Conventions

- **Component names:** `backend`, `cli`, `setup`, `enrichment`, `import`, `queries` (lowercase, match log file names)
- **Correlation ID format:** `{prefix}_{nanoid_12chars}` (e.g., `req_abc123def456`, `cli_import_20260407_1423`)
- **Metric names:** snake_case (e.g., `profiles_imported`, `enrichment_batch`, `embedding_generated`)
- **Report filenames:** `{operation}-YYYYMMDD-HHMMSS.json` (e.g., `import-csv-20260407-142305.json`)
- **Log format (file):** `YYYY-MM-DD HH:mm:ss.SSS | LEVEL | module:func:line | message`
- **Log format (console):** `HH:mm:ss LEVEL module message` (compact, colorized, stderr)

---

## Standard Log Fields (via loguru bind())

Every log entry must carry:
| Field | Type | Description |
|-------|------|-------------|
| `component` | str | Subsystem: `backend`, `cli`, `setup`, `enrichment`, `import`, `queries` |
| `operation` | str | What's happening: `import_csv`, `enrich_profile`, `compute_affinity` |
| `correlation_id` | str | Request/session trace ID: `req_abc123`, `cli_import_20260407_1423` |

---

## Operation Result Pattern (CLI Output)

Every CLI command follows this pattern:
```
Progress indicator (optional)
Results:
  [Action]:  N items
  Skipped:   N (reason)
  Failed:    N

Coverage:
  [Metric]:  X / Y (Z%)

Next steps:
  → Run `linkedout <next-command>` to ...

Report saved: ~/linkedout-data/reports/{operation}-YYYYMMDD-HHMMSS.json
```

---

## Sub-Phase Dependency Graph

```
SP1 (core logging + correlation)
 ├──→ SP2 (metrics collection)     ──→ SP5 (CLI + enrichment logging)
 ├──→ SP3 (operation report)       ──→ SP5
 │                             └───→ SP6 (diagnostics + repair)
 ├──→ SP4 (standardize loggers)    ──→ SP5
 └──→ SP7 (setup + extension logging)
```

**Parallelizable:** SP2, SP3, SP4, SP7 can all run in parallel after SP1.
**Sequential:** SP5 requires SP2 + SP3 + SP4. SP6 requires SP3.

---

## Testing Approach

- **Unit tests:** Test each new module independently. Use `tmp_path` fixture for file-based tests.
- **Do NOT mock loguru internals** — test that the right files get the right entries.
- **Do NOT test file I/O mechanics** — use real temp dirs.
- **Integration tests:** Verify log routing, diagnostics against real PostgreSQL, metrics file writes.
- Existing tests must continue to pass after logger standardization (3C).

---

## What NOT to Do

- Do NOT switch from loguru to structlog
- Do NOT add JSON log format — structured data goes to reports/metrics
- Do NOT refactor CLI commands into the new `linkedout` namespace (that's Phase 6)
- Do NOT restructure the enrichment pipeline — just add logging
- Do NOT add cross-boundary extension→backend correlation (deferred)
- Do NOT change existing log messages when standardizing loggers — only change import/instantiation patterns
- Do NOT write log files inside the repo directory

---

## Agents & Skills to Leverage

The following `.claude/agents/` and `.claude/skills/` are available and SHOULD be invoked during sub-phase execution where applicable:

### Skills (apply to ALL sub-phases)
| Skill | When to Invoke |
|-------|---------------|
| `.claude/skills/python-best-practices/SKILL.md` | When writing any Python code — naming, formatting, type hints |
| `.claude/skills/pytest-best-practices/SKILL.md` | When writing tests — naming conventions, AAA pattern, fixtures |
| `.claude/skills/docstring-best-practices/SKILL.md` | When creating new modules (`correlation.py`, `metrics.py`, `operation_report.py`, `health_checks.py`, `repair.py`) |

### Agents (sub-phase specific)
| Agent | Sub-Phase | When to Invoke |
|-------|-----------|---------------|
| `.claude/agents/integration-test-creator-agent.md` | SP6 (diagnostics tests) | Reference for integration test patterns with real PostgreSQL |

### Notes
- Phase 3 creates cross-cutting utilities, not CRUD entities — CRUD agents don't apply
- All new modules in `shared/utilities/` should follow docstring and Python best practices skills
