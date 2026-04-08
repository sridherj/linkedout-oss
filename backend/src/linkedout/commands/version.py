# SPDX-License-Identifier: Apache-2.0
"""``linkedout version`` — show version information."""
import json
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


@click.command('version')
@click.option('--json', 'as_json', is_flag=True, help='Output version info as JSON.')
def version_command(as_json: bool):
    """Show version information."""
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
