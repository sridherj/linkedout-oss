# SPDX-License-Identifier: Apache-2.0
"""``linkedout upgrade`` — upgrade LinkedOut to the latest version."""
from __future__ import annotations

import click


@click.command('upgrade')
@click.option('--verbose', is_flag=True, help='Show detailed command output')
@click.option('--snooze', 'do_snooze', is_flag=True, help='Snooze update notification')
def upgrade_command(verbose: bool, do_snooze: bool) -> None:
    """Upgrade LinkedOut to the latest version."""
    if do_snooze:
        _handle_snooze()
        return

    from linkedout.upgrade.upgrader import Upgrader

    upgrader = Upgrader(verbose=verbose)

    # Detect install type
    install_type = upgrader.detect_install_type()
    if install_type != 'git_clone':
        click.echo(
            'ERROR: Cannot upgrade — this installation is not a git clone.\n\n'
            '  Only git clone installations are supported for automatic upgrades.\n'
            '  See https://github.com/sridherj/linkedout-oss for install instructions.'
        )
        raise SystemExit(1)

    click.echo('Checking for updates...')
    report = upgrader.run_upgrade()

    # Already up to date
    if report.from_version == report.to_version and not report.failures:
        click.echo(f'Already running the latest version (v{report.from_version}).')
        return

    # Failure
    if report.failures:
        click.echo()
        for failure in report.failures:
            click.echo(f'ERROR: {failure}')
        if report.rollback:
            click.echo()
            click.echo('To rollback to your previous version:')
            click.echo(report.rollback)
        report_path = _find_report_path(report)
        if report_path:
            click.echo()
            click.echo(f'Report saved: {report_path}')
        raise SystemExit(1)

    # Success
    click.echo(f'Upgrading LinkedOut from v{report.from_version} to v{report.to_version}...')
    click.echo()

    for step in report.steps:
        _print_step(step, verbose)

    if report.whats_new:
        click.echo()
        click.echo(report.whats_new)

    duration_s = report.duration_ms / 1000
    click.echo()
    click.echo(
        f'Upgrade complete: v{report.from_version} -> v{report.to_version} '
        f'({duration_s:.1f}s)'
    )

    report_path = _find_report_path(report)
    if report_path:
        click.echo()
        click.echo(f'Report saved: {report_path}')


def _print_step(step, verbose: bool) -> None:
    """Print a step's output following UX design doc format."""
    labels = {
        'pre_flight': 'Checking for updates...',
        'pull_code': 'Pulling latest code...',
        'update_deps': 'Updating Python dependencies...',
        'run_migrations': 'Running database migrations...',
        'version_scripts': 'Running version migration scripts...',
        'post_upgrade': 'Running post-upgrade health check...',
    }
    label = labels.get(step.step, step.step)

    if step.step == 'pre_flight':
        return  # Already printed above

    click.echo(label)
    if step.detail:
        click.echo(f'  {step.detail}')
    click.echo()


def _handle_snooze() -> None:
    """Handle --snooze: snooze update notification with confirmation."""
    from linkedout.upgrade.update_checker import (
        check_for_update,
        get_cached_update,
        get_snooze_duration,
        snooze_update,
    )

    # Try with skip_snooze so we can re-snooze an already-snoozed version
    info = check_for_update(skip_snooze=True)
    if info is None:
        # Network error — try cached data as fallback
        info = get_cached_update()

    if info is None:
        click.echo('Could not check for updates. Try again later.')
        return

    if not info.is_outdated:
        click.echo('Already running the latest version.')
        return

    duration = get_snooze_duration(info.latest_version)
    snooze_update(info.latest_version)

    duration_str = _format_duration(duration)
    click.echo(
        f"Update v{info.latest_version} snoozed for {duration_str}. "
        f"Run 'linkedout upgrade' when ready."
    )


def _format_duration(td) -> str:
    """Format a timedelta as a human-readable duration string."""
    hours = td.total_seconds() / 3600
    if hours <= 24:
        return '24 hours'
    elif hours <= 48:
        return '48 hours'
    else:
        return '1 week'


def _find_report_path(report) -> str | None:
    """Try to locate the saved report path from the reports directory."""
    from pathlib import Path

    reports_dir = Path.home() / 'linkedout-data' / 'reports'
    if not reports_dir.exists():
        return None
    # Find the most recent upgrade report
    reports = sorted(reports_dir.glob('upgrade-*.json'), reverse=True)
    if reports:
        return str(reports[0])
    return None
