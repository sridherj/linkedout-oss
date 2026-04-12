# SPDX-License-Identifier: Apache-2.0
"""Virtual environment creation and package installation.

Handles ``.venv`` creation in the repo root, dependency installation
via ``uv`` (system-installed), CLI entry point verification,
and optional local embedding model pre-download.

All operations are idempotent:
- Skips venv creation if ``.venv/`` exists and is valid
- Always runs dependency install (catches new deps after upgrade)
"""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from linkedout.setup.logging_integration import get_setup_logger
from shared.utilities.operation_report import OperationCounts, OperationReport

_SUBPROCESS_TIMEOUT = 600  # 10 minutes for package installation


def create_venv(repo_root: Path) -> bool:
    """Create a Python virtual environment in the repo root.

    Creates ``.venv/`` using ``python3 -m venv``. Skips creation if
    the venv already exists and has a working Python interpreter.

    Args:
        repo_root: Path to the repository root.

    Returns:
        True if a new venv was created, False if it already existed.
    """
    log = get_setup_logger('python_env')
    venv_path = repo_root / '.venv'
    python_path = venv_path / 'bin' / 'python3'

    # Check if venv already exists and is valid
    if python_path.exists():
        try:
            result = subprocess.run(
                [str(python_path), '--version'],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                log.info('Virtual environment already exists at {}', venv_path)
                return False
        except (subprocess.TimeoutExpired, OSError):
            log.warning('Existing venv is broken, recreating...')

    log.info('Creating virtual environment at {}', venv_path)
    result = subprocess.run(
        ['python3', '-m', 'venv', str(venv_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f'Failed to create venv: {result.stderr.strip()}'
        )

    log.info('Virtual environment created at {}', venv_path)
    return True


def install_dependencies(repo_root: Path) -> OperationReport:
    """Install Python dependencies via uv.

    Uses the system ``uv`` (installed by ``./setup``) directly.
    Falls back to pip if uv is not available.

    Args:
        repo_root: Path to the repository root.

    Returns:
        OperationReport with installation results.
    """
    log = get_setup_logger('python_env')
    start = time.monotonic()
    requirements = repo_root / 'backend' / 'requirements.txt'

    # Find uv: prefer venv copy, then system
    venv_uv = repo_root / '.venv' / 'bin' / 'uv'
    if venv_uv.exists():
        uv_cmd = str(venv_uv)
    elif shutil.which('uv'):
        uv_cmd = 'uv'
    else:
        log.warning('uv not found, falling back to pip')
        return _install_via_pip(repo_root, start)

    # Step 1: Install requirements.txt via uv
    log.info('Installing dependencies via uv...')
    result = subprocess.run(
        [uv_cmd, 'pip', 'install', '-r', str(requirements)],
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
    )
    if result.returncode != 0:
        log.error('uv pip install failed: {}', result.stderr.strip())
        duration_ms = (time.monotonic() - start) * 1000
        return OperationReport(
            operation='python-env-install',
            duration_ms=duration_ms,
            counts=OperationCounts(total=2, succeeded=1, failed=1),
            next_steps=['Check requirements.txt and try: .venv/bin/pip install -r backend/requirements.txt'],
        )

    # Step 2: Install backend as editable package
    log.info('Installing backend package (editable)...')
    backend_dir = repo_root / 'backend'
    result = subprocess.run(
        [uv_cmd, 'pip', 'install', '-e', str(backend_dir)],
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
    )
    if result.returncode != 0:
        log.error('Editable install failed: {}', result.stderr.strip())
        duration_ms = (time.monotonic() - start) * 1000
        return OperationReport(
            operation='python-env-install',
            duration_ms=duration_ms,
            counts=OperationCounts(total=2, succeeded=1, failed=1),
            next_steps=['Check backend/pyproject.toml and try: .venv/bin/pip install -e backend/'],
        )

    duration_ms = (time.monotonic() - start) * 1000
    log.info('Dependencies installed in {:.1f}s', duration_ms / 1000)

    return OperationReport(
        operation='python-env-install',
        duration_ms=duration_ms,
        counts=OperationCounts(total=2, succeeded=2),
    )


def verify_cli(repo_root: Path) -> bool:
    """Verify the CLI entry point works.

    Runs ``.venv/bin/linkedout --help`` and checks for a successful
    exit code.

    Args:
        repo_root: Path to the repository root.

    Returns:
        True if the CLI entry point is working.
    """
    log = get_setup_logger('python_env')
    linkedout_cmd = repo_root / '.venv' / 'bin' / 'linkedout'

    if not linkedout_cmd.exists():
        log.warning('linkedout CLI not found at {}', linkedout_cmd)
        return False

    try:
        result = subprocess.run(
            [str(linkedout_cmd), '--help'],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            log.info('CLI entry point verified: linkedout --help OK')
            return True
        log.warning('linkedout --help exited with code {}', result.returncode)
        return False
    except (subprocess.TimeoutExpired, OSError) as e:
        log.warning('CLI verification failed: {}', e)
        return False


def pre_download_model(provider: str) -> bool:
    """Pre-download the local embedding model if provider is 'local'.

    Downloads nomic-embed-text-v1.5 (~275MB) so the user doesn't wait
    during embedding generation.

    Args:
        provider: The embedding provider name (``"local"`` or ``"openai"``).

    Returns:
        True if a model was downloaded, False if skipped or failed.
    """
    log = get_setup_logger('python_env')

    if provider != 'local':
        log.info('Embedding provider is {!r}, skipping model pre-download', provider)
        return False

    log.info('Pre-downloading nomic-embed-text-v1.5 (~275MB)...')
    try:
        result = subprocess.run(
            [
                'python3', '-c',
                'from sentence_transformers import SentenceTransformer; '
                'SentenceTransformer("nomic-ai/nomic-embed-text-v1.5", trust_remote_code=True)',
            ],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes for large model download
        )
        if result.returncode == 0:
            log.info('Model nomic-embed-text-v1.5 downloaded successfully')
            return True
        log.warning('Model download failed: {}', result.stderr.strip()[:200])
        return False
    except (subprocess.TimeoutExpired, OSError) as e:
        log.warning('Model download failed: {}', e)
        return False


def setup_python_env(
    repo_root: Path,
    embedding_provider: str | None = None,
) -> OperationReport:
    """Full Python environment setup orchestration.

    Steps:
    1. Create virtual environment
    2. Install dependencies via uv
    3. Verify CLI entry point
    4. Optionally pre-download embedding model

    Args:
        repo_root: Path to the repository root.
        embedding_provider: If ``"local"``, pre-downloads the embedding model.

    Returns:
        OperationReport with overall setup results.
    """
    log = get_setup_logger('python_env')
    start = time.monotonic()
    succeeded = 0
    failed = 0
    total_steps = 3
    next_steps: list[str] = []

    # Step 1: Create venv
    try:
        created = create_venv(repo_root)
        succeeded += 1
        if created:
            log.info('Created new virtual environment')
    except Exception as e:
        log.error('Failed to create venv: {}', e)
        failed += 1
        next_steps.append('Create venv manually: python3 -m venv .venv')
        # Can't continue without a venv
        duration_ms = (time.monotonic() - start) * 1000
        return OperationReport(
            operation='python-env-setup',
            duration_ms=duration_ms,
            counts=OperationCounts(total=total_steps, succeeded=succeeded, failed=failed),
            next_steps=next_steps,
        )

    # Step 2: Install dependencies
    install_report = install_dependencies(repo_root)
    if install_report.counts.failed > 0:
        failed += 1
        next_steps.extend(install_report.next_steps)
    else:
        succeeded += 1

    # Step 3: Verify CLI
    if verify_cli(repo_root):
        succeeded += 1
    else:
        failed += 1
        next_steps.append('CLI entry point not working. Try: .venv/bin/pip install -e backend/')

    # Optional: Pre-download model
    if embedding_provider == 'local':
        total_steps += 1
        if pre_download_model(embedding_provider):
            succeeded += 1
        else:
            failed += 1
            next_steps.append(
                'Model download failed. It will be downloaded automatically '
                'when you run: linkedout embed --provider local'
            )

    duration_ms = (time.monotonic() - start) * 1000

    return OperationReport(
        operation='python-env-setup',
        duration_ms=duration_ms,
        counts=OperationCounts(
            total=total_steps,
            succeeded=succeeded,
            failed=failed,
        ),
        next_steps=next_steps,
    )


# ── Internal helpers ──────────────────────────────────────────────


def _install_via_pip(repo_root: Path, start: float) -> OperationReport:
    """Fallback: install dependencies via pip instead of uv."""
    log = get_setup_logger('python_env')
    venv_pip = repo_root / '.venv' / 'bin' / 'pip'
    requirements = repo_root / 'backend' / 'requirements.txt'
    backend_dir = repo_root / 'backend'

    log.info('Falling back to pip for dependency installation...')

    # Install requirements
    result = subprocess.run(
        [str(venv_pip), 'install', '-r', str(requirements)],
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
    )
    if result.returncode != 0:
        duration_ms = (time.monotonic() - start) * 1000
        return OperationReport(
            operation='python-env-install',
            duration_ms=duration_ms,
            counts=OperationCounts(total=2, failed=1),
            next_steps=['pip install -r backend/requirements.txt failed. Check error output.'],
        )

    # Install editable package
    result = subprocess.run(
        [str(venv_pip), 'install', '-e', str(backend_dir)],
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
    )
    if result.returncode != 0:
        duration_ms = (time.monotonic() - start) * 1000
        return OperationReport(
            operation='python-env-install',
            duration_ms=duration_ms,
            counts=OperationCounts(total=2, succeeded=1, failed=1),
            next_steps=['pip install -e backend/ failed. Check pyproject.toml.'],
        )

    duration_ms = (time.monotonic() - start) * 1000
    return OperationReport(
        operation='python-env-install',
        duration_ms=duration_ms,
        counts=OperationCounts(total=2, succeeded=2),
    )
