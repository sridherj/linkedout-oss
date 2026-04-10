# SPDX-License-Identifier: Apache-2.0
"""Gap detection and auto-repair for LinkedOut setup.

Reads the readiness report, identifies actionable gaps, and offers
interactive repair for each one. Repairs are always prompted — no
silent actions. After all accepted repairs, a fresh readiness check
is produced to confirm the updated state.

Each repair is idempotent: it only processes items that actually need
fixing, so re-running is always safe.
"""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from linkedout.setup.logging_integration import get_setup_logger
from linkedout.setup.readiness import ReadinessReport, generate_readiness_report
from shared.utilities.operation_report import OperationCounts, OperationReport


@dataclass
class RepairAction:
    """A single repair action offered to the user.

    Attributes:
        gap_type: Category key (e.g., ``"missing_embeddings"``).
        description: Human-readable description of the gap.
        command: CLI command that performs the repair.
        default_accept: If ``True``, prompt shows ``[Y/n]``; otherwise ``[y/N]``.
        estimated_time: Human-readable time estimate (e.g., ``"~2 minutes"``).
        estimated_cost: Cost string (e.g., ``"$0.01"``) or ``None`` if free.
    """

    gap_type: str
    description: str
    command: str
    default_accept: bool
    estimated_time: str
    estimated_cost: str | None


# ── Gap → RepairAction mapping ────────────────────────────────────

_REPAIR_MAP = {
    "missing_embeddings": lambda gap: RepairAction(
        gap_type="missing_embeddings",
        description=(
            f"{gap['count']} profiles have no embedding vector.\n"
            f"\n"
            f"  Generate embeddings for these {gap['count']} profiles now?"
        ),
        command="linkedout embed",
        default_accept=True,
        estimated_time="~2 minutes",
        estimated_cost=None,
    ),
    "missing_affinity": lambda gap: RepairAction(
        gap_type="missing_affinity",
        description=(
            f"{gap['count']} connections have no affinity score.\n"
            f"\n"
            f"  Compute affinity for these {gap['count']} connections now?"
        ),
        command="linkedout compute-affinity --force",
        default_accept=True,
        estimated_time="~1 minute",
        estimated_cost=None,
    ),
    "stale_embeddings": lambda gap: RepairAction(
        gap_type="stale_embeddings",
        description=(
            f"{gap['count']} profiles have embeddings from a different provider.\n"
            f"  Re-embedding is recommended but not required.\n"
            f"\n"
            f"  Re-embed with current provider?"
        ),
        command="linkedout embed --force",
        default_accept=False,
        estimated_time="~5 minutes",
        estimated_cost=None,
    ),
}


def analyze_gaps(report: ReadinessReport) -> list[RepairAction]:
    """Convert readiness gaps into repair actions.

    Only gaps that have a known repair are included. Unknown gap
    types are silently skipped (they appear in the readiness report
    but are not auto-repairable).

    Args:
        report: A ``ReadinessReport`` with populated ``gaps``.

    Returns:
        List of ``RepairAction`` instances, one per repairable gap.
    """
    actions: list[RepairAction] = []

    for gap in report.gaps:
        gap_type = gap.get("type", "")
        factory = _REPAIR_MAP.get(gap_type)
        if factory is not None:
            actions.append(factory(gap))

    return actions


def prompt_repair(action: RepairAction) -> bool:
    """Ask the user whether to accept a repair action.

    Displays the gap description and waits for confirmation. The
    default response depends on ``action.default_accept``.

    Args:
        action: The repair action to prompt for.

    Returns:
        ``True`` if the user accepted, ``False`` otherwise.
    """
    prompt_suffix = "[Y/n]" if action.default_accept else "[y/N]"

    print(f"  \u26a0 {action.description}")

    parts = [f"  Estimated time: {action.estimated_time}"]
    if action.estimated_cost:
        parts.append(f"  Estimated cost: {action.estimated_cost}")
    print("\n".join(parts))

    try:
        choice = input(f"  {prompt_suffix} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        choice = ""  # follows default_accept behavior

    if action.default_accept:
        return choice not in ("n", "no")
    else:
        return choice in ("y", "yes")


def execute_repair(action: RepairAction) -> OperationReport:
    """Execute a single repair action via CLI subprocess.

    Args:
        action: The repair action to execute.

    Returns:
        ``OperationReport`` summarizing the repair result.

    Raises:
        RuntimeError: If the repair command fails.
    """
    log = get_setup_logger("auto_repair")
    start = time.monotonic()

    print(f"\n  Running: {action.command}")

    # Split command into parts for subprocess
    cmd_parts = ["linkedout"]
    cmd_parts.extend(action.command.replace("linkedout ", "").split())

    result = subprocess.run(cmd_parts, capture_output=True, text=True)
    duration_ms = (time.monotonic() - start) * 1000

    if result.returncode != 0:
        error_output = result.stderr.strip() or result.stdout.strip()
        log.error("Repair '{}' failed: {}", action.gap_type, error_output)
        return OperationReport(
            operation=f"repair-{action.gap_type}",
            duration_ms=duration_ms,
            counts=OperationCounts(total=1, failed=1),
            next_steps=[f"Run `{action.command}` manually to retry"],
        )

    stdout = result.stdout.strip()
    if stdout:
        # Indent subprocess output
        for line in stdout.splitlines():
            print(f"    {line}")

    log.info("Repair '{}' completed in {:.1f}s", action.gap_type, duration_ms / 1000)

    return OperationReport(
        operation=f"repair-{action.gap_type}",
        duration_ms=duration_ms,
        counts=OperationCounts(total=1, succeeded=1),
    )


def run_auto_repair(
    report: ReadinessReport,
    data_dir: Path,
    db_url: str = "",
) -> ReadinessReport:
    """Full auto-repair cycle: analyze, prompt, repair, re-check.

    For each gap in the readiness report that has a known repair,
    the user is prompted. Accepted repairs run sequentially. After
    all repairs, a fresh readiness report is generated to reflect
    the updated state.

    Args:
        report: The initial readiness report.
        data_dir: Root data directory.
        db_url: Database connection URL (for re-check).

    Returns:
        Updated ``ReadinessReport`` after repairs.
    """
    log = get_setup_logger("auto_repair")
    data_dir = Path(data_dir).expanduser()

    actions = analyze_gaps(report)

    if not actions:
        print("\n  No repairable gaps found.")
        return report

    print(f"\nStep 15 of 15: Gap Detection & Auto-Repair\n")

    repairs_run = 0
    repairs_failed = 0

    for action in actions:
        accepted = prompt_repair(action)

        if not accepted:
            print(f"  Skipping {action.gap_type}.\n")
            continue

        repair_report = execute_repair(action)
        if repair_report.counts.failed > 0:
            repairs_failed += 1
            print(f"  Repair failed. Run `{action.command}` manually.\n")
        else:
            repairs_run += 1
            print(f"  \u2713 Repair complete.\n")

    # Re-run readiness check after repairs
    if repairs_run > 0:
        log.info(
            "Repairs complete ({} run, {} failed). Re-checking readiness.",
            repairs_run,
            repairs_failed,
        )
        return generate_readiness_report(db_url, data_dir)

    return report
