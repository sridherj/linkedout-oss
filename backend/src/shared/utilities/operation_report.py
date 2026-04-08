# SPDX-License-Identifier: Apache-2.0
"""Structured operation reports for CLI commands.

Every data-modifying CLI command produces an ``OperationReport`` that
captures counts, coverage gaps, failures, and next steps. Reports are
printed as a human-readable summary and persisted as JSON to the reports
directory for later inspection.

File layout::

    {reports_dir}/
        import-csv-20260407-142305.json
        compute-affinity-20260407-153012.json

Usage::

    from shared.utilities.operation_report import OperationReport, OperationCounts

    report = OperationReport(
        operation="import-csv",
        counts=OperationCounts(total=3870, succeeded=3847, skipped=23, failed=0),
    )
    report.print_summary()
    path = report.save()
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class OperationCounts:
    """Aggregate counts for an operation's processed items."""

    total: int = 0
    succeeded: int = 0
    skipped: int = 0
    failed: int = 0


@dataclass
class CoverageGap:
    """A gap in data coverage discovered during an operation.

    Attributes:
        type: Category of the gap (e.g., ``"missing_company"``).
        count: Number of items affected.
        detail: Human-readable description of the gap.
    """

    type: str
    count: int
    detail: str


@dataclass
class OperationFailure:
    """A single item that failed during an operation.

    Attributes:
        item: Identifier of the failed item.
        reason: Why it failed.
    """

    item: str
    reason: str


@dataclass
class OperationReport:
    """Standardized output artifact for all data-modifying CLI operations.

    Captures the full result of an operation: what was processed, what
    gaps remain, what failed, and what to do next. Supports both
    human-readable console output and JSON persistence.

    Attributes:
        operation: Name of the operation (e.g., ``"import-csv"``).
        timestamp: ISO 8601 timestamp of when the operation started.
        duration_ms: Wall-clock duration in milliseconds.
        counts: Aggregate succeeded/skipped/failed counts.
        coverage_gaps: Data coverage gaps discovered during the operation.
        failures: Individual item failures with reasons.
        next_steps: Suggested follow-up commands for the user.
    """

    operation: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
    )
    duration_ms: float = 0.0
    counts: OperationCounts = field(default_factory=OperationCounts)
    coverage_gaps: list[CoverageGap] = field(default_factory=list)
    failures: list[OperationFailure] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)

    # Path set after save() is called, used by print_summary().
    _saved_path: Path | None = field(default=None, repr=False)

    def save(self, reports_dir: Path | None = None) -> Path:
        """Save the report as JSON to the reports directory.

        Args:
            reports_dir: Override the reports directory. Uses
                ``LINKEDOUT_REPORTS_DIR`` or the default when *None*.

        Returns:
            The path where the report was saved.
        """
        base = reports_dir or _get_reports_dir()
        base.mkdir(parents=True, exist_ok=True)

        # Derive filename from timestamp: {operation}-YYYYMMDD-HHMMSS.json
        ts = datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
        filename = f'{self.operation}-{ts.strftime("%Y%m%d-%H%M%S")}.json'

        filepath = base / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)

        self._saved_path = filepath
        return filepath

    def print_summary(self) -> None:
        """Print a human-readable summary to stdout.

        Follows the operation result pattern from ``docs/decision/cli-surface.md``.
        Sections are conditionally included: Coverage appears only when there
        are coverage gaps, Next steps only when next_steps is non-empty, and
        the Report path only after ``save()`` has been called.
        """
        counts = self.counts

        print('Results:')
        print(f'  Succeeded: {counts.succeeded:,}')
        print(f'  Skipped:   {counts.skipped:,}')
        print(f'  Failed:    {counts.failed:,}')

        if self.coverage_gaps:
            print()
            print('Coverage:')
            for gap in self.coverage_gaps:
                print(f'  {gap.detail}')

        if self.next_steps:
            print()
            print('Next steps:')
            for step in self.next_steps:
                print(f'  \u2192 {step}')

        if self._saved_path is not None:
            print()
            # Use ~ shorthand when the path is under the user's home directory.
            try:
                display_path = '~/' + str(self._saved_path.relative_to(Path.home()))
            except ValueError:
                display_path = str(self._saved_path)
            print(f'Report saved: {display_path}')

    def to_dict(self) -> dict:
        """Serialize the report to a plain dict for JSON output.

        Returns:
            A dict with all public fields recursively converted.
            The internal ``_saved_path`` field is excluded.
        """
        d = asdict(self)
        d.pop('_saved_path', None)
        return d


def _get_reports_dir() -> Path:
    """Get the reports directory from env or default.

    Reads ``LINKEDOUT_REPORTS_DIR`` from the environment. Falls back to
    ``~/linkedout-data/reports/`` when the variable is unset.
    """
    reports_dir = os.environ.get(
        'LINKEDOUT_REPORTS_DIR',
        str(Path.home() / 'linkedout-data' / 'reports'),
    )
    return Path(reports_dir)
