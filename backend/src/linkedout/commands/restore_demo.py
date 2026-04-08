# SPDX-License-Identifier: Apache-2.0
"""``linkedout restore-demo`` — restore the demo database from a cached dump.

Creates the ``linkedout_demo`` database, restores the pg_dump, updates
config to demo mode, and regenerates ``agent-context.env``. Idempotent —
safe to re-run (drops and recreates the database each time).
"""
import os
import time
from pathlib import Path

import click
import yaml

from linkedout.cli_helpers import cli_logged
from linkedout.demo import (
    DEMO_CACHE_DIR,
    DEMO_DB_NAME,
    DEMO_DUMP_FILENAME,
    set_demo_mode,
)
from linkedout.demo.db_utils import (
    check_pg_restore,
    create_demo_database,
    get_demo_stats,
    restore_demo_dump,
)
from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="cli", operation="restore_demo")


def _get_data_dir() -> Path:
    """Get the LinkedOut data directory, respecting LINKEDOUT_DATA_DIR."""
    return Path(os.environ.get("LINKEDOUT_DATA_DIR", os.path.expanduser("~/linkedout-data")))


def _read_database_url(data_dir: Path) -> str:
    """Read the current database_url from config.yaml.

    Falls back to a default local connection string if config is missing.
    """
    config_path = data_dir / "config" / "config.yaml"
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            url = config.get("database_url")
            if url:
                return url
        except (OSError, yaml.YAMLError):
            pass

    return "postgresql://linkedout:@localhost:5432/linkedout"


@click.command("restore-demo")
@cli_logged("restore_demo")
def restore_demo_command():
    """Restore the demo database from a cached dump file."""
    start = time.time()
    data_dir = _get_data_dir()

    # 1. Check pg_restore is available
    if not check_pg_restore():
        raise click.ClickException(
            "pg_restore not found. Install the PostgreSQL client package "
            "(e.g., `sudo apt install postgresql-client`)."
        )

    # 2. Check dump file exists
    dump_path = data_dir / DEMO_CACHE_DIR / DEMO_DUMP_FILENAME
    if not dump_path.exists():
        raise click.ClickException(
            f"Demo dump not found at {dump_path}.\n"
            f"Run `linkedout download-demo` first."
        )

    # 3. Read current database URL for connection credentials
    db_url = _read_database_url(data_dir)
    click.echo(f"Creating database: {DEMO_DB_NAME}")

    # 4. Create demo database (drop + create + pgvector)
    try:
        demo_db_url = create_demo_database(db_url)
    except RuntimeError as e:
        raise click.ClickException(str(e))

    # 5. Restore the dump
    click.echo(f"Restoring demo data from {dump_path.name}...")
    if not restore_demo_dump(demo_db_url, dump_path):
        raise click.ClickException(
            "pg_restore failed. Check the logs for details. "
            "You can safely re-run this command to retry."
        )

    # 6. Update config to demo mode
    click.echo("Updating configuration...")
    set_demo_mode(data_dir, enabled=True)

    # 7. Regenerate agent-context.env
    try:
        from linkedout.setup.database import generate_agent_context_env
        generate_agent_context_env(demo_db_url, data_dir)
        click.echo("Regenerated agent-context.env")
    except Exception as e:
        logger.warning(f"Could not regenerate agent-context.env: {e}")
        click.echo(f"Warning: Could not regenerate agent-context.env: {e}", err=True)

    # 8. Print summary
    elapsed = time.time() - start
    click.echo(f"\nDemo database restored in {elapsed:.1f}s")

    stats = get_demo_stats(demo_db_url)
    if stats.get("profiles", -1) >= 0:
        click.echo(f"  Profiles:    {stats['profiles']:,}")
        click.echo(f"  Companies:   {stats['companies']:,}")
        click.echo(f"  Connections: {stats['connections']:,}")

    click.echo(f"\nDemo mode is now active.")

    from linkedout.demo.sample_queries import format_demo_profile, format_sample_queries

    click.echo()
    click.echo(format_demo_profile())
    click.echo(format_sample_queries())

    click.echo(f"\nNext steps:")
    click.echo(f"  linkedout status          # verify demo mode")
    click.echo(f"  linkedout start-backend   # launch the API server")
    click.echo(f"  linkedout demo-help       # see these queries again")

    logger.info(f"Demo restore completed in {elapsed:.1f}s")
