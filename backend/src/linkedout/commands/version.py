# SPDX-License-Identifier: Apache-2.0
"""``linkedout version`` — show version information."""
import json
import sys
from pathlib import Path

import click


def _read_logo() -> str:
    """Read ASCII logo from docs/brand/logo-ascii.txt, falling back to a built-in copy."""
    logo_path = Path(__file__).resolve().parent.parent.parent.parent.parent / 'docs' / 'brand' / 'logo-ascii.txt'
    if logo_path.exists():
        return logo_path.read_text().rstrip('\n')

    return (
        ' _     _       _            _\n'
        '| |   (_)_ __ | | _____  __| |\n'
        '| |   | | \'_ \\| |/ / _ \\/ _` |\n'
        '| |___| | | | |   <  __/ (_| |\n'
        '|_____|_|_| |_|_|\\_\\___|\\__,_|\n'
        '                            \\\n'
        '                             \u2588\u2580\u2580\u2588 \u2588  \u2588 \u2580\u2588\u2580\n'
        '                             \u2588  \u2588 \u2588  \u2588  \u2588\n'
        '                             \u2588\u2584\u2584\u2588 \u2580\u2584\u2584\u2580  \u2588'
    )


def _handle_check(as_json: bool) -> None:
    """Handle the --check flag: fresh update check with exit code."""
    from linkedout.upgrade.update_checker import check_for_update
    from linkedout.version import __version__

    info = check_for_update(force=True, skip_snooze=True)

    if info is None:
        if as_json:
            click.echo(json.dumps({'error': 'Could not check for updates'}))
        else:
            click.echo('Could not check for updates. Try again later.')
        sys.exit(1)

    if as_json:
        click.echo(json.dumps({
            'update_available': info.is_outdated,
            'current': info.current_version,
            'latest': info.latest_version,
            'release_url': info.release_url,
        }, indent=2))
        sys.exit(1 if info.is_outdated else 0)

    if info.is_outdated:
        click.echo(
            f'Update available: v{info.current_version} -> v{info.latest_version}. '
            f'Run: linkedout upgrade'
        )
        sys.exit(1)
    else:
        click.echo(f'Up to date (v{info.current_version})')
        sys.exit(0)


@click.command('version')
@click.option('--json', 'as_json', is_flag=True, help='Output version info as JSON.')
@click.option('--check', 'check_update', is_flag=True, help='Check for available updates.')
def version_command(as_json: bool, check_update: bool):
    """Show version information."""
    if check_update:
        _handle_check(as_json)
        return

    from linkedout.version import __version__, get_version_info

    if as_json:
        click.echo(json.dumps(get_version_info(), indent=2))
        return

    info = get_version_info()
    click.echo(_read_logo())
    click.echo()
    click.echo(f"v{info['version']}")
    click.echo(f"Python {info['python_version']}")
    click.echo(f"PostgreSQL {info['pg_version']}")
    click.echo(f"Install path: {info['install_path']}")
    click.echo(f"Config: {info['config_path']}")
    click.echo(f"Data dir: {info['data_dir']}")
