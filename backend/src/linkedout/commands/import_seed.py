# SPDX-License-Identifier: Apache-2.0
"""``linkedout import-seed`` — import seed dataset from pg_dump into PostgreSQL.

Restores a downloaded seed ``.dump`` file into a ``_seed_staging`` schema,
then upserts the 6 company/reference tables into the ``public`` schema.
Idempotent: running twice with the same data is safe (identical rows are skipped).

Profile data (crawled_profile, experience, education, profile_skill) is not
part of seed data — it ships via the demo pipeline.
"""
import json
import shutil
import subprocess
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


# ── pg_restore helpers ──────────────────────────────────────────────────────


def _check_pg_restore():
    """Ensure pg_restore is available on the system PATH."""
    if not shutil.which("pg_restore"):
        raise click.ClickException(
            "pg_restore not found. Install the PostgreSQL client package.\n"
            "  Ubuntu/Debian: sudo apt-get install postgresql-client\n"
            "  macOS: brew install libpq"
        )


def _get_db_url() -> str:
    """Get DATABASE_URL from config (Decision #6: not session.get_bind().url)."""
    return get_config().database_url


def _restore_to_staging(session, db_url: str, dump_path: Path):
    """Restore a .dump file into the _seed_staging schema.

    Decision #7: no manual CREATE SCHEMA — pg_restore creates it from the dump.
    We only DROP IF EXISTS to clean up prior failed imports.
    """
    session.execute(text("DROP SCHEMA IF EXISTS _seed_staging CASCADE"))
    session.commit()

    result = subprocess.run(
        ["pg_restore", f"--dbname={db_url}", "--no-owner",
         "--clean", "--if-exists", str(dump_path)],
        capture_output=True, text=True, timeout=300,
    )
    # Match demo pattern: 0 and 1 are OK, >= 2 is failure
    if result.returncode not in (0, 1):
        raise click.ClickException(
            f"pg_restore failed (exit {result.returncode}): {result.stderr[:500]}"
        )
    if result.returncode == 1 and result.stderr:
        logger.warning(f"pg_restore warnings: {result.stderr[:500]}")


def _get_intersected_columns(session, table: str) -> list[str]:
    """Get columns present in both _seed_staging and public schemas for a table.

    Uses column intersection for schema version safety — only columns present
    in BOTH schemas are upserted.
    """
    rows = session.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = '_seed_staging' AND table_name = :table
        INTERSECT
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = :table
    """), {"table": table}).fetchall()
    return [r[0] for r in rows]


def _build_staging_upsert_sql(table: str, columns: list[str]) -> str:
    """Build a single SQL statement that upserts all rows from staging to public.

    Source is SELECT FROM _seed_staging.{table}, not parameterized VALUES.
    Uses IS DISTINCT FROM for null-safe change detection.
    RETURNING (xmax = 0) distinguishes inserts from updates.
    """
    col_list = ", ".join(columns)
    non_pk = [c for c in columns if c != "id"]
    set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in non_pk)
    where_parts = [f"public.{table}.{c} IS DISTINCT FROM EXCLUDED.{c}" for c in non_pk]
    where_clause = " OR ".join(where_parts)

    return f"""
    WITH upserted AS (
        INSERT INTO public.{table} ({col_list})
        SELECT {col_list} FROM _seed_staging.{table}
        ON CONFLICT (id) DO UPDATE SET {set_clause}
        WHERE {where_clause}
        RETURNING (xmax = 0) AS was_insert
    )
    SELECT
        COUNT(*) FILTER (WHERE was_insert) AS inserted,
        COUNT(*) FILTER (WHERE NOT was_insert) AS updated
    FROM upserted
    """


def _count_staging_rows(session, table: str) -> int:
    """Count rows in a staging table."""
    return session.execute(
        text(f"SELECT COUNT(*) FROM _seed_staging.{table}")  # noqa: S608
    ).scalar() or 0


def _drop_staging_schema(session):
    """Clean up the _seed_staging schema."""
    session.execute(text("DROP SCHEMA IF EXISTS _seed_staging CASCADE"))
    session.commit()


def _read_manifest(dump_path: Path) -> dict | None:
    """Read seed-manifest.json from the same directory as the dump file."""
    manifest_path = dump_path.parent / "seed-manifest.json"
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text())


# ── Seed file location ──────────────────────────────────────────────────────


def _locate_seed_file(seed_file: str | None) -> Path:
    """Locate the seed .dump file, auto-detecting if no path given."""
    if seed_file:
        return Path(seed_file)

    settings = get_config()
    seed_dir = Path(settings.data_dir) / 'seed'

    for name in ('seed-core.dump', 'seed-full.dump'):
        candidate = seed_dir / name
        if candidate.exists():
            return candidate

    raise click.ClickException(
        f'No seed file found in {seed_dir}/\n\n'
        'To get seed data, run:\n'
        '  linkedout download-seed\n\n'
        'Or specify a file directly:\n'
        '  linkedout import-seed --seed-file /path/to/seed.dump'
    )


# ── Report ───────────────────────────────────────────────────────────────────


def _write_report(
    results: dict[str, dict],
    manifest: dict | None,
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
        'seed_version': manifest.get('version') if manifest else None,
        'seed_created_at': manifest.get('created_at') if manifest else None,
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
    help='Path to seed .dump file (default: auto-detect in ~/linkedout-data/seed/)',
)
@click.option('--dry-run', is_flag=True, help='Report what would be imported, do not write')
@cli_logged('import_seed')
def import_seed_command(seed_file: str | None, dry_run: bool):
    """Import seed company data from pg_dump into PostgreSQL."""
    start = time.time()

    # 1. Locate dump file, check pg_restore
    dump_path = _locate_seed_file(seed_file)
    click.echo(f'Seed file: {dump_path}')
    _check_pg_restore()
    manifest = _read_manifest(dump_path)

    if manifest:
        click.echo(f'Seed version: {manifest.get("version", "unknown")}')

    if dry_run:
        click.echo('\n[DRY RUN — no data will be written]\n')

    # 2. Restore to staging + upsert
    results: dict[str, dict] = {}

    with db_session_manager.get_session(DbSessionType.WRITE, app_user_id=SYSTEM_USER_ID) as session:
        db_url = _get_db_url()
        _restore_to_staging(session, db_url, dump_path)

        if dry_run:
            for table_name in IMPORT_ORDER:
                staging_count = _count_staging_rows(session, table_name)
                public_count = session.execute(
                    text(f'SELECT COUNT(*) FROM {table_name}')  # noqa: S608
                ).scalar() or 0
                would_insert = max(0, staging_count - public_count)
                results[table_name] = {
                    'inserted': would_insert,
                    'updated': 0,
                    'skipped': staging_count - would_insert,
                    'total': staging_count,
                }
                click.echo(f'  {table_name}: {staging_count:,} rows ({would_insert:,} new)')
            _drop_staging_schema(session)
        else:
            for table_name in IMPORT_ORDER:
                staging_count = _count_staging_rows(session, table_name)
                columns = _get_intersected_columns(session, table_name)
                sql = _build_staging_upsert_sql(table_name, columns)
                row = session.execute(text(sql)).fetchone()
                assert row is not None, f"upsert CTE for {table_name} returned no rows"
                inserted, updated = row[0], row[1]
                skipped = staging_count - inserted - updated
                results[table_name] = {
                    'inserted': inserted,
                    'updated': updated,
                    'skipped': skipped,
                    'total': staging_count,
                }
                click.echo(
                    f'  {table_name}: {inserted:,} inserted, '
                    f'{updated:,} updated, {skipped:,} skipped'
                )
                logger.info(
                    f'Imported {table_name}: {inserted} inserted, '
                    f'{updated} updated, {skipped} skipped'
                )

            _drop_staging_schema(session)

    elapsed_ms = (time.time() - start) * 1000

    # 3. Generate detailed report
    report_path = _write_report(results, manifest, elapsed_ms, dry_run)

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
