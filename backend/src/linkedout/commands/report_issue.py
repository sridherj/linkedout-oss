# SPDX-License-Identifier: Apache-2.0
"""``linkedout report-issue`` — generate a diagnostic bundle for bug reports."""
import click


@click.command('report-issue')
@click.option('--dry-run', is_flag=True, help='Show the redacted report without filing an issue')
def report_issue_command(dry_run: bool):
    """Generate a diagnostic bundle for bug reports."""
    click.echo("Not yet implemented -- coming in Phase 3")
    raise SystemExit(0)
