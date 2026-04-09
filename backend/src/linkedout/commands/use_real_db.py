# SPDX-License-Identifier: Apache-2.0
"""``linkedout use-real-db`` — switch from demo mode to the real database.

Disables demo mode in config, optionally drops the demo database,
and regenerates ``agent-context.env``.
"""
import os
from pathlib import Path

import click
import yaml

from linkedout.cli_helpers import cli_logged
from linkedout.demo import is_demo_mode, set_demo_mode
from linkedout.demo.db_utils import drop_demo_database
from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="cli", operation="use_real_db")


def _get_data_dir() -> Path:
    return Path(os.environ.get("LINKEDOUT_DATA_DIR", os.path.expanduser("~/linkedout-data")))


def _read_database_url(data_dir: Path) -> str:
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
    return "postgresql://linkedout:linkedout@localhost:5432/linkedout"


@click.command("use-real-db")
@click.option("--drop-demo", is_flag=True, help="Also drop the demo database.")
@cli_logged("use_real_db")
def use_real_db_command(drop_demo: bool):
    """Switch from demo mode to your real database."""
    if not is_demo_mode():
        click.echo("Already using real database.")
        return

    data_dir = _get_data_dir()
    db_url = _read_database_url(data_dir)

    if drop_demo:
        click.echo("Dropping demo database...")
        if not drop_demo_database(db_url):
            click.echo("Warning: Could not drop demo database.", err=True)

    # Switch config to real database
    set_demo_mode(data_dir, enabled=False)
    click.echo("Switched to real database.")

    # Regenerate agent-context.env with the real database URL
    try:
        # Re-read the updated URL after set_demo_mode changed it
        real_db_url = _read_database_url(data_dir)
        from linkedout.setup.database import generate_agent_context_env

        generate_agent_context_env(real_db_url, data_dir)
        click.echo("Regenerated agent-context.env")
    except Exception as e:
        logger.warning(f"Could not regenerate agent-context.env: {e}")
        click.echo(f"Warning: Could not regenerate agent-context.env: {e}", err=True)

    click.echo("Run `linkedout setup` to continue setup.")
