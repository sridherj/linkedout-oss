# SPDX-License-Identifier: Apache-2.0
"""``linkedout download-seed`` — download seed company data from GitHub Releases.

Downloads the seed dump file with progress bar, SHA256 checksum
verification, and skip-if-exists logic. Follows the Operation Result Pattern.
"""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import click
import requests
from tqdm import tqdm

from linkedout.cli_helpers import cli_logged
from shared.utils.checksum import verify_checksum
from shared.utilities.logger import get_logger
from shared.utilities.operation_report import OperationCounts, OperationReport

logger = get_logger(__name__, component="cli", operation="download_seed")

DEFAULT_REPO = "sridherj/linkedout-oss"
DEFAULT_BASE_URL = f"https://github.com/{DEFAULT_REPO}/releases/download"
GITHUB_API_BASE = f"https://api.github.com/repos/{DEFAULT_REPO}/releases"


def _get_data_dir() -> Path:
    """Get the LinkedOut data directory, respecting LINKEDOUT_DATA_DIR."""
    return Path(os.environ.get("LINKEDOUT_DATA_DIR", os.path.expanduser("~/linkedout-data")))


def _get_seed_dir(output_override: str | None) -> Path:
    """Get the seed download directory."""
    if output_override:
        return Path(output_override)
    return _get_data_dir() / "seed"


def _get_base_url() -> str:
    """Get the base URL for seed downloads, respecting LINKEDOUT_SEED_URL."""
    return os.environ.get("LINKEDOUT_SEED_URL", DEFAULT_BASE_URL)


def get_release_url(version: str | None = None) -> tuple[str, str]:
    """Get the GitHub Release download base URL and resolved version.

    Checks LINKEDOUT_SEED_URL env var first (for forks).
    If version is None, queries GitHub API for latest.

    Returns:
        Tuple of (base_download_url, resolved_version).
    """
    base_url = _get_base_url()

    if version:
        return f"{base_url}/{version}", version

    # Query GitHub API for latest release
    headers = {}
    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    try:
        resp = requests.get(f"{GITHUB_API_BASE}/latest", headers=headers, timeout=30)
        if resp.status_code == 403 or resp.status_code == 429:
            raise click.ClickException(
                "GitHub API rate limit reached. Set GITHUB_TOKEN env var or wait and retry."
            )
        resp.raise_for_status()
        tag = resp.json()["tag_name"]
        # Strip leading 'v' if present
        resolved = tag.lstrip("v")
        return f"{base_url}/{tag}", resolved
    except requests.ConnectionError as e:
        raise click.ClickException(
            f"Cannot reach GitHub API: {e}. Check your internet connection and try again."
        )
    except requests.RequestException as e:
        raise click.ClickException(f"Failed to query latest release: {e}")


def _fetch_manifest(release_url: str) -> dict:
    """Download and parse seed-manifest.json from a release."""
    url = f"{release_url}/seed-manifest.json"
    headers = {}
    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 404:
            raise click.ClickException(
                f"Manifest not found at {url}. The release may not contain seed data."
            )
        resp.raise_for_status()
    except requests.ConnectionError as e:
        raise click.ClickException(
            f"Download failed: {e}. Check your internet connection and try again."
        )
    except requests.RequestException as e:
        raise click.ClickException(f"Failed to download manifest: {e}")

    try:
        manifest = resp.json()
    except json.JSONDecodeError as e:
        raise click.ClickException(f"Manifest validation failed: {e}. The release may be corrupted.")

    # Validate structure
    if "files" not in manifest or not isinstance(manifest["files"], list):
        raise click.ClickException(
            "Manifest validation failed: missing or invalid 'files' array. The release may be corrupted."
        )

    for f in manifest["files"]:
        for key in ("name", "sha256", "size_bytes"):
            if key not in f:
                raise click.ClickException(
                    f"Manifest validation failed: file entry missing '{key}'. The release may be corrupted."
                )

    return manifest


def _download_file(url: str, dest: Path, expected_size: int) -> None:
    """Stream-download a file with a tqdm progress bar."""
    headers = {}
    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    try:
        resp = requests.get(url, headers=headers, stream=True, timeout=60)
        resp.raise_for_status()
    except requests.ConnectionError as e:
        raise click.ClickException(
            f"Download failed: {e}. Check your internet connection and try again."
        )
    except requests.RequestException as e:
        raise click.ClickException(f"Download failed: {e}")

    total = int(resp.headers.get("content-length", expected_size))

    # Write to a temp file first, rename on success
    tmp_dest = dest.with_suffix(".tmp")
    try:
        with open(tmp_dest, "wb") as f, tqdm(
            total=total,
            unit="B",
            unit_scale=True,
            desc=dest.name,
            ncols=80,
        ) as progress:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                progress.update(len(chunk))
        tmp_dest.rename(dest)
    except Exception:
        if tmp_dest.exists():
            tmp_dest.unlink()
        raise


def _format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    if size_bytes >= 1_000_000_000:
        return f"{size_bytes / 1_000_000_000:.1f} GB"
    if size_bytes >= 1_000_000:
        return f"{size_bytes / 1_000_000:.0f} MB"
    if size_bytes >= 1_000:
        return f"{size_bytes / 1_000:.0f} KB"
    return f"{size_bytes} B"


@click.command("download-seed")
@click.option("--output", "output_dir", default=None, help="Download location (default: ~/linkedout-data/seed/)")
@click.option("--version", "release_version", default=None, help="Specific release version (default: latest)")
@click.option("--force", is_flag=True, help="Re-download even if file exists and checksum matches")
@cli_logged("download_seed")
def download_seed_command(output_dir: str | None, release_version: str | None, force: bool):
    """Download seed company data from GitHub Releases."""
    start = time.time()

    # 1. Determine download directory
    seed_dir = _get_seed_dir(output_dir)
    seed_dir.mkdir(parents=True, exist_ok=True)

    # 2. Determine release version and URL
    click.echo(f"Resolving {'v' + release_version if release_version else 'latest'} release...")
    release_url, resolved_version = get_release_url(release_version)
    logger.info(f"Release URL: {release_url}, version: {resolved_version}")

    # 3. Download manifest
    click.echo("Fetching manifest...")
    manifest = _fetch_manifest(release_url)

    # 4. Get the seed file info (single file)
    file_info = manifest["files"][0]
    filename = file_info["name"]
    expected_sha256 = file_info["sha256"]
    expected_size = file_info["size_bytes"]
    dest = seed_dir / filename

    # 5. Check existing file
    if dest.exists() and not force:
        if verify_checksum(dest, expected_sha256):
            click.echo(
                f"\nSeed data already downloaded (v{resolved_version}, checksum OK). "
                f"Use --force to re-download."
            )
            return
        else:
            click.echo("Existing file has mismatched checksum. Re-downloading...")

    # 6. Download with progress
    download_url = f"{release_url}/{filename}"
    click.echo(f"\nDownloading {filename} ({_format_size(expected_size)})...")
    _download_file(download_url, dest, expected_size)

    # 7. Verify checksum
    click.echo("Verifying checksum...")
    if not verify_checksum(dest, expected_sha256):
        dest.unlink(missing_ok=True)
        raise click.ClickException(
            "Checksum verification failed. File may be corrupted. Try --force to re-download."
        )

    elapsed_ms = (time.time() - start) * 1000
    actual_size = dest.stat().st_size

    # 8. Generate report
    report = OperationReport(
        operation="download-seed",
        duration_ms=elapsed_ms,
        counts=OperationCounts(total=1, succeeded=1),
        next_steps=["Run `linkedout import-seed` to load data into PostgreSQL"],
    )
    report_path = report.save()

    # Also save a detailed download report
    _save_download_report(
        version=resolved_version,
        filename=filename,
        size_bytes=actual_size,
        sha256=expected_sha256,
        duration_ms=elapsed_ms,
        source_url=download_url,
        dest_path=str(dest),
    )

    # 9. Print summary (Operation Result Pattern)
    try:
        display_dest = "~/" + str(dest.relative_to(Path.home()))
    except ValueError:
        display_dest = str(dest)

    click.echo(f"\nDownloaded: {filename} ({_format_size(actual_size)})")
    click.echo(f"Version:   {resolved_version}")
    click.echo(f"Checksum:  OK (SHA256 verified)")
    click.echo(f"Location:  {display_dest}")

    click.echo("\nNext steps:")
    click.echo("  \u2192 Run `linkedout import-seed` to load data into PostgreSQL")

    try:
        display_report = "~/" + str(report_path.relative_to(Path.home()))
    except ValueError:
        display_report = str(report_path)
    click.echo(f"\nReport saved: {display_report}")

    logger.info(
        f"Downloaded {filename} v{resolved_version} "
        f"({_format_size(actual_size)}, {elapsed_ms:.0f}ms)"
    )


def _save_download_report(
    version: str,
    filename: str,
    size_bytes: int,
    sha256: str,
    duration_ms: float,
    source_url: str,
    dest_path: str,
) -> Path:
    """Save a detailed JSON download report."""
    data_dir = _get_data_dir()
    reports_dir = data_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc)
    report_name = f"download-seed-{ts.strftime('%Y%m%d-%H%M%S')}.json"
    path = reports_dir / report_name

    report = {
        "operation": "download-seed",
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "version": version,
        "filename": filename,
        "size_bytes": size_bytes,
        "sha256": sha256,
        "duration_ms": round(duration_ms, 1),
        "source_url": source_url,
        "dest_path": dest_path,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return path
