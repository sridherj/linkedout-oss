# SPDX-License-Identifier: Apache-2.0
"""``linkedout config`` — view or modify configuration."""
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
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def config_show(output_json: bool):
    """Show current config with secrets redacted."""
    import json as json_mod

    from shared.config import get_config

    settings = get_config()

    data = {
        'embedding_provider': settings.embedding.provider,
        'embedding_model': settings.embedding.model,
        'database_url': '***' if settings.database_url else 'not configured',
        'data_dir': str(settings.data_dir),
        'demo_mode': settings.demo_mode,
        'backend_port': settings.backend_port,
        'api_keys': {
            'openai': 'configured' if settings.openai_api_key else 'not configured',
            'apify': 'configured' if settings.apify_api_key else 'not configured',
        },
    }

    if output_json:
        click.echo(json_mod.dumps(data, indent=2))
    else:
        for key, value in data.items():
            if isinstance(value, dict):
                for k, v in value.items():
                    click.echo(f'{key}.{k}: {v}')
            else:
                click.echo(f'{key}: {value}')
