# SPDX-License-Identifier: Apache-2.0
"""``linkedout import-seed`` — import seed dataset from SQLite into PostgreSQL.

Reads a downloaded seed SQLite file and upserts the 6 company/reference tables
into the local PostgreSQL database. Idempotent: running twice with the same
data is safe.

Profile data (crawled_profile, experience, education, profile_skill) is not
part of seed data — it ships via the demo pipeline.
"""
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import click
from sqlalchemy import text

from dev_tools.db.fixed_data import SYSTEM_USER_ID
from linkedout.cli_helpers import cli_logged
from shared.config import get_config
from shared.infra.db.db_session_manager import db_session_manager, DbSessionType
from shared.utilities.logger import get_logger
from shared.utilities.metrics import record_metric
from shared.utilities.operation_report import OperationCounts, OperationReport

logger = get_logger(__name__, component='cli', operation='import_seed')

# Tables in FK-safe order (must match seed_export.py SEED_TABLES).
# Only company/reference tables — profile data ships via the demo pipeline.
IMPORT_ORDER = [
    'company',
    'company_alias',
    'role_alias',
    'funding_round',
    'startup_tracking',
    'growth_signal',
]

# Columns that are PostgreSQL arrays (stored as JSON strings in SQLite).
# Must be parsed back from JSON text to Python lists for psycopg2 ARRAY binding.
ARRAY_COLUMNS = {
    'company': {'enrichment_sources'},
    'funding_round': {'lead_investors', 'all_investors'},
}

# Columns that are booleans (stored as INTEGER 0/1 in SQLite).
# is_active comes from BaseEntity and is present in all seed tables.
_COMMON_BOOL = {'is_active'}
BOOL_COLUMNS = {
    'company': _COMMON_BOOL,
    'company_alias': _COMMON_BOOL,
    'role_alias': _COMMON_BOOL,
    'funding_round': _COMMON_BOOL,
    'startup_tracking': _COMMON_BOOL | {'watching'},
    'growth_signal': _COMMON_BOOL,
}

BATCH_SIZE = 1000


# ── SQLite reader ────────────────────────────────────────────────────────────


def read_seed_metadata(sqlite_path: Path) -> dict:
    """Read the _metadata table from a seed SQLite file."""
    conn = sqlite3.connect(str(sqlite_path))
    try:
        cursor = conn.execute('SELECT key, value FROM _metadata')
        return {row[0]: row[1] for row in cursor.fetchall()}
    finally:
        conn.close()


def read_seed_table(sqlite_path: Path, table_name: str) -> list[dict]:
    """Read all rows from a SQLite table as list of dicts.

    ``table_name`` comes from the hardcoded IMPORT_ORDER list, not user input.
    """
    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(f'SELECT * FROM {table_name}')  # noqa: S608
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_sqlite_tables(sqlite_path: Path) -> list[str]:
    """List all non-metadata tables in a SQLite file."""
    conn = sqlite3.connect(str(sqlite_path))
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name != '_metadata'"
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_sqlite_columns(sqlite_path: Path, table_name: str) -> list[str]:
    """Get column names for a table in the SQLite file."""
    conn = sqlite3.connect(str(sqlite_path))
    try:
        cursor = conn.execute(f'PRAGMA table_info({table_name})')  # noqa: S608
        return [row[1] for row in cursor.fetchall()]
    finally:
        conn.close()


# ── Type conversion ──────────────────────────────────────────────────────────


def _convert_row(row: dict, table_name: str) -> dict:
    """Convert SQLite values back to PostgreSQL-compatible types."""
    for col in ARRAY_COLUMNS.get(table_name, ()):
        if col in row and row[col] is not None:
            try:
                row[col] = json.loads(row[col])
            except (json.JSONDecodeError, TypeError):
                pass

    for col in BOOL_COLUMNS.get(table_name, ()):
        if col in row and row[col] is not None:
            row[col] = bool(row[col])

    return row


# ── Upsert logic ─────────────────────────────────────────────────────────────


def _build_upsert_sql(table_name: str, columns: list[str]) -> str:
    """Build INSERT ... ON CONFLICT (id) DO UPDATE with change detection.

    Uses IS DISTINCT FROM for null-safe comparison so identical rows are skipped.
    RETURNING (xmax = 0) distinguishes inserts (xmax=0) from updates.
    """
    col_list = ', '.join(columns)
    placeholders = ', '.join(f':{c}' for c in columns)

    non_pk_cols = [c for c in columns if c != 'id']
    set_clause = ', '.join(f'{c} = EXCLUDED.{c}' for c in non_pk_cols)

    where_parts = [f'{table_name}.{c} IS DISTINCT FROM EXCLUDED.{c}' for c in non_pk_cols]
    where_clause = ' OR '.join(where_parts)

    return (
        f'INSERT INTO {table_name} ({col_list}) '
        f'VALUES ({placeholders}) '
        f'ON CONFLICT (id) DO UPDATE SET {set_clause} '
        f'WHERE {where_clause} '
        f'RETURNING (xmax = 0) AS inserted'
    )


def _import_table(session, table_name: str, rows: list[dict], columns: list[str]) -> dict:
    """Import rows into a single PostgreSQL table. Returns per-outcome counts."""
    total = len(rows)
    if total == 0:
        return {'inserted': 0, 'updated': 0, 'skipped': 0, 'total': 0}

    inserted = 0
    updated = 0
    skipped = 0
    upsert_sql = text(_build_upsert_sql(table_name, columns))

    for batch_start in range(0, total, BATCH_SIZE):
        batch = rows[batch_start:batch_start + BATCH_SIZE]

        for row in batch:
            result = session.execute(upsert_sql, row)
            returned = result.fetchall()
            if not returned:
                # ON CONFLICT matched but WHERE excluded the update → data identical
                skipped += 1
            elif returned[0][0]:
                inserted += 1
            else:
                updated += 1

        done = min(batch_start + BATCH_SIZE, total)
        click.echo(f'\r  Importing {table_name}... {done:,}/{total:,}', nl=False)

    click.echo()
    return {'inserted': inserted, 'updated': updated, 'skipped': skipped, 'total': total}


# ── Seed file location ──────────────────────────────────────────────────────


def _locate_seed_file(seed_file: str | None) -> Path:
    """Locate the seed SQLite file, auto-detecting if no path given."""
    if seed_file:
        return Path(seed_file)

    settings = get_config()
    seed_dir = Path(settings.data_dir) / 'seed'

    for name in ('seed-core.sqlite', 'seed-full.sqlite'):
        candidate = seed_dir / name
        if candidate.exists():
            return candidate

    raise click.ClickException(
        f'No seed file found in {seed_dir}/\n\n'
        'To get seed data, run:\n'
        '  linkedout download-seed\n\n'
        'Or specify a file directly:\n'
        '  linkedout import-seed --seed-file /path/to/seed.sqlite'
    )


def _validate_seed_file(sqlite_path: Path) -> dict:
    """Validate seed file structure. Returns metadata dict."""
    metadata = read_seed_metadata(sqlite_path)
    tables = get_sqlite_tables(sqlite_path)

    missing = [t for t in IMPORT_ORDER if t not in tables]
    if missing:
        raise click.ClickException(
            f'Seed file is missing tables: {", ".join(missing)}\n'
            'The file may be corrupted or from an incompatible version.'
        )

    click.echo(f'Seed version: {metadata.get("version", "unknown")}')
    click.echo(f'Created: {metadata.get("created_at", "unknown")}')

    table_counts = json.loads(metadata.get('table_counts', '{}'))
    if table_counts:
        total = sum(table_counts.values())
        click.echo(f'Tables: {len(table_counts)}, Total rows: {total:,}')

    return metadata


# ── Report ───────────────────────────────────────────────────────────────────


def _write_report(
    results: dict[str, dict],
    metadata: dict,
    duration_ms: float,
    dry_run: bool,
) -> Path:
    """Write JSON import report and return its path."""
    settings = get_config()
    reports_dir = Path(settings.data_dir) / 'reports'
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    report_path = reports_dir / f'seed-import-{timestamp}.json'

    report = {
        'operation': 'import-seed',
        'seed_version': metadata.get('version'),
        'seed_created_at': metadata.get('created_at'),
        'dry_run': dry_run,
        'duration_ms': round(duration_ms, 1),
        'tables': {
            table: {k: v for k, v in r.items()}
            for table, r in results.items()
        },
        'totals': {
            'inserted': sum(r['inserted'] for r in results.values()),
            'updated': sum(r['updated'] for r in results.values()),
            'skipped': sum(r['skipped'] for r in results.values()),
            'total': sum(r['total'] for r in results.values()),
        },
        'imported_at': datetime.now(timezone.utc).isoformat(),
    }

    report_path.write_text(json.dumps(report, indent=2) + '\n')
    return report_path


# ── CLI command ──────────────────────────────────────────────────────────────


@click.command('import-seed')
@click.option(
    '--seed-file',
    type=click.Path(exists=True),
    default=None,
    help='Path to seed SQLite file (default: auto-detect in ~/linkedout-data/seed/)',
)
@click.option('--dry-run', is_flag=True, help='Report what would be imported, do not write')
@cli_logged('import_seed')
def import_seed_command(seed_file: str | None, dry_run: bool):
    """Import seed company data from SQLite into PostgreSQL."""
    start = time.time()

    # 1. Locate and validate
    sqlite_path = _locate_seed_file(seed_file)
    click.echo(f'Seed file: {sqlite_path}')
    metadata = _validate_seed_file(sqlite_path)

    if dry_run:
        click.echo('\n[DRY RUN — no data will be written]\n')

    # 2. Import tables in FK order
    results: dict[str, dict] = {}

    if dry_run:
        for table_name in IMPORT_ORDER:
            rows = read_seed_table(sqlite_path, table_name)
            converted = [_convert_row(row, table_name) for row in rows]

            with db_session_manager.get_session(DbSessionType.READ, app_user_id=SYSTEM_USER_ID) as session:
                existing_ids = {
                    r[0]
                    for r in session.execute(
                        text(f'SELECT id FROM {table_name}')  # noqa: S608
                    ).fetchall()
                }

            would_insert = sum(1 for r in converted if r['id'] not in existing_ids)
            would_skip = len(converted) - would_insert

            results[table_name] = {
                'inserted': would_insert,
                'updated': 0,
                'skipped': would_skip,
                'total': len(converted),
            }
            click.echo(f'  {table_name}: {len(converted):,} rows ({would_insert:,} new)')
    else:
        with db_session_manager.get_session(DbSessionType.WRITE, app_user_id=SYSTEM_USER_ID) as session:
            for table_name in IMPORT_ORDER:
                rows = read_seed_table(sqlite_path, table_name)
                columns = get_sqlite_columns(sqlite_path, table_name)
                converted = [_convert_row(row, table_name) for row in rows]
                result = _import_table(session, table_name, converted, columns)
                results[table_name] = result
                logger.info(
                    f'Imported {table_name}: {result["inserted"]} inserted, '
                    f'{result["updated"]} updated, {result["skipped"]} skipped'
                )

    elapsed_ms = (time.time() - start) * 1000

    # 3. Generate detailed report
    report_path = _write_report(results, metadata, elapsed_ms, dry_run)

    # 4. Also generate OperationReport for consistency
    total_inserted = sum(r['inserted'] for r in results.values())
    total_updated = sum(r['updated'] for r in results.values())
    total_skipped = sum(r['skipped'] for r in results.values())

    op_report = OperationReport(
        operation='import-seed',
        duration_ms=elapsed_ms,
        counts=OperationCounts(
            total=sum(r['total'] for r in results.values()),
            succeeded=total_inserted + total_updated,
            skipped=total_skipped,
        ),
        next_steps=(
            ['Run `linkedout status` to verify database state']
            if not dry_run else []
        ),
    )
    op_report.save()

    if not dry_run:
        record_metric(
            'seed_imported', total_inserted + total_updated,
            duration_ms=elapsed_ms,
            inserted=total_inserted, updated=total_updated, skipped=total_skipped,
        )

    # 5. Print summary (Operation Result Pattern)
    click.echo(f'\n{"=" * 60}')
    click.echo('Results:')
    for table_name, r in results.items():
        click.echo(
            f'  {table_name + ":":<22} '
            f'{r["inserted"]:,} inserted, {r["updated"]:,} updated, {r["skipped"]:,} skipped'
        )

    click.echo()
    if total_inserted > 0 or total_updated > 0:
        click.echo(
            f'Total: {total_inserted + total_updated:,} rows imported across '
            f'{len(IMPORT_ORDER)} tables'
        )
    else:
        click.echo(f'Total: 0 rows imported ({total_skipped:,} already up to date)')

    if dry_run:
        click.echo('\nDRY RUN \u2014 no data written. Remove --dry-run to import.')
    else:
        click.echo('\nNext steps:')
        click.echo('  \u2192 Run `linkedout status` to verify database state')

    try:
        display_path = '~/' + str(report_path.relative_to(Path.home()))
    except ValueError:
        display_path = str(report_path)
    click.echo(f'\nReport saved: {display_path}')
