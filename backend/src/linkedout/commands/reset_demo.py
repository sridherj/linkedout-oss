# SPDX-License-Identifier: Apache-2.0
"""``linkedout reset-demo`` — reset the demo database to its original state.

Drops and re-restores ``linkedout_demo`` from the cached dump file
without re-downloading. Instant reset for experimentation.
"""
import os
from pathlib import Path

import click

from linkedout.cli_helpers import cli_logged
from linkedout.demo import DEMO_CACHE_DIR, DEMO_DB_NAME, DEMO_DUMP_FILENAME, is_demo_mode
from linkedout.demo.db_utils import (
    check_pg_restore,
    create_demo_database,
    get_demo_stats,
    restore_demo_dump,
)
from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="cli", operation="reset_demo")


def _get_data_dir() -> Path:
    return Path(os.environ.get("LINKEDOUT_DATA_DIR", os.path.expanduser("~/linkedout-data")))


@click.command("reset-demo")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
@cli_logged("reset_demo")
def reset_demo_command(yes: bool):
    """Reset the demo database to its original state (re-restore from cache)."""
    data_dir = _get_data_dir()

    if not is_demo_mode():
        raise click.ClickException(
            "Not in demo mode. Run `linkedout restore-demo` to set up demo mode first."
        )

    if not check_pg_restore():
        raise click.ClickException(
            "pg_restore not found. Install the PostgreSQL client package "
            "(e.g., `sudo apt install postgresql-client`)."
        )

    dump_path = data_dir / DEMO_CACHE_DIR / DEMO_DUMP_FILENAME
    if not dump_path.exists():
        raise click.ClickException(
            f"Demo dump not found at {dump_path}.\n"
            f"Run `linkedout download-demo` first."
        )

    if not yes:
        click.confirm(
            "This will drop and re-create the demo database. Continue?",
            abort=True,
        )

    # Read current database URL for connection credentials
    import yaml

    config_path = data_dir / "config" / "config.yaml"
    db_url = "postgresql://linkedout:linkedout@localhost:5432/linkedout"
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            db_url = config.get("database_url", db_url)
        except (OSError, yaml.YAMLError):
            pass

    click.echo(f"Resetting database: {DEMO_DB_NAME}")

    try:
        demo_db_url = create_demo_database(db_url)
    except RuntimeError as e:
        raise click.ClickException(str(e))

    click.echo(f"Restoring demo data from {dump_path.name}...")
    if not restore_demo_dump(demo_db_url, dump_path):
        raise click.ClickException(
            "pg_restore failed. Check the logs for details. "
            "You can safely re-run this command to retry."
        )

    stats = get_demo_stats(demo_db_url)
    click.echo("Demo database reset to original state.")
    if stats.get("profiles", -1) >= 0:
        click.echo(f"  Profiles:    {stats['profiles']:,}")
        click.echo(f"  Companies:   {stats['companies']:,}")
        click.echo(f"  Connections: {stats['connections']:,}")
