# Shared Context: Phase 11 — Query History & Reporting

## Goal
Users can track and review their network queries and system health. After a week of usage, `/linkedout-history` and `/linkedout-report` produce meaningful output. `/linkedout-setup-report` is useful for diagnosing any issue. This phase delivers file-based query logging (JSONL), three skill implementations, and report formatting utilities for terminal and shareable output.

## Key Artifacts
- **Phase plan (source of truth):** `docs/plan/phase-11-query-history.md`
- **CLI surface decision:** `docs/decision/cli-surface.md`
- **Config design decision:** `docs/decision/env-config-design.md`
- **Data directory convention:** `docs/decision/2026-04-07-data-directory-convention.md`
- **Logging strategy decision:** `docs/decision/logging-observability-strategy.md`
- **Queue strategy decision:** `docs/decision/queue-strategy.md`
- **Skill distribution pattern:** `docs/decision/2026-04-07-skill-distribution-pattern.md`

## Architecture Overview

### Data Flow
```
Skills (user-facing)                    Data Layer (file-based)
┌─────────────────────┐                ┌──────────────────────────────┐
│ /linkedout-history   │──reads──────▶│ ~/linkedout-data/queries/     │
│ /linkedout-report    │──reads──────▶│   YYYY-MM-DD.jsonl            │
│ /linkedout-setup-rpt │──calls──────▶│ ~/linkedout-data/metrics/     │
└─────────────────────┘                │   daily/YYYY-MM-DD.jsonl     │
        │                              │ ~/linkedout-data/reports/     │
        │calls                         │   *.json                     │
        ▼                              └──────────────────────────────┘
CLI Commands (existing)                          ▲
┌─────────────────────┐                          │
│ linkedout diagnostics│──writes─────────────────┘
│ linkedout status     │
└─────────────────────┘

Query Logging (write path)
┌─────────────────────┐     ┌───────────────────────────────┐
│ /linkedout skill     │────▶│ query_logger.log_query()      │
│ (from Phase 8)       │     │   → append JSONL to queries/  │
└─────────────────────┘     │   → record_metric("query")    │
                             │   → log to queries.log        │
                             └───────────────────────────────┘
```

### Key Design Decisions
- **Query history is file-based (JSONL), NOT database-backed.** The existing `search_session`/`search_turn` tables are for the backend API (Chrome extension search UI). The skill-driven query flow writes to `~/linkedout-data/queries/` — simple, inspectable, no DB dependency.
- **No dedicated CLI commands for history or reports.** These are skills, not CLI commands. The CLI surface is the 13 approved commands only. Skills call CLI commands under the hood.
- **All query logging and report generation runs synchronously.** No async processing (per queue strategy decision).
- **Plain text output only.** No ANSI escape codes, no terminal-specific formatting. Output must be copy-pasteable into GitHub issues, Slack, and documentation.
- **Query type classification is best-effort.** The `/linkedout` skill sets it based on which DB queries/tools it used. Default: `general`.
- **No auto-cleanup of JSONL history.** A year of heavy use is <2MB. Users can `rm` files manually.
- **Skills written as plain `SKILL.md` targeting Claude Code first.** Templatize when Phase 8 infrastructure is ready. If Phase 8 IS ready, use `.tmpl` files.

## Codebase Conventions
- **Build system:** `uv run` for Python commands. Dependencies in `backend/requirements.txt`.
- **ORM:** SQLAlchemy 2.0 with `Mapped[]` type annotations. Alembic for migrations.
- **Entities:** Domain entities in `backend/src/linkedout/<domain>/entities/`. Base class: `BaseEntity`.
- **Services:** Business logic in `backend/src/linkedout/<domain>/services/`.
- **CLI:** Click commands in `backend/src/dev_tools/`. Rewired to `linkedout` namespace.
- **Logging:** loguru via `get_logger()`. Bind `component` and `operation` fields.
- **Config:** pydantic-settings via `backend/src/shared/config/config.py`. Env vars override YAML. Prefix: `LINKEDOUT_`.
- **DB sessions:** `db_session_manager.get_session(DbSessionType.READ|WRITE, app_user_id=...)` context manager.
- **Tests:** pytest in `backend/tests/`. Unit tests mock external APIs. Integration tests use real DB.
- **System user:** `SYSTEM_USER_ID` from `dev_tools.db.fixed_data` for CLI operations.

## Key File Paths

| File | Purpose |
|------|---------|
| `backend/src/linkedout/query_history/` | NEW — query logging module (this phase) |
| `backend/src/shared/utilities/metrics.py` | Phase 3I metrics module — `record_metric()` |
| `backend/src/shared/utilities/logger.py` | Logging setup — `get_logger()` |
| `backend/src/shared/config/config.py` | Config singleton, `LinkedOutSettings` |
| `skills/linkedout-history/SKILL.md.tmpl` | NEW — history skill template |
| `skills/linkedout-report/SKILL.md.tmpl` | NEW — report skill template |
| `skills/linkedout-setup-report/SKILL.md.tmpl` | NEW — setup report skill template |
| `docs/decision/cli-surface.md` | CLI command names: `linkedout status`, `linkedout diagnostics` |
| `docs/decision/env-config-design.md` | `~/linkedout-data/config/agent-context.env`, config layout |
| `docs/decision/2026-04-07-data-directory-convention.md` | All data under `~/linkedout-data/` |

## Key Dependencies from Other Phases

| Phase | What's Needed | Status |
|-------|--------------|--------|
| Phase 3 (Logging & Observability) | `record_metric()`, `get_logger()`, `OperationReport` pattern, diagnostics framework | Required |
| Phase 8 (Skill System) | Skill template system, CLAUDE.md routing, template engine, host configs | Required |
| Phase 9 (AI-Native Setup Flow) | Users must have data to query against | Required |
| Phase 6 (CLI namespace) | `linkedout status --json`, `linkedout diagnostics --json` commands | Required |

## Build Order

```
sp1 (Query Logging + Session Manager: 11A + 11B)
  ↓
sp2 (Report Formatting Utilities: 11F) ─── can parallel with sp1
  ↓
sp3 (/linkedout-history: 11C)    ─┐
sp4 (/linkedout-report: 11D)      ├── all depend on sp1 + sp2, can parallel with each other
sp5 (/linkedout-setup-report: 11E)─┘
  ↓
sp6 (Integration Tests + Verification)  ── depends on sp3, sp4, sp5
```

## Phase Dependency Summary

| Sub-Phase | Plan Tasks | Depends On | Blocks | Can Parallel With |
|-----------|-----------|-----------|--------|-------------------|
| sp1 | 11A, 11B | Phase 3 (metrics, logging), Phase 8 (skill template system) | sp3, sp4, sp6 | sp2 |
| sp2 | 11F | — | sp3, sp4, sp5 | sp1 |
| sp3 | 11C | sp1, sp2 | sp6 | sp4, sp5 |
| sp4 | 11D | sp1, sp2 | sp6 | sp3, sp5 |
| sp5 | 11E | sp2 | sp6 | sp3, sp4 |
| sp6 | Tests | sp1, sp2, sp3, sp4, sp5 | — | — |

---

## Agents & Skills to Leverage

The following `.claude/agents/` and `.claude/skills/` are available and SHOULD be invoked during sub-phase execution where applicable:

### Skills (apply to ALL sub-phases)
| Skill | When to Invoke |
|-------|---------------|
| `.claude/skills/python-best-practices/SKILL.md` | When writing query logger, report formatter, session manager |
| `.claude/skills/pytest-best-practices/SKILL.md` | When writing tests (sp6) — naming, AAA pattern, `tmp_path` for JSONL files |
| `.claude/skills/docstring-best-practices/SKILL.md` | When creating `backend/src/linkedout/query_history/` modules |

### Agents (sub-phase specific)
| Agent | Sub-Phase | When to Invoke |
|-------|-----------|---------------|
| `.claude/agents/integration-test-creator-agent.md` | sp6 (Integration Tests) | Reference for test fixture patterns when testing query logging + report generation end-to-end |

### Notes
- Phase 11 is primarily file-based (JSONL) rather than DB-backed — CRUD agents don't apply to the query history itself
- The skill templates (sp3-sp5) should follow the conventions established by Phase 8's template system
