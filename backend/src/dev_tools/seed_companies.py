# SPDX-License-Identifier: Apache-2.0
"""Seed companies from YC (yc-oss API) and PDL (CSV cross-reference).

Step 9a: Fetch YC companies from yc-oss API, upsert into company table.
Step 9c: Import PDL CSV into temp SQLite, cross-reference by linkedin_url.

Usage:
    cd src && uv run python -m dev_tools.seed_companies [--yc-only] [--pdl-only] [--dry-run]
"""
import csv
import json
import os
import re
import tempfile
import time
import urllib.request
from pathlib import Path

import click
from sqlalchemy import text

from shared.infra.db.cli_db import cli_db_manager
from shared.infra.db.db_session_manager import DbSessionType
from shared.utils.company_matcher import normalize_company_name

YC_API_URL = 'https://yc-oss.github.io/api/companies/all.json'
PDL_CSV_PATH = Path.home() / 'workspace/second-brain/data/pdl/companies.csv'


# ─── YC Helpers ────────────────────────────────────────────────────────────


def team_size_to_range(size):
    if not size:
        return None
    if size <= 10:
        return '1-10'
    if size <= 50:
        return '11-50'
    if size <= 200:
        return '51-200'
    if size <= 500:
        return '201-500'
    if size <= 1000:
        return '501-1000'
    if size <= 5000:
        return '1001-5000'
    return '5001-10000'


def size_tier(size):
    if not size:
        return None
    if size <= 10:
        return 'micro'
    if size <= 50:
        return 'small'
    if size <= 200:
        return 'medium'
    if size <= 1000:
        return 'large'
    return 'enterprise'


def parse_location(loc_str):
    if not loc_str:
        return None, None
    first = loc_str.split(';')[0].strip()
    parts = [p.strip() for p in first.split(',')]
    if len(parts) >= 2:
        return parts[0], parts[-1]
    if len(parts) == 1:
        return None, parts[0]
    return None, None


def parse_batch_year(batch):
    if not batch:
        return None
    match = re.search(r'(\d{4})', batch)
    return int(match.group(1)) if match else None


def domain_from_website(url):
    if not url:
        return None
    url = url.lower().replace('https://', '').replace('http://', '')
    url = url.split('/')[0].split('?')[0]
    if url.startswith('www.'):
        url = url[4:]
    return url or None


# ─── YC Import ─────────────────────────────────────────────────────────────


def import_yc_companies(dry_run: bool) -> dict[str, int]:
    """Fetch YC companies from yc-oss API and upsert into company table."""
    db_manager = cli_db_manager()
    click.echo(f'Fetching YC companies from {YC_API_URL}...')
    with urllib.request.urlopen(YC_API_URL) as resp:
        data = json.loads(resp.read().decode())
    click.echo(f'  -> {len(data)} companies fetched')

    if dry_run:
        click.echo('  [DRY RUN] Would process YC companies')
        return {'fetched': len(data), 'inserted': 0, 'updated': 0, 'skipped': 0}

    inserted = 0
    updated = 0
    skipped = 0

    with db_manager.get_session(DbSessionType.WRITE) as session:
        # Pre-load existing companies by normalized_name for fast lookup
        existing_rows = session.execute(text(
            "SELECT id, canonical_name, normalized_name, enrichment_sources FROM company"
        )).fetchall()
        by_normalized: dict[str, tuple] = {}
        by_canonical: dict[str, tuple] = {}
        for row in existing_rows:
            by_normalized[row[2]] = (row[0], row[1], row[3])
            by_canonical[row[1]] = (row[0], row[1], row[3])

        for company in data:
            name = (company.get('name') or '').strip()
            if not name:
                skipped += 1
                continue

            normalized = normalize_company_name(name)
            if not normalized:
                skipped += 1
                continue

            # Check if already has yc source
            existing = by_normalized.get(normalized) or by_canonical.get(name)
            if existing:
                cid, _, sources = existing
                if sources and 'yc-oss-api' in sources:
                    skipped += 1
                    continue

                # Update existing with YC data (fill blanks)
                website = company.get('website') or ''
                domain = domain_from_website(website)
                team_sz = company.get('team_size')
                hq_city, hq_country = parse_location(company.get('all_locations'))

                session.execute(text(
                    "UPDATE company SET "
                    "  website = COALESCE(NULLIF(website, ''), :website), "
                    "  domain = COALESCE(NULLIF(domain, ''), :domain), "
                    "  industry = COALESCE(NULLIF(industry, ''), :industry), "
                    "  hq_city = COALESCE(NULLIF(hq_city, ''), :hq_city), "
                    "  hq_country = COALESCE(NULLIF(hq_country, ''), :hq_country), "
                    "  founded_year = COALESCE(founded_year, :founded_year), "
                    "  estimated_employee_count = COALESCE(estimated_employee_count, :est_emp), "
                    "  employee_count_range = COALESCE(NULLIF(employee_count_range, ''), :emp_range), "
                    "  size_tier = COALESCE(NULLIF(size_tier, ''), :size_tier), "
                    "  enrichment_sources = array_append(COALESCE(enrichment_sources, '{}'), 'yc-oss-api') "
                    "WHERE id = :cid"
                ), {
                    'website': website, 'domain': domain,
                    'industry': company.get('industry') or '',
                    'hq_city': hq_city, 'hq_country': hq_country,
                    'founded_year': parse_batch_year(company.get('batch')),
                    'est_emp': team_sz, 'emp_range': team_size_to_range(team_sz),
                    'size_tier': size_tier(team_sz), 'cid': cid,
                })
                updated += 1
            else:
                # Insert new company
                website = company.get('website') or ''
                domain = domain_from_website(website)
                team_sz = company.get('team_size')
                hq_city, hq_country = parse_location(company.get('all_locations'))
                norm_name = normalize_company_name(name)

                session.execute(text(
                    "INSERT INTO company (id, canonical_name, normalized_name, website, domain, "
                    "  industry, hq_city, hq_country, founded_year, "
                    "  estimated_employee_count, employee_count_range, size_tier, "
                    "  enrichment_sources, network_connection_count) "
                    "VALUES (:id, :canonical, :normalized, :website, :domain, "
                    "  :industry, :hq_city, :hq_country, :founded_year, "
                    "  :est_emp, :emp_range, :size_tier, "
                    "  ARRAY['yc-oss-api'], 0) "
                    "ON CONFLICT (canonical_name) DO UPDATE SET "
                    "  enrichment_sources = array_append(COALESCE(company.enrichment_sources, '{}'), 'yc-oss-api')"
                ), {
                    'id': _generate_company_id(),
                    'canonical': name, 'normalized': norm_name,
                    'website': website, 'domain': domain,
                    'industry': company.get('industry') or None,
                    'hq_city': hq_city, 'hq_country': hq_country,
                    'founded_year': parse_batch_year(company.get('batch')),
                    'est_emp': team_sz, 'emp_range': team_size_to_range(team_sz),
                    'size_tier': size_tier(team_sz),
                })
                inserted += 1

            if (inserted + updated) % 500 == 0 and (inserted + updated) > 0:
                click.echo(f'  Progress: {inserted} inserted, {updated} updated, {skipped} skipped')

    return {'fetched': len(data), 'inserted': inserted, 'updated': updated, 'skipped': skipped}


def _generate_company_id() -> str:
    """Generate a prefixed company ID matching BaseEntity pattern."""
    import uuid
    return f'co_{uuid.uuid4().hex[:24]}'


# ─── PDL Cross-Reference ──────────────────────────────────────────────────


def normalize_linkedin_company_url(url: str) -> str | None:
    """Normalize a LinkedIn company URL from PDL format to canonical."""
    if not url:
        return None
    url = url.strip().lower()
    if not url.startswith('http'):
        url = f'https://www.{url}'
    match = re.search(r'/company/([^/?#]+)', url)
    if not match:
        return None
    slug = match.group(1).rstrip('/')
    return f'https://www.linkedin.com/company/{slug}'


def pdl_cross_reference(pdl_csv_path: str, dry_run: bool) -> dict[str, int]:
    """Import PDL CSV into temp SQLite, cross-reference companies by linkedin_url."""
    db_manager = cli_db_manager()
    csv_path = Path(pdl_csv_path)
    if not csv_path.exists():
        click.echo(f'  PDL CSV not found: {csv_path}')
        return {'matched': 0, 'enriched': 0}

    click.echo(f'Loading PDL CSV into temp SQLite (this may take a few minutes for 5GB)...')

    # Create temp SQLite DB
    fd, sqlite_path = tempfile.mkstemp(suffix='.db', prefix='pdl_temp_')
    os.close(fd)

    try:
        # Step 1: Get all company linkedin_urls from our DB
        click.echo('  Fetching company linkedin_urls from DB...')
        with db_manager.get_session(DbSessionType.READ) as session:
            rows = session.execute(text(
                "SELECT id, linkedin_url FROM company "
                "WHERE linkedin_url IS NOT NULL AND linkedin_url != ''"
            )).fetchall()

        our_companies: dict[str, str] = {}  # normalized_url -> company_id
        for row in rows:
            norm = normalize_linkedin_company_url(row[1])
            if norm:
                our_companies[norm] = row[0]

        click.echo(f'  -> {len(our_companies)} companies with linkedin_urls')

        if dry_run:
            click.echo('  [DRY RUN] Would cross-reference with PDL')
            return {'matched': 0, 'enriched': 0}

        # Step 2: Build a set of target slugs for fast CSV filtering
        target_slugs: set[str] = set()
        for url in our_companies:
            match = re.search(r'/company/([^/?#]+)', url)
            if match:
                target_slugs.add(match.group(1))

        click.echo(f'  Scanning PDL CSV for {len(target_slugs)} target companies...')

        # Step 3: Stream through CSV, only keep rows that match our companies
        matched_data: dict[str, dict] = {}  # normalized_url -> pdl row data
        rows_scanned = 0

        with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows_scanned += 1
                if rows_scanned % 5_000_000 == 0:
                    click.echo(f'    Scanned {rows_scanned:,} rows, found {len(matched_data)} matches...')

                li_url = row.get('linkedin_url', '').strip()
                if not li_url:
                    continue

                # Quick slug check before full normalization
                slug_match = re.search(r'/company/([^/?#]+)', li_url)
                if not slug_match or slug_match.group(1).lower() not in target_slugs:
                    continue

                norm = normalize_linkedin_company_url(li_url)
                if norm and norm in our_companies:
                    matched_data[norm] = {
                        'industry': row.get('industry', '').strip() or None,
                        'founded_year': int(row['founded']) if row.get('founded', '').strip().isdigit() else None,
                        'employee_count_range': row.get('size', '').strip() or None,
                        'website': row.get('website', '').strip() or None,
                        'domain': domain_from_website(row.get('website', '')),
                        'hq_city': row.get('locality', '').strip() or None,
                        'hq_country': row.get('country', '').strip() or None,
                    }

        click.echo(f'  -> Scanned {rows_scanned:,} rows, {len(matched_data)} matches')

        # Step 4: Update matched companies
        enriched = 0
        with db_manager.get_session(DbSessionType.WRITE) as session:
            for norm_url, pdl_data in matched_data.items():
                company_id = our_companies[norm_url]
                session.execute(text(
                    "UPDATE company SET "
                    "  industry = COALESCE(NULLIF(industry, ''), :industry), "
                    "  founded_year = COALESCE(founded_year, :founded_year), "
                    "  employee_count_range = COALESCE(NULLIF(employee_count_range, ''), :emp_range), "
                    "  website = COALESCE(NULLIF(website, ''), :website), "
                    "  domain = COALESCE(NULLIF(domain, ''), :domain), "
                    "  hq_city = COALESCE(NULLIF(hq_city, ''), :hq_city), "
                    "  hq_country = COALESCE(NULLIF(hq_country, ''), :hq_country), "
                    "  enrichment_sources = array_append(COALESCE(enrichment_sources, '{}'), 'pdl'), "
                    "  enriched_at = NOW() "
                    "WHERE id = :cid AND NOT (COALESCE(enrichment_sources, '{}') @> ARRAY['pdl'])"
                ), {
                    'industry': pdl_data['industry'],
                    'founded_year': pdl_data['founded_year'],
                    'emp_range': pdl_data['employee_count_range'],
                    'website': pdl_data['website'],
                    'domain': pdl_data['domain'],
                    'hq_city': pdl_data['hq_city'],
                    'hq_country': pdl_data['hq_country'],
                    'cid': company_id,
                })
                enriched += 1

        return {'matched': len(matched_data), 'enriched': enriched}

    finally:
        # Cleanup temp SQLite
        if os.path.exists(sqlite_path):
            os.unlink(sqlite_path)


# ─── Main ──────────────────────────────────────────────────────────────────


@click.command()
@click.option('--dry-run', is_flag=True, help='Report only, do not write to DB')
@click.option('--yc-only', is_flag=True, help='Only import YC companies')
@click.option('--pdl-only', is_flag=True, help='Only run PDL cross-reference')
@click.option('--pdl-csv', default=str(PDL_CSV_PATH), help='Path to PDL companies CSV')
def main(dry_run: bool, yc_only: bool, pdl_only: bool, pdl_csv: str):
    """Seed companies from YC and PDL sources."""
    start_time = time.time()

    if not pdl_only:
        click.echo('\n=== Step 9a: YC Companies Import ===')
        yc_stats = import_yc_companies(dry_run)
        click.echo(f'  YC: fetched={yc_stats["fetched"]}, inserted={yc_stats["inserted"]}, '
                    f'updated={yc_stats["updated"]}, skipped={yc_stats["skipped"]}')

    if not yc_only:
        click.echo('\n=== Step 9c: PDL Cross-Reference ===')
        pdl_stats = pdl_cross_reference(pdl_csv, dry_run)
        click.echo(f'  PDL: matched={pdl_stats["matched"]}, enriched={pdl_stats["enriched"]}')

    elapsed = time.time() - start_time
    click.echo(f'\nElapsed: {elapsed:.1f}s')


if __name__ == '__main__':
    main()
