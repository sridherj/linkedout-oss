# SPDX-License-Identifier: Apache-2.0
"""Chrome extension upgrade support.

Downloads the latest extension zip from GitHub Releases and provides
re-sideload instructions. Extension update is non-blocking — failure
does not stop the core upgrade.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import httpx
from loguru import logger

from linkedout.upgrade.update_checker import GITHUB_REPO

_EXTENSION_DIR = Path.home() / 'linkedout-data' / 'extension'
_RELEASE_ASSET_URL = (
    f'https://github.com/{GITHUB_REPO}/releases/download'
    '/v{version}/linkedout-extension-v{version}.zip'
)
_CHECKSUM_ASSET_URL = (
    f'https://github.com/{GITHUB_REPO}/releases/download'
    '/v{version}/linkedout-extension-v{version}.zip.sha256'
)


def check_extension_installed() -> bool:
    """Check whether the user has previously installed the Chrome extension.

    Returns True if the extension directory exists and is non-empty.
    """
    if not _EXTENSION_DIR.exists():
        return False
    # Consider installed if the directory has any files (zip or unpacked)
    return any(_EXTENSION_DIR.iterdir())


def download_extension_zip(
    version: str,
    *,
    extension_dir: Path | None = None,
) -> Path:
    """Download the extension zip for the given version from GitHub Releases.

    Args:
        version: Semver string (e.g., ``"0.2.0"``).
        extension_dir: Override the download directory. Defaults to
            ``~/linkedout-data/extension/``.

    Returns:
        Path to the downloaded zip file.

    Raises:
        httpx.HTTPStatusError: On non-2xx response.
        httpx.ConnectError: On network failure.
    """
    dest_dir = extension_dir or _EXTENSION_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)

    filename = f'linkedout-extension-v{version}.zip'
    dest_path = dest_dir / filename
    url = _RELEASE_ASSET_URL.format(version=version)

    headers: dict[str, str] = {}
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'

    logger.info('Downloading extension: {}', filename)

    with httpx.Client(timeout=60, follow_redirects=True) as client:
        with client.stream('GET', url, headers=headers) as resp:
            resp.raise_for_status()
            with open(dest_path, 'wb') as f:
                for chunk in resp.iter_bytes(chunk_size=8192):
                    f.write(chunk)

    logger.info('Extension saved to {}', dest_path)
    return dest_path


def fetch_expected_checksum(version: str) -> str | None:
    """Fetch the expected SHA256 checksum from the release's .sha256 file.

    Returns the hex digest string, or ``None`` if unavailable.
    """
    url = _CHECKSUM_ASSET_URL.format(version=version)
    headers: dict[str, str] = {}
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'

    try:
        with httpx.Client(timeout=10, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
        # .sha256 file format: "<hex_digest>  <filename>\n" or just "<hex_digest>\n"
        text = resp.text.strip()
        return text.split()[0]
    except Exception:
        logger.debug('Could not fetch checksum file for v{}', version)
        return None


def verify_checksum(path: Path, expected_sha256: str) -> bool:
    """Verify the SHA256 checksum of a downloaded file.

    Args:
        path: Path to the file to verify.
        expected_sha256: Expected hex digest.

    Returns:
        True if the computed checksum matches, False otherwise.
    """
    sha256 = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    actual = sha256.hexdigest()
    if actual != expected_sha256.lower():
        logger.warning(
            'Checksum mismatch: expected={}, actual={}',
            expected_sha256,
            actual,
        )
        return False
    return True


def get_sideload_instructions() -> str:
    """Return formatted instructions for re-sideloading the extension.

    Text matches the UX design doc (docs/designs/upgrade-flow-ux.md, Section 3 Step 7).
    """
    return (
        '  To update the extension:\n'
        '    1. Open chrome://extensions\n'
        '    2. Remove the old LinkedOut extension\n'
        '    3. Drag and drop the new zip file onto the page\n'
        '       (or click "Load unpacked" after extracting)'
    )
