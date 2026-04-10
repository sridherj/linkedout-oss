# SPDX-License-Identifier: Apache-2.0
"""Burnish mode: self-healing loop scaffolding for integration tests.

Provides limit enforcement, git checkpointing, error classification,
file scope validation, and decision logging. The actual root cause
analysis and fix application is performed by the parent Claude agent —
this module is the guardrails and bookkeeping layer.

Usage (from integration_test.py):
    from dev_tools.burnish import BurnishState, DecisionLog, BurnishLimits
    from dev_tools.burnish import classify_error, check_file_scope
    from dev_tools.burnish import create_checkpoint, can_attempt

    state = BurnishState()
    decision_log = DecisionLog()

    error = classify_error(error_context)
    if error["action"] == "escalate":
        # Infrastructure error — stop and flag to SJ
        ...
    if not can_attempt(state, error_hash):
        # Limits exceeded — escalate
        ...
    checkpoint = create_checkpoint("before fixing pg_trgm issue")
    # ... parent Claude applies fix ...
    state.record_attempt(error_hash)
    decision_log.record({...})
"""
import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


# ---------------------------------------------------------------------------
# Limits and state
# ---------------------------------------------------------------------------

@dataclass
class BurnishLimits:
    """Hard limits for the self-healing loop."""

    max_per_error: int = 5
    max_total: int = 15
    allowed_paths: tuple[str, ...] = ("backend/src/", "skills/", "scripts/", "tests/")
    prohibited_paths: tuple[str, ...] = ("migrations/", ".github/", "docs/specs/")


@dataclass
class BurnishState:
    """Tracks burnish loop progress. Not persisted — lives for one test run."""

    total_attempts: int = 0
    error_attempts: dict[str, int] = field(default_factory=dict)

    def record_attempt(self, error_hash: str) -> None:
        """Record one fix attempt for an error."""
        self.total_attempts += 1
        self.error_attempts[error_hash] = self.error_attempts.get(error_hash, 0) + 1

    def attempts_for(self, error_hash: str) -> int:
        return self.error_attempts.get(error_hash, 0)


def can_attempt(
    state: BurnishState, error_hash: str, limits: BurnishLimits | None = None,
) -> tuple[bool, str]:
    """Check whether another fix attempt is allowed.

    Returns (allowed, reason). If not allowed, reason explains why.
    """
    limits = limits or BurnishLimits()

    if state.total_attempts >= limits.max_total:
        return False, f"Total attempt limit reached ({limits.max_total})"
    if state.attempts_for(error_hash) >= limits.max_per_error:
        return False, (
            f"Per-error limit reached for this error "
            f"({limits.max_per_error} attempts)"
        )
    return True, ""


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

# Infrastructure patterns — these should NOT be self-healed.
_INFRASTRUCTURE_PATTERNS = (
    "docker daemon",
    "docker build",
    "cannot connect to the docker",
    "network is unreachable",
    "connection refused",
    "no space left on device",
)


def classify_error(error_context: dict) -> dict:
    """Classify an error and determine the appropriate action.

    Args:
        error_context: Dict with at least 'type' and 'line' keys
            (as returned by SessionLogReader.detect_errors()).

    Returns:
        Dict with keys: type, line, action ('burnish' or 'escalate').
    """
    error_type = error_context.get("type", "unknown")
    line = error_context.get("line", "").lower()

    # Infrastructure errors always escalate
    for pattern in _INFRASTRUCTURE_PATTERNS:
        if pattern in line:
            return {
                "type": "infrastructure",
                "line": error_context.get("line", ""),
                "action": "escalate",
            }

    return {
        "type": error_type,
        "line": error_context.get("line", ""),
        "action": "burnish",
    }


# ---------------------------------------------------------------------------
# Error hashing
# ---------------------------------------------------------------------------

def hash_error(error_context: dict) -> str:
    """Create a stable hash for an error to track per-error attempt counts.

    Uses error type + first meaningful line of the error message.
    """
    error_type = error_context.get("type", "unknown")
    line = error_context.get("line", "").strip()
    # Take the first 200 chars to keep hashes stable across minor variations
    key = f"{error_type}:{line[:200]}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# File scope validation
# ---------------------------------------------------------------------------

def check_file_scope(
    file_paths: list[str], limits: BurnishLimits | None = None,
) -> tuple[bool, list[str]]:
    """Check that all files to be modified are within allowed scope.

    Args:
        file_paths: List of file paths (relative to repo root).

    Returns:
        (allowed, violations). If not allowed, violations lists the offending paths.
    """
    limits = limits or BurnishLimits()
    violations: list[str] = []

    for path in file_paths:
        # Check prohibited first
        if any(path.startswith(p) for p in limits.prohibited_paths):
            violations.append(f"{path} (prohibited)")
            continue
        # Check allowed
        if not any(path.startswith(p) for p in limits.allowed_paths):
            violations.append(f"{path} (not in allowed paths)")

    return len(violations) == 0, violations


# ---------------------------------------------------------------------------
# Git checkpointing
# ---------------------------------------------------------------------------

def create_checkpoint(description: str, repo_dir: Path | None = None) -> str:
    """Create a git commit checkpoint before applying a fix.

    Returns the commit hash. If there's nothing to commit, returns
    the current HEAD hash instead.
    """
    cwd = str(repo_dir or REPO_ROOT)

    # Stage everything
    subprocess.run(
        ["git", "add", "-A"], cwd=cwd, capture_output=True, check=True, timeout=30,
    )

    # Check if there's anything to commit
    status = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=cwd, capture_output=True, check=False, timeout=10,
    )

    if status.returncode != 0:
        # There are staged changes — commit them
        subprocess.run(
            ["git", "commit", "-m", f"checkpoint: {description}"],
            cwd=cwd, capture_output=True, check=True, timeout=30,
        )

    # Return current HEAD hash
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=cwd, capture_output=True, text=True, check=True, timeout=10,
    )
    commit_hash = result.stdout.strip()
    logger.info("Checkpoint {}: {}", commit_hash, description)
    return commit_hash


# ---------------------------------------------------------------------------
# Decision log
# ---------------------------------------------------------------------------

class DecisionLog:
    """Append-only JSONL decision log for burnish mode fixes."""

    def __init__(self, log_dir: str = "/tmp/linkedout-oss"):
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        self.path = log_path / f"burnish-decisions-{timestamp}.jsonl"

    def record(self, decision: dict) -> None:
        """Append one decision entry to the JSONL file.

        Adds a timestamp if not already present.
        """
        if "timestamp" not in decision:
            decision["timestamp"] = datetime.now(timezone.utc).isoformat()
        with open(self.path, "a") as f:
            f.write(json.dumps(decision) + "\n")
        logger.debug("Decision logged to {}", self.path)

    def read_all(self) -> list[dict]:
        """Read all decision entries."""
        if not self.path.exists():
            return []
        entries = []
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries
