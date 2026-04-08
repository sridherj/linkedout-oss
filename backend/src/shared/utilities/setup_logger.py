# SPDX-License-Identifier: Apache-2.0
"""Setup-specific logging utilities for Phase 9 setup flow.

Provides a thin wrapper around the core logging framework (SP1) with:
- get_setup_logger(): logger pre-bound to component='setup'
- setup_step(): context manager for logging setup steps with timing and diagnostics

All setup log entries route to ~/linkedout-data/logs/setup.log via the
component-based routing in LoggerSingleton.
"""
import os
import platform
import shutil
import sys
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone

from shared.config import get_config
from shared.utilities.correlation import get_correlation_id
from shared.utilities.logger import get_logger


def get_setup_logger(step: str | None = None):
    """Get a logger bound to component='setup'.

    Args:
        step: Optional operation name to bind (e.g., 'install_deps').

    Returns:
        A loguru logger bound with component='setup' and optionally operation=step.
    """
    bindings: dict = {"component": "setup"}
    if step:
        bindings["operation"] = step
    return get_logger("setup", **bindings)


class _StepContext:
    """Mutable container passed into setup_step() for recording details."""

    def __init__(self):
        self._details: list[str] = []

    def detail(self, message: str) -> None:
        """Record a detail message to include in the completion log line."""
        self._details.append(message)


@contextmanager
def setup_step(step_number: int, total_steps: int, description: str):
    """Context manager for setup step logging with timing and diagnostics.

    Logs step start/completion with duration. On failure, generates a
    diagnostic file at ~/linkedout-data/logs/setup-diagnostic-YYYYMMDD-HHMMSS.txt.

    Args:
        step_number: Current step number (1-based).
        total_steps: Total number of steps.
        description: Human-readable description of the step.

    Yields:
        A context object with a .detail(message) method for recording
        extra information to include in the completion log line.

    Example:
        with setup_step(3, 9, "Installing Python dependencies") as step:
            # do work
            step.detail("47 packages installed")
    """
    log = get_setup_logger(step=f"step_{step_number}")
    prefix = f"Step {step_number}/{total_steps}"
    ctx = _StepContext()

    log.info(f"{prefix}: {description}...")
    start = time.monotonic()

    try:
        yield ctx
    except Exception as exc:
        elapsed = time.monotonic() - start
        log.error(f"{prefix}: FAILED ({elapsed:.1f}s) \u2014 {exc}")
        _write_diagnostic(step_number, total_steps, description, elapsed, exc)
        raise
    else:
        elapsed = time.monotonic() - start
        detail_suffix = f" \u2014 {'; '.join(ctx._details)}" if ctx._details else ""
        log.info(f"{prefix}: Complete ({elapsed:.1f}s){detail_suffix}")


def _write_diagnostic(
    step_number: int,
    total_steps: int,
    description: str,
    elapsed: float,
    exc: Exception,
) -> str | None:
    """Write a self-contained diagnostic file on setup failure.

    Returns the path to the diagnostic file, or None if writing failed.
    """
    settings = get_config()
    log_dir = settings.log_dir
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    diag_path = os.path.join(log_dir, f"setup-diagnostic-{timestamp}.txt")

    try:
        disk = shutil.disk_usage("/")
        disk_info = (
            f"  Total: {disk.total // (1024**3)} GB\n"
            f"  Used:  {disk.used // (1024**3)} GB\n"
            f"  Free:  {disk.free // (1024**3)} GB"
        )
    except OSError:
        disk_info = "  (unavailable)"

    correlation_id = get_correlation_id() or "(none)"
    tb = traceback.format_exception(type(exc), exc, exc.__traceback__)

    lines = [
        f"LinkedOut Setup Diagnostic — {timestamp}",
        "=" * 60,
        "",
        "SYSTEM INFO",
        f"  OS:      {platform.system()} {platform.release()} ({platform.machine()})",
        f"  Python:  {sys.version}",
        f"  Disk:",
        disk_info,
        "",
        "SETUP CONTEXT",
        f"  Correlation ID: {correlation_id}",
        f"  Failed Step:    {step_number}/{total_steps} — {description}",
        f"  Elapsed:        {elapsed:.1f}s",
        "",
        "ERROR",
        "".join(tb),
        "",
        "=" * 60,
        "This file is self-contained enough to file as a bug report.",
    ]

    try:
        with open(diag_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        log = get_setup_logger()
        log.info(f"Diagnostic saved: {diag_path}")
        return diag_path
    except OSError:
        return None
