# SPDX-License-Identifier: Apache-2.0
"""Demo mode constants and helpers.

Provides the canonical check for demo mode and utilities for switching
between the real and demo databases.
"""
from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import yaml

DEMO_DB_NAME = "linkedout_demo"
DEMO_CACHE_DIR = "cache"
DEMO_DUMP_FILENAME = "demo-seed.dump"


def is_demo_mode() -> bool:
    """Return True if the application is running in demo mode."""
    from shared.config.settings import get_config

    return get_config().demo_mode


def get_demo_db_url(base_url: str) -> str:
    """Replace the database name in a PostgreSQL URL with the demo database name.

    Args:
        base_url: A PostgreSQL connection string.

    Returns:
        The same URL with the database name replaced by ``linkedout_demo``.
    """
    parsed = urlparse(base_url)
    # Replace the path (which is /dbname) with /linkedout_demo
    replaced = parsed._replace(path=f"/{DEMO_DB_NAME}")
    return urlunparse(replaced)


def set_demo_mode(data_dir: Path, enabled: bool) -> None:
    """Toggle demo_mode in config.yaml and update the database_url accordingly.

    Uses atomic write (tempfile + rename) to avoid partial writes.

    Args:
        data_dir: Root data directory (e.g., ``~/linkedout-data``).
        enabled: Whether to enable or disable demo mode.
    """
    config_path = data_dir / "config" / "config.yaml"
    config: dict = {}
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

    config["demo_mode"] = enabled

    # Update database_url to point at the correct database
    current_url = config.get("database_url", "postgresql://linkedout:linkedout@localhost:5432/linkedout")
    if enabled:
        config["database_url"] = get_demo_db_url(current_url)
    else:
        # Restore to the non-demo database name
        parsed = urlparse(current_url)
        config["database_url"] = urlunparse(parsed._replace(path="/linkedout"))

    # Atomic write: write to temp file, then rename
    config_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=config_path.parent, suffix=".yaml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)
        os.replace(tmp_path, config_path)
    except BaseException:
        # Clean up temp file on failure
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise
