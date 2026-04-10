# Phase 11: Query History & Reporting — Detailed Execution Plan

**Version:** 1.0
**Date:** 2026-04-07
**Status:** Ready for implementation
**Phase goal:** Users can track and review their network queries and system health. After a week of usage, `/linkedout-history` and `/linkedout-report` produce meaningful output. `/linkedout-setup-report` is useful for diagnosing any issue.
**Dependencies:** Phase 9 (AI-Native Setup Flow) — the setup flow must be complete so that users have data to query against. Phase 3 (Logging & Observability) — the readiness report framework, operation result pattern, metrics collection, and diagnostic report infrastructure are prerequisites. Phase 8 (Skill System) — skill template system and CLAUDE.md routing must exist for the three new skills.
**Delivers:** File-based query logging (JSONL), three skill implementations (`/linkedout-history`, `/linkedout-report`, `/linkedout-setup-report`), and report formatting utilities for terminal and shareable output.

---

## Phase 0 Decisions That Constrain This Phase

| Decision Doc | Constraint on Phase 11 |
|---|---|
| `docs/decision/cli-surface.md` | No dedicated CLI commands for history or reports — these are **skills**, not CLI. The CLI surface is the 13 approved commands only. `linkedout diagnostics` (already defined) handles system health. `linkedout status` provides quick health check. Skills call these CLI commands under the hood. |
| `docs/decision/env-config-design.md` | Query history logs to `~/linkedout-data/queries/YYYY-MM-DD.jsonl`. Reports to `~/linkedout-data/reports/`. All paths configurable via `LINKEDOUT_DATA_DIR`. Config in `~/linkedout-data/config/config.yaml`. |
| `docs/decision/logging-observability-strategy.md` | Query operations log to `~/linkedout-data/logs/queries.log` via loguru. Metrics written to `~/linkedout-data/metrics/daily/YYYY-MM-DD.jsonl` (the `query` metric type). Human-readable log format. Reports follow the `OperationReport` pattern from Phase 3K. |
| `docs/decision/queue-strategy.md` | No async processing. All query logging and report generation runs synchronously. |
| `docs/decision/2026-04-07-data-directory-convention.md` | `~/linkedout-data/` is the unified data directory. |

---

## Architecture Overview

Phase 11 introduces three layers:

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

**Key design decision:** Query history is file-based (JSONL), NOT database-backed. The existing `search_session`/`search_turn` tables in the DB are for the backend API (used by the Chrome extension's search UI). The skill-driven query flow writes to flat files in `~/linkedout-data/queries/` — simple, inspectable, no DB dependency for query logging, easy to back up or delete.

The existing `search_session`/`search_turn`/`search_tag` DB entities (in `backend/src/linkedout/search_session/`) remain available for the backend API but are NOT the data source for `/linkedout-history`. The skill's query log is its own first-class data store.

---

## Detailed Task Breakdown

### 11A. Query Logging Module

**Goal:** A lightweight Python module that the `/linkedout` skill invokes to record every query. Writes JSONL files organized by day.

**Acceptance criteria:**
- `log_query()` function appends a single JSON line to `~/linkedout-data/queries/YYYY-MM-DD.jsonl`
- Each JSONL entry contains: `timestamp` (ISO 8601), `query_id` (nanoid, prefix `q_`), `session_id` (groups related queries in a conversation), `query_text` (the user's natural language query), `query_type` (e.g., `company_lookup`, `person_search`, `semantic_search`, `network_stats`), `result_count` (number of results returned), `duration_ms`, `model_used` (which LLM processed the query), `is_refinement` (boolean — true if this query refines a prior query in the same session)
- Also records a `query` metric to `~/linkedout-data/metrics/daily/YYYY-MM-DD.jsonl` via the Phase 3I metrics module (`record_metric()`)
- Also logs a summary line to `~/linkedout-data/logs/queries.log` via loguru (component: `skill`, operation: `query`)
- File creation is lazy — directory and file created on first write
- Thread-safe (fcntl advisory lock on the JSONL file for concurrent writes)
- Handles `LINKEDOUT_DATA_DIR` override for all paths

**File targets:**
- `backend/src/linkedout/query_history/query_logger.py` — new file, the logging module
- `backend/src/linkedout/query_history/__init__.py` — new file

**Integration points:**
- Uses `record_metric()` from Phase 3I metrics module (`backend/src/shared/utilities/metrics.py` or similar)
- Uses `get_logger()` from `backend/src/shared/utilities/logger.py` with `component="skill"`, `operation="query"`
- Uses config for `LINKEDOUT_DATA_DIR` resolution from Phase 2's `LinkedOutSettings`

**Complexity:** S

---

### 11B. Session Management for Conversations vs Refinements

**Goal:** Enable the `/linkedout` skill to distinguish between new conversations and refinements of existing queries, persisting session context.

**Acceptance criteria:**
- A session file at `~/linkedout-data/queries/.active_session.json` tracks the current active session: `session_id`, `initial_query`, `started_at`, `last_query_at`, `turn_count`
- New conversation: skill starts fresh session (new `session_id`). Triggered when user explicitly says "new search" or when idle time exceeds 30 minutes (configurable via `LINKEDOUT_SESSION_TIMEOUT_MINUTES`, default 30)
- Refinement: skill continues existing session (same `session_id`, increments `turn_count`, sets `is_refinement=true` on the query log entry). Triggered when user's query clearly refines the prior query (e.g., "filter those by Series B", "show me only in SF")
- Session detection logic lives in the skill template, NOT in the Python module — the skill decides whether to start a new session or continue. The Python module just records what it's told.
- `log_query()` accepts an optional `session_id` parameter. If omitted, creates a new session.

**File targets:**
- `backend/src/linkedout/query_history/session_manager.py` — new file, manages `.active_session.json`
- Updates to `backend/src/linkedout/query_history/query_logger.py` — `session_id` parameter

**Integration points:**
- The `/linkedout` skill template (Phase 8) needs to call `session_manager.get_or_create_session()` before logging. This is a skill-side concern, documented here for the skill author.

**Complexity:** S

---

### 11C. `/linkedout-history` Skill Implementation

**Goal:** Users can browse their past network queries in reverse chronological order, with conversation grouping and drill-down.

**Acceptance criteria:**
- Skill reads JSONL files from `~/linkedout-data/queries/` directory
- Default view: last 7 days of queries, grouped by session (conversation), most recent first
- Each session shows: initial query, turn count, timestamp, total results across turns
- Drill-down: user can ask to see all turns within a specific session
- Supports date range filtering: "show me queries from last month", "queries on April 5th"
- Supports search: "find queries about Stripe", "queries mentioning AI startups"
- Output formatted as a clean table in terminal (no colors — plain text for copy-paste compatibility)
- Shows session boundaries clearly: `--- Session: "who do I know at Stripe?" (3 turns, Apr 7 14:23) ---`
- If no query history exists, shows a helpful message: "No query history found. Start querying with `/linkedout`."

**File targets:**
- `skills/claude-code/linkedout-history/SKILL.md.tmpl` — new skill template (Phase 8 template system)
- The skill reads JSONL files directly via Python inline or by invoking a thin CLI helper

**Implementation notes:**
- The skill is primarily a **reader** — it reads JSONL files and formats output. No complex backend logic needed.
- For the Claude Code host, the skill can read files directly using the Read tool and parse JSONL inline. No dedicated CLI command needed (per CLI surface decision — keep CLI to the 13 approved commands).
- The skill template should use the `agent-context.env` to locate `LINKEDOUT_DATA_DIR`.

**Integration points:**
- Reads `~/linkedout-data/queries/*.jsonl` files (written by 11A)
- Reads `~/linkedout-data/config/agent-context.env` for data dir location
- Skill distribution follows Phase 8 template system (`SKILL.md.tmpl` → per-host generation)

**Complexity:** M

---

### 11D. `/linkedout-report` Skill Implementation

**Goal:** Users get a usage summary showing query patterns, network activity, and enrichment costs.

**Acceptance criteria:**
- Skill aggregates data from multiple sources:
  - Query history: `~/linkedout-data/queries/*.jsonl` — queries per day, most queried companies/topics, busiest days
  - Metrics: `~/linkedout-data/metrics/daily/*.jsonl` — enrichment costs, embedding generation stats, import history
  - Database: direct psql queries for network stats (profile count, company count, connections by tier, embedding coverage %)
- Report sections:
  1. **Query Activity:** total queries, queries this week/month, average queries/day, most active days
  2. **Top Searches:** most frequently searched companies, people, topics (extracted from query text)
  3. **Network Stats:** total connections, connections by Dunbar tier, profiles with embeddings, companies in DB
  4. **Network Growth:** new connections added over time (from import reports in `~/linkedout-data/reports/import-csv-*.json`)
  5. **Cost Tracker:** cumulative enrichment cost (from metrics), embedding cost, total API spend
  6. **Profile Freshness:** % of profiles enriched in last 30/90/180 days (from DB), stale profiles count
- Output as clean terminal tables (plain text, no ANSI colors — copyable to Slack/GitHub)
- Supports `--json` flag equivalent (skill outputs structured JSON for programmatic use)
- If insufficient data for a section (e.g., no queries yet, no enrichment), skip the section with a note

**File targets:**
- `skills/claude-code/linkedout-report/SKILL.md.tmpl` — new skill template

**Implementation notes:**
- The skill combines file reads (JSONL parsing) with DB queries (via `agent-context.env` for DB credentials)
- For DB queries, the skill uses the Read tool to read `agent-context.env`, then constructs psql queries inline
- No dedicated CLI command — the skill IS the report generator. It uses `linkedout status --json` for quick DB stats.

**Integration points:**
- Reads `~/linkedout-data/queries/*.jsonl` (query history from 11A)
- Reads `~/linkedout-data/metrics/daily/*.jsonl` (metrics from Phase 3I)
- Reads `~/linkedout-data/reports/*.json` (operation reports from Phase 3K)
- Calls `linkedout status --json` (from Phase 6E CLI surface) for quick DB stats
- Uses `agent-context.env` for direct DB queries on network stats

**Complexity:** M

---

### 11E. `/linkedout-setup-report` Skill Implementation

**Goal:** Users and maintainers can quickly assess system health and diagnose issues.

**Acceptance criteria:**
- Skill wraps `linkedout diagnostics --json` (from Phase 3G) and presents the output in a human-friendly format
- Adds skill-specific intelligence on top of raw diagnostics:
  - **Recommendations** with priorities: "CRITICAL: 342 profiles missing embeddings — run `linkedout embed`"
  - **Health score:** simple aggregate (e.g., "System health: 92% — 1 issue found")
  - **Comparison with last report:** "Since last check (Apr 5): +47 profiles, embedding coverage up 3%"
- Persists the report to `~/linkedout-data/reports/setup-report-YYYYMMDD-HHMMSS.json`
- Two output modes:
  - **Summary (default):** One-screen overview with health score, key stats, and top recommendations
  - **Detailed:** Full diagnostic output (everything from `linkedout diagnostics`)
- If critical issues are found, prompts the user: "Found 2 critical issues. Want me to fix them?" (leverages `linkedout diagnostics --repair` under the hood)
- Output is designed to be pasted into a GitHub issue for remote debugging

**File targets:**
- `skills/claude-code/linkedout-setup-report/SKILL.md.tmpl` — new skill template

**Implementation notes:**
- This skill is primarily a **wrapper** around `linkedout diagnostics`. The value-add is the skill's intelligence: prioritization, comparison, and interactive repair.
- The skill runs `linkedout diagnostics --json`, parses the output, enhances it with recommendations and health scoring, then presents it.
- For "comparison with last report," the skill reads the most recent `setup-report-*.json` from `~/linkedout-data/reports/` and diffs key metrics.

**Integration points:**
- Calls `linkedout diagnostics --json` (Phase 3G)
- Calls `linkedout diagnostics --repair` when user approves fixes (Phase 3M auto-repair)
- Calls `linkedout status --json` (Phase 6E)
- Reads `~/linkedout-data/reports/setup-report-*.json` for historical comparison
- Uses `agent-context.env` for DB access if needed for additional queries

**Complexity:** M

---

### 11F. Report Formatting Utilities

**Goal:** Shared formatting functions for consistent report output across all three skills.

**Acceptance criteria:**
- A Python module with formatting utilities that skills can invoke:
  - `format_table(headers, rows, max_col_width=40)` — plain text table (no ANSI, no Unicode box chars — just pipes and dashes for maximum portability)
  - `format_stat_line(label, value, unit=None)` — e.g., "Profiles loaded:  4,012"
  - `format_health_badge(score)` — e.g., "[HEALTHY]", "[WARNING: 1 issue]", "[CRITICAL: 3 issues]"
  - `format_duration(ms)` — human-readable duration: "2.3s", "1m 45s", "2h 15m"
  - `format_count(n)` — locale-aware number formatting: "4,012", "52,000"
  - `format_pct(num, denom)` — percentage with denominator: "95.9% (3,691/3,847)"
  - `truncate_text(text, max_len=80)` — truncate with ellipsis
- All formatters produce plain text — no ANSI escape codes, no terminal-specific formatting
- Output is designed to be copy-pasted into GitHub issues, Slack messages, or documentation

**File targets:**
- `backend/src/linkedout/query_history/formatters.py` — new file

**Integration points:**
- Used by all three skills (11C, 11D, 11E) and potentially by future skills
- Could be used by `linkedout diagnostics` and `linkedout status` CLI commands if they want consistent formatting

**Complexity:** S

---

## Testing Strategy

### Unit Tests

| Test | What It Verifies | File |
|------|-----------------|------|
| `test_query_logger.py` | JSONL entries are correctly formatted, written to correct date-based file, thread-safe, process-safe (review finding 2026-04-07: two Claude sessions invoking `/linkedout` simultaneously is realistic — test both threading and multiprocessing concurrent writes via `fcntl.flock()`) | `backend/tests/unit/query_history/test_query_logger.py` |
| `test_session_manager.py` | Session creation, continuation, timeout-based new session, `.active_session.json` lifecycle | `backend/tests/unit/query_history/test_session_manager.py` |
| `test_formatters.py` | Table formatting, stat lines, health badges, edge cases (empty data, very long strings) | `backend/tests/unit/query_history/test_formatters.py` |

### Integration Tests

| Test | What It Verifies | File |
|------|-----------------|------|
| `test_query_history_flow.py` | Full flow: log query → read back via JSONL → verify session grouping | `backend/tests/integration/query_history/test_query_history_flow.py` |
| `test_report_data_aggregation.py` | Report skill data aggregation: reads queries + metrics + reports, produces correct summary stats | `backend/tests/integration/query_history/test_report_data_aggregation.py` |

### Skill Tests (Manual / LLM Eval)

These are not automated in CI — they require an actual AI host (Claude Code) to verify:

| Test | What It Verifies |
|------|-----------------|
| `/linkedout-history` with no data | Shows helpful empty-state message |
| `/linkedout-history` with 1 week of data | Correct reverse-chronological grouping |
| `/linkedout-history "queries about Stripe"` | Filters correctly |
| `/linkedout-report` with fresh install | Gracefully handles missing metrics/reports |
| `/linkedout-report` after active usage | All sections populated with real numbers |
| `/linkedout-setup-report` on healthy system | Health score reflects reality |
| `/linkedout-setup-report` on system with gaps | Identifies issues, offers repair |

---

## Exit Criteria Verification Checklist

- [ ] `log_query()` writes correctly formatted JSONL to `~/linkedout-data/queries/YYYY-MM-DD.jsonl`
- [ ] Query JSONL entries include all required fields: timestamp, query_id, session_id, query_text, query_type, result_count, duration_ms, model_used, is_refinement
- [ ] Session management correctly groups related queries and creates new sessions on timeout
- [ ] `/linkedout-history` displays queries in reverse chronological order, grouped by session
- [ ] `/linkedout-history` supports date range filtering and text search
- [ ] `/linkedout-history` shows helpful message when no history exists
- [ ] `/linkedout-report` aggregates query activity, network stats, cost tracking, and profile freshness
- [ ] `/linkedout-report` gracefully skips sections with insufficient data
- [ ] `/linkedout-setup-report` wraps `linkedout diagnostics` with health scoring and recommendations
- [ ] `/linkedout-setup-report` offers interactive repair for critical issues
- [ ] All report output is plain text (no ANSI) and copy-pasteable
- [ ] After a week of usage, `/linkedout-history` and `/linkedout-report` produce meaningful, accurate output
- [ ] Unit tests pass for query logger, session manager, and formatters
- [ ] Integration test verifies end-to-end query logging and readback flow

---

## Complexity Summary

| Task | Complexity | Rationale |
|------|-----------|-----------|
| 11A. Query Logging Module | S | Append-only JSONL writer with a few integrations |
| 11B. Session Management | S | File-based session tracking, simple timeout logic |
| 11C. `/linkedout-history` | M | Skill template with JSONL parsing, grouping, filtering, formatting |
| 11D. `/linkedout-report` | M | Multi-source data aggregation (files + DB), section-based report generation |
| 11E. `/linkedout-setup-report` | M | Wrapper around diagnostics with health scoring, historical comparison, interactive repair |
| 11F. Report Formatting Utilities | S | Pure formatting functions, no I/O |

---

## Open Questions

1. **Query type classification:** The `query_type` field in the JSONL entry (e.g., `company_lookup`, `person_search`, `semantic_search`) must be set by the `/linkedout` skill when it calls `log_query()`. The skill needs to classify its own queries. Should this classification be best-effort (skill guesses based on query text) or explicit (skill must tag every query with a type)? **Recommendation:** Best-effort — the skill sets it based on which DB queries/tools it used to answer. If uncertain, use `general`.

2. **History retention policy:** JSONL files accumulate over time. Should there be an automatic cleanup? **Recommendation:** No auto-cleanup in v1. JSONL is tiny (~100 bytes per query; 1000 queries/month = ~100KB/month). A year of heavy use is <2MB. Document that users can `rm ~/linkedout-data/queries/*.jsonl` to clear history.

3. **Skill template generation timing:** The three skills (11C, 11D, 11E) depend on the Phase 8 skill template system (`SKILL.md.tmpl` + host configs + `bin/generate-skills`). If Phase 8 is not complete when Phase 11 starts, the skill templates can be written as plain `SKILL.md` files first and converted to templates later. **Recommendation:** Write as plain `SKILL.md` targeting Claude Code first, templatize when Phase 8 infrastructure is ready.

4. **Report cost tracking accuracy:** The `/linkedout-report` cost tracker section depends on metrics being consistently recorded by Phase 3I and Phase 5 (embedding providers). If those phases don't record cost metrics reliably, the cost section will be empty. **Recommendation:** Skip the cost section gracefully if no cost metrics exist. Add a note: "Cost tracking requires OpenAI embedding provider."

5. **Interaction between DB-backed search sessions and file-based query history:** The existing `search_session`/`search_turn` tables are DB-backed and used by the backend API. The new query logging is file-based and used by skills. These are two separate systems that both track "queries." Should they be unified? **Recommendation:** Keep them separate. DB sessions serve the Chrome extension API. File-based logging serves the skill-first experience. Different consumers, different needs. Document this distinction in the codebase.
