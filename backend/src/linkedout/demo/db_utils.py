# SPDX-License-Identifier: Apache-2.0
"""Demo database utilities — create, drop, restore, and inspect the demo DB.

All database operations use subprocess with ``psql`` / ``pg_restore``,
matching the patterns in ``linkedout.setup.database`` and
``linkedout.commands.reset_db``.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from shared.utilities.logger import get_logger

from linkedout.demo import DEMO_DB_NAME

logger = get_logger(__name__, component="demo", operation="db_utils")


def check_pg_restore() -> bool:
    """Return True if ``pg_restore`` is available on the system PATH."""
    return shutil.which("pg_restore") is not None


def _build_maintenance_url(db_url: str) -> str:
    """Replace the database name with ``postgres`` for administrative commands.

    CREATE/DROP DATABASE cannot run against the target database itself,
    so we connect to the ``postgres`` maintenance database instead.
    """
    parsed = urlparse(db_url)
    return urlunparse(parsed._replace(path="/postgres"))


def create_demo_database(db_url: str) -> str:
    """Create the ``linkedout_demo`` database and return its connection URL.

    Connects to the ``postgres`` maintenance DB to issue CREATE DATABASE.
    If the database already exists, drops it first for a clean slate.

    Args:
        db_url: PostgreSQL connection string (any database on the same cluster).

    Returns:
        Connection URL for the newly created demo database.
    """
    maintenance_url = _build_maintenance_url(db_url)
    parsed = urlparse(db_url)
    demo_url = urlunparse(parsed._replace(path=f"/{DEMO_DB_NAME}"))

    # Drop if exists, then create
    drop_sql = f'DROP DATABASE IF EXISTS "{DEMO_DB_NAME}";'
    create_sql = f'CREATE DATABASE "{DEMO_DB_NAME}";'

    for label, sql in [("drop", drop_sql), ("create", create_sql)]:
        result = subprocess.run(
            ["psql", maintenance_url, "-c", sql],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to {label} demo database: {result.stderr.strip()}"
            )

    # Enable pgvector in the new database (usually inherited from template1)
    ext_sql = "CREATE EXTENSION IF NOT EXISTS vector;"
    result = subprocess.run(
        ["psql", demo_url, "-c", ext_sql],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "pgvector extension not available in demo database.\n"
            "This requires superuser privileges that the application cannot use directly.\n"
            'Run: sudo -u postgres psql -d template1 -c "CREATE EXTENSION IF NOT EXISTS vector;"\n'
            "Then retry."
        )

    logger.info(f"Created demo database: {DEMO_DB_NAME}")
    return demo_url


def drop_demo_database(db_url: str) -> bool:
    """Drop the ``linkedout_demo`` database if it exists.

    Args:
        db_url: PostgreSQL connection string (any database on the same cluster).

    Returns:
        True if the drop succeeded (or DB didn't exist), False on error.
    """
    maintenance_url = _build_maintenance_url(db_url)
    sql = f'DROP DATABASE IF EXISTS "{DEMO_DB_NAME}";'

    result = subprocess.run(
        ["psql", maintenance_url, "-c", sql],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        logger.error(f"Failed to drop demo database: {result.stderr.strip()}")
        return False

    logger.info(f"Dropped demo database: {DEMO_DB_NAME}")
    return True


def restore_demo_dump(demo_db_url: str, dump_path: Path) -> bool:
    """Restore a pg_dump file into the demo database.

    Uses ``pg_restore --clean --if-exists --no-owner`` so the command is
    idempotent — partial restores can be re-run safely.

    Args:
        demo_db_url: Connection URL for the demo database.
        dump_path: Path to the ``.dump`` file.

    Returns:
        True if restore succeeded, False otherwise.
    """
    if not dump_path.exists():
        raise FileNotFoundError(f"Dump file not found: {dump_path}")

    if not check_pg_restore():
        raise RuntimeError(
            "pg_restore not found. Install the PostgreSQL client package."
        )

    result = subprocess.run(
        [
            "pg_restore",
            f"--dbname={demo_db_url}",
            "--clean",
            "--if-exists",
            "--no-owner",
            str(dump_path),
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )

    # pg_restore returns 0 on success, 1 on warnings (e.g. "table does not exist" during --clean)
    if result.returncode not in (0, 1):
        logger.error(f"pg_restore failed (exit {result.returncode}): {result.stderr.strip()}")
        return False

    if result.returncode == 1 and result.stderr:
        logger.warning(f"pg_restore completed with warnings: {result.stderr.strip()[:500]}")

    logger.info(f"Restored demo dump from {dump_path}")
    return True


def get_demo_stats(demo_db_url: str) -> dict:
    """Query the demo database for record counts.

    Returns:
        Dict with keys ``profiles``, ``companies``, ``connections``.
        Values are integers, or -1 if the query failed.
    """
    stats = {}
    queries = {
        "profiles": "SELECT count(*) FROM crawled_profile;",
        "companies": "SELECT count(*) FROM company;",
        "connections": "SELECT count(*) FROM connection;",
    }

    for key, sql in queries.items():
        try:
            result = subprocess.run(
                ["psql", demo_db_url, "-t", "-A", "-c", sql],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                stats[key] = int(result.stdout.strip())
            else:
                stats[key] = -1
        except (subprocess.TimeoutExpired, ValueError):
            stats[key] = -1

    return stats
