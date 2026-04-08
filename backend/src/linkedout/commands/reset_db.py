# SPDX-License-Identifier: Apache-2.0
"""``linkedout reset-db`` — reset the database.

Default: truncate data (fastest). Use ``--full`` for drop+recreate.
"""
import subprocess
import sys

import click
from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker

from shared.utilities.logger import get_logger
from shared.config import get_config
from common.entities.base_entity import TableName

logger = get_logger(__name__, component="cli", operation="reset_db")


def _get_db_session():
    """Create a standalone database session for maintenance."""
    engine = create_engine(get_config().database_url)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return session_factory()


def _truncate_all_tables(session):
    """Truncate all tables (data only reset)."""
    click.echo('Truncating all tables...')
    try:
        session.execute(text("SET session_replication_role = 'replica';"))
        all_tables = TableName.get_all_table_names()
        for table in reversed(all_tables):
            session.execute(text(f'TRUNCATE TABLE "{table}" CASCADE'))
        session.commit()
        session.execute(text("SET session_replication_role = 'origin';"))
        click.echo('All tables truncated successfully')
        return True
    except Exception as e:
        session.rollback()
        click.echo(f'Failed to truncate tables: {e}', err=True)
        try:
            session.execute(text("SET session_replication_role = 'origin';"))
        except Exception:
            pass
        return False


def _drop_all_tables():
    """Drop all tables and recreate via migrations."""
    click.echo('Dropping all tables...')
    try:
        engine = create_engine(get_config().database_url)
        with engine.connect() as conn:
            query = text("""
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
            """)
            result = conn.execute(query)
            tables = [row[0] for row in result]

            if tables:
                click.echo(f'  Found {len(tables)} tables to drop.')
                for table in tables:
                    conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
                conn.commit()

        click.echo('All tables dropped successfully')
        return True
    except Exception as e:
        click.echo(f'Failed to drop tables: {e}', err=True)
        return False


def _run_migrations():
    """Run Alembic migrations."""
    click.echo('Running Alembic migrations...')
    try:
        subprocess.run(
            ['alembic', 'upgrade', 'head'],
            capture_output=True,
            text=True,
            check=True,
        )
        click.echo('Migrations applied successfully')
        return True
    except subprocess.CalledProcessError as e:
        click.echo(f'Migration failed: {e}', err=True)
        if e.stderr:
            click.echo(e.stderr, err=True)
        return False


@click.command('reset-db')
@click.option('--full', is_flag=True, help='Drop all tables and recreate (default: truncate data only)')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompt')
def reset_db_command(full: bool, yes: bool):
    """Reset the database."""
    if not yes:
        mode_desc = 'DROP all tables and recreate' if full else 'TRUNCATE all data'
        if not click.confirm(f'This will {mode_desc}. Are you sure?'):
            click.echo('Cancelled.')
            return

    if full:
        if not _drop_all_tables():
            sys.exit(1)
        if not _run_migrations():
            sys.exit(1)
    else:
        session = _get_db_session()
        try:
            if not _truncate_all_tables(session):
                sys.exit(1)
        finally:
            session.close()

    click.echo('Done.')
