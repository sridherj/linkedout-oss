# SPDX-License-Identifier: Apache-2.0
"""``linkedout stop-backend`` — stop the LinkedOut API server.

Reads the PID file written by ``start-backend --background``, sends SIGTERM,
waits up to 10 seconds, then SIGKILL if the process is still alive.
"""
import os
import signal as _signal
import time
from pathlib import Path

import click


def _data_dir() -> Path:
    return Path(os.environ.get('LINKEDOUT_DATA_DIR', os.path.expanduser('~/linkedout-data')))


def _pid_file() -> Path:
    return _data_dir() / 'state' / 'backend.pid'


def _process_alive(pid: int) -> bool:
    """Check if a process with the given PID is running."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


@click.command('stop-backend')
def stop_backend_command():
    """Stop the LinkedOut API server.

    Reads the PID from ~/linkedout-data/state/backend.pid, sends SIGTERM,
    and waits for the process to exit. Falls back to SIGKILL after 10 seconds.
    """
    pid_path = _pid_file()

    if not pid_path.exists():
        click.echo('Backend is not running.')
        return

    try:
        pid = int(pid_path.read_text().strip())
    except (ValueError, OSError):
        click.echo('Backend is not running. (corrupt PID file removed)')
        pid_path.unlink(missing_ok=True)
        return

    if not _process_alive(pid):
        click.echo('Backend is not running. (stale PID file removed)')
        pid_path.unlink(missing_ok=True)
        return

    # Send SIGTERM and wait
    click.echo(f'Stopping backend (PID {pid})...')
    try:
        os.kill(pid, _signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        click.echo('Backend is not running.')
        pid_path.unlink(missing_ok=True)
        return

    # Wait up to 10 seconds for graceful shutdown
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if not _process_alive(pid):
            break
        time.sleep(0.25)
    else:
        # Force kill if still alive
        click.echo(f'Process {pid} did not exit gracefully, sending SIGKILL...')
        try:
            os.kill(pid, _signal.SIGKILL)
            time.sleep(0.5)
        except (ProcessLookupError, PermissionError):
            pass

    pid_path.unlink(missing_ok=True)
    click.echo('Backend stopped.')
