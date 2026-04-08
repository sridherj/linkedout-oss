# SPDX-License-Identifier: Apache-2.0
"""Logging helpers for upgrade operations.

Provides pre-configured loggers and step-timing utilities for the
upgrade flow. All logs use ``component="cli"`` and ``operation="upgrade"``
bindings, with a per-invocation correlation ID.

Usage::

    from linkedout.upgrade.logging import get_upgrade_logger, log_step

    logger = get_upgrade_logger()
    logger.info("Starting upgrade from {old} to {new}", old="0.1.0", new="0.2.0")

    with log_step(logger, "pre_flight") as step:
        # ... do pre-flight checks ...
        step.detail = "All checks passed"
    # step.result is an UpgradeStepResult with timing filled in
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime, timezone

from shared.utilities.correlation import set_correlation_id
from shared.utilities.logger import get_logger

from linkedout.upgrade.report import UpgradeStepResult


def get_upgrade_logger():
    """Return a logger bound with upgrade-specific fields.

    Binds ``component="cli"`` and ``operation="upgrade"`` per the
    logging strategy. Generates and sets a correlation ID of the form
    ``cli_upgrade_YYYYMMDD_HHMM``.
    """
    now = datetime.now(timezone.utc)
    correlation_id = f'cli_upgrade_{now.strftime("%Y%m%d_%H%M")}'
    set_correlation_id(correlation_id)

    return get_logger(
        name='linkedout.upgrade',
        component='cli',
        operation='upgrade',
    )


class _StepContext:
    """Mutable context for a step being logged — used by ``log_step``."""

    def __init__(self, step_name: str):
        self.step_name = step_name
        self.detail: str | None = None
        self.extra: dict = {}
        self.status: str = 'success'
        self.result: UpgradeStepResult | None = None


@contextmanager
def log_step(logger, step_name: str):
    """Context manager that times and logs an upgrade step.

    Yields a ``_StepContext`` so the caller can set ``detail``, ``extra``,
    or ``status`` (defaults to ``"success"``). On exception, status is set
    to ``"failed"`` and the error is logged. The ``result`` attribute
    holds the completed ``UpgradeStepResult`` after the block exits.

    Args:
        logger: A loguru logger (typically from ``get_upgrade_logger()``).
        step_name: Identifier for this step (e.g., ``"pre_flight"``).

    Yields:
        A ``_StepContext`` whose ``result`` is populated on exit.
    """
    ctx = _StepContext(step_name)
    logger.info('Step {step}: starting', step=step_name)
    start = time.monotonic()

    try:
        yield ctx
    except Exception as exc:
        ctx.status = 'failed'
        ctx.detail = str(exc)
        duration_ms = int((time.monotonic() - start) * 1000)
        ctx.result = UpgradeStepResult(
            step=step_name,
            status='failed',
            duration_ms=duration_ms,
            detail=ctx.detail,
            extra=ctx.extra,
        )
        logger.error(
            'Step {step}: failed after {ms}ms — {err}',
            step=step_name,
            ms=duration_ms,
            err=str(exc),
        )
        raise
    else:
        duration_ms = int((time.monotonic() - start) * 1000)
        ctx.result = UpgradeStepResult(
            step=step_name,
            status=ctx.status,
            duration_ms=duration_ms,
            detail=ctx.detail,
            extra=ctx.extra,
        )
        logger.info(
            'Step {step}: {status} ({ms}ms)',
            step=step_name,
            status=ctx.status,
            ms=duration_ms,
        )
