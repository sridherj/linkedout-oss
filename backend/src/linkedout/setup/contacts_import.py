# SPDX-License-Identifier: Apache-2.0
"""Optional contacts import (Google CSV or iCloud vCard) for LinkedOut setup.

Prompts the user to optionally import personal address book contacts
from Google Contacts or iCloud. The import command automatically
reconciles against existing LinkedIn connections.

All operations are idempotent:
- Reconciliation handles re-imports gracefully
- Declining the import returns early with a skip status
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from linkedout.setup.logging_integration import get_setup_logger
from shared.utilities.operation_report import OperationCounts, OperationReport

# ── Prompt text (exact wording from setup-flow-ux.md) ────────────────

_PROMPT_OPT_IN = """\
Step 8 of 15: Contacts Import (optional)

You can import your personal contacts (Google or iCloud) to
enrich your network with phone numbers and email addresses.
These are matched against your LinkedIn connections automatically.

Import personal contacts? [y/N] """

_PROMPT_FORMAT = """\
  Contact format:
    [1] Google Contacts CSV  (export from contacts.google.com)
    [2] iCloud vCard          (export from icloud.com/contacts)

  Choice [1/2]: """

_PROMPT_GOOGLE_PATH = """\
  Export your contacts:
    1. Go to contacts.google.com
    2. Click the gear icon \u2192 Export
    3. Select "Google CSV" format
    4. Save the file

  Enter path to Google Contacts CSV
  (or press Enter to auto-detect in ~/Downloads/): """

_PROMPT_ICLOUD_PATH = """\
  Export your contacts:
    1. Go to icloud.com/contacts
    2. Select All (Cmd+A / Ctrl+A)
    3. Click the gear icon \u2192 Export vCard

  Enter path to iCloud vCard file
  (or press Enter to auto-detect in ~/Downloads/): """


def prompt_contacts_import() -> bool:
    """Ask if the user wants to import personal contacts.

    Default is No (contacts import is entirely optional).

    Returns:
        ``True`` if the user wants to import, ``False`` otherwise.
    """
    try:
        choice = input(_PROMPT_OPT_IN).strip().lower()
    except (EOFError, KeyboardInterrupt):
        choice = ""  # default to no (skip contacts import)
    return choice in ("y", "yes")


def prompt_contacts_format() -> str:
    """Prompt the user to choose between Google CSV or iCloud vCard.

    Returns:
        ``"google"`` or ``"icloud"``.
    """
    while True:
        try:
            choice = input(_PROMPT_FORMAT).strip()
        except (EOFError, KeyboardInterrupt):
            return "google"  # default to google
        if choice == "1":
            return "google"
        if choice == "2":
            return "icloud"
        print("  Please enter 1 or 2.")


def find_contacts_file(
    format: str,
    downloads_dir: Path | None = None,
) -> Path | None:
    """Auto-detect a contacts file in the downloads directory.

    For Google format, looks for files matching ``contacts*.csv`` or
    ``google*.csv`` (case-insensitive). For iCloud format, looks for
    ``*.vcf`` files.

    Args:
        format: Either ``"google"`` or ``"icloud"``.
        downloads_dir: Directory to scan. Defaults to ``~/Downloads/``.

    Returns:
        Path to the detected file, or ``None`` if not found.
    """
    search_dir = downloads_dir or (Path.home() / "Downloads")
    if not search_dir.is_dir():
        return None

    candidates: list[Path] = []
    for f in search_dir.iterdir():
        if not f.is_file():
            continue
        name_lower = f.name.lower()
        if format == "google":
            if f.suffix.lower() == ".csv" and (
                name_lower.startswith("contacts") or name_lower.startswith("google")
            ):
                candidates.append(f)
        elif format == "icloud":
            if f.suffix.lower() == ".vcf":
                candidates.append(f)

    if not candidates:
        return None

    # Return the most recently modified file
    return max(candidates, key=lambda p: p.stat().st_mtime)


def run_contacts_import(path: Path, format: str) -> OperationReport:
    """Execute the contacts import via the ``linkedout`` CLI.

    Runs ``linkedout import-contacts <path> --format <format>`` as a
    subprocess and reports the result.

    Args:
        path: Path to the contacts file.
        format: Contact format (``"google"`` or ``"icloud"``).

    Returns:
        OperationReport summarizing the import result.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        RuntimeError: If the import command fails.
    """
    log = get_setup_logger("contacts_import")
    start = time.monotonic()

    if not path.is_file():
        raise FileNotFoundError(f"Contacts file not found: {path}")

    print(f"  Importing {format} contacts from {_display_path(path)}...")

    result = subprocess.run(
        [
            "linkedout",
            "import-contacts", str(path),
            "--format", format,
        ],
        capture_output=True,
        text=True,
    )

    duration_ms = (time.monotonic() - start) * 1000

    if result.returncode != 0:
        log.error("import-contacts failed: {}", result.stderr.strip())
        error_output = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(
            f"linkedout import-contacts failed (exit code {result.returncode}):\n"
            f"  {error_output}"
        )

    stdout = result.stdout.strip()
    if stdout:
        print(stdout)

    log.info("Contacts import completed in {:.1f}s", duration_ms / 1000)

    return OperationReport(
        operation="contacts-import",
        duration_ms=duration_ms,
        counts=OperationCounts(total=1, succeeded=1),
    )


def setup_contacts_import(data_dir: Path) -> OperationReport:
    """Full contacts import orchestration.

    Steps:
    1. Ask if user wants to import contacts
    2. If yes, choose format (Google / iCloud)
    3. Auto-detect or prompt for file
    4. Run import command

    Returns early with skip status if user declines.

    Args:
        data_dir: Root data directory (e.g., ``~/linkedout-data``).

    Returns:
        OperationReport summarizing what was done.
    """
    start = time.monotonic()

    # Step 1: Ask if they want to import
    if not prompt_contacts_import():
        print("  Skipping contacts import.")
        duration_ms = (time.monotonic() - start) * 1000
        return OperationReport(
            operation="contacts-import",
            duration_ms=duration_ms,
            counts=OperationCounts(total=0, skipped=1),
        )

    # Step 2: Choose format
    format = prompt_contacts_format()

    # Step 3: Auto-detect or prompt for file
    prompt_text = _PROMPT_GOOGLE_PATH if format == "google" else _PROMPT_ICLOUD_PATH
    try:
        user_input = input(prompt_text).strip()
    except (EOFError, KeyboardInterrupt):
        user_input = ""  # default to auto-detect

    if user_input:
        contacts_path = Path(user_input).expanduser().resolve()
    else:
        contacts_path = find_contacts_file(format)

    if contacts_path is None or not contacts_path.is_file():
        print(f"  No {format} contacts file found in ~/Downloads/.")
        print(f"  You can import later: linkedout import-contacts <path> --format {format}")
        duration_ms = (time.monotonic() - start) * 1000
        return OperationReport(
            operation="contacts-import",
            duration_ms=duration_ms,
            counts=OperationCounts(total=0, skipped=1),
            next_steps=[f"Import {format} contacts later: linkedout import-contacts <path> --format {format}"],
        )

    # Step 4: Run import
    report = run_contacts_import(contacts_path, format)

    duration_ms = (time.monotonic() - start) * 1000
    report.duration_ms = duration_ms

    return report


def _display_path(path: Path) -> str:
    """Display a path with ``~`` shorthand for the home directory."""
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)
