# SPDX-License-Identifier: Apache-2.0
"""``linkedout status`` — quick system health check.

Reports DB connectivity, profile/company counts, embedding coverage,
backend server status, and demo mode indicator.
"""
import json as _json
import os
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

import click


def _data_dir() -> Path:
    return Path(os.environ.get('LINKEDOUT_DATA_DIR', os.path.expanduser('~/linkedout-data')))


def _pid_file() -> Path:
    return _data_dir() / 'state' / 'backend.pid'


def _check_backend(port: int) -> dict:
    """Check if the backend is running via PID file and health endpoint.

    Returns a dict with keys: running (bool), pid (int|None), port (int).
    """
    result = {'running': False, 'pid': None, 'port': port}
    pid_path = _pid_file()

    # Check PID file
    if pid_path.exists():
        try:
            pid = int(pid_path.read_text().strip())
            os.kill(pid, 0)  # check alive
            result['pid'] = pid
        except (ValueError, ProcessLookupError, PermissionError, OSError):
            pass

    # Check health endpoint
    try:
        resp = urlopen(f'http://localhost:{port}/health', timeout=2)
        if resp.status == 200:
            result['running'] = True
            return result
    except (URLError, OSError, TimeoutError):
        pass

    # PID exists but health check failed — still report as running if PID is alive
    if result['pid'] is not None:
        result['running'] = True

    return result


@click.command('status')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def status_command(output_json: bool):
    """Show current system status."""
    from linkedout.version import __version__

    # --- DB check ---
    db_ok = False
    profiles = 0
    companies = 0
    embedding_pct = 0.0
    demo_mode = False
    database_name = 'linkedout'
    try:
        from shared.config import get_config
        from shared.utilities.health_checks import check_db_connection, get_db_stats

        config = get_config()
        port = config.backend_port
        demo_mode = config.demo_mode
        database_name = urlparse(config.database_url).path.lstrip('/')

        db_result = check_db_connection()
        db_ok = db_result.status == 'pass'

        if db_ok:
            stats = get_db_stats()
            profiles = stats.get('profiles_total', 0)
            companies = stats.get('companies_total', 0)
            total = stats.get('profiles_total', 0)
            with_emb = stats.get('profiles_with_embeddings', 0)
            embedding_pct = (with_emb / total * 100) if total > 0 else 0.0
    except Exception:
        from shared.config import get_config
        config = get_config()
        port = config.backend_port
        demo_mode = config.demo_mode
        database_name = urlparse(config.database_url).path.lstrip('/')

    # --- Backend check ---
    backend = _check_backend(port)

    if output_json:
        data = {
            'version': __version__,
            'demo_mode': demo_mode,
            'database_name': database_name,
            'db_connected': db_ok,
            'profiles': profiles,
            'companies': companies,
            'embedding_coverage_pct': round(embedding_pct, 1),
            'backend': {
                'running': backend['running'],
                'pid': backend['pid'],
                'port': backend['port'],
            },
        }
        click.echo(_json.dumps(data, indent=2))
    else:
        db_label = f'DB: {database_name}'
        if demo_mode:
            db_label += ' (demo)'
        db_status = 'connected' if db_ok else 'NOT connected'
        backend_status = (
            f"running (PID {backend['pid']}, port {backend['port']})"
            if backend['running']
            else 'not running'
        )

        title = 'LinkedOut v{}'.format(__version__)
        if demo_mode:
            title += ' [DEMO]'

        parts = [
            title,
            db_label,
            f'{profiles:,} profiles',
            f'{companies:,} companies',
            f'embeddings: {embedding_pct:.1f}%',
            f'backend: {backend_status}',
        ]
        if not db_ok:
            parts = [title, db_label, f'DB: {db_status}', f'backend: {backend_status}']

        click.echo(' | '.join(parts))
