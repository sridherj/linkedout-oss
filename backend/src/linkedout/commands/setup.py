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
@click.option(
    '--demo',
    is_flag=True,
    default=False,
    help='Use demo data (skip interactive prompt).',
)
@click.option(
    '--full',
    is_flag=True,
    default=False,
    help='Full setup with your own data (skip interactive prompt).',
)
def setup_command(data_dir: str | None, demo: bool, full: bool):
    """Run the LinkedOut setup flow."""
    if demo and full:
        raise click.UsageError('Cannot use both --demo and --full.')

    from linkedout.setup.orchestrator import run_setup

    # Map flags to demo_choice: True=demo, False=full, None=ask interactively
    demo_choice: bool | None = None
    if demo:
        demo_choice = True
    elif full:
        demo_choice = False

    run_setup(data_dir=Path(data_dir) if data_dir else None, demo_choice=demo_choice)
