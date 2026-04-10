# SP-B: Orchestration Layer (tmux Harness + Log Reader)

**Phase:** Integration Test for Installation
**Plan tasks:** B1 (orchestrator agent definition), B2 (tmux harness), B3 (session log reader)
**Dependencies:** SP-A (sandbox must support `--detach` and `--dev` modes)
**Blocks:** SP-D (parent harness depends on tmux harness and log reader)
**Can run in parallel with:** SP-C

## Objective

Build the tmux interaction module and session log reader that the parent harness (SP-D) uses to drive and monitor the child Claude Code instance inside the sandbox. These are utility modules — they don't implement the test flow itself, just the communication primitives.

Also define the integration-orchestrator agent that uses the TaskOS delegation pattern.

## Context

- Read shared context: `docs/execution/integration-test/_shared_context.md`
- Read plan (Sub-phase B section): `docs/plan/integration-test-installation.md`
- Read orchestration dispatch pattern: `docs/decision/2026-03-28-orchestration-dispatch-pattern.md`
- Read existing `sandbox.py` for container launch patterns: `backend/src/dev_tools/sandbox.py`

## Deliverables

### B1. Integration-orchestrator agent definition

**File to create:** `.claude/agents/integration-test-orchestrator.md`

The orchestrator agent definition. Modeled after `/taskos-orchestrate`:

1. Dispatches child agent via `POST /api/agents/{name}/trigger` with delegation context:
   - Test mode (burnish/regression)
   - Test data fixture paths
   - API key references
   - Phase to run (all/demo/full/verify)
2. Monitors child via `sleep + capture-pane` (same 3-tier polling as taskos-orchestrate)
3. Guides child through test phases by sending tmux keystrokes
4. Reads completion from `.agent-{run_id}.output.json`

This is a markdown agent definition, not Python code. It describes the agent's role, tools, and behavior for Claude Code to follow.

### B2. tmux interaction module

**File to create:** `backend/src/dev_tools/tmux_harness.py`

Class `TmuxHarness` that manages tmux interaction with the sandbox container. Uses the same `sleep + capture-pane` pattern as `taskos-orchestrate`.

```python
class TmuxHarness:
    """Manages tmux interaction with the sandbox.

    Uses the same sleep + capture-pane pattern as taskos-orchestrate:
    poll pane output at intervals, compare hashes to detect idle/stall.
    """

    def __init__(self, session_name: str = "linkedout-test"):
        self.session_name = session_name

    def create_session(self, container_id: str) -> None:
        """Create a tmux session and exec into the sandbox container."""
        # tmux new-session -d -s {session_name}
        # tmux send-keys -t {session_name} "docker exec -it {container_id} bash" Enter

    def kill_session(self) -> None:
        """Kill the tmux session."""

    def send_keys(self, keys: str, enter: bool = True) -> None:
        """Send keystrokes to the active pane.
        If enter=True, append Enter key."""
        # subprocess.run(["tmux", "send-keys", "-t", self.session_name, keys, "Enter"])

    def capture_pane(self, lines: int = 200) -> str:
        """Capture the last N lines of pane output."""
        # subprocess.run(["tmux", "capture-pane", "-t", self.session_name, "-p", "-S", f"-{lines}"])

    def wait_for_idle(self, idle_seconds: int = 10, timeout: int = 600) -> bool:
        """Wait until pane output stops changing (Claude finished processing).

        Same pattern as taskos-orchestrate's content hash comparison:
        capture pane at time T, sleep idle_seconds, capture again at T+N.
        If hash matches -> idle. Repeat until idle or timeout.

        Returns True if idle detected, False if timeout.
        """

    def wait_for_pattern(self, pattern: str, timeout: int = 300, poll_interval: int = 5) -> str | None:
        """Poll pane output until regex pattern appears or timeout.

        Returns the matched line if found, None if timeout.
        """

    def send_to_claude(self, message: str) -> None:
        """Send a message to the Claude Code prompt.

        Convenience wrapper: send_keys(message, enter=True),
        then wait_for_idle() to let Claude process.
        """
```

**Design decisions:**
- **Poll-based** — `sleep + capture-pane` every N seconds (proven pattern)
- **Idle detection** = capture pane hash at time T, compare at T+idle_seconds. Identical = idle.
- **Stall detection** = no change for 120s (setup steps) or 60s (queries) — configurable thresholds
- All subprocess calls use `subprocess.run()` with `capture_output=True`, `text=True`, `timeout=10`
- Use `hashlib.md5` for content hash comparison (fast, not security-sensitive)

### B3. Session log reader

**File to create:** `backend/src/dev_tools/log_reader.py`

Class `SessionLogReader` that reads and tails session logs from the sandbox:

```python
class SessionLogReader:
    """Reads and tails session logs from /tmp/linkedout-oss/.

    Session logs are created by the sandbox's script(1) wrapper.
    """

    def __init__(self, log_dir: str = "/tmp/linkedout-oss"):
        self.log_dir = Path(log_dir)
        self._last_position: int = 0  # byte offset for tailing

    def latest_log(self) -> Path | None:
        """Find the most recent session-*.log file."""

    def read_new_lines(self) -> str:
        """Read lines added since last call (tail behavior).
        Tracks byte offset internally."""

    def search(self, pattern: str) -> list[str]:
        """Search the latest log for lines matching regex pattern."""

    def detect_errors(self) -> list[dict]:
        """Scan for known error patterns in the latest log.

        Returns list of dicts with keys: type, line, line_number.

        Patterns:
        - "Traceback (most recent call last):" -> python_traceback
        - "[sudo] password for" -> unexpected_sudo
        - "Error:" or "error:" in CLI output -> cli_error
        - "FAILED" in readiness report -> setup_failure
        """
```

**Design decisions:**
- Simple file-based — no external dependencies
- Byte-offset tracking for efficient tailing (don't re-read the entire log)
- Error pattern list matches the plan's F1 error detection table

## Verification

1. **B1:** `.claude/agents/integration-test-orchestrator.md` exists and follows agent definition format
2. **B2 — unit test:**
   - `TmuxHarness.send_keys("echo hello")` + `capture_pane()` returns output containing "hello" (requires tmux installed)
   - `wait_for_idle()` detects idle within timeout
   - `wait_for_pattern("ready")` returns matched line when pattern appears
3. **B3 — unit test:**
   - `SessionLogReader.latest_log()` returns a `Path` when session logs exist
   - `detect_errors()` returns entries for injected traceback/sudo patterns
   - `read_new_lines()` returns only new content on subsequent calls

## Notes

- The tmux harness is a utility module — it doesn't know about the test flow. SP-D composes it.
- `send_to_claude()` is a convenience method for SP-D. It sends a message and waits for idle.
- Error detection in the log reader overlaps with burnish mode (SP-F), but the log reader just detects — SP-F acts on it.
- Keep these modules thin. They're developer tools, not production code.
- Tests for B2 require tmux to be installed on the host. Mark them with `@pytest.mark.requires_tmux` so they can be skipped in CI.
