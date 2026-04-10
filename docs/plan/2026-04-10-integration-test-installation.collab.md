# Integration Test for Installation — Detailed Execution Plan

**Version:** 1.1
**Date:** 2026-04-10
**Status:** Plan review complete — all blocking questions resolved
**Task:** Create a Claude-driven sandbox E2E integration test
**Requirement source:** `integration_test_refined_requirements.collab.md`
**Output directory:** `.`

---

## Summary

A parent Claude Code instance (integration-orchestrator, modeled after `/taskos-orchestrate`) dispatches a child agent via TaskOS HTTP delegation, then drives it through the complete LinkedOut setup-to-query journey inside a Docker sandbox (Ubuntu 24.04). Two modes: **burnish** (self-healing iteration via volume mount) and **regression** (clean GitHub clone, pass/fail verdict). The parent uses `sleep + tmux capture-pane` to read the child's terminal and guide it — the same proven pattern as `taskos-orchestrate` → `taskos-subphase-runner`. Invoked via the `/linkedout-integration-test` Claude Code skill.

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

## Existing Infrastructure (What We Have)

| Component | Status | Location |
|-----------|--------|----------|
| `Dockerfile.sandbox` | ✅ Exists | `/linkedout-oss/Dockerfile.sandbox` |
| `sandbox.py` CLI | ✅ Exists | `backend/src/dev_tools/sandbox.py` — builds image, runs container, wraps with `script(1)` for session logging |
| `linkedout setup --demo` | ✅ Exists | Full 14-step orchestrator with demo/full paths, state tracking, idempotent re-runs |
| `linkedout setup --full` | ✅ Exists | Steps 5-14: API keys, profile, CSV import, contacts, seed, embeddings, affinity, skills, readiness, auto-repair |
| `/linkedout-setup` skill | ✅ Exists | `skills/claude-code/linkedout-setup/SKILL.md` — drives setup via skill invocation |
| `setup` script | ✅ Exists | Root `./setup` — installs skills, checks prerequisites, initializes PostgreSQL |
| Session log capture | ✅ Exists | `script(1)` wrapper in `sandbox.py` logs to `/tmp/linkedout-oss/session-*.log` |
| TaskOS delegation | ✅ Exists | HTTP dispatch, file-based delegation context, output contract, 3-tier polling |
| tmux | ✅ Available | tmux 3.5a on host |
| `settings.json` bake-in | ❌ Missing | Dockerfile doesn't configure `/root/.claude/settings.json` for headless mode |
| `--dev` mode | ❌ Missing | `sandbox.py` has no `--dev` flag for volume mounting |
| Test data fixtures | ❌ Missing | No curated subset of LinkedIn connections CSV or Gmail contacts |
| `/linkedout-integration-test` skill | ❌ Missing | No skill to invoke the test |
| Evaluation/verdict | ❌ Missing | No structured verdict or quality rating framework |
| Decision log framework | ❌ Missing | No structured file for recording burnish-mode fix decisions |

---

## What Needs to Be Built

### Sub-phase A: Sandbox Infrastructure Enhancements

Modify existing `sandbox.py` and `Dockerfile.sandbox` to support headless Claude Code and dev-mode volume mounting.

### Sub-phase B: Orchestration Layer

Build the integration-orchestrator using the TaskOS delegation pattern — dispatch child, `sleep + capture-pane` to monitor and guide, file-based completion detection.

### Sub-phase C: Test Data Curation

Select and prepare curated subsets of LinkedIn connections and Gmail contacts as version-controlled fixtures.

### Sub-phase D: Parent Harness (3-Phase Flow)

The main test driver that orchestrates Phase I (demo), Phase II (full with own data), and Phase III (verification + queries).

### Sub-phase E: Evaluation & Verdict

Log analysis, structural pass/fail per phase, advisory UX quality rating.

### Sub-phase F: Burnish Mode (Self-Healing Loop)

Error detection, root cause analysis, fix application via volume mount, decision logging. Bounded: 5 per error, 15 total.

---

## Sub-phase A: Sandbox Infrastructure Enhancements

**Goal:** Make the sandbox container work headlessly with Claude Code, and support dev-mode volume mounting.

### A1. Bake `settings.json` into Dockerfile

**File:** `Dockerfile.sandbox`

After the Claude credentials block, add:

```dockerfile
# ── Claude Code headless config ─────────────────────────────────
RUN mkdir -p /root/.claude && \
    echo '{ \
      "skipDangerousModePermissionPrompt": true, \
      "effortLevel": "medium", \
      "permissions": { \
        "allow": ["Bash(*)", "Read", "Edit", "Write", "Glob", "Grep"], \
        "defaultMode": "bypassPermissions" \
      } \
    }' > /root/.claude/settings.json
```

**Verify:** `docker run --rm linkedout-sandbox cat /root/.claude/settings.json` shows the expected config.

### A2. Add `--dev` flag to `sandbox.py`

**File:** `backend/src/dev_tools/sandbox.py`

Add a `--dev` click option that:
1. Adds `-v $(pwd):/linkedout-oss` to the `docker run` command (volume-mounts local repo into the container)
2. Skips the `git clone` step in the container (the mount overlays `/linkedout-oss`)

Implementation:
- Add `@click.option('--dev', is_flag=True, help='Volume-mount local repo for live editing.')` to the `sandbox` command
- In the run section, if `--dev`:
  ```python
  docker_cmd = f'docker run -it --rm -v {REPO_ROOT}:/linkedout-oss {IMAGE_NAME}'
  ```
- Log a message: `"Dev mode: local repo mounted at /linkedout-oss (changes appear instantly)"`

**Verify:** `linkedout-sandbox --dev` → inside container, `ls /linkedout-oss/setup` shows host file, modify a file on host → visible inside container.

### A3. Add `--detach` flag to `sandbox.py`

**File:** `backend/src/dev_tools/sandbox.py`

Add `--detach` flag that returns the container ID instead of exec'ing into it:

```python
@click.option('--detach', is_flag=True, help='Start container detached, print container ID.')
```

When `--detach`:
```python
docker_cmd_list = ['docker', 'run', '-d', '--rm', IMAGE_NAME, 'sleep', 'infinity']
# (with -v flag if --dev)
result = subprocess.run(docker_cmd_list, capture_output=True, text=True, check=True)
container_id = result.stdout.strip()
click.echo(container_id)
```

The parent harness will then `docker exec -it <id> bash` inside a tmux pane.

**Verify:** `linkedout-sandbox --detach` prints a container ID. `docker exec -it <id> bash` drops into the container.

### A4. Session log volume mount

**File:** `backend/src/dev_tools/sandbox.py`

Always mount `/tmp/linkedout-oss` for session log access from the host:

```python
'-v', '/tmp/linkedout-oss:/tmp/linkedout-oss'
```

This allows the parent harness to read session logs even when the container is running detached.

**Verify:** Session logs written inside the container appear at `/tmp/linkedout-oss/` on the host.

---

## Sub-phase B: Orchestration Layer

**Goal:** Integration-orchestrator using the TaskOS delegation pattern. Dispatches child via HTTP, monitors via `sleep + capture-pane`, guides via tmux send-keys.

### B1. Integration-orchestrator agent definition

**File:** `.claude/agents/integration-test-orchestrator.md` (new) or skill definition

The orchestrator is modeled after `/taskos-orchestrate`:
1. Dispatches child agent via `POST /api/agents/{name}/trigger` with delegation context containing:
   - Test mode (burnish/regression)
   - Test data fixture paths
   - API key references
   - Phase to run (all/demo/full/verify)
2. Monitors child via `sleep + capture-pane` (same 3-tier polling as taskos-orchestrate)
3. Guides child through test phases by sending tmux keystrokes to the child's session
4. Reads completion from `.agent-{run_id}.output.json`

### B2. tmux interaction module

**File:** `backend/src/dev_tools/tmux_harness.py` (new)

Class `TmuxHarness`:

```python
class TmuxHarness:
    """Manages tmux interaction with the sandbox, using the same
    sleep + capture-pane pattern as taskos-orchestrate."""

    def __init__(self, session_name: str = "linkedout-test"):
        self.session_name = session_name

    def send_keys(self, keys: str, enter: bool = True) -> None:
        """Send keystrokes to the active pane."""

    def capture_pane(self, lines: int = 200) -> str:
        """Capture the last N lines of pane output."""

    def wait_for_idle(self, idle_seconds: int = 10, timeout: int = 600) -> bool:
        """Wait until pane output stops changing (Claude finished processing).
        Same pattern as taskos-orchestrate's content hash comparison."""

    def wait_for_pattern(self, pattern: str, timeout: int = 300, poll_interval: int = 5) -> str | None:
        """Poll pane output until regex pattern appears or timeout."""
```

Key design decisions:
- **Poll-based** — `sleep + capture-pane` every N seconds (same as taskos-orchestrate)
- **Idle detection** = capture pane hash at time T, compare at T+N. Identical = idle.
- **Stall detection** = no change for 120s (setup steps) or 60s (queries)

### B3. Session log reader

**File:** `backend/src/dev_tools/log_reader.py` (new)

```python
class SessionLogReader:
    """Reads and tails session logs from /tmp/linkedout-oss/."""

    def latest_log(self) -> Path | None:
    def read_new_lines(self) -> str:
    def search(self, pattern: str) -> list[str]:
    def detect_errors(self) -> list[dict]:
        # Patterns: tracebacks, sudo prompts, FAILED, stalls
```

---

## Sub-phase C: Test Data Curation

**Goal:** Prepare curated, reproducible test data subsets for Phase II (full setup). Pre-curated and version-controlled.

### C1. LinkedIn connections subset

**Source:** `<prior-project>/data/linkedin_connections.csv` (~24,800 rows)
**Output:** `tests/e2e/fixtures/linkedin-connections-subset.csv` (10-20 rows)

Selection criteria for coverage:
1. **Company diversity:** 8-10 different companies (mix of FAANG, startups, mid-size)
2. **Role diversity:** Engineering, product, leadership, other
3. **Location diversity:** Different geographies
4. **Temporal diversity:** Recent and older connections
5. **Name diversity:** Varied first/last names to exercise parsing

One-time curation script at `backend/src/dev_tools/curate_test_data.py`. Output goes to `tests/e2e/fixtures/` and is version-controlled in the repo.

### C2. Gmail contacts subset

**Source files:**
- `<prior-project>/agents/taskos-linkedin-ai/gmail_contacts/contacts_from_google_job.csv`
- `<prior-project>/agents/taskos-linkedin-ai/gmail_contacts/contacts_with_phone.csv`
- `<prior-project>/agents/taskos-linkedin-ai/gmail_contacts/gmail_contacts_email_id_only.csv`

**Output:** `tests/e2e/fixtures/gmail-contacts-subset.csv` (10-15 rows)

Selection criteria:
1. **Some match** LinkedIn connections subset (same name/company) → tests affinity overlap
2. **Some don't match** → tests no-match handling
3. **Mix of data completeness:** Some with phone, some email-only

### C3. API key sourcing

**Source:** `./.env.local`
**Mechanism:** The parent harness reads this file at runtime, never copies or commits keys.

---

## Sub-phase D: Parent Harness (3-Phase Flow)

**Goal:** The main orchestration logic that drives the full E2E test.

### D1. `/linkedout-integration-test` skill

**File:** `skills/claude-code/linkedout-integration-test/SKILL.md` (new)

The skill is the invocation mechanism. It:
1. Accepts mode (burnish/regression) and phase (all/demo/full/verify)
2. Launches the integration-orchestrator
3. Drives the 3-phase flow
4. Produces the verdict

### D2. Phase I — Demo flow

**Sequence:**

1. **Launch sandbox** via tmux harness
   - `TmuxHarness.create_session()`
   - Launch sandbox container (dev mode in burnish, default in regression)
   - Wait for sandbox banner

2. **Run `./setup`** (prerequisite script)
   - `send_keys("./setup")`
   - Wait for completion or error
   - If error → burnish loop (Sub-phase F) or fail

3. **Start Claude Code**
   - `send_keys("claude")`
   - Wait for Claude prompt

4. **Send `/linkedout-setup`**
   - `send_to_claude("/linkedout-setup")`
   - Wait for demo/full question

5. **Select demo path**
   - `send_to_claude("Quick start")`
   - Wait for setup completion (readiness check output)

6. **Run sample queries with structural assertions**
   - `send_to_claude("who do I know at Google")`
   - Assert: at least 1 result, each with non-null `name`, `company`, `title`
   - `send_to_claude("find engineers in SF")`
   - Assert: same structural checks

7. **Log Phase I result**

### D3. Phase II — Full setup with own data

**Sequence:**

1. **Trigger full setup** (within same Claude session)
   - `send_to_claude("/linkedout-setup")`
   - The skill detects demo mode is active and offers transition

2. **Provide inputs when prompted**
   - Self-profile URL: `https://www.linkedin.com/in/sridher-jeyachandran/`
   - API keys from `./.env.local`
   - LinkedIn CSV: fixture from `tests/e2e/fixtures/linkedin-connections-subset.csv` (mounted into container)
   - Gmail contacts: fixture from `tests/e2e/fixtures/gmail-contacts-subset.csv`

3. **Wait for enrichment + embedding + affinity**
   - Monitor progress via session log
   - Budget: 10-20 profiles × ~$0.005/profile = ~$0.10 Apify cost

4. **Wait for readiness check**
   - Verify readiness report shows zero gaps

5. **Log Phase II result**

### D4. Phase III — Verification + queries

**Sequence:**

1. **Database verification** (structural assertions)
   - Embeddings: `SELECT count(*) FROM crawled_profile WHERE embedding IS NOT NULL` → > 0
   - Affinity: `SELECT count(*) FROM affinity_score` → > 0

2. **Run queries with structural + qualitative assertions**
   - Query by company from test data → assert results have non-null `name`, `company`, `title`, `affinity_score`
   - Query by role → same structural checks
   - Query by enriched field → assert enriched fields populated

3. **Qualitative LLM evaluation (advisory)**
   - Parent Claude reviews query output quality
   - Checks: information density, formatting, clarity, suggested follow-ups
   - If format is poor → feed back as prompt improvement suggestion

4. **Log Phase III result**

### D5. State machine for flow control

The harness tracks state to enable resume-from-failure:

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

State persisted to `/tmp/linkedout-oss/test-state.json` for resume.

---

## Sub-phase E: Evaluation & Verdict

**Goal:** Analyze the full session and produce a structured verdict.

### E1. Verdict data structure

```python
@dataclass
class PhaseVerdict:
    phase: str  # "I", "II", "III"
    passed: bool  # based on structural assertions
    errors: list[str]
    warnings: list[str]
    duration_seconds: float

@dataclass
class UXQualityScore:
    overall: int  # 1-10 (advisory, not a gate)
    clarity: int
    information_density: int
    options_quality: int
    error_recovery: int
    polish: int
    reasoning: str
    prompt_improvements: list[str]  # specific suggestions for skill prompt changes

@dataclass
class TestVerdict:
    timestamp: str
    mode: str  # "burnish" or "regression"
    phases: list[PhaseVerdict]
    ux_quality: UXQualityScore | None  # advisory commentary
    overall_passed: bool  # based ONLY on structural assertions
    session_log_path: str
    decision_log_path: str | None  # burnish mode only
```

### E2. Hard gate (structural) vs advisory (qualitative)

**Hard gate (determines pass/fail):**
- Zero tracebacks across all phases
- Zero unexpected sudo prompts
- Zero stalls >120s (setup) or >60s (queries)
- All queries return ≥1 result
- All results have non-null `name`, `company`, `title`
- Phase II: `affinity_score` present, enriched fields populated
- Readiness report shows zero gaps

**Advisory (feeds into prompt improvements):**
- UX quality score 1-10 per dimension
- Specific prompt improvement suggestions
- "Would I be proud to ship this?" reasoning

### E3. Verdict output

Written to `/tmp/linkedout-oss/verdict-YYYYMMDD-HHMMSS.json` and printed to stdout.

---

## Sub-phase F: Burnish Mode (Self-Healing Loop)

**Goal:** When the harness detects errors, analyze root cause, fix in real codebase, and re-run. Bounded by strict limits.

### F1. Error detection

After every `send_to_claude()` call, scan for:

| Pattern | Type | Action |
|---------|------|--------|
| `Traceback (most recent call last):` | Python traceback | Enter burnish loop |
| `[sudo] password for` | Unexpected sudo prompt | Enter burnish loop |
| `Error:` / `error:` in CLI output | CLI error | Enter burnish loop |
| No output change for >120 seconds | Stall | Enter burnish loop |
| `FAILED` in readiness report | Incomplete setup | Enter burnish loop |
| Docker-related errors (daemon, network) | Infrastructure | **Stop and flag to SJ** |

### F2. Self-healing loop (bounded)

**Limits:**
- **5 fix attempts per error.** If the same error persists after 5 attempts, escalate to SJ.
- **15 total fix attempts** across the entire run. Hard stop.
- **File scope:** Only `backend/src/`, `skills/`, `scripts/`, `tests/`. Never `migrations/`, `.github/`, `docs/specs/`.
- **Git checkpoint:** Commit before each fix for rollback capability.

```python
def burnish_loop(error_context: dict, harness: TmuxHarness) -> bool:
    """Attempt to fix an error and re-run. Returns True if fixed."""
    # 1. Create git commit checkpoint
    # 2. Capture error context (session log snippet, pane output, failed step)
    # 3. Analyze root cause in LinkedOut OSS codebase
    # 4. Check file scope — if root cause is in restricted file, escalate to SJ
    # 5. Apply fix in local repo (appears instantly via volume mount)
    # 6. Record decision in JSONL log
    # 7. Re-run from failed point (or scratch if state contaminated)
```

**Ambiguity gate:** If multiple valid fix approaches exist, stop and ask SJ.

### F3. Decision log

**File:** `/tmp/linkedout-oss/burnish-decisions-YYYYMMDD-HHMMSS.jsonl`

One JSONL entry per fix decision:
```json
{
  "timestamp": "2026-04-10T12:34:56Z",
  "phase": "I",
  "step": "setup step 3 — database creation",
  "error_description": "pg_trgm extension not found",
  "root_cause": "system-setup.sh doesn't install postgresql-XX-contrib",
  "fix_applied": "Added postgresql-17-contrib to apt install list",
  "files_modified": ["scripts/system-setup.sh"],
  "rationale": "pg_trgm is required for fuzzy search; contrib package provides it",
  "attempt_number": 1,
  "git_checkpoint": "abc1234"
}
```

---

## File Inventory (All New/Modified Files)

| File | Action | Sub-phase |
|------|--------|-----------|
| `Dockerfile.sandbox` | **Modify** — add `settings.json` bake-in | A1 |
| `backend/src/dev_tools/sandbox.py` | **Modify** — add `--dev`, `--detach` flags, log volume mount | A2, A3, A4 |
| `backend/src/dev_tools/tmux_harness.py` | **New** — tmux session management, keystroke sending, output reading | B2 |
| `backend/src/dev_tools/log_reader.py` | **New** — session log reader with tail and error detection | B3 |
| `backend/src/dev_tools/curate_test_data.py` | **New** — one-time script to select test data subsets | C1, C2 |
| `tests/e2e/fixtures/linkedin-connections-subset.csv` | **New** — curated 10-20 row subset | C1 |
| `tests/e2e/fixtures/gmail-contacts-subset.csv` | **New** — curated 10-15 row subset | C2 |
| `skills/claude-code/linkedout-integration-test/SKILL.md` | **New** — skill definition | D1 |
| `backend/src/dev_tools/integration_test.py` | **New** — main harness: 3-phase flow, state machine | D2-D5 |
| `backend/src/dev_tools/verdict.py` | **New** — verdict data structures and rendering | E1 |

---

## Execution Order and Dependencies

```
A1 (settings.json) ──┐
A2 (--dev flag) ──────┤
A3 (--detach flag) ───┤── All independent, can run in parallel
A4 (log mount) ───────┘
        │
        ▼
B2 (tmux harness) ───┐
B3 (log reader) ─────┤── Can run in parallel
C1 (LinkedIn subset) ─┤
C2 (Gmail subset) ────┘
        │
        ▼
D1 (skill definition) ── depends on B2, B3, C1, C2
D2 (Phase I demo) ── depends on D1
D3 (Phase II full) ── depends on D2
D4 (Phase III verify) ── depends on D3
D5 (state machine) ── depends on D1
        │
        ▼
E1 (verdict structures) ── can start in parallel with D
        │
        ▼
F1 (error detection) ── integrated into D, depends on B2/B3
F2 (burnish loop) ── depends on F1
F3 (decision log) ── depends on F2
```

**Suggested implementation order:**
1. **First:** A1-A4 (sandbox infra) — small, contained changes to existing files
2. **Second:** B2, B3, C1, C2 (in parallel) — new utility modules + test data
3. **Third:** D1, D5, E1 — skill, state machine, verdict structures
4. **Fourth:** D2-D4 — main harness flow (the big piece)
5. **Fifth:** F1-F3 — burnish mode (can start after D2 is working)

---

## Verification Criteria

| Criterion | How to verify |
|-----------|--------------|
| Sandbox boots with headless Claude | `docker run --rm linkedout-sandbox cat /root/.claude/settings.json` returns valid config |
| `--dev` mode mounts correctly | File edited on host appears inside container without rebuild |
| tmux harness can send/receive | `send_keys("echo hello")` + `capture_pane()` returns "hello" |
| Demo flow completes | Phase I passes all structural assertions |
| Full setup completes with test data | Phase II passes, enrichment/embedding/affinity all succeed |
| Verification queries work | Phase III passes, queries return results with required fields |
| Verdict is produced | JSON file at `/tmp/linkedout-oss/verdict-*.json` with all fields populated |
| Burnish mode respects limits | After 5 failed attempts on same error, escalates instead of looping |
| Decision log records fixes | Each fix gets a JSONL entry with all required fields |

---

## Branch Strategy

All integration test work happens on a dedicated branch — **never directly on `main`**.

- **Branch name:** `feat/integration-test-e2e`
- **All sub-phases** (A through F) are implemented on this branch
- **Dockerfile.sandbox** must be updated to clone from this branch (not `main`) during development:
  ```dockerfile
  RUN git clone -b feat/integration-test-e2e https://github.com/sridherj/linkedout-oss.git /linkedout-oss
  ```
- **Burnish mode** (`--dev`) uses volume mount, so the branch name doesn't matter for dev iteration — but regression mode (clean clone) needs the correct branch
- After all burnish/polish iterations are clean, SJ reviews the branch diff and decides what to merge to `main`
- The branch may accumulate many commits during burnish iterations — squash or organize before merge

---

## Estimated Scope

| Sub-phase | New lines (est.) | Effort |
|-----------|------------------|--------|
| A: Sandbox infra | ~50 lines modified | Small |
| B: Orchestration layer | ~300 lines new | Medium |
| C: Test data curation | ~150 lines new + 2 CSV files | Small |
| D: Parent harness + skill | ~500 lines new | Large |
| E: Evaluation | ~200 lines new | Medium |
| F: Burnish mode | ~200 lines new | Medium |
| **Total** | **~1,400 lines** | |

This is a developer tool, not user-facing code. Functional but doesn't need the same polish level as the setup flow itself.
