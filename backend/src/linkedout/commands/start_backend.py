# SPDX-License-Identifier: Apache-2.0
"""``linkedout start-backend`` — start the LinkedOut API server.

Supports foreground (default) and background daemon modes. Background mode
writes a PID file and waits for a health check before returning.

Idempotent: detects existing processes on the target port and kills them
before starting fresh.
"""
import os
import signal as _signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import click


def _data_dir() -> Path:
    """Return the LinkedOut data directory, expanding ~."""
    return Path(os.environ.get('LINKEDOUT_DATA_DIR', os.path.expanduser('~/linkedout-data')))


def _pid_file() -> Path:
    return _data_dir() / 'state' / 'backend.pid'


def _log_file() -> Path:
    return _data_dir() / 'logs' / 'backend.log'


def _ensure_dirs() -> None:
    """Create state/ and logs/ directories if they don't exist."""
    _pid_file().parent.mkdir(parents=True, exist_ok=True)
    _log_file().parent.mkdir(parents=True, exist_ok=True)


def _kill_port(port: int) -> None:
    """Kill any process listening on the given port and wait for it to die."""
    try:
        result = subprocess.run(
            ['lsof', '-ti', f':{port}'],
            capture_output=True, text=True,
        )
        pids = [int(p) for p in result.stdout.strip().split('\n') if p]
        for pid in pids:
            try:
                os.kill(pid, _signal.SIGTERM)
                click.echo(f'Killed process {pid} on port {port}')
            except (ProcessLookupError, PermissionError):
                pass
        # Wait until the port is actually free
        for _ in range(40):
            check = subprocess.run(
                ['lsof', '-ti', f':{port}'], capture_output=True, text=True,
            )
            if not check.stdout.strip():
                break
            time.sleep(0.25)
        else:
            # Force kill if SIGTERM didn't work
            for pid in pids:
                try:
                    os.kill(pid, _signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
    except FileNotFoundError:
        # lsof not available, try fuser
        subprocess.run(['fuser', '-k', f'{port}/tcp'], capture_output=True)


def _cleanup_stale_pid() -> None:
    """Remove stale PID file if the recorded process is no longer running."""
    pid_path = _pid_file()
    if not pid_path.exists():
        return
    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, 0)  # check if alive
    except (ValueError, ProcessLookupError, PermissionError):
        pid_path.unlink(missing_ok=True)


def _wait_for_health(host: str, port: int, timeout: int = 10) -> bool:
    """Poll GET /health until it returns 200 or timeout expires."""
    url = f'http://{host}:{port}/health'
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = urlopen(url, timeout=2)
            if resp.status == 200:
                return True
        except (URLError, OSError, TimeoutError):
            pass
        time.sleep(0.5)
    return False


def _resolve_backend_dir() -> str:
    """Return the backend/ directory (where main.py lives)."""
    # This file is at backend/src/linkedout/commands/start_backend.py
    return str(Path(__file__).resolve().parent.parent.parent.parent)


@click.command('start-backend')
@click.option('--port', default=None, type=int, help='Bind port (default: 8001, from config/env)')
@click.option('--host', default=None, help='Bind host (default: 127.0.0.1, from config/env)')
@click.option('--background', is_flag=True, help='Run as background daemon')
def start_backend_command(port: int | None, host: str | None, background: bool):
    """Start the LinkedOut API server.

    Only needed when using the Chrome extension. The extension communicates
    with this server for profile crawling and enrichment.

    Idempotent: if a process is already running on the target port, it will
    be killed before starting fresh.
    """
    from shared.config import get_config

    config = get_config()

    # CLI flags override config/env defaults
    port = port or config.backend_port
    host = host or config.backend_host

    _ensure_dirs()
    _cleanup_stale_pid()

    # Idempotent: kill anything on the target port
    _kill_port(port)

    backend_dir = _resolve_backend_dir()
    log_path = _log_file()

    if background:
        click.echo(f'Starting backend on {host}:{port} (background)...')

        log_fh = open(log_path, 'a')
        proc = subprocess.Popen(
            [sys.executable, '-m', 'uvicorn', 'main:app', '--host', host, '--port', str(port)],
            cwd=backend_dir,
            stdout=log_fh,
            stderr=log_fh,
            start_new_session=True,
            env={**os.environ, 'PYTHONPATH': str(Path(backend_dir) / 'src')},
        )

        # Write PID file
        _pid_file().write_text(str(proc.pid))

        # Wait for health check
        if _wait_for_health(host, port, timeout=10):
            click.echo(f'Backend started on http://{host}:{port} (PID: {proc.pid})')
            click.echo(f'Logs: {log_path}')
        else:
            click.echo(
                f'ERROR: Backend failed to start within 10 seconds.\n\n'
                f'  Check the logs: {log_path}\n'
                f'  Try running in foreground to see errors:\n'
                f'    linkedout start-backend --port {port}\n\n'
                f'  Common issues:\n'
                f'    - DATABASE_URL not configured (run: linkedout setup)\n'
                f'    - Port {port} still in use (run: linkedout stop-backend)',
                err=True,
            )
            # Kill the failed process
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass
            _pid_file().unlink(missing_ok=True)
            raise SystemExit(1)
    else:
        import uvicorn

        click.echo(f'Starting backend on http://{host}:{port}...')
        click.echo(f'Logs also written to: {log_path}')
        click.echo('Press Ctrl+C to stop.\n')

        # Write PID for status reporting (foreground still benefits from it)
        _pid_file().write_text(str(os.getpid()))

        try:
            uvicorn.run(
                'main:app',
                app_dir=backend_dir,
                host=host,
                port=port,
                reload=False,
                log_level='info',
            )
        finally:
            _pid_file().unlink(missing_ok=True)
