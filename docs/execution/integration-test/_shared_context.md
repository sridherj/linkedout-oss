# Integration Test for Installation — Shared Context

**Project:** LinkedOut OSS
**Phase:** Integration Test for Installation
**Phase Plan:** `docs/plan/integration-test-installation.md`
**Requirements:** `.taskos/integration_test_refined_requirements.collab.md`
**Plan Review:** `.taskos/docs/plan-review-integration-test.md`
**Date:** 2026-04-10

---

## Goal

A parent Claude Code instance (integration-orchestrator) dispatches a child agent via TaskOS HTTP delegation, then drives it through the complete LinkedOut setup-to-query journey inside a Docker sandbox (Ubuntu 24.04). Two modes: **burnish** (self-healing iteration via volume mount) and **regression** (clean GitHub clone, pass/fail verdict). The parent uses `sleep + tmux capture-pane` to read the child's terminal and guide it — the same proven pattern as `taskos-orchestrate` -> `taskos-subphase-runner`. Invoked via the `/linkedout-integration-test` Claude Code skill.

---

## Decisions from Plan Review (2026-04-10)

| # | Question | Decision |
|---|----------|----------|
| 1 | **Orchestration model** | TaskOS delegation pattern. Integration-orchestrator dispatches child via HTTP (`/api/agents/{name}/trigger`), monitors via `sleep + capture-pane`. Same pattern as `taskos-orchestrate`. |
| 2 | **Self-healing limits** | 5 attempts per error, 15 total. File scope: `backend/src/`, `skills/`, `scripts/`, `tests/`. Never: `migrations/`, `.github/`, `docs/specs/`. Git commit checkpoint before each fix. |
| 3 | **Test data strategy** | Pre-curated, version-controlled in `tests/e2e/fixtures/`. Reproducible across runs. |
| 4 | **Assertion criteria** | Structural assertions (non-null fields, min 1 result, enriched fields) as hard gate. Qualitative LLM evaluation (1-10 score) as advisory commentary for prompt improvements. |
| 5 | **Invocation mechanism** | Claude Code skill: `/linkedout-integration-test`. |

---

## Existing Infrastructure

| Component | Status | Location |
|-----------|--------|----------|
| `Dockerfile.sandbox` | Exists | `/linkedout-oss/Dockerfile.sandbox` |
| `sandbox.py` CLI | Exists | `backend/src/dev_tools/sandbox.py` — builds image, runs container, wraps with `script(1)` for session logging |
| `linkedout setup --demo` | Exists | Full 14-step orchestrator with demo/full paths, state tracking, idempotent re-runs |
| `linkedout setup --full` | Exists | Steps 5-14: API keys, profile, CSV import, contacts, seed, embeddings, affinity, skills, readiness, auto-repair |
| `/linkedout-setup` skill | Exists | `skills/claude-code/linkedout-setup/SKILL.md` — drives setup via skill invocation |
| `setup` script | Exists | Root `./setup` — installs skills, checks prerequisites, initializes PostgreSQL |
| Session log capture | Exists | `script(1)` wrapper in `sandbox.py` logs to `/tmp/linkedout-oss/session-*.log` |
| TaskOS delegation | Exists | HTTP dispatch, file-based delegation context, output contract, 3-tier polling |
| tmux | Available | tmux 3.5a on host |

---

## What Needs to Be Built

| Sub-Phase | Scope | Effort |
|-----------|-------|--------|
| A: Sandbox Infrastructure | Modify `sandbox.py` and `Dockerfile.sandbox` for headless Claude + dev mode | Small (~50 lines) |
| B: Orchestration Layer | tmux harness, session log reader, orchestrator agent definition | Medium (~300 lines) |
| C: Test Data Curation | Curated LinkedIn + Gmail subsets as version-controlled fixtures | Small (~150 lines + 2 CSVs) |
| D: Parent Harness | Skill definition, 3-phase flow (demo, full, verify), state machine | Large (~500 lines) |
| E: Evaluation & Verdict | Verdict data structures, hard gate + advisory scoring, output | Medium (~200 lines) |
| F: Burnish Mode | Error detection, self-healing loop, decision logging | Medium (~200 lines) |

---

## Architecture Overview

```
/linkedout-integration-test skill (invocation)
  |
  v
Integration-Orchestrator (parent agent)
  |
  +-- Dispatches child via POST /api/agents/{name}/trigger
  |
  +-- Launches sandbox container (Docker)
  |     +-- Burnish mode: --dev (volume mount, instant edits)
  |     +-- Regression mode: default (clean GitHub clone)
  |
  +-- tmux session management
  |     +-- send_keys() -> drive child Claude
  |     +-- capture_pane() -> read child output
  |     +-- wait_for_idle() -> detect processing complete
  |
  +-- 3-Phase Test Flow
  |     +-- Phase I: Demo setup + sample queries
  |     +-- Phase II: Full setup with curated test data
  |     +-- Phase III: Verification + enriched queries
  |
  +-- Evaluation
  |     +-- Structural assertions (hard gate)
  |     +-- UX quality rating (advisory)
  |
  +-- Burnish Mode (if errors)
        +-- Root cause analysis
        +-- Fix via volume mount
        +-- Decision log (JSONL)
        +-- Bounded: 5/error, 15 total
```

---

## File Inventory (All New/Modified Files)

| File | Action | Sub-phase |
|------|--------|-----------|
| `Dockerfile.sandbox` | **Modify** — add `settings.json` bake-in | A |
| `backend/src/dev_tools/sandbox.py` | **Modify** — add `--dev`, `--detach` flags, log volume mount | A |
| `backend/src/dev_tools/tmux_harness.py` | **New** — tmux session management | B |
| `backend/src/dev_tools/log_reader.py` | **New** — session log reader with error detection | B |
| `backend/src/dev_tools/curate_test_data.py` | **New** — one-time curation script | C |
| `tests/e2e/fixtures/linkedin-connections-subset.csv` | **New** — curated 10-20 row subset | C |
| `tests/e2e/fixtures/gmail-contacts-subset.csv` | **New** — curated 10-15 row subset | C |
| `skills/claude-code/linkedout-integration-test/SKILL.md` | **New** — skill definition | D |
| `backend/src/dev_tools/integration_test.py` | **New** — main harness: 3-phase flow, state machine | D |
| `backend/src/dev_tools/verdict.py` | **New** — verdict data structures and rendering | E |

---

## Execution Order and Dependencies

```
SP-A (sandbox infra) ───────────────────── [A1-A4 all independent, parallel]
        |
        v
SP-B (tmux + log reader) ──┐
SP-C (test data curation) ──┤── Can run in parallel after A
        |                    |
        v                    v
SP-D (parent harness) ──────────────────── Depends on B + C
        |
        v
SP-E (evaluation + verdict) ────────────── Depends on D
        |
        v
SP-F (burnish mode) ────────────────────── Depends on D (E can start in parallel)
```

**Recommended implementation order:**
1. **SP-A:** Sandbox infra (small, contained changes to existing files)
2. **SP-B + SP-C** (in parallel): Orchestration utilities + test data
3. **SP-D:** Parent harness (the big piece, depends on B + C)
4. **SP-E + SP-F** (in parallel): Evaluation and burnish mode

---

## Key Decision Documents

| Decision Doc | Constraint |
|---|---|
| `docs/plan/integration-test-installation.md` | Full plan with all sub-phase details |
| `.taskos/integration_test_refined_requirements.collab.md` | Refined requirements with all scenarios |
| `.taskos/docs/plan-review-integration-test.md` | Plan review — 5 blocking questions resolved |
| `docs/decision/2026-03-28-orchestration-dispatch-pattern.md` | 3-tier polling, stuck detection for TaskOS delegation |

---

## Key Constraints

- **Branch:** All work on `feat/integration-test-e2e` branch, never directly on `main`
- **API keys:** Sourced from `./.env.local` at runtime — never hardcoded or committed
- **Test data budget:** Max 10-20 LinkedIn profiles for Apify enrichment (~$0.10)
- **Single session:** All three phases run in one sandbox session, no tear-down between phases
- **Decision log:** All burnish-mode fix decisions recorded per-decision in JSONL, not batched into summaries
- **Self-healing scope:** Only `backend/src/`, `skills/`, `scripts/`, `tests/`. Never `migrations/`, `.github/`, `docs/specs/`
- **Self-healing limits:** 5 attempts per error, 15 total. Git checkpoint before each fix.
- **Docker infra errors:** Stop and flag to SJ — don't attempt self-healing

---

## Key File Paths

| File | Purpose |
|------|---------|
| `Dockerfile.sandbox` | Sandbox container definition |
| `backend/src/dev_tools/sandbox.py` | Sandbox CLI (`linkedout-sandbox`) |
| `skills/claude-code/linkedout-setup/SKILL.md` | Setup skill (already exists, used by test) |
| `./.env.local` | API keys (Apify, OpenAI) |
| `<prior-project>/data/linkedin_connections.csv` | Source LinkedIn data (~24,800 rows) |
| `/tmp/linkedout-oss/` | Session logs, verdict output, decision logs |

---

## Codebase Conventions

- **CLI:** Click commands in `backend/src/dev_tools/`. Namespace: `linkedout`.
- **Config:** pydantic-settings via `backend/src/shared/config/config.py`
- **Logging:** loguru via `get_logger()`
- **DB sessions:** `db_session_manager.get_session(DbSessionType.READ|WRITE, app_user_id=...)`
- **System user:** `SYSTEM_USER_ID` from `dev_tools.db.fixed_data` for CLI operations
- **Testing:** pytest. Unit tests mock external APIs. Integration tests use real DB.
- **Dependency management:** `uv` with `requirements.txt`
