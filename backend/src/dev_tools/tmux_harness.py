# SPDX-License-Identifier: Apache-2.0
"""tmux session harness for driving Claude Code inside a Docker sandbox.

Uses the same sleep + capture-pane polling pattern as taskos-orchestrate:
capture pane output, hash it, compare across intervals to detect idle/stall.

Usage (from parent harness):
    harness = TmuxHarness("linkedout-test")
    harness.create_session(container_id)
    harness.send_keys("claude --dangerously-skip-permissions")
    harness.wait_for_idle()
    harness.send_to_claude("/linkedout-setup --demo")
    output = harness.capture_pane()
    harness.kill_session()
"""
import hashlib
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

from loguru import logger

LOG_DIR = Path("/tmp/linkedout-oss")


class TmuxHarness:
    """Manages tmux interaction with a Docker sandbox container.

    Poll-based design: sleep + capture-pane every N seconds, compare
    content hashes to detect when Claude has finished processing.
    """

    def __init__(self, session_name: str = "linkedout-test"):
        self.session_name = session_name
        self.log_path: Path | None = None

    def create_session(self, container_id: str) -> None:
        """Create a tmux session and exec into the sandbox container."""
        # Kill any stale session from a previous interrupted run
        self._run_tmux("kill-session", "-t", self.session_name, check=False)
        self._run_tmux("new-session", "-d", "-s", self.session_name)

        # Capture full pane output to a session log via pipe-pane
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.log_path = LOG_DIR / f"session-{timestamp}.log"
        self._run_tmux(
            "pipe-pane", "-t", self.session_name,
            f"cat >> {self.log_path}",
        )
        logger.info("Created tmux session: {} (log: {})", self.session_name, self.log_path)

        self.send_keys(f"docker exec -it {container_id} bash")
        # Wait for the container shell prompt instead of a blind sleep
        if not self.wait_for_pattern(r"sandbox@", timeout=15):
            logger.warning("Container shell prompt not detected within 15s")

    def kill_session(self) -> None:
        """Kill the tmux session. No-op if session doesn't exist."""
        result = self._run_tmux("kill-session", "-t", self.session_name, check=False)
        if result.returncode == 0:
            logger.info("Killed tmux session: {}", self.session_name)
        else:
            logger.debug("Session {} already gone", self.session_name)

    def send_keys(self, keys: str, enter: bool = True) -> None:
        """Send keystrokes to the active pane.

        Args:
            keys: Text to send.
            enter: If True, append Enter key.
        """
        args = ["send-keys", "-t", self.session_name, keys]
        if enter:
            args.append("Enter")
        self._run_tmux(*args)
        logger.debug("Sent keys to {}: {!r}", self.session_name, keys[:80])

    def capture_pane(self, lines: int = 200) -> str:
        """Capture the last N lines of pane output."""
        result = self._run_tmux(
            "capture-pane", "-t", self.session_name, "-p", "-S", f"-{lines}",
        )
        return result.stdout

    def wait_for_idle(self, idle_seconds: int = 10, timeout: int = 600) -> bool:
        """Wait until pane output stops changing.

        Captures pane content, sleeps, captures again. If the MD5 hash
        matches, the pane is idle (Claude finished processing).

        Returns True if idle detected, False if timeout.
        """
        deadline = time.monotonic() + timeout
        prev_hash = ""

        while time.monotonic() < deadline:
            content = self.capture_pane()
            current_hash = hashlib.md5(content.encode()).hexdigest()

            if current_hash == prev_hash and prev_hash != "":
                logger.debug("Pane idle after hash match")
                return True

            prev_hash = current_hash
            remaining = deadline - time.monotonic()
            sleep_time = min(idle_seconds, max(0, remaining))
            if sleep_time <= 0:
                break
            time.sleep(sleep_time)

        logger.warning("wait_for_idle timed out after {}s", timeout)
        return False

    def wait_for_pattern(
        self, pattern: str, timeout: int = 300, poll_interval: int = 5,
    ) -> str | None:
        """Poll pane output until a regex pattern appears or timeout.

        Returns the first matched line if found, None if timeout.
        """
        compiled = re.compile(pattern)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            content = self.capture_pane()
            for line in content.splitlines():
                if compiled.search(line):
                    logger.debug("Pattern {!r} matched: {!r}", pattern, line.strip())
                    return line

            remaining = deadline - time.monotonic()
            sleep_time = min(poll_interval, max(0, remaining))
            if sleep_time <= 0:
                break
            time.sleep(sleep_time)

        logger.warning("wait_for_pattern timed out for {!r} after {}s", pattern, timeout)
        return None

    def send_to_claude(self, message: str, idle_timeout: int = 600) -> bool:
        """Send a message to the Claude Code prompt and wait for it to finish.

        Convenience wrapper: send_keys then wait_for_idle.

        Returns True if Claude went idle, False if it timed out.
        """
        self.send_keys(message, enter=True)
        return self.wait_for_idle(timeout=idle_timeout)

    # -- internals --

    def session_alive(self) -> bool:
        """Check if the tmux session still exists."""
        result = self._run_tmux(
            "has-session", "-t", self.session_name, check=False, _raw=True,
        )
        return result.returncode == 0

    def _run_tmux(
        self, *args: str, check: bool = True, _raw: bool = False,
    ) -> subprocess.CompletedProcess:
        """Run a tmux subcommand.

        If the command times out or fails due to a dead session, raises
        RuntimeError with a descriptive message instead of leaking
        subprocess exceptions.
        """
        cmd = ["tmux", *args]
        try:
            return subprocess.run(
                cmd, capture_output=True, text=True, timeout=10, check=check,
            )
        except subprocess.TimeoutExpired:
            if _raw:
                raise
            raise RuntimeError(
                f"tmux command timed out: {' '.join(args[:3])}. "
                "Session may have died."
            )
        except subprocess.CalledProcessError:
            if _raw:
                raise
            raise RuntimeError(
                f"tmux command failed: {' '.join(args[:3])}. "
                "Session may have died."
            )
