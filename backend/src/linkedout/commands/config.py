# SPDX-License-Identifier: Apache-2.0
"""``linkedout config`` — view or modify configuration.

Currently supports ``config path`` only. Full impl in Phase 2.
"""
from pathlib import Path

import click


@click.group('config')
def config_group():
    """View or modify configuration."""


@config_group.command('path')
def config_path():
    """Show config file location."""
    config_path = Path.home() / '.linkedout' / 'config.yaml'
    click.echo(str(config_path))


@config_group.command('show')
def config_show():
    """Show current config (secrets redacted)."""
    click.echo("Not yet implemented -- coming in Phase 2")
    raise SystemExit(0)
