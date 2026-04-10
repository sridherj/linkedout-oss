# SPDX-License-Identifier: Apache-2.0
"""Version utilities — single source of truth from the repo-root ``VERSION`` file."""
import sys
from pathlib import Path


def _repo_root() -> Path:
    """Return the repository root (parent of ``backend/``)."""
    return Path(__file__).resolve().parent.parent.parent.parent


def _read_version_file() -> str:
    """Read and return the version string from the ``VERSION`` file.

    Raises ``FileNotFoundError`` with a clear message when the file is missing.
    """
    version_file = _repo_root() / 'VERSION'
    if not version_file.exists():
        raise FileNotFoundError(
            f'VERSION file not found at {version_file}. '
            'This file is the single source of truth for the LinkedOut version.'
        )
    return version_file.read_text().strip()


__version__: str = _read_version_file()


def get_version_info() -> dict:
    """Return a dict of version and environment information.

    Fields:
        version:      semver from VERSION file
        python_version: current Python interpreter version
        pg_version:   PostgreSQL server version, or "not connected"
        install_path: repository root path
        config_path:  expected config file path
        data_dir:     expected data directory
    """
    return {
        'version': __version__,
        'python_version': sys.version.split()[0],
        'pg_version': _pg_version(),
        'install_path': str(_repo_root()),
        'config_path': str(Path.home() / 'linkedout-data' / 'config' / 'config.yaml'),
        'data_dir': str(Path.home() / 'linkedout-data'),
    }


def _pg_version() -> str:
    """Query PostgreSQL for its version string, returning "not connected" on failure."""
    try:
        from sqlalchemy import text
        from shared.infra.db.cli_db import cli_db_manager
        from shared.infra.db.db_session_manager import DbSessionType
        db_manager = cli_db_manager()
        with db_manager.get_session(DbSessionType.READ) as session:
            row = session.execute(text('SELECT version()')).scalar()
            return row or 'not connected'
    except Exception:
        return 'not connected'
