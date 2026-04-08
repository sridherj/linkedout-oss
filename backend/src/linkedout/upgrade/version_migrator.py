# SPDX-License-Identifier: Apache-2.0
"""Version migration script discovery and execution.

Version migration scripts live in ``migrations/version/`` and follow the
naming convention ``v{from}_to_v{to}.py`` (e.g., ``v0_1_0_to_v0_2_0.py``).
Each script must define a ``migrate(config)`` function.
"""
from __future__ import annotations

import importlib.util
import re
import time
from pathlib import Path

from loguru import logger
from packaging.version import InvalidVersion, Version


def _repo_root() -> Path:
    """Return the repository root (parent of ``backend/``)."""
    return Path(__file__).resolve().parent.parent.parent.parent


_SCRIPT_PATTERN = re.compile(
    r'^v(\d+_\d+_\d+)_to_v(\d+_\d+_\d+)\.py$',
)


def _ver_from_underscores(s: str) -> str:
    """Convert ``0_1_0`` to ``0.1.0``."""
    return s.replace('_', '.')


def find_migration_scripts(
    from_ver: str,
    to_ver: str,
    *,
    scripts_dir: Path | None = None,
) -> list[Path]:
    """Find version migration scripts applicable to the upgrade range.

    Returns scripts whose *from* version is ``>= from_ver`` and whose
    *to* version is ``<= to_ver``, sorted by *to* version ascending.

    Args:
        from_ver: Version upgrading from (exclusive lower bound).
        to_ver: Version upgrading to (inclusive upper bound).
        scripts_dir: Override the scripts directory (for testing).
    """
    directory = scripts_dir or (_repo_root() / 'migrations' / 'version')
    if not directory.exists():
        return []

    try:
        from_v = Version(from_ver)
        to_v = Version(to_ver)
    except InvalidVersion:
        return []

    matches: list[tuple[Version, Path]] = []
    for path in directory.iterdir():
        if not path.is_file() or path.suffix != '.py':
            continue
        m = _SCRIPT_PATTERN.match(path.name)
        if not m:
            continue
        script_from = _ver_from_underscores(m.group(1))
        script_to = _ver_from_underscores(m.group(2))
        try:
            sf = Version(script_from)
            st = Version(script_to)
        except InvalidVersion:
            continue
        # Include scripts that bridge from >= from_ver to <= to_ver
        if sf >= from_v and st <= to_v:
            matches.append((st, path))

    matches.sort(key=lambda x: x[0])
    return [p for _, p in matches]


def run_version_migrations(
    from_ver: str,
    to_ver: str,
    config: object,
    *,
    scripts_dir: Path | None = None,
) -> list[dict]:
    """Execute version migration scripts in ascending version order.

    Each script is dynamically imported and its ``migrate(config)``
    function is called.

    Args:
        from_ver: Version upgrading from.
        to_ver: Version upgrading to.
        config: Application config object passed to each script's ``migrate()``.
        scripts_dir: Override the scripts directory (for testing).

    Returns:
        List of dicts with keys: ``script``, ``status``, ``duration_ms``, ``error``.
    """
    scripts = find_migration_scripts(from_ver, to_ver, scripts_dir=scripts_dir)
    results: list[dict] = []

    for script_path in scripts:
        logger.info('Running version migration script: {}', script_path.name)
        start = time.monotonic()
        try:
            spec = importlib.util.spec_from_file_location(
                f'version_migration.{script_path.stem}',
                script_path,
            )
            if spec is None or spec.loader is None:
                raise ImportError(f'Cannot load {script_path}')
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            if not hasattr(mod, 'migrate'):
                raise AttributeError(
                    f'Script {script_path.name} does not define a migrate() function'
                )
            mod.migrate(config)
            duration_ms = int((time.monotonic() - start) * 1000)
            results.append({
                'script': script_path.name,
                'status': 'success',
                'duration_ms': duration_ms,
                'error': None,
            })
            logger.info('Version migration {} completed ({}ms)', script_path.name, duration_ms)
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            results.append({
                'script': script_path.name,
                'status': 'failed',
                'duration_ms': duration_ms,
                'error': str(exc),
            })
            logger.error('Version migration {} failed: {}', script_path.name, exc)
            raise

    return results
