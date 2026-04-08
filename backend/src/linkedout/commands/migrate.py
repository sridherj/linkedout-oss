# SPDX-License-Identifier: Apache-2.0
"""``linkedout migrate`` — run database migrations (internal).

Wraps ``alembic upgrade head`` with ``--dry-run`` support.
Hidden from main help text.
"""
import subprocess
import sys

import click


@click.command('migrate', hidden=True)
@click.option('--dry-run', is_flag=True, help='Preview migrations without applying')
def migrate_command(dry_run: bool):
    """Run database migrations (internal)."""
    if dry_run:
        click.echo('Pending migrations:')
        result = subprocess.run(
            ['alembic', 'history', '--indicate-current', '-v'],
            capture_output=True,
            text=True,
        )
        click.echo(result.stdout)
        if result.returncode != 0 and result.stderr:
            click.echo(result.stderr, err=True)
        return

    click.echo('Running migrations...')
    result = subprocess.run(
        ['alembic', 'upgrade', 'head'],
        capture_output=True,
        text=True,
    )
    click.echo(result.stdout)
    if result.returncode != 0:
        click.echo('Migration failed.', err=True)
        if result.stderr:
            click.echo(result.stderr, err=True)
        sys.exit(result.returncode)
    click.echo('Migrations applied successfully.')
