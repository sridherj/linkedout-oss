# SPDX-License-Identifier: Apache-2.0
"""Fix crawled_profile rows where full_name contains the literal string 'None'.

Caused by f-string interpolation of Python None values during Apify data loading.
Reconstructs full_name from first_name + last_name where possible, otherwise NULL.
"""
import click
from sqlalchemy import text

from dev_tools.db.fixed_data import SYSTEM_USER_ID
from shared.infra.db.cli_db import cli_db_manager
from shared.infra.db.db_session_manager import DbSessionType


def main(dry_run: bool = False) -> int:
    db_manager = cli_db_manager()
    count_sql = text("""
        SELECT COUNT(*) FROM crawled_profile WHERE full_name LIKE '%None%'
    """)
    fix_sql = text("""
        UPDATE crawled_profile
        SET full_name = CASE
            WHEN first_name IS NOT NULL AND last_name IS NOT NULL
                THEN first_name || ' ' || last_name
            WHEN first_name IS NOT NULL THEN first_name
            WHEN last_name IS NOT NULL THEN last_name
            ELSE NULL
        END
        WHERE full_name LIKE '%None%'
    """)

    with db_manager.get_session(DbSessionType.READ, app_user_id=SYSTEM_USER_ID) as session:
        affected = session.execute(count_sql).scalar()

    click.echo(f"Rows with 'None' in full_name: {affected}")

    if dry_run:
        click.echo('Dry run — no changes written.')
        return 0

    if affected == 0:
        click.echo('Nothing to fix.')
        return 0

    with db_manager.get_session(DbSessionType.WRITE, app_user_id=SYSTEM_USER_ID) as session:
        session.execute(fix_sql)

    click.echo(f'Fixed {affected} rows.')
    return 0
