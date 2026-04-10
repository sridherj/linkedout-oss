# SPDX-License-Identifier: Apache-2.0
"""Import top companies from PDL SQLite into the LinkedOut company table.

One-time maintainer script for populating the full seed tier. Reads from a PDL
SQLite database, filters to US/India companies with 201+ employees and quality
data (website + known industry), and inserts into PostgreSQL. Skips companies
that already exist (by normalized_name). Uses RLS with system user.

Usage:
    cd src && DATABASE_URL="postgresql://..." python -m dev_tools.import_pdl_companies \
        --pdl-db ~/workspace/second-brain/data/pdl/companies.sqlite \
        --dry-run
"""
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlparse

import click
from sqlalchemy import text

from dev_tools.db.fixed_data import SYSTEM_USER_ID
from shared.infra.db.cli_db import cli_db_manager
from shared.infra.db.db_session_manager import DbSessionType

# PDL size bracket -> (estimated_employee_count, size_tier)
SIZE_MAP = {
    '201-500': (350, 'mid'),
    '501-1000': (750, 'mid'),
    '1001-5000': (3000, 'large'),
    '5001-10000': (7500, 'large'),
    '10001+': (15000, 'enterprise'),
}

VALID_SIZES = tuple(SIZE_MAP.keys())

BATCH_SIZE = 1000


def _extract_domain(website: str | None) -> str | None:
    """Extract domain from a website URL."""
    if not website:
        return None
    try:
        url = website if '://' in website else f'https://{website}'
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        domain = domain.lower().removeprefix('www.')
        return domain if domain else None
    except Exception:
        return None


def _normalize_name(name: str) -> str:
    """Lowercase name for dedup matching."""
    return name.strip().lower()


def _title_case_name(name: str) -> str:
    """Convert lowercase name to title case for canonical_name."""
    return name.strip().title()


def _read_pdl_companies(pdl_db: Path) -> list[dict]:
    """Read qualifying companies from PDL SQLite."""
    conn = sqlite3.connect(str(pdl_db))
    conn.row_factory = sqlite3.Row

    placeholders = ','.join(['?'] * len(VALID_SIZES))
    query = f"""
        SELECT name_lower, pdl_id, industry, website, founded, country, locality, size
        FROM pdl_companies
        WHERE country IN ('united states', 'india')
          AND size IN ({placeholders})
          AND website IS NOT NULL AND website != ''
          AND industry IS NOT NULL AND industry != '' AND industry != 'Unknown'
          AND name_lower IS NOT NULL AND name_lower != ''
        ORDER BY CASE size
            WHEN '10001+' THEN 1 WHEN '5001-10000' THEN 2 WHEN '1001-5000' THEN 3
            WHEN '501-1000' THEN 4 WHEN '201-500' THEN 5 END
    """

    rows = [dict(r) for r in conn.execute(query, VALID_SIZES).fetchall()]
    conn.close()
    return rows


def _get_existing_names(session) -> set[str]:
    """Get all normalized_name values already in the company table."""
    result = session.execute(text('SELECT normalized_name FROM company'))
    return {row[0] for row in result.fetchall()}


@click.command()
@click.option('--pdl-db', required=True, type=click.Path(exists=True), help='Path to PDL companies.sqlite')
@click.option('--dry-run', is_flag=True, help='Show counts without writing')
def main(pdl_db: str, dry_run: bool):
    """Import top US/India companies from PDL SQLite into company table."""
    db_manager = cli_db_manager()
    pdl_path = Path(pdl_db)
    start = time.time()

    click.echo(f'Reading PDL data from {pdl_path}...')
    pdl_rows = _read_pdl_companies(pdl_path)
    click.echo(f'  PDL companies matching filter: {len(pdl_rows):,}')

    # Get existing names for dedup
    with db_manager.get_session(DbSessionType.READ, app_user_id=SYSTEM_USER_ID) as session:
        existing_names = _get_existing_names(session)
    click.echo(f'  Existing companies in DB: {len(existing_names):,}')

    # Build insert list (dedup by normalized_name)
    to_insert = []
    seen_names: set[str] = set()
    skipped_existing = 0
    skipped_dupe = 0

    for row in pdl_rows:
        norm_name = _normalize_name(row['name_lower'])
        if not norm_name:
            continue
        if norm_name in existing_names:
            skipped_existing += 1
            continue
        if norm_name in seen_names:
            skipped_dupe += 1
            continue
        seen_names.add(norm_name)

        est_count, tier = SIZE_MAP[row['size']]
        founded = None
        if row['founded']:
            try:
                founded = int(row['founded'])
            except (ValueError, TypeError):
                pass

        to_insert.append({
            'canonical_name': _title_case_name(row['name_lower']),
            'normalized_name': norm_name,
            'pdl_id': row['pdl_id'],
            'industry': row['industry'],
            'website': row['website'],
            'domain': _extract_domain(row['website']),
            'founded_year': founded,
            'hq_country': row['country'],
            'hq_city': row['locality'],
            'employee_count_range': row['size'],
            'estimated_employee_count': est_count,
            'size_tier': tier,
            'enrichment_sources': ['pdl-seed'],
        })

    click.echo(f'  To insert: {len(to_insert):,}')
    click.echo(f'  Skipped (already in DB): {skipped_existing:,}')
    click.echo(f'  Skipped (PDL duplicates): {skipped_dupe:,}')

    if dry_run:
        click.echo('\n[DRY RUN] No data written.')
        return

    # Insert in batches
    click.echo(f'\nInserting {len(to_insert):,} companies...')
    inserted = 0

    insert_sql = text("""
        INSERT INTO company (
            id, canonical_name, normalized_name, pdl_id, industry, website, domain,
            founded_year, hq_country, hq_city, employee_count_range,
            estimated_employee_count, size_tier, enrichment_sources,
            network_connection_count, is_active, version
        ) VALUES (
            'co' || substr(md5(random()::text), 1, 12),
            :canonical_name, :normalized_name, :pdl_id, :industry, :website, :domain,
            :founded_year, :hq_country, :hq_city, :employee_count_range,
            :estimated_employee_count, :size_tier, :enrichment_sources,
            0, true, 1
        )
        ON CONFLICT (canonical_name) DO NOTHING
    """)

    with db_manager.get_session(DbSessionType.WRITE, app_user_id=SYSTEM_USER_ID) as session:
        for batch_start in range(0, len(to_insert), BATCH_SIZE):
            batch = to_insert[batch_start:batch_start + BATCH_SIZE]
            for row in batch:
                try:
                    result = session.execute(insert_sql, row)
                    if result.rowcount > 0:
                        inserted += 1
                except Exception as e:
                    click.echo(f'  Error inserting {row["canonical_name"]}: {e}')

            done = min(batch_start + BATCH_SIZE, len(to_insert))
            click.echo(f'\r  Progress: {done:,}/{len(to_insert):,} ({inserted:,} inserted)', nl=False)

        click.echo()

    elapsed = time.time() - start
    click.echo(f'\nDone: {inserted:,} companies inserted in {elapsed:.1f}s')


if __name__ == '__main__':
    main()
