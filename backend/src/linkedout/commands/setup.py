# SPDX-License-Identifier: Apache-2.0
"""``linkedout setup`` — run the LinkedOut setup flow."""
from pathlib import Path

import click


@click.command('setup')
@click.option(
    '--data-dir',
    type=click.Path(),
    default=None,
    help='Override data directory (default: ~/linkedout-data).',
)
def setup_command(data_dir: str | None):
    """Run the LinkedOut setup flow."""
    from linkedout.setup.orchestrator import run_setup

    run_setup(data_dir=Path(data_dir) if data_dir else None)
