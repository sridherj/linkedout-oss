# SPDX-License-Identifier: Apache-2.0
"""Load JSON fixture data into the database.

Loads pre-extracted fixture data (profiles, companies, experiences, educations, skills)
from src/dev_tools/db/fixtures/ JSON files. Intended for dev environments where
you want a representative slice of data without running the full Apify/CSV loaders.

Usage:
    uv run python -m dev_tools.db.load_fixtures [--dry-run]
"""
import json
from pathlib import Path

import click
from sqlalchemy import text

from shared.infra.db.cli_db import cli_db_manager
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger

logger = get_logger(__name__)

FIXTURES_DIR = Path(__file__).parent / 'fixtures'

# Table -> JSON file -> columns to insert
FIXTURE_TABLES = [
    ('company', 'companies.json', [
        'id', 'canonical_name', 'normalized_name', 'linkedin_url', 'universal_name',
        'website', 'domain', 'industry', 'founded_year', 'hq_city', 'hq_country',
        'employee_count_range', 'estimated_employee_count', 'size_tier',
        'network_connection_count', 'enrichment_sources',
    ]),
    ('crawled_profile', 'crawled_profiles.json', [
        'id', 'linkedin_url', 'public_identifier', 'first_name', 'last_name', 'full_name',
        'headline', 'about', 'location_city', 'location_state', 'location_country',
        'location_country_code', 'connections_count', 'follower_count',
        'current_company_name', 'current_position', 'company_id',
        'seniority_level', 'function_area', 'has_enriched_data', 'data_source',
        'profile_image_url', 'open_to_work', 'premium',
    ]),
    ('experience', 'experiences.json', [
        'id', 'crawled_profile_id', 'position', 'company_name', 'company_id',
        'employment_type', 'start_year', 'start_month', 'end_year', 'end_month',
        'is_current', 'seniority_level', 'function_area', 'location',
    ]),
    ('education', 'educations.json', [
        'id', 'crawled_profile_id', 'school_name', 'degree', 'field_of_study',
        'start_year', 'end_year',
    ]),
    ('profile_skill', 'profile_skills.json', [
        'id', 'crawled_profile_id', 'skill_name', 'endorsement_count',
    ]),
]


def _load_json(filename: str) -> list[dict]:
    path = FIXTURES_DIR / filename
    if not path.exists():
        logger.warning(f'Fixture file not found: {path}')
        return []
    with open(path) as f:
        data = json.load(f)
    return data if data else []


@click.command()
@click.option('--dry-run', is_flag=True, help='Report counts only, do not insert')
def main(dry_run: bool):
    """Load JSON fixture data into the database."""
    db_manager = cli_db_manager()
    for table_name, json_file, columns in FIXTURE_TABLES:
        rows = _load_json(json_file)
        if not rows:
            logger.info(f'{table_name}: no fixture data')
            continue

        logger.info(f'{table_name}: {len(rows)} rows from {json_file}')

        if dry_run:
            continue

        col_list = ', '.join(columns)
        param_list = ', '.join(f':{c}' for c in columns)
        sql = text(
            f'INSERT INTO {table_name} ({col_list}) VALUES ({param_list}) '
            f'ON CONFLICT (id) DO NOTHING'
        )

        with db_manager.get_session(DbSessionType.WRITE) as session:
            inserted = 0
            for row in rows:
                params = {c: row.get(c) for c in columns}
                result = session.execute(sql, params)
                inserted += result.rowcount
            session.commit()
            logger.info(f'{table_name}: inserted {inserted}/{len(rows)} rows')

    logger.info('Fixture loading complete.')


if __name__ == '__main__':
    main()
