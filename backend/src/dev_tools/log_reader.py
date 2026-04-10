# SPDX-License-Identifier: Apache-2.0
"""Session log reader for the Docker sandbox.

Reads and tails session logs created by the sandbox's script(1) wrapper.
Logs are written to /tmp/linkedout-oss/session-*.log by sandbox.py.

Usage (from parent harness):
    reader = SessionLogReader()
    log = reader.latest_log()
    new_output = reader.read_new_lines()
    errors = reader.detect_errors()
"""
import re
from pathlib import Path

from loguru import logger

# Error patterns matched against each log line.
# Each tuple: (compiled regex, error type label)
_ERROR_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"Traceback \(most recent call last\):"), "python_traceback"),
    (re.compile(r"\[sudo\] password for"), "unexpected_sudo"),
    (re.compile(r"(?:Error|error):"), "cli_error"),
    (re.compile(r"FAILED"), "setup_failure"),
]


class SessionLogReader:
    """Reads and tails session logs from the sandbox log directory.

    Tracks byte offset internally so read_new_lines() returns only
    content added since the last call (efficient tailing).
    """

    def __init__(self, log_dir: str = "/tmp/linkedout-oss"):
        self.log_dir = Path(log_dir)
        self._current_log: Path | None = None
        # Seek past any existing content so we only see new output
        log = self.latest_log()
        if log is not None:
            self._current_log = log
            self._last_position = log.stat().st_size
        else:
            self._last_position = 0

    def latest_log(self) -> Path | None:
        """Find the most recent session-*.log file by modification time."""
        logs = sorted(
            self.log_dir.glob("session-*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not logs:
            logger.debug("No session logs found in {}", self.log_dir)
            return None
        return logs[0]

    def read_new_lines(self) -> str:
        """Read lines added since the last call (tail behavior).

        On first call or when the log file changes, resets the offset.
        Returns empty string if no new content.
        """
        log = self.latest_log()
        if log is None:
            return ""

        # Reset offset if the log file changed
        if log != self._current_log:
            self._current_log = log
            self._last_position = 0

        try:
            with log.open("r", errors="replace") as f:
                f.seek(self._last_position)
                new_content = f.read()
                self._last_position = f.tell()
        except OSError as e:
            logger.warning("Failed to read log {}: {}", log, e)
            return ""

        return new_content

    def search(self, pattern: str) -> list[str]:
        """Search the latest log for lines matching a regex pattern."""
        log = self.latest_log()
        if log is None:
            return []

        compiled = re.compile(pattern)
        matches = []
        try:
            with log.open("r", errors="replace") as f:
                for line in f:
                    if compiled.search(line):
                        matches.append(line.rstrip("\n"))
        except OSError as e:
            logger.warning("Failed to search log {}: {}", log, e)

        return matches

    def detect_errors(self) -> list[dict]:
        """Scan new log content for known error patterns.

        Only scans content added since the last call (or since construction),
        so stale errors from previous sessions are never reported.

        Returns a list of dicts with keys: type, line.
        """
        new_content = self.read_new_lines()
        if not new_content:
            return []

        errors = []
        for line in new_content.splitlines():
            for regex, error_type in _ERROR_PATTERNS:
                if regex.search(line):
                    errors.append({
                        "type": error_type,
                        "line": line.rstrip("\n"),
                    })
                    break  # one match per line is enough

        return errors
