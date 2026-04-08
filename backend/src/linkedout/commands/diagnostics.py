# SPDX-License-Identifier: Apache-2.0
"""``linkedout diagnostics`` — check system health and configuration.

Produces a comprehensive, shareable system health report. Designed to be
pasted directly into a GitHub issue for troubleshooting.
"""
import json as _json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

from linkedout.cli_helpers import cli_logged
from shared.utilities.logger import get_logger

logger = get_logger(__name__, component='cli', operation='diagnostics')


def _data_dir() -> Path:
    return Path(os.environ.get('LINKEDOUT_DATA_DIR', os.path.expanduser('~/linkedout-data')))


def _reports_dir() -> Path:
    return Path(os.environ.get(
        'LINKEDOUT_REPORTS_DIR',
        str(_data_dir() / 'reports'),
    ))


def _get_linkedout_version() -> str:
    try:
        from linkedout.version import __version__
        return __version__
    except Exception:
        version_file = Path(__file__).parent.parent.parent.parent.parent / 'VERSION'
        if version_file.exists():
            return version_file.read_text().strip()
        return 'unknown'


def _get_pg_version() -> str:
    try:
        result = subprocess.run(
            ['psql', '--version'], capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip().split()[-1]
    except Exception:
        pass
    return 'unknown'


def _get_data_dir_size_mb() -> float:
    data_dir = _data_dir()
    if not data_dir.exists():
        return 0.0
    total = sum(f.stat().st_size for f in data_dir.rglob('*') if f.is_file())
    return total / (1024 * 1024)


def _collect_system_info() -> dict:
    disk = shutil.disk_usage(_data_dir() if _data_dir().exists() else Path.home())
    return {
        'os': f'{platform.system()} {platform.release()}',
        'python': platform.python_version(),
        'postgresql': _get_pg_version(),
        'linkedout_version': _get_linkedout_version(),
        'disk_free_gb': round(disk.free / (1024 ** 3), 1),
        'data_dir': str(_data_dir()),
        'data_dir_size_mb': round(_get_data_dir_size_mb(), 1),
    }


def _collect_config_info() -> dict:
    try:
        from shared.config import get_config
        settings = get_config()
        return {
            'embedding_provider': settings.embedding.provider,
            'embedding_model': settings.embedding.model,
            'backend_port': settings.backend_port,
            'api_keys': {
                'openai': 'configured' if settings.openai_api_key else 'not configured',
                'apify': 'configured' if settings.apify_api_key else 'not configured',
            },
        }
    except Exception as e:
        return {'error': str(e)}


def _collect_health_checks() -> list[dict]:
    from shared.utilities.health_checks import (
        check_api_keys,
        check_db_connection,
        check_disk_space,
        check_embedding_model,
    )

    results = []
    for check_fn in [check_db_connection, check_embedding_model, check_disk_space]:
        r = check_fn()
        results.append({'check': r.check, 'status': r.status, 'detail': r.detail})

    for r in check_api_keys():
        results.append({'check': r.check, 'status': r.status, 'detail': r.detail})

    return results


def _collect_db_stats() -> dict:
    try:
        from shared.utilities.health_checks import check_db_connection, get_db_stats
        db_result = check_db_connection()
        if db_result.status != 'pass':
            return {'connected': False}
        stats = get_db_stats()
        stats['connected'] = True
        return stats
    except Exception as e:
        return {'connected': False, 'error': str(e)}


def _build_report() -> dict:
    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'system': _collect_system_info(),
        'config': _collect_config_info(),
        'database': _collect_db_stats(),
        'health_checks': _collect_health_checks(),
    }


def _save_report(report: dict) -> Path:
    reports_dir = _reports_dir()
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    path = reports_dir / f'diagnostic-{ts}.json'
    path.write_text(_json.dumps(report, indent=2))
    return path


def _print_human_readable(report: dict) -> None:
    """Print a human-readable diagnostic summary."""
    sys_info = report.get('system', {})
    config = report.get('config', {})
    db = report.get('database', {})
    checks = report.get('health_checks', [])

    click.echo('\n=== System ===')
    click.echo(f'  LinkedOut:   v{sys_info.get("linkedout_version", "?")}')
    click.echo(f'  OS:          {sys_info.get("os", "?")}')
    click.echo(f'  Python:      {sys_info.get("python", "?")}')
    click.echo(f'  PostgreSQL:  {sys_info.get("postgresql", "?")}')
    click.echo(f'  Disk free:   {sys_info.get("disk_free_gb", "?")} GB')
    click.echo(f'  Data dir:    {sys_info.get("data_dir", "?")} ({sys_info.get("data_dir_size_mb", 0)} MB)')

    click.echo('\n=== Config ===')
    click.echo(f'  Embedding:   {config.get("embedding_provider", "?")}/{config.get("embedding_model", "?")}')
    api_keys = config.get('api_keys', {})
    for name, status in api_keys.items():
        click.echo(f'  {name + " key:":13s}{status}')

    click.echo('\n=== Database ===')
    if db.get('connected'):
        click.echo(f'  Connected:   yes')
        click.echo(f'  Profiles:    {db.get("profiles_total", 0):,}')
        click.echo(f'  Companies:   {db.get("companies_total", 0):,}')
        click.echo(f'  Connections: {db.get("connections_total", 0):,}')
        with_emb = db.get('profiles_with_embeddings', 0)
        total = db.get('profiles_total', 0)
        pct = (with_emb / total * 100) if total > 0 else 0
        click.echo(f'  Embeddings:  {with_emb:,}/{total:,} ({pct:.1f}%)')
        click.echo(f'  Schema:      {db.get("schema_version", "?")}')
    else:
        click.echo(f'  Connected:   NO')
        if 'error' in db:
            click.echo(f'  Error:       {db["error"]}')

    click.echo('\n=== Health Checks ===')
    for c in checks:
        icon = {'pass': 'OK', 'fail': 'FAIL', 'skip': 'SKIP'}.get(c['status'], '?')
        detail = f' — {c["detail"]}' if c.get('detail') else ''
        click.echo(f'  [{icon:4s}] {c["check"]}{detail}')

    # Recommendations
    recommendations = []
    if not db.get('connected'):
        recommendations.append('Database is not connected. Check DATABASE_URL and PostgreSQL status.')
    if db.get('profiles_without_embeddings', 0) > 0:
        count = db['profiles_without_embeddings']
        recommendations.append(f'{count:,} profiles without embeddings. Run `linkedout embed`.')
    for c in checks:
        if c['status'] == 'fail' and c['check'] == 'disk_space':
            recommendations.append('Low disk space. Free up space in the data directory.')

    if recommendations:
        click.echo('\n=== Recommendations ===')
        for r in recommendations:
            click.echo(f'  - {r}')


def _run_repair(report: dict) -> None:
    """Detect and offer to fix common issues."""
    db = report.get('database', {})

    if not db.get('connected'):
        click.echo('\nRepair: Database not connected — cannot run auto-repair.')
        return

    fixes_offered = 0

    without_emb = db.get('profiles_without_embeddings', 0)
    if without_emb > 0:
        fixes_offered += 1
        if click.confirm(f'\n{without_emb:,} profiles lack embeddings. Run `linkedout embed` now?'):
            click.echo('Running: linkedout embed')
            try:
                subprocess.run([sys.executable, '-m', 'linkedout.cli', 'embed'], check=False)
            except Exception as e:
                click.echo(f'  Failed: {e}', err=True)

    if fixes_offered == 0:
        click.echo('\nNo issues found that can be auto-repaired.')


@click.command('diagnostics')
@click.option('--repair', is_flag=True, help='Auto-fix common issues')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
@click.option('--output', 'output_path', default=None, help='Write report to file')
@cli_logged("diagnostics")
def diagnostics_command(repair: bool, output_json: bool, output_path: str | None):
    """Check system health and configuration."""
    report = _build_report()

    # Save report
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_json.dumps(report, indent=2))
    else:
        path = _save_report(report)

    if output_json:
        click.echo(_json.dumps(report, indent=2))
    else:
        _print_human_readable(report)

        try:
            display = '~/' + str(path.relative_to(Path.home()))
        except ValueError:
            display = str(path)
        click.echo(f'\nReport saved: {display}')

    if repair:
        _run_repair(report)
