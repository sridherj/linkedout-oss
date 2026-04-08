# SPDX-License-Identifier: Apache-2.0
"""Setup-specific logging configuration.

Wraps Phase 3 logging infrastructure (``get_logger()``) with setup-specific
concerns: correlation IDs, per-step logging, setup log file routing, and
failure diagnostic generation.

All setup output routes to ``~/linkedout-data/logs/setup.log`` (appended
across re-runs). On failure, a diagnostic file is written to
``~/linkedout-data/logs/setup-diagnostic-YYYYMMDD-HHMMSS.txt``.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from shared.config import get_config
from shared.utilities.correlation import set_correlation_id
from shared.utilities.logger import get_logger
from shared.utilities.operation_report import OperationReport

# Fields that must never appear in diagnostic output
_SENSITIVE_FIELDS = frozenset({
    'openai_api_key',
    'apify_api_key',
    'langfuse_secret_key',
    'langfuse_public_key',
    'password',
    'secret',
    'token',
    'api_key',
})


def init_setup_logging() -> str:
    """Initialize setup logging and return a correlation ID.

    Generates a ``setup_{timestamp}`` correlation ID, sets it in the
    contextvar so all downstream loguru calls carry it, and ensures the
    log directory exists.

    Returns:
        The generated correlation ID string (e.g., ``"setup_20260407_1423"``).
    """
    ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    correlation_id = f'setup_{ts}'
    set_correlation_id(correlation_id)

    # Ensure log directory exists
    settings = get_config()
    os.makedirs(settings.log_dir, exist_ok=True)

    return correlation_id


def get_setup_logger(step_name: str):
    """Return a logger bound to setup context and a specific step.

    Args:
        step_name: Human-readable step identifier
            (e.g., ``"prerequisites_detection"``).

    Returns:
        A loguru logger bound with ``component="setup"`` and
        ``operation=step_name``.
    """
    return get_logger(
        name='linkedout.setup',
        component='setup',
        operation=step_name,
    )


def log_step_start(step_num: int, total: int, step_name: str) -> None:
    """Log a standardized step start message.

    Produces: ``"Starting step N/M: {step_name}"``

    Args:
        step_num: Current step number (1-based).
        total: Total number of steps.
        step_name: Human-readable step name.
    """
    log = get_setup_logger(step_name)
    log.info('Starting step {}/{}: {}', step_num, total, step_name)


def log_step_complete(
    step_name: str,
    duration: float,
    report: OperationReport | None = None,
) -> None:
    """Log a standardized step completion message.

    Produces: ``"{step_name} complete ({duration}s)"`` plus optional
    report summary.

    Args:
        step_name: Human-readable step name.
        duration: Step duration in seconds.
        report: Optional operation report with counts/gaps.
    """
    log = get_setup_logger(step_name)
    log.info('{} complete ({:.1f}s)', step_name, duration)
    if report and report.counts.failed > 0:
        log.warning(
            '{} had {} failures out of {} total',
            step_name,
            report.counts.failed,
            report.counts.total,
        )


def generate_diagnostic(
    error: Exception,
    steps_completed: list[dict],
    config: dict,
) -> Path:
    """Write a diagnostic file for a setup failure.

    The diagnostic file follows the exact format specified in the UX
    design doc (Section 7) and is designed to be attached to a GitHub
    issue for remote debugging.

    Args:
        error: The exception that caused the failure.
        steps_completed: List of dicts with keys ``name``, ``status``
            (``"success"``/``"failed"``/``"skipped"``), ``timestamp``,
            and ``duration``.
        config: Raw config dict — sensitive values will be redacted.

    Returns:
        Path to the diagnostic file.
    """
    settings = get_config()
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc)
    filename = f'setup-diagnostic-{ts.strftime("%Y%m%d-%H%M%S")}.txt'
    diag_path = log_dir / filename

    lines: list[str] = []
    sep = '=' * 80

    lines.append(sep)
    lines.append('LinkedOut Setup Diagnostic Report')
    lines.append(f'Generated: {ts.strftime("%Y-%m-%d %H:%M:%S")} UTC')
    lines.append(sep)
    lines.append('')

    # System section
    lines.append('SYSTEM')
    lines.append('------')
    lines.append(f'OS:               {_get_os_description()}')
    lines.append(f'Kernel:           {platform.release()}')
    lines.append(f'Python:           {platform.python_version()} ({_get_python_path()})')
    lines.append(f'PostgreSQL:       {_get_pg_version_string()}')
    lines.append(f'Disk free:        {_get_disk_free_string(settings.data_dir)}')
    lines.append(f'RAM:              {_get_ram_string()}')
    lines.append('')

    # Config section (redacted)
    lines.append('CONFIGURATION (secrets redacted)')
    lines.append('--------------------------------')
    redacted = _redact_config(config)
    for key, value in redacted.items():
        lines.append(f'{key + ":":<22}{value}')
    lines.append('')

    # Setup progress section
    lines.append('SETUP PROGRESS')
    lines.append('--------------')
    for step in steps_completed:
        status = step.get('status', 'unknown')
        name = step.get('name', 'Unknown')
        timestamp = step.get('timestamp', '')
        duration = step.get('duration', '')
        marker = '\u2713' if status == 'success' else '\u2717' if status == 'failed' else '-'
        dur_str = f' ({duration})' if duration else ''
        ts_str = f'  {timestamp}' if timestamp else ''
        lines.append(f'  {marker} {name}{ts_str}{dur_str}')
    lines.append('')

    # Failure details
    lines.append('FAILURE DETAILS')
    lines.append('---------------')
    lines.append(f'Error:     {type(error).__name__}: {error}')
    lines.append('')

    # Recent log entries
    setup_log = log_dir / 'setup.log'
    if setup_log.exists():
        lines.append(f'RECENT LOG ENTRIES (last 50 lines of {setup_log})')
        lines.append('-' * 69)
        try:
            with open(setup_log, encoding='utf-8', errors='replace') as f:
                all_lines = f.readlines()
                for line in all_lines[-50:]:
                    lines.append(line.rstrip())
        except OSError:
            lines.append('  (could not read setup.log)')
        lines.append('')

    lines.append(sep)
    lines.append('To report this issue:')
    lines.append('  https://github.com/anthropics/linkedout-oss/issues/new')
    lines.append('')
    lines.append(f'Attach this file: {diag_path}')
    lines.append(sep)

    diag_path.write_text('\n'.join(lines), encoding='utf-8')

    log = get_setup_logger('diagnostic')
    log.info('Diagnostic report written to {}', diag_path)

    return diag_path


# ── Internal helpers ──────────────────────────────────────────────


def _redact_config(config: dict) -> dict:
    """Redact sensitive values in a config dict.

    Keys containing any of the sensitive field patterns have their values
    replaced with ``[REDACTED]``. Database URLs have the password portion
    masked with ``****``.
    """
    redacted = {}
    for key, value in config.items():
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in _SENSITIVE_FIELDS):
            redacted[key] = '[REDACTED]'
        elif key_lower in ('database_url',) and isinstance(value, str) and '@' in value:
            # Mask password: postgresql://user:PASSWORD@host → postgresql://user:****@host
            before_at = value.split('@')[0]
            after_at = value.split('@', 1)[1]
            if ':' in before_at:
                scheme_user = before_at.rsplit(':', 1)[0]
                redacted[key] = f'{scheme_user}:****@{after_at}'
            else:
                redacted[key] = value
        else:
            redacted[key] = str(value)
    return redacted


def _get_os_description() -> str:
    """Get a human-readable OS description."""
    system = platform.system()
    if system == 'Linux':
        try:
            with open('/etc/os-release', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('PRETTY_NAME='):
                        return line.split('=', 1)[1].strip().strip('"')
        except OSError:
            pass
        return f'Linux ({platform.machine()})'
    if system == 'Darwin':
        ver = platform.mac_ver()[0]
        return f'macOS {ver} ({platform.machine()})'
    return f'{system} ({platform.machine()})'


def _get_python_path() -> str:
    """Get the path to the current Python interpreter."""
    import sys
    return sys.executable


def _get_pg_version_string() -> str:
    """Get PostgreSQL version or 'not found'."""
    try:
        result = subprocess.run(
            ['psql', '--version'],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip().split('\n')[0]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return 'not found'


def _get_disk_free_string(data_dir: str) -> str:
    """Get free disk space on the data directory mount."""
    try:
        path = Path(data_dir)
        # Walk up to an existing parent if data_dir doesn't exist yet
        while not path.exists() and path.parent != path:
            path = path.parent
        usage = shutil.disk_usage(str(path))
        free_gb = usage.free / (1024 ** 3)
        return f'{free_gb:.1f} GB'
    except OSError:
        return 'unknown'


def _get_ram_string() -> str:
    """Get total and available RAM (Linux/macOS)."""
    try:
        if platform.system() == 'Linux':
            with open('/proc/meminfo', encoding='utf-8') as f:
                info = {}
                for line in f:
                    parts = line.split(':')
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val_kb = int(parts[1].strip().split()[0])
                        info[key] = val_kb
                total = info.get('MemTotal', 0) / (1024 * 1024)
                avail = info.get('MemAvailable', 0) / (1024 * 1024)
                return f'{total:.1f} GB total, {avail:.1f} GB available'
        elif platform.system() == 'Darwin':
            result = subprocess.run(
                ['sysctl', '-n', 'hw.memsize'],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                total = int(result.stdout.strip()) / (1024 ** 3)
                return f'{total:.1f} GB total'
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return 'unknown'
