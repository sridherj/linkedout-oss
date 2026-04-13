# SPDX-License-Identifier: Apache-2.0
"""``linkedout import-connections`` — import LinkedIn connections from CSV export.

Parses the LinkedIn connections CSV, matches against existing crawled profiles
by normalized URL, creates stub profiles for unmatched connections, and inserts
connection rows.
"""
import csv
import json
import time
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path

import click
from sqlalchemy import text
from sqlalchemy.orm import Session

from linkedout.connection.entities.connection_entity import ConnectionEntity
from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
from dev_tools.db.fixed_data import SYSTEM_BU, SYSTEM_TENANT, SYSTEM_USER_ID
from shared.infra.db.cli_db import cli_db_manager
from shared.infra.db.db_session_manager import DbSessionType
from shared.utils.date_parsing import parse_linkedin_csv_date
from shared.utils.linkedin_url import normalize_linkedin_url
from shared.utilities.logger import get_logger
from shared.utilities.metrics import record_metric
from shared.config import get_config
from shared.utilities.operation_report import OperationCounts, OperationReport
from linkedout.cli_helpers import cli_logged

logger = get_logger(__name__, component="import")

APP_USER_ID = SYSTEM_USER_ID
TENANT_ID = SYSTEM_TENANT['id']
BU_ID = SYSTEM_BU['id']

# LinkedIn CSV preamble: 3 lines of notes before the actual CSV header
PREAMBLE_LINES = 3


def _auto_detect_csv(csv_path: Path) -> Path:
    """Auto-detect CSV file in ~/Downloads if no path given."""
    if csv_path.is_file():
        return csv_path
    # Try to find a LinkedIn CSV in ~/Downloads
    downloads = Path.home() / 'Downloads'
    if downloads.is_dir():
        candidates = sorted(
            downloads.glob('Connections*.csv'),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            return candidates[0]
    return csv_path  # Return as-is, will fail with clear error


def build_linkedin_url_index(session: Session) -> dict[str, str]:
    """Build {normalized_linkedin_url: crawled_profile_id} lookup."""
    rows = session.execute(
        text('SELECT id, linkedin_url FROM crawled_profile WHERE linkedin_url IS NOT NULL')
    ).fetchall()
    return {r[1]: r[0] for r in rows}


def parse_csv(csv_path: Path) -> list[dict]:
    """Parse the LinkedIn CSV, skipping the 3-line preamble."""
    rows = []
    with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
        # Skip preamble lines
        for _ in range(PREAMBLE_LINES):
            f.readline()

        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def create_stub_profile(
    first_name: str | None,
    last_name: str | None,
    linkedin_url: str | None,
    company: str | None,
    position: str | None,
    now: datetime,
) -> CrawledProfileEntity:
    """Create a stub CrawledProfileEntity for unenriched connections."""
    full_name = f'{first_name or ""} {last_name or ""}'.strip() or None

    return CrawledProfileEntity(
        linkedin_url=linkedin_url or f'stub://{full_name or "unknown"}-{uuid4().hex}',
        first_name=first_name or None,
        last_name=last_name or None,
        full_name=full_name,
        current_company_name=company or None,
        current_position=position or None,
        data_source='csv_stub',
        has_enriched_data=False,
        last_crawled_at=now,
    )


def load_csv_batch(
    session: Session,
    batch: list[dict],
    url_index: dict[str, str],
    now: datetime,
) -> dict[str, int]:
    """Process a batch of CSV rows. Returns counts."""
    counts = {'total': 0, 'matched': 0, 'unenriched': 0, 'no_url': 0, 'errors': 0}

    for row in batch:
        counts['total'] += 1
        savepoint = session.begin_nested()
        try:
            first_name = (row.get('First Name') or '').strip() or None
            last_name = (row.get('Last Name') or '').strip() or None
            raw_url = (row.get('URL') or '').strip()
            email = (row.get('Email Address') or '').strip() or None
            company = (row.get('Company') or '').strip() or None
            position = (row.get('Position') or '').strip() or None
            connected_on = (row.get('Connected On') or '').strip()

            norm_url = normalize_linkedin_url(raw_url) if raw_url else None
            connected_at = parse_linkedin_csv_date(connected_on) if connected_on else None

            # Match or create stub profile
            pending_counter = None
            pending_url_entry = None  # (url, profile_id) to cache after commit

            if norm_url and norm_url in url_index:
                profile_id = url_index[norm_url]
                pending_counter = 'matched'
            elif norm_url:
                stub = create_stub_profile(first_name, last_name, norm_url, company, position, now)
                session.add(stub)
                session.flush()
                profile_id = stub.id
                pending_url_entry = (norm_url, profile_id)
                pending_counter = 'unenriched'
            else:
                stub = create_stub_profile(first_name, last_name, None, company, position, now)
                session.add(stub)
                session.flush()
                profile_id = stub.id
                pending_counter = 'no_url'

            source_details = json.dumps({
                'first_name': first_name,
                'last_name': last_name,
                'url': raw_url or None,
                'email': email,
                'company': company,
                'position': position,
                'connected_on': connected_on or None,
            })

            connection = ConnectionEntity(
                app_user_id=APP_USER_ID,
                crawled_profile_id=profile_id,
                tenant_id=TENANT_ID,
                bu_id=BU_ID,
                connected_at=connected_at,
                emails=email,
                sources=['linkedin_csv'],
                source_details=source_details,
            )
            session.add(connection)
            savepoint.commit()

            # Commit succeeded — now safe to update counters and index
            counts[pending_counter] += 1
            if pending_url_entry:
                url_index[pending_url_entry[0]] = pending_url_entry[1]

        except Exception as e:
            savepoint.rollback()
            counts['errors'] += 1
            name = f'{row.get("First Name", "")} {row.get("Last Name", "")}'.strip()
            click.echo(f'  Error on row ({name}): {e}', err=True)

    return counts


@click.command('import-connections')
@click.argument('csv_file', default='', required=False)
@click.option('--format', 'fmt', type=click.Choice(['linkedin', 'google', 'auto']),
              default='auto', help='CSV format: linkedin, google, auto (default: auto)')
@click.option('--dry-run', is_flag=True, help='Parse and report only, do not write to DB')
@click.option('--batch-size', default=1000, type=int, help='Rows per commit batch')
@cli_logged("import_connections")
def import_connections_command(csv_file: str, fmt: str, dry_run: bool, batch_size: int):
    """Import LinkedIn connections from CSV export."""
    db_manager = cli_db_manager()
    start_time = time.time()

    if csv_file:
        csv_path = Path(csv_file)
    else:
        csv_path = _auto_detect_csv(Path.home() / 'Downloads' / 'Connections.csv')

    if not csv_path.exists():
        click.echo(f'ERROR: File not found: {csv_path}', err=True)
        raise SystemExit(1)

    # Parse CSV
    click.echo(f'Parsing {csv_path.name}...')
    rows = parse_csv(csv_path)
    click.echo(f'  -> {len(rows)} data rows')

    if dry_run:
        with_url = sum(1 for r in rows if (r.get('URL') or '').strip())
        with_email = sum(1 for r in rows if (r.get('Email Address') or '').strip())
        click.echo('\n--- DRY RUN ---')
        click.echo(f'Total rows:     {len(rows):>8,}')
        click.echo(f'With URL:       {with_url:>8,}')
        click.echo(f'Without URL:    {len(rows) - with_url:>8,}')
        click.echo(f'With email:     {with_email:>8,}')
        return

    # Build URL index
    click.echo('Building crawled_profile URL index...')
    with db_manager.get_session(DbSessionType.READ, app_user_id=SYSTEM_USER_ID) as session:
        url_index = build_linkedin_url_index(session)
    click.echo(f'  -> {len(url_index)} existing profiles indexed')

    # Load in batches
    click.echo(f'\nLoading connections (batch size: {batch_size})...')
    now = datetime.now(timezone.utc)
    totals = {'total': 0, 'matched': 0, 'unenriched': 0, 'no_url': 0, 'errors': 0}

    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]

        with db_manager.get_session(DbSessionType.WRITE, app_user_id=SYSTEM_USER_ID) as session:
            counts = load_csv_batch(session, batch, url_index, now)

        for k in totals:
            totals[k] += counts[k]

        progress = min(i + batch_size, len(rows))
        click.echo(
            f'  Batch: {progress}/{len(rows)} '
            f'({totals["matched"]} matched, {totals["unenriched"]} unenriched, '
            f'{totals["no_url"]} no-url, {totals["errors"]} errors)'
        )

    elapsed = time.time() - start_time
    duration_ms = elapsed * 1000

    logger.info(
        f'Import complete: {totals["total"]} rows, '
        f'{totals["matched"]} matched, {totals["unenriched"]} unenriched, '
        f'{totals["no_url"]} no-url, {totals["errors"]} errors, '
        f'{duration_ms:.0f}ms'
    )
    record_metric(
        "profiles_imported", totals["total"],
        source="csv", duration_ms=duration_ms,
        matched=totals["matched"], unenriched=totals["unenriched"],
        errors=totals["errors"],
    )

    click.echo('\nResults:')
    click.echo(f'  Imported:    {totals["matched"] + totals["unenriched"] + totals["no_url"]:>8,}')
    click.echo(f'  Matched:     {totals["matched"]:>8,}')
    click.echo(f'  Unenriched:  {totals["unenriched"]:>8,}')
    click.echo(f'  No URL:      {totals["no_url"]:>8,}')
    click.echo(f'  Errors:      {totals["errors"]:>8,}')
    click.echo(f'  Elapsed:     {elapsed:>7.1f}s')

    # Generate operation report
    imported = totals['matched'] + totals['unenriched'] + totals['no_url']

    cfg = get_config()
    next_steps = []
    if totals['unenriched'] > 0:
        cost_per = cfg.enrichment.cost_per_profile_usd
        cost = totals['unenriched'] * cost_per
        next_steps.append(
            f'Run `linkedout enrich` to fetch full profiles via Apify '
            f'(~${cost:.2f} for {totals["unenriched"]:,} profiles)'
        )
    next_steps.append('Run `linkedout compute-affinity` to calculate affinity scores')

    report = OperationReport(
        operation='import-connections',
        duration_ms=duration_ms,
        counts=OperationCounts(
            total=totals['total'],
            succeeded=imported,
            skipped=0,
            failed=totals['errors'],
        ),
        next_steps=next_steps,
    )
    report_path = report.save()

    click.echo('\nNext steps:')
    for step in next_steps:
        click.echo(f'  -> {step}')

    try:
        display = '~/' + str(report_path.relative_to(Path.home()))
    except ValueError:
        display = str(report_path)
    click.echo(f'\nReport saved: {display}')
