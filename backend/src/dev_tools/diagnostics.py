# SPDX-License-Identifier: Apache-2.0
"""Diagnostics command for LinkedOut — ``linkedout diagnostics``.

Produces a comprehensive diagnostic report covering system info,
configuration, database statistics, health checks, and recent errors.
Output is human-readable by default, with ``--json`` for structured JSON.
The ``--repair`` flag detects and offers to fix common issues interactively.

Reports are always persisted to ``~/linkedout-data/reports/diagnostic-*.json``.
"""
from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

from shared.utilities.health_checks import (
    HealthCheckResult,
    check_api_keys,
    check_db_connection,
    check_disk_space,
    check_embedding_model,
    get_db_stats,
)
from shared.utilities.repair import get_repair_hooks


def _get_data_dir() -> Path:
    """Return the LinkedOut data directory."""
    return Path(
        os.environ.get('LINKEDOUT_DATA_DIR', os.path.expanduser('~/linkedout-data'))
    )


def _get_reports_dir() -> Path:
    """Return the reports directory."""
    return Path(
        os.environ.get(
            'LINKEDOUT_REPORTS_DIR',
            str(_get_data_dir() / 'reports'),
        )
    )


def _get_linkedout_version() -> str:
    """Read the LinkedOut version from pyproject.toml or fallback."""
    try:
        import importlib.metadata
        return importlib.metadata.version('linkedout')
    except Exception:
        pass

    # Fallback: read pyproject.toml
    try:
        pyproject = Path(__file__).resolve().parents[2] / 'pyproject.toml'
        if pyproject.exists():
            text = pyproject.read_text()
            match = re.search(r'version\s*=\s*"([^"]+)"', text)
            if match:
                return match.group(1)
    except Exception:
        pass

    return 'unknown'


def _get_pg_version() -> str:
    """Get PostgreSQL version from DB connection or psql."""
    try:
        from shared.infra.db.db_session_manager import DbSessionManager, DbSessionType
        from sqlalchemy import text

        db_mgr = DbSessionManager()
        with db_mgr.get_session(DbSessionType.READ) as session:
            row = session.execute(text('SHOW server_version')).first()
            if row:
                return row[0]
    except Exception:
        pass

    try:
        result = subprocess.run(
            ['psql', '--version'],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            # e.g. "psql (PostgreSQL) 16.2"
            match = re.search(r'(\d+\.\d+)', result.stdout)
            if match:
                return match.group(1)
    except Exception:
        pass

    return 'unknown'


def _get_data_dir_size_mb() -> float:
    """Calculate the total size of the data directory in MB."""
    data_dir = _get_data_dir()
    if not data_dir.exists():
        return 0.0
    total = 0
    try:
        for entry in data_dir.rglob('*'):
            if entry.is_file():
                total += entry.stat().st_size
    except Exception:
        pass
    return total / (1024 * 1024)


def _collect_system_info() -> dict:
    """Collect system information for the diagnostic report."""
    import shutil

    data_dir = _get_data_dir()
    check_path = data_dir if data_dir.exists() else data_dir.parent
    try:
        free_gb = shutil.disk_usage(check_path).free / (1024 ** 3)
    except Exception:
        free_gb = -1.0

    return {
        'os': f'{platform.system()} {platform.release()}',
        'python': platform.python_version(),
        'postgresql': _get_pg_version(),
        'linkedout_version': _get_linkedout_version(),
        'disk_free_gb': round(free_gb, 1),
        'data_dir': str(data_dir),
        'data_dir_size_mb': round(_get_data_dir_size_mb(), 1),
    }


def _collect_config_summary() -> dict:
    """Collect configuration summary for the diagnostic report."""
    try:
        from shared.config import get_config
        settings = get_config()

        api_keys = {}
        for key_name, value in [
            ('openai', settings.openai_api_key),
            ('apify', settings.apify_api_key),
        ]:
            api_keys[key_name] = 'configured' if value else 'not configured'

        return {
            'embedding_provider': settings.embedding.provider,
            'embedding_model': settings.embedding.model,
            'backend_url': settings.backend_url,
            'api_keys': api_keys,
            'langfuse_enabled': settings.langfuse_enabled,
            'log_level': settings.log_level,
        }
    except Exception as e:
        return {'error': str(e)}


def _collect_db_stats() -> dict:
    """Collect database statistics."""
    try:
        stats = get_db_stats()
        stats['connected'] = True
        return stats
    except Exception as e:
        return {
            'connected': False,
            'error': str(e),
        }


def _collect_health_checks() -> list[dict]:
    """Run all health check functions and collect results."""
    results: list[HealthCheckResult] = []

    results.append(check_db_connection())
    results.append(check_embedding_model())
    results.extend(check_api_keys())
    results.append(check_disk_space())

    return [
        {'check': r.check, 'status': r.status, 'detail': r.detail}
        for r in results
    ]


def _collect_recent_errors() -> list[dict]:
    """Parse recent ERROR/CRITICAL entries from log files."""
    data_dir = _get_data_dir()
    log_dir = data_dir / 'logs'
    errors: list[dict] = []

    if not log_dir.exists():
        return errors

    error_pattern = re.compile(r'(ERROR|CRITICAL)', re.IGNORECASE)
    timestamp_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\.\d{3})')

    try:
        for log_file in sorted(log_dir.glob('*.log')):
            component = log_file.stem
            try:
                lines = log_file.read_text(errors='replace').splitlines()
                # Take last 50 lines
                recent = lines[-50:] if len(lines) > 50 else lines
                component_errors: list[str] = []
                for line in recent:
                    if error_pattern.search(line):
                        component_errors.append(line.strip())

                if component_errors:
                    errors.append({
                        'component': component,
                        'count': len(component_errors),
                        'recent': component_errors[:5],  # Show up to 5
                    })
            except Exception:
                continue
    except Exception:
        pass

    return errors


def _build_full_report() -> dict:
    """Build the complete diagnostic report dict."""
    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'system': _collect_system_info(),
        'config': _collect_config_summary(),
        'database': _collect_db_stats(),
        'health_checks': _collect_health_checks(),
        'recent_errors': _collect_recent_errors(),
    }


def _save_report(report: dict) -> Path:
    """Save the report to ~/linkedout-data/reports/diagnostic-*.json."""
    reports_dir = _get_reports_dir()
    reports_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc)
    filename = f'diagnostic-{ts.strftime("%Y%m%d-%H%M%S")}.json'
    filepath = reports_dir / filename

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)

    return filepath


def _print_human_summary(report: dict, report_path: Path) -> None:
    """Print the diagnostic report in human-readable format."""
    sys_info = report.get('system', {})
    config = report.get('config', {})
    db = report.get('database', {})
    checks = report.get('health_checks', [])
    errors = report.get('recent_errors', [])

    click.echo()
    click.echo(click.style('=== LinkedOut Diagnostics ===', bold=True))
    click.echo()

    # System Info
    click.echo(click.style('System:', bold=True))
    click.echo(f'  OS:               {sys_info.get("os", "unknown")}')
    click.echo(f'  Python:           {sys_info.get("python", "unknown")}')
    click.echo(f'  PostgreSQL:       {sys_info.get("postgresql", "unknown")}')
    click.echo(f'  LinkedOut:        {sys_info.get("linkedout_version", "unknown")}')
    click.echo(f'  Disk free:        {sys_info.get("disk_free_gb", "?")} GB')
    click.echo(f'  Data dir:         {sys_info.get("data_dir", "?")}')
    click.echo(f'  Data dir size:    {sys_info.get("data_dir_size_mb", "?")} MB')
    click.echo()

    # Config
    click.echo(click.style('Config:', bold=True))
    click.echo(f'  Embedding:        {config.get("embedding_provider", "?")} / {config.get("embedding_model", "?")}')
    click.echo(f'  Backend URL:      {config.get("backend_url", "?")}')
    api_keys = config.get('api_keys', {})
    for key_name, status in api_keys.items():
        click.echo(f'  API key ({key_name:>6}): {status}')
    click.echo(f'  Langfuse:         {"enabled" if config.get("langfuse_enabled") else "disabled"}')
    click.echo(f'  Log level:        {config.get("log_level", "?")}')
    click.echo()

    # Database Stats
    click.echo(click.style('Database:', bold=True))
    if db.get('connected'):
        click.echo(f'  Profiles:         {db.get("profiles_total", 0):,}')
        with_emb = db.get('profiles_with_embeddings', 0)
        total = db.get('profiles_total', 0)
        pct = (with_emb / total * 100) if total > 0 else 0
        click.echo(f'  With embeddings:  {with_emb:,} / {total:,} ({pct:.0f}%)')
        click.echo(f'  Companies:        {db.get("companies_total", 0):,}')
        click.echo(f'  Connections:      {db.get("connections_total", 0):,}')
        click.echo(f'  Last enrichment:  {db.get("last_enrichment", "never")}')
        click.echo(f'  Schema version:   {db.get("schema_version", "unknown")}')
    else:
        click.echo(f'  Status:           NOT CONNECTED')
        if 'error' in db:
            click.echo(f'  Error:            {db["error"]}')
    click.echo()

    # Health Checks
    click.echo(click.style('Health Checks:', bold=True))
    status_icons = {'pass': click.style('PASS', fg='green'), 'fail': click.style('FAIL', fg='red'), 'skip': click.style('SKIP', fg='yellow')}
    for check in checks:
        icon = status_icons.get(check['status'], check['status'])
        detail = f' — {check["detail"]}' if check.get('detail') else ''
        click.echo(f'  [{icon}] {check["check"]}{detail}')
    click.echo()

    # Recent Errors
    if errors:
        click.echo(click.style('Recent Errors:', bold=True))
        for group in errors:
            click.echo(f'  {group["component"]}: {group["count"]} error(s)')
            for line in group.get('recent', []):
                click.echo(f'    {line[:120]}')
        click.echo()

    # Report path
    try:
        display_path = '~/' + str(report_path.relative_to(Path.home()))
    except ValueError:
        display_path = str(report_path)
    click.echo(f'Report saved: {display_path}')


def _run_repair_flow() -> None:
    """Run the --repair interactive flow."""
    hooks = get_repair_hooks()
    if not hooks:
        click.echo('No repair hooks registered.')
        return

    any_detected = False
    for hook in hooks:
        try:
            detection = hook.detect()
        except Exception as e:
            click.echo(f'  [{hook.name}] Detection error: {e}')
            continue

        if not detection.needs_repair:
            continue

        any_detected = True
        click.echo()
        click.echo(f'  {hook.description}: {detection.description}')

        if click.confirm(f'  Fix {detection.count} item(s)?', default=False):
            try:
                report = hook.repair()
                report.print_summary()
            except Exception as e:
                click.echo(f'  Repair failed: {e}')

    if not any_detected:
        click.echo('No issues found.')


def _register_builtin_repair_hooks() -> None:
    """Register the built-in repair hooks for common issues."""
    from shared.utilities.repair import RepairDetection, RepairHook, register_repair_hook
    from shared.utilities.operation_report import OperationReport, OperationCounts

    def _detect_missing_embeddings() -> RepairDetection:
        try:
            stats = get_db_stats()
            count = stats.get('profiles_without_embeddings', 0)
            if count > 0:
                return RepairDetection(
                    needs_repair=True,
                    count=count,
                    description=f'{count} profiles missing embeddings',
                )
            return RepairDetection(needs_repair=False)
        except Exception:
            return RepairDetection(needs_repair=False)

    def _repair_missing_embeddings() -> OperationReport:
        click.echo('  Run `linkedout embed` to generate embeddings.')
        return OperationReport(
            operation='repair-missing-embeddings',
            counts=OperationCounts(),
            next_steps=['Run `linkedout embed` to generate embeddings'],
        )

    def _detect_missing_affinity() -> RepairDetection:
        try:
            from shared.infra.db.db_session_manager import DbSessionManager, DbSessionType
            from linkedout.connection.entities.connection_entity import ConnectionEntity
            from sqlalchemy import func

            db_mgr = DbSessionManager()
            with db_mgr.get_session(DbSessionType.READ) as session:
                count = session.execute(
                    func.count(ConnectionEntity.id).select().where(
                        ConnectionEntity.affinity_score.is_(None),
                    ),
                ).scalar() or 0

            if count > 0:
                return RepairDetection(
                    needs_repair=True,
                    count=count,
                    description=f'{count} connections without affinity scores',
                )
            return RepairDetection(needs_repair=False)
        except Exception:
            return RepairDetection(needs_repair=False)

    def _repair_missing_affinity() -> OperationReport:
        click.echo('  Run `linkedout compute-affinity` to compute affinity scores.')
        return OperationReport(
            operation='repair-missing-affinity',
            counts=OperationCounts(),
            next_steps=['Run `linkedout compute-affinity` to compute affinity scores'],
        )

    def _detect_stale_enrichment() -> RepairDetection:
        try:
            from shared.config import get_config
            from shared.infra.db.db_session_manager import DbSessionManager, DbSessionType
            from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
            from sqlalchemy import func

            settings = get_config()
            ttl_days = settings.enrichment_cache_ttl_days

            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)

            db_mgr = DbSessionManager()
            with db_mgr.get_session(DbSessionType.READ) as session:
                count = session.execute(
                    func.count(CrawledProfileEntity.id).select().where(
                        CrawledProfileEntity.has_enriched_data.is_(True),
                        CrawledProfileEntity.last_crawled_at < cutoff,
                    ),
                ).scalar() or 0

            if count > 0:
                return RepairDetection(
                    needs_repair=True,
                    count=count,
                    description=f'{count} profiles with enrichment older than {ttl_days} days',
                )
            return RepairDetection(needs_repair=False)
        except Exception:
            return RepairDetection(needs_repair=False)

    def _repair_stale_enrichment() -> OperationReport:
        click.echo('  Re-enrich stale profiles by running the enrichment pipeline.')
        return OperationReport(
            operation='repair-stale-enrichment',
            counts=OperationCounts(),
            next_steps=['Re-run enrichment pipeline for stale profiles'],
        )

    register_repair_hook(RepairHook(
        name='missing_embeddings',
        description='Profiles without embeddings',
        detect=_detect_missing_embeddings,
        repair=_repair_missing_embeddings,
    ))

    register_repair_hook(RepairHook(
        name='missing_affinity',
        description='Connections without affinity scores',
        detect=_detect_missing_affinity,
        repair=_repair_missing_affinity,
    ))

    register_repair_hook(RepairHook(
        name='stale_enrichment',
        description='Profiles with stale enrichment data',
        detect=_detect_stale_enrichment,
        repair=_repair_stale_enrichment,
    ))


def run_diagnostics(output_json: bool = False, repair: bool = False) -> None:
    """Run the diagnostics command.

    Args:
        output_json: When *True*, print structured JSON to stdout.
        repair: When *True*, run the interactive repair flow after diagnostics.
    """
    # Register built-in repair hooks
    _register_builtin_repair_hooks()

    # Build and save the report
    report = _build_full_report()
    report_path = _save_report(report)

    # Output
    if output_json:
        click.echo(json.dumps(report, indent=2))
    else:
        _print_human_summary(report, report_path)

    # Repair flow
    if repair:
        click.echo()
        click.echo(click.style('=== Auto-Repair ===', bold=True))
        _run_repair_flow()
