# SPDX-License-Identifier: Apache-2.0
"""Pytest configuration for search quality eval tests.

Eval tests run against the REAL production database with real LinkedIn data.
They are excluded from regular test runs via the 'eval' marker.

Run with: pytest tests/eval/ -m eval -v
"""
import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add src directory to Python path
src_path = Path(__file__).parent.parent.parent / 'src'
sys.path.insert(0, str(src_path))

# Load environment
env_path = Path(__file__).parent.parent.parent
load_dotenv(env_path / '.env', override=False)
load_dotenv(env_path / '.env.local', override=True)


def pytest_configure(config):
    config.addinivalue_line(
        'markers',
        'eval: Search quality evaluation tests (run with -m eval)'
    )


@pytest.fixture(scope="session")
def db_session():
    """Create a session against the real production database."""
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        pytest.skip('DATABASE_URL not configured — cannot run eval tests')
    if 'postgresql' not in db_url.lower():
        pytest.skip('Eval tests require PostgreSQL')

    engine = create_engine(db_url, echo=False)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(scope="session")
def app_user_id(db_session):
    """Get the first real app_user_id that has connections."""
    # Check if the connection table exists at all
    table_exists = db_session.execute(
        text("SELECT to_regclass('public.connection')")
    ).scalar()
    if not table_exists:
        pytest.skip('No connection table — run LinkedIn CSV loader first')

    result = db_session.execute(text(
        "SELECT app_user_id FROM connection "
        "GROUP BY app_user_id "
        "ORDER BY count(*) DESC "
        "LIMIT 1"
    )).scalar()
    if not result:
        pytest.skip('No app_users with connections found — run LinkedIn CSV loader first')
    return result
