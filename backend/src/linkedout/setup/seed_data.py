# SPDX-License-Identifier: Apache-2.0
"""Seed data download and import orchestration for LinkedOut setup.

Handles downloading pre-curated reference data from GitHub Releases,
verifying checksums, and importing into the local PostgreSQL database.

All operations are idempotent:
- Download is skipped if checksum matches existing file
- Import handles existing data gracefully (upsert or skip)
"""
from __future__ import annotations

import hashlib
import subprocess
import time
from pathlib import Path

from linkedout.setup.logging_integration import get_setup_logger
from shared.utilities.operation_report import OperationCounts, OperationReport


def download_seed() -> OperationReport:
    """Download seed data via the ``linkedout`` CLI.

    Runs ``linkedout download-seed`` as a subprocess. The CLI
    command handles progress bars and checksum verification.

    Returns:
        OperationReport summarizing the download result.

    Raises:
        RuntimeError: If the download command fails.
    """
    log = get_setup_logger("seed_data")
    start = time.monotonic()

    print("  Downloading seed data...")

    cmd = ["linkedout", "download-seed"]

    result = subprocess.run(cmd, capture_output=True, text=True)
    duration_ms = (time.monotonic() - start) * 1000

    if result.returncode != 0:
        log.error("download-seed failed: {}", result.stderr.strip())
        error_output = result.stderr.strip() or result.stdout.strip()

        # Provide actionable error for network failures
        raise RuntimeError(
            f"linkedout download-seed failed (exit code {result.returncode}):\n"
            f"  {error_output}\n\n"
            f"  If this is a network issue, try again later.\n"
            f"  You can also download manually from the GitHub Releases page\n"
            f"  and place the file in ~/linkedout-data/seed/"
        )

    stdout = result.stdout.strip()
    if stdout:
        print(stdout)

    log.info("Seed download completed in {:.1f}s", duration_ms / 1000)

    return OperationReport(
        operation="seed-download",
        duration_ms=duration_ms,
        counts=OperationCounts(total=1, succeeded=1),
    )


def import_seed() -> OperationReport:
    """Import downloaded seed data into PostgreSQL via the ``linkedout`` CLI.

    Runs ``linkedout import-seed`` as a subprocess. The CLI command
    handles per-table progress and idempotent upsert logic.

    Returns:
        OperationReport summarizing the import result.

    Raises:
        RuntimeError: If the import command fails.
    """
    log = get_setup_logger("seed_data")
    start = time.monotonic()

    print("  Importing seed data into database...")

    result = subprocess.run(
        ["linkedout", "import-seed"],
        capture_output=True,
        text=True,
    )

    duration_ms = (time.monotonic() - start) * 1000

    if result.returncode != 0:
        log.error("import-seed failed: {}", result.stderr.strip())
        error_output = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(
            f"linkedout import-seed failed (exit code {result.returncode}):\n"
            f"  {error_output}\n\n"
            f"  Partial imports are safe \u2014 re-running will continue\n"
            f"  from where it stopped."
        )

    stdout = result.stdout.strip()
    if stdout:
        print(stdout)

    log.info("Seed import completed in {:.1f}s", duration_ms / 1000)

    return OperationReport(
        operation="seed-import",
        duration_ms=duration_ms,
        counts=OperationCounts(total=1, succeeded=1),
    )


def verify_seed_checksum(seed_dir: Path) -> bool:
    """Verify the SHA256 checksum of the downloaded seed file.

    Reads the expected checksum from ``{seed_dir}/CHECKSUM`` and
    compares it against the actual checksum of the seed file.

    The checksum file format is: ``<sha256hex>  <filename>``
    (GNU coreutils style).

    Args:
        seed_dir: Directory containing the seed file and CHECKSUM file.

    Returns:
        ``True`` if the checksum matches, ``False`` otherwise.
    """
    log = get_setup_logger("seed_data")

    checksum_file = seed_dir / "CHECKSUM"
    if not checksum_file.exists():
        log.warning("No CHECKSUM file found in {}", seed_dir)
        return False

    try:
        checksum_content = checksum_file.read_text(encoding="utf-8").strip()
        expected_hash, filename = checksum_content.split(None, 1)
        # Strip leading ./ or * from filename (GNU coreutils format)
        filename = filename.lstrip("*./")
    except (ValueError, OSError) as e:
        log.warning("Could not parse CHECKSUM file: {}", e)
        return False

    seed_file = seed_dir / filename
    if not seed_file.exists():
        log.warning("Seed file {} not found", seed_file)
        return False

    # Compute actual SHA256
    sha256 = hashlib.sha256()
    with open(seed_file, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    actual_hash = sha256.hexdigest()

    match = actual_hash == expected_hash
    if match:
        log.info("Seed checksum verified: {}", filename)
    else:
        log.warning(
            "Seed checksum mismatch for {}: expected={}, actual={}",
            filename, expected_hash, actual_hash,
        )
    return match


def setup_seed_data(data_dir: Path) -> OperationReport:
    """Full seed data orchestration.

    Steps:
    1. Download seed data
    2. Import into database

    Args:
        data_dir: Root data directory (e.g., ``~/linkedout-data``).

    Returns:
        OperationReport summarizing what was done.
    """
    start = time.monotonic()

    # Step 1: Download
    download_report = download_seed()

    # Step 2: Import
    import_report = import_seed()

    # Combine results
    total_succeeded = (
        download_report.counts.succeeded + import_report.counts.succeeded
    )

    duration_ms = (time.monotonic() - start) * 1000

    return OperationReport(
        operation="seed-data-setup",
        duration_ms=duration_ms,
        counts=OperationCounts(total=total_succeeded, succeeded=total_succeeded),
    )
