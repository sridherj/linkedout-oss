# SP-D: Parent Harness (3-Phase Flow)

**Phase:** Integration Test for Installation
**Plan tasks:** D1 (skill definition), D2 (Phase I demo), D3 (Phase II full), D4 (Phase III verify), D5 (state machine)
**Dependencies:** SP-B (tmux harness + log reader), SP-C (test data fixtures)
**Blocks:** SP-E (evaluation), SP-F (burnish mode)
**Can run in parallel with:** —

## Objective

Build the main orchestration logic that drives the full E2E test. This is the largest sub-phase — it creates the `/linkedout-integration-test` skill, the state machine for flow control, and the 3-phase test sequence (demo, full setup, verification). It composes the tmux harness (SP-B) and test data (SP-C) to drive the child Claude through the entire setup-to-query journey.

## Context

- Read shared context: `docs/execution/integration-test/_shared_context.md`
- Read plan (Sub-phase D section): `docs/plan/integration-test-installation.md`
- Read requirements (Scenarios 1-5): `.taskos/integration_test_refined_requirements.collab.md`
- Read tmux harness: `backend/src/dev_tools/tmux_harness.py` (created in SP-B)
- Read log reader: `backend/src/dev_tools/log_reader.py` (created in SP-B)
- Read existing setup skill: `skills/claude-code/linkedout-setup/SKILL.md`
- Read existing sandbox CLI: `backend/src/dev_tools/sandbox.py` (modified in SP-A)

## Deliverables

### D1. `/linkedout-integration-test` skill

**File to create:** `skills/claude-code/linkedout-integration-test/SKILL.md`

The skill is the invocation mechanism. When a user runs `/linkedout-integration-test`, it:
1. Accepts mode argument: `burnish` (default) or `regression`
2. Accepts phase argument: `all` (default), `demo`, `full`, or `verify`
3. Launches the integration-orchestrator
4. Drives the 3-phase flow
5. Produces the verdict

The skill should reference the orchestrator agent definition (`.claude/agents/integration-test-orchestrator.md` from SP-B) and explain the test flow at a high level. Follow the existing skill format from `skills/claude-code/linkedout-setup/SKILL.md`.

### D2. Phase I — Demo flow

The first test phase. Runs the demo setup and verifies basic queries work.

**Sequence:**
1. **Launch sandbox** via tmux harness
   - `TmuxHarness.create_session(container_id)`
   - Wait for shell prompt inside container

2. **Run `./setup`** (prerequisite script)
   - `harness.send_keys("cd /linkedout-oss && ./setup")`
   - `harness.wait_for_idle(idle_seconds=15, timeout=600)` — setup takes time
   - If error detected (via log reader) -> enter burnish loop or fail

3. **Start Claude Code**
   - `harness.send_keys("claude")`
   - `harness.wait_for_pattern(">")`  — wait for Claude prompt

4. **Send `/linkedout-setup`**
   - `harness.send_to_claude("/linkedout-setup")`
   - Wait for demo/full question

5. **Select demo path**
   - `harness.send_to_claude("Quick start")`
   - `harness.wait_for_idle(idle_seconds=30, timeout=900)` — demo setup takes time

6. **Run sample queries with structural assertions**
   - `harness.send_to_claude("who do I know at Google")`
   - Assert: at least 1 result, each with non-null `name`, `company`, `title`
   - `harness.send_to_claude("find engineers in SF")`
   - Assert: same structural checks
   - Parse query output from `harness.capture_pane()`

7. **Log Phase I result** — update `TestState`

### D3. Phase II — Full setup with own data

**Sequence:**
1. **Trigger full setup** (within same Claude session)
   - `harness.send_to_claude("/linkedout-setup")`
   - The skill detects demo mode is active and offers transition

2. **Provide inputs when prompted** — the parent sends responses to Claude's prompts:
   - Self-profile URL: `https://www.linkedin.com/in/sridher-jeyachandran/`
   - API keys: read from `./.env.local`
   - LinkedIn CSV: path to `tests/e2e/fixtures/linkedin-connections-subset.csv` (mounted via `--dev`)
   - Gmail contacts: path to `tests/e2e/fixtures/gmail-contacts-subset.csv`

3. **Wait for enrichment + embedding + affinity**
   - Monitor progress via session log reader
   - Budget: 10-20 profiles x ~$0.005/profile = ~$0.10 Apify cost
   - `harness.wait_for_idle(idle_seconds=30, timeout=1800)` — enrichment can take minutes

4. **Wait for readiness check**
   - Verify readiness report shows zero gaps
   - `harness.wait_for_pattern("readiness")` or similar completion marker

5. **Log Phase II result** — update `TestState`

### D4. Phase III — Verification + queries

**Sequence:**
1. **Database verification** (structural assertions)
   - Send SQL queries via Claude to verify:
   - Embeddings: `SELECT count(*) FROM crawled_profile WHERE embedding IS NOT NULL` -> > 0
   - Affinity: `SELECT count(*) FROM affinity_score` -> > 0

2. **Run queries with structural + qualitative assertions**
   - Query by company from test data -> assert results have non-null `name`, `company`, `title`, `affinity_score`
   - Query by role -> same structural checks
   - Query by enriched field -> assert enriched fields populated

3. **Qualitative LLM evaluation (advisory)**
   - The parent Claude reviews query output quality
   - Checks: information density, formatting, clarity, suggested follow-ups
   - If format is poor -> feed back as prompt improvement suggestion
   - This produces advisory commentary, NOT a pass/fail gate

4. **Log Phase III result** — update `TestState`

### D5. State machine and main harness

**File to create:** `backend/src/dev_tools/integration_test.py`

This is the main harness module that ties everything together. Contains:

**State tracking:**
```python
@dataclass
class TestState:
    phase: str = "not_started"  # not_started, demo, full, verify, complete
    phase_i_passed: bool = False
    phase_ii_passed: bool = False
    phase_iii_passed: bool = False
    errors: list[dict] = field(default_factory=list)
    burnish_fixes: list[dict] = field(default_factory=list)
```

State persisted to `/tmp/linkedout-oss/test-state.json` for resume-from-failure.

**Main entry point:**
```python
def run_integration_test(mode: str = "burnish", phase: str = "all") -> TestVerdict:
    """Run the integration test.

    Args:
        mode: "burnish" (self-healing) or "regression" (clean clone)
        phase: "all", "demo", "full", or "verify"

    Returns:
        TestVerdict with pass/fail per phase and UX quality score.
    """
```

**Key responsibilities:**
- Launch sandbox container (via `sandbox.py --detach`, with `--dev` if burnish mode)
- Create tmux session and exec into container
- Drive the 3-phase flow (D2, D3, D4)
- On error: delegate to burnish loop (SP-F) or fail
- On completion: produce verdict (SP-E)
- Persist state for resume
- Clean up: kill tmux session, optionally stop container

**Branch handling:**
- Before starting, create/checkout `feat/integration-test-e2e` branch
- Burnish mode: volume mount uses current branch (whatever is checked out)
- Regression mode: Dockerfile must be updated to clone from `feat/integration-test-e2e` during development

## Verification

1. **D1:** `skills/claude-code/linkedout-integration-test/SKILL.md` exists and follows skill format
2. **D5:** `backend/src/dev_tools/integration_test.py` exists with `run_integration_test()` entry point
3. **State machine:** `TestState` can be serialized to and deserialized from JSON
4. **Phase I smoke test:** Running in burnish mode, Phase I (demo) completes and produces a pass/fail result
5. **Full run:** All three phases complete and produce a `TestVerdict`

## Notes

- This is the largest sub-phase. It may benefit from being split into implementation sessions: D1+D5 first (skill + skeleton), then D2 (Phase I), then D3+D4 (Phase II + III).
- The harness must handle the child Claude's interactive prompts. Study `skills/claude-code/linkedout-setup/SKILL.md` to understand what prompts the setup flow asks and in what order.
- Structural assertions are defined in the plan's E2 section. They are the hard gate — the harness must check them.
- The qualitative LLM evaluation is advisory — it produces commentary and suggestions, not a pass/fail. This is implemented in SP-E but called from here.
- Parsing query results from `capture_pane()` output is non-trivial. The output is whatever Claude formats. Use heuristics: look for table-like formatting, extract rows, check for required fields.
- API keys must NEVER be logged, committed, or written to any file except in-memory use during the test.
