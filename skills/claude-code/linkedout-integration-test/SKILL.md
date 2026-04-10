---
name: linkedout-integration-test
description: Run the LinkedOut installation integration test — drives a child Claude
  through the full setup-to-query journey inside a Docker sandbox
tools:
- Bash
- Read
---

# /linkedout-integration-test — Integration Test

Run the full LinkedOut installation integration test. Launches a Docker sandbox, drives a child Claude Code instance through setup and query phases via tmux, and produces a structured pass/fail verdict.

## Usage

```
/linkedout-integration-test                    # burnish mode, all phases
/linkedout-integration-test --mode regression  # clean clone, pass/fail
/linkedout-integration-test --phase demo       # only Phase I (demo setup)
```

## Modes

| Mode | Container | Purpose |
|------|-----------|---------|
| **burnish** (default) | `--dev` (volume mount) | Iterate: find errors, fix via host mount, re-run |
| **regression** | default (clean clone) | CI-style pass/fail against current main |

## Test Phases

The test runs three phases in a single sandbox session:

### Phase I: Demo Setup + Sample Queries
1. Run `./setup` (install skills, prerequisites, PostgreSQL)
2. Start Claude Code inside the container
3. Run `/linkedout-setup` and select **Quick start** (demo path)
4. Execute sample queries (`who do I know at Google`, `find engineers in SF`)
5. Assert: non-empty results with structured output

### Phase II: Full Setup with Curated Test Data
1. Re-run `/linkedout-setup` and select **Full setup**
2. Provide inputs when prompted: profile URL, API keys, LinkedIn CSV, Gmail contacts
3. Wait for enrichment, embeddings, and affinity scoring to complete
4. Verify readiness check passes

### Phase III: Verification + Enriched Queries
1. Verify database has embeddings and affinity scores via SQL
2. Run enriched queries against the full dataset
3. Assert: results contain enriched fields (title, company, affinity)
4. Advisory quality evaluation (commentary, not a gate)

## Running

Activate the backend virtual environment and run:

```bash
cd $(git rev-parse --show-toplevel)/backend && source .venv/bin/activate && linkedout-integration-test
```

Or with options:

```bash
linkedout-integration-test --mode regression --phase all
```

## Prerequisites

- Docker with buildx installed
- Claude Code credentials baked into sandbox image (`~/.claude/.credentials.json`)
- API keys at `~/workspace/linkedout/.env.local` (for full setup)
- Test fixtures at `tests/e2e/fixtures/` (linkedin-connections-subset.csv, gmail-contacts-subset.csv)

## Output

- **State file:** `/tmp/linkedout-oss/test-state.json` (progress tracking, resume support)
- **Verdict:** `/tmp/linkedout-oss/verdict.json` (structured pass/fail per phase)
- **Session logs:** `/tmp/linkedout-oss/session-*.log` (full terminal output)

## Architecture

Uses the integration-test-orchestrator agent pattern (`.claude/agents/integration-test-orchestrator.md`):
- **TmuxHarness** (`backend/src/dev_tools/tmux_harness.py`) — send keystrokes, capture pane output, detect idle
- **SessionLogReader** (`backend/src/dev_tools/log_reader.py`) — tail session logs, detect errors
- **TestState** — dataclass persisted to JSON for resume-from-failure
- **TestVerdict** — final output with per-phase status, error list, burnish fix count

## Constraints

- API keys are never hardcoded or committed — sourced from env file at runtime
- Test data budget: max 10-20 LinkedIn profiles for enrichment (~$0.10)
- All three phases run in one sandbox session, no tear-down between phases
- All work on `feat/integration-test-e2e` branch, never `main`
