# SPDX-License-Identifier: Apache-2.0
"""Pytest configuration for integration tests.

This module provides session-scoped fixtures for integration testing against
a real PostgreSQL database. It creates an isolated test schema, runs migrations,
seeds test data, and cleans up after the test session.

Key fixtures:
- test_client: FastAPI TestClient for HTTP requests
- seeded_data: Dictionary of seeded entities by entity type
- test_tenant_id, test_bu_id: IDs for URL path parameters

Usage:
    pytestmark = pytest.mark.integration

    class TestYourControllerIntegration:
        def test_list_returns_data(self, test_client, test_tenant_id, test_bu_id):
            response = test_client.get(
                f"/tenants/{test_tenant_id}/bus/{test_bu_id}/your-entities"
            )
            assert response.status_code == 200
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from fastapi.testclient import TestClient
from dotenv import load_dotenv

# Add src directory to Python path
src_path = Path(__file__).parent.parent.parent / 'src'
sys.path.insert(0, str(src_path))

# Load environment files (.env.local takes precedence)
env_path = Path(__file__).parent.parent.parent
load_dotenv(env_path / '.env', override=False)
load_dotenv(env_path / '.env.local', override=True)

# Set environment for integration tests
os.environ['LINKEDOUT_ENVIRONMENT'] = 'integration_test'
os.environ.setdefault('LINKEDOUT_EMBEDDING__PROVIDER', 'local')

from common.entities.base_entity import Base
from shared.config.config import backend_config
from shared.infra.db.db_session_manager import db_session_manager
from shared.utilities.logger import get_logger
from dev_tools.db import fixed_data

# Import all entities to ensure they're registered with SQLAlchemy
import organization.entities  # noqa

# Common agent infrastructure
import common.entities.agent_run_entity  # noqa

import organization.entities.app_user_entity  # noqa
import organization.entities.app_user_tenant_role_entity  # noqa

# LinkedOut domain entities
import linkedout.company.entities.company_entity  # noqa
import linkedout.role_alias.entities.role_alias_entity  # noqa

logger = get_logger(__name__)

# Integration test schema name (per-worker for xdist parallelism)
_worker_id = os.environ.get('PYTEST_XDIST_WORKER', 'gw0')
TEST_SCHEMA = f'integration_test_{_worker_id}'


def _get_integration_db_url() -> str:
    """Get PostgreSQL database URL for integration tests.

    Loads DATABASE_URL from environment (.env.local preferred).

    Returns:
        str: PostgreSQL connection URL.

    Raises:
        pytest.skip: If DATABASE_URL is SQLite or not configured for PostgreSQL.
    """
    db_url = os.environ.get('DATABASE_URL', backend_config.database_url)

    if not db_url:
        pytest.skip('DATABASE_URL not configured - skipping integration tests')

    if 'sqlite' in db_url.lower():
        pytest.skip(
            'Integration tests require PostgreSQL. '
            'Configure DATABASE_URL in .env.local pointing to a PostgreSQL database.'
        )

    if 'postgresql' not in db_url.lower():
        pytest.skip(
            f'Integration tests require PostgreSQL, got: {db_url[:30]}...'
        )

    return db_url


@pytest.fixture(scope='session')
def integration_db_engine() -> Generator[Engine, None, None]:
    """Create PostgreSQL engine with test schema.

    Creates an isolated schema for integration tests, runs all table
    creations, and cleans up the schema after the test session.

    Yields:
        Engine: SQLAlchemy engine connected to the test schema.
    """
    db_url = _get_integration_db_url()
    logger.info(f'Setting up integration test database: {db_url}')

    # Create engine for schema management (without schema search path)
    admin_engine = create_engine(db_url, echo=False)

    try:
        # Create test schema
        with admin_engine.connect() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE'))
            conn.execute(text(f'CREATE SCHEMA {TEST_SCHEMA}'))
            conn.commit()
            logger.info(f'Created schema: {TEST_SCHEMA}')
    except OperationalError as e:
        admin_engine.dispose()
        pytest.skip(
            f'Cannot connect to PostgreSQL database. '
            f'Ensure PostgreSQL is running and DATABASE_URL is correct. '
            f'Error: {str(e)[:100]}'
        )

    try:
        # Create engine with test schema in search path
        # Include public so pgvector types (installed there) are resolvable.
        # Use checkfirst=False in create_all to avoid SQLAlchemy seeing
        # public.* tables and skipping creation in the test schema.
        if '?' in db_url:
            test_url = f'{db_url}&options=-csearch_path%3D{TEST_SCHEMA}%2Cpublic'
        else:
            test_url = f'{db_url}?options=-csearch_path%3D{TEST_SCHEMA}%2Cpublic'

        engine = create_engine(test_url, echo=False)

        # Create all tables in the test schema.
        # checkfirst=False prevents SQLAlchemy from using has_table() which
        # would see public.* tables via the search_path and skip creation.
        Base.metadata.create_all(engine, checkfirst=False)
        logger.info('Created all tables in test schema')

        yield engine

    finally:
        # Cleanup: drop test schema
        try:
            with admin_engine.connect() as conn:
                conn.execute(text(f'DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE'))
                conn.commit()
                logger.info(f'Dropped schema: {TEST_SCHEMA}')
        except Exception as e:
            logger.warning(f'Failed to drop schema: {e}')

        admin_engine.dispose()


@pytest.fixture(scope='session')
def integration_db_session(
    integration_db_engine: Engine,
) -> Generator[Session, None, None]:
    """Create a database session for the integration test schema.

    Args:
        integration_db_engine: The PostgreSQL engine with test schema.

    Yields:
        Session: SQLAlchemy session bound to the test schema.
    """
    SessionLocal = sessionmaker(
        bind=integration_db_engine,
        autoflush=False,
        autocommit=False,
    )

    session = SessionLocal()

    # Configure db_session_manager to use this engine
    db_session_manager.set_engine(integration_db_engine)

    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope='session')
def seeded_data(
    integration_db_session: Session,
) -> Dict[str, list[Any]]:
    """Seed the integration test database with test data.

    Uses BaseSeeder to populate the database with deterministic test data.

    Args:
        integration_db_session: SQLAlchemy session for the test schema.

    Returns:
        Dict[str, list[Any]]: Dictionary mapping entity type names to
            lists of seeded entities.
    """
    from shared.test_utils.entity_factories import EntityFactory
    from shared.test_utils.seeders.base_seeder import BaseSeeder
    from shared.test_utils.seeders.seed_config import SeedConfig

    logger.info('Seeding integration test database...')
    factory = EntityFactory(integration_db_session)
    seeder = BaseSeeder(integration_db_session, factory)
    config = SeedConfig(tables=['*'])
    data = seeder.seed(config)
    logger.info(f'Seeding complete. Entities: {list(data.keys())}')
    return data


@pytest.fixture(scope='session')
def test_tenant_id(seeded_data: Dict[str, list[Any]]) -> str:
    """Get the primary test tenant ID.

    Args:
        seeded_data: Dictionary of seeded entities.

    Returns:
        str: The tenant ID for URL path parameters.
    """
    return fixed_data.FIXED_TENANT['id']


@pytest.fixture(scope='session')
def test_bu_id(seeded_data: Dict[str, list[Any]]) -> str:
    """Get the primary test business unit ID.

    Args:
        seeded_data: Dictionary of seeded entities.

    Returns:
        str: The BU ID for URL path parameters.
    """
    return fixed_data.FIXED_BUS[0]['id']


@pytest.fixture(scope='session')
def test_client(
    integration_db_engine: Engine,
    seeded_data: Dict[str, list[Any]],
) -> Generator[TestClient, None, None]:
    """Create FastAPI TestClient for integration tests.

    The TestClient is configured to use the integration test database
    and is session-scoped for efficiency.

    Args:
        integration_db_engine: PostgreSQL engine with test schema.
        seeded_data: Ensures seeding happens before client is used.

    Yields:
        TestClient: FastAPI test client for HTTP requests.
    """
    # Configure db_session_manager to use the test engine
    db_session_manager.set_engine(integration_db_engine)

    # Import app after configuring database
    from main import app

    with TestClient(app) as client:
        yield client


# =============================================================================
# PYTEST HOOKS
# =============================================================================


def pytest_configure(config):
    """Register integration test marker."""
    config.addinivalue_line(
        'markers',
        'integration: mark test as an integration test'
    )
