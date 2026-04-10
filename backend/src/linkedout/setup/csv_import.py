# SPDX-License-Identifier: Apache-2.0
"""Guided LinkedIn CSV import flow for LinkedOut setup.

Walks the user through exporting their LinkedIn connections as CSV,
auto-detects the file in ``~/Downloads/``, copies it to the uploads
directory for record-keeping, and runs ``linkedout import-connections``
to load the data into the database.

All operations are idempotent:
- Re-running on the same CSV skips already-imported profiles
- New profiles in a re-import are added without duplicating existing ones
"""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from linkedout.setup.logging_integration import get_setup_logger
from shared.utilities.operation_report import OperationCounts, OperationReport

# ── Prompt text (exact wording from setup-flow-ux.md) ────────────────

_PROMPT_EXPORT_GUIDANCE = """\
Step 7 of 15: LinkedIn CSV Import

To import your connections, you need a CSV export from LinkedIn.

How to get it:
  1. Go to linkedin.com/mypreferences/d/download-my-data
  2. Select "Connections" (you only need this one)
  3. Click "Request archive"
  4. Wait for the email from LinkedIn (~10 minutes)
  5. Download and unzip the archive
  6. The file you need is "Connections.csv"

If you already have the CSV, great \u2014 we will auto-detect it."""

_MSG_FILE_FOUND = """\
  Found: {path} ({size}, modified {modified})

  Use this file? [Y/n] """

_MSG_FILE_NOT_FOUND = """\
  Could not find a Connections CSV in ~/Downloads/.

  Options:
    [1] Enter the file path manually
    [2] Skip for now (you can import later with: linkedout import-connections)

  Choice [1/2]: """

_MSG_SKIP = """\
  Skipping CSV import.

  When you have your CSV ready, run:
    linkedout import-connections ~/path/to/Connections.csv

  Then re-run /linkedout-setup to complete embedding generation
  and affinity scoring for the new connections."""

_MSG_ENTER_PATH = "  Enter path to Connections CSV: "


def find_linkedin_csv(downloads_dir: Path | None = None) -> Path | None:
    """Auto-detect a LinkedIn Connections CSV in the downloads directory.

    Scans for files matching ``Connections*.csv`` or ``connections*.csv``
    (case-insensitive). Returns the most recently modified match.

    Args:
        downloads_dir: Directory to scan. Defaults to ``~/Downloads/``.

    Returns:
        Path to the detected CSV file, or ``None`` if not found.
    """
    search_dir = downloads_dir or (Path.home() / "Downloads")
    if not search_dir.is_dir():
        return None

    candidates: list[Path] = []
    for f in search_dir.iterdir():
        if f.is_file() and f.name.lower().startswith("connections") and f.suffix.lower() == ".csv":
            candidates.append(f)

    if not candidates:
        return None

    # Return the most recently modified file
    return max(candidates, key=lambda p: p.stat().st_mtime)


def prompt_csv_path(auto_detected: Path | None) -> Path | None:
    """Confirm auto-detected CSV or prompt the user for a path.

    Args:
        auto_detected: Path found by ``find_linkedin_csv()``, or ``None``.

    Returns:
        The confirmed/entered CSV path, or ``None`` if the user skips.
    """
    if auto_detected is not None:
        stat = auto_detected.stat()
        size_mb = stat.st_size / (1024 * 1024)
        from datetime import datetime, timezone
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y-%m-%d")
        size_str = f"{size_mb:.1f} MB" if size_mb >= 1.0 else f"{stat.st_size / 1024:.0f} KB"

        try:
            choice = input(_MSG_FILE_FOUND.format(
                path=_display_path(auto_detected),
                size=size_str,
                modified=modified,
            )).strip().lower()
        except (EOFError, KeyboardInterrupt):
            choice = ""  # default to yes (use detected file)

        if choice in ("", "y", "yes"):
            return auto_detected
        # User said no — fall through to manual entry

    # No auto-detect or user declined
    try:
        choice = input(_MSG_FILE_NOT_FOUND).strip()
    except (EOFError, KeyboardInterrupt):
        choice = "2"  # default to skip
    if choice == "2":
        print(_MSG_SKIP)
        return None

    # Manual entry (choice '1' or default)
    while True:
        try:
            path_str = input(_MSG_ENTER_PATH).strip()
        except (EOFError, KeyboardInterrupt):
            print(_MSG_SKIP)
            return None
        path = Path(path_str).expanduser().resolve()
        if path.is_file() and path.suffix.lower() == ".csv":
            return path
        print(f"  File not found or not a CSV: {path_str}")
        try:
            retry = input("  Try again? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            retry = "n"  # default to stop retrying
        if retry in ("n", "no"):
            print(_MSG_SKIP)
            return None


def copy_to_uploads(csv_path: Path, data_dir: Path) -> Path:
    """Copy the CSV file to the uploads directory for record-keeping.

    Creates ``{data_dir}/uploads/`` if it doesn't exist. The copy
    preserves the original filename.

    Args:
        csv_path: Path to the CSV file to copy.
        data_dir: Root data directory (e.g., ``~/linkedout-data``).

    Returns:
        Path to the copied file.
    """
    uploads_dir = data_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    dest = uploads_dir / csv_path.name
    if dest.exists() and dest.resolve() == csv_path.resolve():
        return dest  # Already in uploads

    shutil.copy2(csv_path, dest)
    return dest


def run_csv_import(csv_path: Path) -> OperationReport:
    """Execute the LinkedIn CSV import via the ``linkedout`` CLI.

    Runs ``linkedout import-connections <csv_path>`` as a subprocess
    and reports the result.

    Args:
        csv_path: Path to the Connections CSV file.

    Returns:
        OperationReport summarizing the import result.

    Raises:
        FileNotFoundError: If ``csv_path`` does not exist.
        RuntimeError: If the import command fails.
    """
    log = get_setup_logger("csv_import")
    start = time.monotonic()

    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    print(f"  Importing connections from {_display_path(csv_path)}...")

    result = subprocess.run(
        ["linkedout", "import-connections", str(csv_path)],
        capture_output=True,
        text=True,
    )

    duration_ms = (time.monotonic() - start) * 1000

    if result.returncode != 0:
        log.error("import-connections failed: {}", result.stderr.strip())
        error_output = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(
            f"linkedout import-connections failed (exit code {result.returncode}):\n"
            f"  {error_output}"
        )

    # Parse output for counts if available
    stdout = result.stdout.strip()
    if stdout:
        print(stdout)

    log.info("CSV import completed in {:.1f}s", duration_ms / 1000)

    return OperationReport(
        operation="csv-import",
        duration_ms=duration_ms,
        counts=OperationCounts(total=1, succeeded=1),
    )


def setup_csv_import(data_dir: Path) -> OperationReport:
    """Full LinkedIn CSV import orchestration.

    Steps:
    1. Show export guidance
    2. Auto-detect or prompt for CSV file
    3. Copy to uploads directory
    4. Run import command

    Args:
        data_dir: Root data directory (e.g., ``~/linkedout-data``).

    Returns:
        OperationReport summarizing what was done.
    """
    start = time.monotonic()

    # Step 1: Show guidance
    print(_PROMPT_EXPORT_GUIDANCE)
    print()

    # Step 2: Find or prompt for CSV
    auto_detected = find_linkedin_csv()
    csv_path = prompt_csv_path(auto_detected)

    if csv_path is None:
        duration_ms = (time.monotonic() - start) * 1000
        return OperationReport(
            operation="csv-import",
            duration_ms=duration_ms,
            counts=OperationCounts(total=0, skipped=1),
            next_steps=["Import LinkedIn CSV later: linkedout import-connections <path>"],
        )

    # Step 3: Copy to uploads
    copy_to_uploads(csv_path, data_dir)

    # Step 4: Run import
    report = run_csv_import(csv_path)

    duration_ms = (time.monotonic() - start) * 1000
    report.duration_ms = duration_ms

    return report


def _display_path(path: Path) -> str:
    """Display a path with ``~`` shorthand for the home directory."""
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)
