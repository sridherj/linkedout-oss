# SPDX-License-Identifier: Apache-2.0
"""``linkedout download-demo`` — download the demo pg_dump from GitHub Releases.

Downloads a pre-built demo database dump with SHA256 checksum verification
and skip-if-cached logic. Follows the same patterns as ``download_seed.py``.
"""
import json
import os
import time
from pathlib import Path

import click
import requests
from tqdm import tqdm

from linkedout.cli_helpers import cli_logged
from shared.utils.checksum import verify_checksum
from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="cli", operation="download_demo")

DEMO_REPO = "sridherj/linkedout-oss"
DEMO_RELEASE_TAG = "demo-v1"
DEMO_BASE_URL = f"https://github.com/{DEMO_REPO}/releases/download"
DEMO_MANIFEST_NAME = "demo-manifest.json"


def _get_data_dir() -> Path:
    """Get the LinkedOut data directory, respecting LINKEDOUT_DATA_DIR."""
    return Path(os.environ.get("LINKEDOUT_DATA_DIR", os.path.expanduser("~/linkedout-data")))


def _get_cache_dir() -> Path:
    """Get the demo cache directory."""
    return _get_data_dir() / "cache"


def _get_release_url(version: str | None = None) -> tuple[str, str]:
    """Get the GitHub Release download URL and resolved tag.

    Args:
        version: Specific release tag (e.g., ``demo-v1``). If None, uses
            the default ``DEMO_RELEASE_TAG``.

    Returns:
        Tuple of (base_download_url, resolved_tag).
    """
    base_url = os.environ.get("LINKEDOUT_DEMO_URL", DEMO_BASE_URL)
    tag = version or DEMO_RELEASE_TAG
    return f"{base_url}/{tag}", tag


def _fetch_manifest(release_url: str) -> dict:
    """Download and parse demo-manifest.json from a release."""
    url = f"{release_url}/{DEMO_MANIFEST_NAME}"
    headers = {}
    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 404:
            raise click.ClickException(
                f"Demo manifest not found at {url}. "
                f"The release may not contain demo data."
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
        raise click.ClickException(
            f"Manifest validation failed: {e}. The release may be corrupted."
        )

    # Validate required fields
    for key in ("name", "sha256", "size_bytes"):
        if key not in manifest:
            raise click.ClickException(
                f"Manifest validation failed: missing '{key}'. "
                f"The release may be corrupted."
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


@click.command("download-demo")
@click.option("--version", "release_version", default=None, help="Specific release tag (default: demo-v1)")
@click.option("--force", is_flag=True, help="Re-download even if file exists and checksum matches")
@cli_logged("download_demo")
def download_demo_command(release_version: str | None, force: bool):
    """Download demo database dump from GitHub Releases."""
    from linkedout.demo import DEMO_DUMP_FILENAME

    start = time.time()

    # 1. Determine cache directory
    cache_dir = _get_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    # 2. Resolve release URL
    release_url, tag = _get_release_url(release_version)
    click.echo(f"Resolving release {tag}...")

    # 3. Fetch manifest
    click.echo("Fetching demo manifest...")
    manifest = _fetch_manifest(release_url)

    filename = manifest["name"]
    expected_sha256 = manifest["sha256"]
    expected_size = manifest["size_bytes"]
    dest = cache_dir / DEMO_DUMP_FILENAME

    # 4. Check existing file
    if dest.exists() and not force:
        if verify_checksum(dest, expected_sha256):
            click.echo(
                f"\nDemo dump already cached (checksum OK). "
                f"Use --force to re-download."
            )
            click.echo(f"\nNext step:")
            click.echo("  → Run `linkedout restore-demo` to load the demo database")
            return
        else:
            click.echo("Existing file has mismatched checksum. Re-downloading...")

    # 5. Download with progress
    download_url = f"{release_url}/{filename}"
    click.echo(f"\nDownloading {filename} ({_format_size(expected_size)})...")
    _download_file(download_url, dest, expected_size)

    # 6. Verify checksum
    click.echo("Verifying checksum...")
    if not verify_checksum(dest, expected_sha256):
        dest.unlink(missing_ok=True)
        raise click.ClickException(
            "Checksum verification failed. File may be corrupted. Try --force to re-download."
        )

    elapsed = time.time() - start
    actual_size = dest.stat().st_size

    # 7. Print summary
    try:
        display_dest = "~/" + str(dest.relative_to(Path.home()))
    except ValueError:
        display_dest = str(dest)

    click.echo(f"\nDownloaded: {DEMO_DUMP_FILENAME} ({_format_size(actual_size)})")
    click.echo(f"Checksum:  OK (SHA256 verified)")
    click.echo(f"Location:  {display_dest}")

    click.echo(f"\nNext step:")
    click.echo("  → Run `linkedout restore-demo` to load the demo database")

    logger.info(
        f"Downloaded demo dump ({_format_size(actual_size)}, {elapsed:.1f}s)"
    )
