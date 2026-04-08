# SPDX-License-Identifier: Apache-2.0
"""Upgrade report data structures and persistence.

Defines the structured output for upgrade operations. Every upgrade
invocation produces an ``UpgradeReport`` containing per-step results,
timing, and rollback instructions. Reports are saved as JSON to the
reports directory and appended as JSONL metrics for trend tracking.

File layout::

    ~/linkedout-data/reports/
        upgrade-20260408-143012.json

    ~/linkedout-data/metrics/daily/
        2026-04-08.jsonl   # appended: {"metric":"upgrade", ...}

Usage::

    from linkedout.upgrade.report import (
        UpgradeReport,
        UpgradeStepResult,
        write_upgrade_report,
    )

    step = UpgradeStepResult(step="pre_flight", status="success", duration_ms=150)
    report = UpgradeReport(
        from_version="0.1.0",
        to_version="0.2.0",
        steps=[step],
        rollback="git checkout v0.1.0",
    )
    path = write_upgrade_report(report)
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class UpgradeStepResult:
    """Result of a single step within the upgrade process.

    Attributes:
        step: Step identifier (e.g., ``"pre_flight"``, ``"pull_code"``).
        status: Outcome — ``"success"``, ``"skipped"``, or ``"failed"``.
        duration_ms: Wall-clock time for this step in milliseconds.
        detail: Optional human-readable detail about what happened.
        extra: Additional step-specific data (e.g., ``{"migrations_applied": 3}``).
    """

    step: str
    status: str  # "success" | "skipped" | "failed"
    duration_ms: int = 0
    detail: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class UpgradeReport:
    """Structured report for a complete upgrade operation.

    Compatible with the ``OperationReport`` pattern from Phase 3 — same
    directory, similar fields, but upgrade-specific (version info, rollback,
    what's-new).

    Attributes:
        operation: Always ``"upgrade"``.
        timestamp: ISO 8601 timestamp of the upgrade start.
        duration_ms: Total wall-clock time in milliseconds.
        from_version: Version before the upgrade.
        to_version: Version after the upgrade.
        counts: Aggregate step counts (total, succeeded, skipped, failed).
        steps: Per-step results.
        whats_new: Changelog excerpt for this version, or None.
        next_steps: Suggested follow-up actions.
        failures: Human-readable failure descriptions.
        rollback: Instruction for reverting the upgrade.
    """

    from_version: str
    to_version: str
    steps: list[UpgradeStepResult] = field(default_factory=list)
    operation: str = 'upgrade'
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
    )
    duration_ms: int = 0
    whats_new: str | None = None
    next_steps: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    rollback: str = ''

    @property
    def counts(self) -> dict[str, int]:
        """Compute step counts from the steps list."""
        total = len(self.steps)
        succeeded = sum(1 for s in self.steps if s.status == 'success')
        skipped = sum(1 for s in self.steps if s.status == 'skipped')
        failed = sum(1 for s in self.steps if s.status == 'failed')
        return {
            'total_steps': total,
            'succeeded': succeeded,
            'skipped': skipped,
            'failed': failed,
        }

    @property
    def overall_status(self) -> str:
        """Derive overall status from step results."""
        if not self.steps:
            return 'success'
        if any(s.status == 'failed' for s in self.steps):
            return 'failed'
        return 'success'

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON output."""
        d = {
            'operation': self.operation,
            'timestamp': self.timestamp,
            'duration_ms': self.duration_ms,
            'from_version': self.from_version,
            'to_version': self.to_version,
            'counts': self.counts,
            'steps': [asdict(s) for s in self.steps],
            'whats_new': self.whats_new,
            'next_steps': self.next_steps,
            'failures': self.failures,
            'rollback': self.rollback,
        }
        return d


def _get_reports_dir() -> Path:
    """Get the reports directory from env or default."""
    reports_dir = os.environ.get(
        'LINKEDOUT_REPORTS_DIR',
        str(Path.home() / 'linkedout-data' / 'reports'),
    )
    return Path(reports_dir)


def _get_metrics_dir() -> Path:
    """Get the metrics directory from env or default."""
    metrics_dir = os.environ.get(
        'LINKEDOUT_METRICS_DIR',
        str(Path.home() / 'linkedout-data' / 'metrics'),
    )
    return Path(metrics_dir)


def write_upgrade_report(
    report: UpgradeReport,
    *,
    reports_dir: Path | None = None,
    metrics_dir: Path | None = None,
) -> Path:
    """Write the upgrade report as JSON and append a metrics event.

    1. Writes the full report to
       ``{reports_dir}/upgrade-YYYYMMDD-HHMMSS.json``.
    2. Appends a compact metrics event to
       ``{metrics_dir}/daily/YYYY-MM-DD.jsonl``.

    Args:
        report: The upgrade report to persist.
        reports_dir: Override the reports directory. Uses
            ``LINKEDOUT_REPORTS_DIR`` or the default when *None*.
        metrics_dir: Override the metrics directory. Uses
            ``LINKEDOUT_METRICS_DIR`` or the default when *None*.

    Returns:
        The path where the JSON report was saved.
    """
    # ── Write JSON report ────────────────────────────────────
    r_dir = reports_dir or _get_reports_dir()
    r_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.fromisoformat(report.timestamp.replace('Z', '+00:00'))
    filename = f'upgrade-{ts.strftime("%Y%m%d-%H%M%S")}.json'
    filepath = r_dir / filename

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(report.to_dict(), f, indent=2)

    # ── Append metrics JSONL ─────────────────────────────────
    m_dir = metrics_dir or _get_metrics_dir()
    daily_dir = m_dir / 'daily'
    daily_dir.mkdir(parents=True, exist_ok=True)

    today = ts.strftime('%Y-%m-%d')
    metrics_path = daily_dir / f'{today}.jsonl'

    metric_event = {
        'metric': 'upgrade',
        'from': report.from_version,
        'to': report.to_version,
        'status': report.overall_status,
        'duration_ms': report.duration_ms,
        'timestamp': report.timestamp,
    }
    line = json.dumps(metric_event, separators=(',', ':')) + '\n'

    with open(metrics_path, 'a', encoding='utf-8') as f:
        f.write(line)
        f.flush()

    return filepath
