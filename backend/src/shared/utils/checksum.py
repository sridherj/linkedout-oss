# SPDX-License-Identifier: Apache-2.0
"""SHA256 checksum utilities for seed data files."""
import hashlib
from pathlib import Path


def compute_sha256(filepath: Path) -> str:
    """Compute SHA256 hex digest of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_checksum(filepath: Path, expected_sha256: str) -> bool:
    """Verify SHA256 checksum of a downloaded file."""
    return compute_sha256(filepath) == expected_sha256
