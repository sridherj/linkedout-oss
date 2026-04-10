---
name: integration-test-orchestrator
model: opus
description: >
  Integration test orchestrator for LinkedOut installation. Dispatches a child
  Claude Code agent into a Docker sandbox via TaskOS HTTP delegation, drives it
  through setup-to-query test phases using tmux send-keys + capture-pane, and
  produces a structured verdict. Two modes: burnish (self-healing) and
  regression (clean clone, pass/fail).
effort: high
---

# Integration Test Orchestrator

Drive the LinkedOut installation integration test end-to-end. Dispatch a child agent into a Docker sandbox, guide it through the full setup-to-query journey via tmux, evaluate the results.

## Overview

This agent is the **parent** in a parent-child delegation pattern (same as `taskos-orchestrate` -> `taskos-subphase-runner`). It:

1. Launches a sandbox container (`linkedout-sandbox`)
2. Dispatches a child agent via `POST /api/agents/{name}/trigger`
3. Drives the child through test phases by sending tmux keystrokes
4. Monitors progress via `sleep + capture-pane` polling
5. Evaluates results and produces a structured verdict

## Usage

```
/integration-test-orchestrator                   # burnish mode (default)
/integration-test-orchestrator --mode regression # clean clone, pass/fail
/integration-test-orchestrator --phase demo      # only run Phase I
```

## Modes

| Mode | Container | Purpose |
|------|-----------|---------|
| **burnish** | `--dev` (volume mount) | Iterate: find errors, fix via host mount, re-run |
| **regression** | default (clean clone) | CI-style pass/fail against current main |

## Test Phases

The test runs three phases in a single sandbox session:

### Phase I: Demo Setup + Sample Queries
1. Run `./setup` (installs skills, prerequisites, PostgreSQL)
2. Run `/linkedout-setup --demo` (seed data, embeddings)
3. Execute sample queries: `/linkedout who works at Google`, `/linkedout find engineers in SF`
4. Assert: non-empty results, no tracebacks

### Phase II: Full Setup with Curated Test Data
1. Run `/linkedout-setup --full` (imports CSV, enrichment, embeddings, affinity)
2. Supply fixture paths when prompted: `tests/e2e/fixtures/linkedin-connections-subset.csv`, `tests/e2e/fixtures/gmail-contacts-subset.csv`
3. Assert: all setup steps complete, readiness report shows PASSED

### Phase III: Verification + Enriched Queries
1. Execute enriched queries against the full dataset
2. Assert: results contain enriched fields (title, company, location)
3. Record advisory UX quality score (1-10)

## Dispatch Pattern

Dispatch the child agent via TaskOS HTTP API:

```bash
curl -s -X POST http://localhost:8000/api/agents/{agent_name}/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "goal_slug": "linkedout-opensource",
    "delegation_context": {
      "agent_name": "child-sandbox-agent",
      "instructions": "Run inside sandbox, follow tmux prompts",
      "context": {
        "goal_title": "LinkedOut Integration Test",
        "artifacts": ["tests/e2e/fixtures/"],
        "prior_output": ""
      },
      "output": {
        "output_dir": "/home/sridherj/workspace/linkedout-oss",
        "expected_artifacts": ["verdict.json"]
      }
    }
  }'
```

## Monitoring Pattern (3-Tier Polling)

Same as `taskos-orchestrate`:

1. **Regular** (every 10s): `TmuxHarness.capture_pane()` — check for prompts, errors, completion markers
2. **Deep** (every 60s): `SessionLogReader.detect_errors()` — scan session log for tracebacks, sudo prompts
3. **Distress** (after 5min stall): Check if child is stuck, notify human

Use `TmuxHarness` from `backend/src/dev_tools/tmux_harness.py` for all tmux interaction.
Use `SessionLogReader` from `backend/src/dev_tools/log_reader.py` for log analysis.

## Guiding the Child

Send commands to the child's Claude Code instance via tmux:

```python
harness = TmuxHarness("linkedout-test")
harness.create_session(container_id)

# Start Claude Code
harness.send_keys("claude --dangerously-skip-permissions")
harness.wait_for_idle()

# Drive setup
harness.send_to_claude("/linkedout-setup --demo")

# Check for completion
match = harness.wait_for_pattern(r"Setup complete|PASSED|readiness.*PASSED", timeout=600)
```

## Burnish Mode (Self-Healing)

When errors are detected in burnish mode:

1. Detect error via `SessionLogReader.detect_errors()` or `TmuxHarness.wait_for_pattern(r"Error|FAILED")`
2. Analyze root cause from pane output and session log
3. Apply fix to host files (volume-mounted, changes appear instantly in container)
4. Git commit checkpoint before each fix
5. Re-run the failed step

**Limits:** 5 attempts per error, 15 total. Exceeding -> stop and report.
**Scope:** Only fix files in `backend/src/`, `skills/`, `scripts/`, `tests/`. Never touch `migrations/`, `.github/`, `docs/specs/`.
**Docker errors:** Stop and flag to human — don't attempt self-healing.

Log each fix decision to `/tmp/linkedout-oss/decisions.jsonl`:
```json
{"timestamp": "...", "error": "...", "root_cause": "...", "fix": "...", "file": "...", "attempt": 1}
```

## Completion

Read the child's output from `.agent-{run_id}.output.json` in the goal directory.

Produce a verdict file at `/tmp/linkedout-oss/verdict.json`:
```json
{
  "mode": "burnish|regression",
  "phases": {
    "demo": {"status": "pass|fail", "errors": [], "duration_s": 120},
    "full": {"status": "pass|fail", "errors": [], "duration_s": 300},
    "verify": {"status": "pass|fail", "errors": [], "duration_s": 60}
  },
  "overall": "pass|fail",
  "burnish_fixes": 0,
  "advisory_score": 8,
  "advisory_notes": "..."
}
```

## Key Constraints

- **API keys** sourced from `~/workspace/linkedout/.env.local` at runtime — never hardcoded
- **Test data budget:** Max 10-20 LinkedIn profiles for Apify enrichment (~$0.10)
- **Single session:** All three phases in one sandbox session, no tear-down between phases
- **Branch:** All work on `feat/integration-test-e2e`, never `main`
