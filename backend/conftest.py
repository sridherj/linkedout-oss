"""
Pytest configuration and fixtures for the sample backend.

# HOW TO USE THIS TESTING INFRASTRUCTURE

This conftest provides fixtures for repository layer testing with two patterns:

## Pattern 1: Read-Only Tests (Shared Database)
Use for tests that only READ data (list, get, count, filter operations).
Faster because all read-only tests share one pre-seeded database.

    class TestYourRepositoryReadOnly:
        @pytest.fixture
        def db_session(self, shared_db_session):
            return shared_db_session

        @pytest.fixture
        def seeded_data(self, all_seeded_data_for_shared_db):
            return all_seeded_data_for_shared_db

        def test_list_entities(self, db_session, seeded_data):
            repo = YourRepository(db_session)
            # seeded_data contains pre-populated entities by TableName
            results = repo.list_with_filters(...)
            assert len(results) > 0

## Pattern 2: Mutation Tests (Isolated Database)
Use for tests that CREATE, UPDATE, or DELETE data.
Each test class gets its own fresh database.

    from tests.seed_db import SeedDb, TableName

    # Only seed what this test class needs
    CUSTOM_SEED_CONFIG = SeedDb.SeedConfig(
        tables_to_populate=[TableName.TENANT, TableName.BU, TableName.LABEL],
        label_count=0,  # Tests create their own
    )

    @pytest.mark.seed_config(CUSTOM_SEED_CONFIG)
    class TestYourRepositoryCreate:
        @pytest.fixture(scope='class')
        def class_db_resources(self, class_scoped_isolated_db_session):
            return class_scoped_isolated_db_session

        @pytest.fixture(scope='class')
        def db_session(self, class_db_resources):
            session, _ = class_db_resources
            return session

        @pytest.fixture(scope='class')
        def seeded_data(self, class_db_resources):
            _, data = class_db_resources
            return data

        def test_create_entity(self, db_session, seeded_data):
            repo = YourRepository(db_session)
            entity = repo.create(...)
            db_session.commit()
            assert entity.id is not None

## Quick Reference
- `shared_db_session` -> For read-only tests (function-scoped)
- `class_scoped_isolated_db_session` -> For mutation tests (class-scoped)
- `function_scoped_isolated_db_session` -> For isolated single tests (function-scoped)
- `all_seeded_data_for_shared_db` -> Pre-seeded data from shared DB
- `@pytest.mark.seed_config(config)` -> Custom seeding for isolated DBs
"""

import os
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from typing import Generator, Dict, Any, Tuple

# Add src directory to Python path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

# Session-level temp data dir — set BEFORE any config import to prevent
# tests from ever writing to ~/linkedout-data/.
_test_data_dir = tempfile.mkdtemp(prefix='linkedout-test-')
os.environ.setdefault('LINKEDOUT_DATA_DIR', _test_data_dir)

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine, event, Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles
import json

# Handle PostgreSQL JSONB for SQLite tests
from sqlalchemy.dialects.postgresql import JSONB as _pg_jsonb
from sqlalchemy.dialects.postgresql import ARRAY as _pg_array
from sqlalchemy.dialects.sqlite import JSON as _sqlite_json


@compiles(_pg_jsonb, 'sqlite')
def compile_pgjsonb_as_sqlitejson(type_, compiler, **kw):
    """
    Compile PostgreSQL JSONB as SQLite JSON.

    When SQLAlchemy encounters the postgresql.JSONB type and the target
    dialect is SQLite, this function tells the compiler to treat it as
    sqlite.JSON.
    """
    return compiler.visit_JSON(_sqlite_json(), **kw)


@compiles(_pg_array, 'sqlite')
def compile_pgarray_as_sqlitejson(type_, compiler, **kw):
    """
    Compile PostgreSQL ARRAY as SQLite JSON.

    SQLite has no native array type. We store arrays as JSON text,
    which is sufficient for test purposes.
    """
    return compiler.visit_JSON(_sqlite_json(), **kw)



# Load test defaults from .env.test (override=False so CI env vars and .env.local win).
load_dotenv(Path(__file__).parent / '.env.test', override=False)

from common.entities.base_entity import Base
from shared.utilities.logger import get_logger
from tests.seed_db import SeedDb, TableName

# Import all entities to ensure they're registered with SQLAlchemy
# Organization entities
import organization.entities.tenant_entity  # noqa
import organization.entities.bu_entity  # noqa
import organization.entities.app_user_entity  # noqa
import organization.entities.app_user_tenant_role_entity  # noqa


# Common agent infrastructure
import common.entities.agent_run_entity  # noqa

# LinkedOut domain entities
import linkedout.company.entities.company_entity  # noqa
import linkedout.role_alias.entities.role_alias_entity  # noqa
import linkedout.search_session.entities.search_session_entity  # noqa
import linkedout.search_session.entities.search_turn_entity  # noqa

logger = get_logger(__name__)


# =============================================================================
# CONFIG FIXTURES
# =============================================================================

@pytest.fixture(autouse=True)
def reset_config():
    """Reset the config singleton between tests."""
    import shared.config.settings as settings_module
    settings_module._settings_instance = None
    yield
    settings_module._settings_instance = None


@pytest.fixture
def data_dir(tmp_path):
    """Provide a temp data directory for tests.

    Sets LINKEDOUT_DATA_DIR to a temporary path so tests never write
    to the real ~/linkedout-data/ directory.
    """
    os.environ['LINKEDOUT_DATA_DIR'] = str(tmp_path)
    yield tmp_path
    os.environ.pop('LINKEDOUT_DATA_DIR', None)


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        'markers', 'seed_config(config): specify custom SeedDb.SeedConfig for isolated DB fixtures'
    )


def pytest_collection_modifyitems(config, items):
    """
    Modify test collection to add markers and organize test execution.

    This hook is called after test collection. It can be used to:
    - Add markers to tests
    - Reorder tests
    - Skip tests based on conditions
    """
    for item in items:
        # Add unit marker to repository and service tests
        if 'repositories' in str(item.fspath) or 'services' in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        # Add integration marker to controller tests
        elif 'controllers' in str(item.fspath):
            item.add_marker(pytest.mark.integration)


# =============================================================================
# SHARED DATABASE FIXTURES (Session-Scoped, for Read-Only Tests)
# =============================================================================

def _create_test_engine() -> Engine:
    """Create a SQLite in-memory engine with foreign key support."""
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
        echo=False,
    )

    @event.listens_for(engine, 'connect')
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()

    return engine


@pytest.fixture(scope='session')
def _shared_db_resources() -> Tuple[Engine, Dict[TableName, list[Any]]]:
    """
    Internal fixture to set up a shared in-memory SQLite database engine
    once per session, create all tables, and seed it with default data.

    Returns:
        Tuple[Engine, Dict[TableName, list[Any]]]: The initialized SQLAlchemy engine
            and a dictionary containing the data seeded by SeedDb.
    """
    engine = _create_test_engine()
    Base.metadata.create_all(engine)

    # SeedDb uses its own sessionmaker from config.custom_engine — it doesn't need db_session_manager
    seeder = SeedDb()
    seed_config = SeedDb.SeedConfig()
    seed_config.custom_engine = engine
    seeder.init(config=seed_config)
    seeded_data = seeder.seed_data()

    return engine, seeded_data


@pytest.fixture(scope='session')
def all_seeded_data_for_shared_db(
    _shared_db_resources: Tuple[Engine, Dict[TableName, list[Any]]]
) -> Dict[TableName, list[Any]]:
    """
    Provides the dictionary of data that was seeded into the shared,
    session-scoped database.

    This fixture creates detached copies with all attributes loaded to prevent
    DetachedInstanceError across tests.
    """
    engine, seeded_data = _shared_db_resources
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as session:
        detached_data = {}

        for table_name, entity_list in seeded_data.items():
            detached_entities = []

            for entity in entity_list:
                # Merge the entity into this session
                attached_entity = session.merge(entity)

                # Force loading of all column attributes
                mapper = attached_entity.__mapper__
                for prop in mapper.column_attrs:
                    try:
                        _ = getattr(attached_entity, prop.key)
                    except Exception:
                        pass

                # Expunge to make detached but keep loaded data
                session.expunge(attached_entity)
                detached_entities.append(attached_entity)

            detached_data[table_name] = detached_entities

        return detached_data


@pytest.fixture(scope='function')
def shared_db_session(_shared_db_resources: Tuple[Engine, Dict[TableName, list[Any]]]) -> Generator[Session, None, None]:
    """
    Provides a SQLAlchemy session to the shared, pre-seeded in-memory database.

    Ideal for:
    - Read-only tests
    - Tests that don't modify state

    The session auto-rolls back changes at the end (READ mode behavior).
    """
    shared_engine, _ = _shared_db_resources
    SessionLocal = sessionmaker(bind=shared_engine, autoflush=False, autocommit=False)

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# =============================================================================
# ISOLATED DATABASE FIXTURES (For Mutation Tests)
# =============================================================================

@pytest.fixture(scope='function')
def function_scoped_isolated_db_session(
    request: pytest.FixtureRequest
) -> Generator[Tuple[Session, Dict[TableName, list[Any]]], None, None]:
    """
    Provides a completely isolated in-memory database session for a single test function.

    Use `@pytest.mark.seed_config(SeedDb.SeedConfig(...))` to customize seeding.

    Yields:
        Tuple[Session, Dict[TableName, list[Any]]]: Session and seeded data dictionary.
    """
    seed_config = _get_seed_config_from_marker(request)

    isolated_engine = _create_test_engine()
    Base.metadata.create_all(isolated_engine)

    seeder = SeedDb()
    seed_config.custom_engine = isolated_engine
    seeder.init(config=seed_config)
    seeded_data = seeder.seed_data()

    IsolatedSessionLocal = sessionmaker(bind=isolated_engine, autoflush=False, autocommit=False)
    session = IsolatedSessionLocal()

    try:
        yield session, seeded_data
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        isolated_engine.dispose()


@pytest.fixture(scope='class')
def class_scoped_isolated_db_session(
    request: pytest.FixtureRequest
) -> Generator[Tuple[Session, Dict[TableName, list[Any]]], None, None]:
    """
    Provides a completely isolated in-memory database session for an entire test class.

    All test methods within the class share this database. Use for related mutation
    tests that build upon each other's state.

    Use `@pytest.mark.seed_config(SeedDb.SeedConfig(...))` on the class to customize seeding.

    Yields:
        Tuple[Session, Dict[TableName, list[Any]]]: Session and seeded data dictionary.
    """
    seed_config = _get_seed_config_from_marker(request)

    isolated_engine = _create_test_engine()
    Base.metadata.create_all(isolated_engine)

    seeder = SeedDb()
    seed_config.custom_engine = isolated_engine
    seeder.init(config=seed_config)
    seeded_data = seeder.seed_data()

    ClassScopedSessionLocal = sessionmaker(bind=isolated_engine, autoflush=False, autocommit=False)
    session = ClassScopedSessionLocal()

    # Merge seeded entities into the class-scoped session
    merged_seeded_data = {}
    for table_key, entity_list in seeded_data.items():
        merged_list = [session.merge(entity) for entity in entity_list] if entity_list else []
        merged_seeded_data[table_key] = merged_list

    try:
        yield session, merged_seeded_data
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        isolated_engine.dispose()


def _get_seed_config_from_marker(request: pytest.FixtureRequest) -> 'SeedDb.SeedConfig':
    """Extract SeedConfig from pytest marker or return default."""
    # Check class-level marker first (for class-scoped fixtures)
    if hasattr(request, 'cls') and request.cls is not None:
        for mark in getattr(request.cls, 'pytestmark', []):
            if mark.name == 'seed_config':
                if mark.args and isinstance(mark.args[0], SeedDb.SeedConfig):
                    return mark.args[0]

    # Check node-level marker
    marker = request.node.get_closest_marker('seed_config')
    if marker and marker.args and isinstance(marker.args[0], SeedDb.SeedConfig):
        return marker.args[0]

    return SeedDb.SeedConfig()


# =============================================================================
# LEGACY/UTILITY FIXTURES (Backward Compatibility)
# =============================================================================

@pytest.fixture(scope='function')
def db_engine():
    """
    Create a test database engine (legacy fixture).

    For new tests, prefer:
    - `shared_db_session` for read-only tests
    - `class_scoped_isolated_db_session` for mutation tests
    """
    engine = _create_test_engine()
    Base.metadata.create_all(bind=engine)
    logger.info('Created all database tables')

    yield engine

    Base.metadata.drop_all(bind=engine)
    logger.info('Dropped all database tables')
    engine.dispose()


@pytest.fixture(scope='function')
def db_session(db_engine) -> Generator[Session, None, None]:
    """
    Create a test database session (legacy fixture).

    For new tests, prefer:
    - `shared_db_session` for read-only tests
    - `class_scoped_isolated_db_session` for mutation tests
    """
    TestSessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    session = TestSessionLocal()

    yield session

    session.rollback()
    session.close()


# =============================================================================
# UTILITY FIXTURES
# =============================================================================

class DateTimeComparator:
    """
    Helper class to compare datetime objects with tolerance.

    Useful for comparing timestamps that might have minor differences
    due to timing of creation vs assertion.
    """

    def __init__(self, dt: datetime, tolerance_seconds: int = 2):
        self.dt = dt
        self.tolerance_seconds = tolerance_seconds

    def __eq__(self, other: datetime) -> bool:
        if not isinstance(other, datetime):
            return False

        # Ensure both are timezone-aware
        if self.dt.tzinfo is None:
            self.dt = self.dt.replace(tzinfo=timezone.utc)
        if other.tzinfo is None:
            other = other.replace(tzinfo=timezone.utc)

        diff = abs((self.dt - other).total_seconds())
        return diff <= self.tolerance_seconds

    def __repr__(self) -> str:
        return f'DateTimeComparator({self.dt}, tolerance={self.tolerance_seconds}s)'

    @staticmethod
    def compare_le(entity_dt: datetime, test_dt: datetime) -> bool:
        """Compare if entity_dt <= test_dt, handling timezone differences."""
        normalized = DateTimeComparator._normalize(entity_dt, test_dt)
        return entity_dt <= normalized

    @staticmethod
    def compare_ge(entity_dt: datetime, test_dt: datetime) -> bool:
        """Compare if entity_dt >= test_dt, handling timezone differences."""
        normalized = DateTimeComparator._normalize(entity_dt, test_dt)
        return entity_dt >= normalized

    @staticmethod
    def _normalize(dt: datetime, reference_dt: datetime) -> datetime:
        """Normalize datetime for comparison by matching timezone awareness."""
        if dt.tzinfo is None and reference_dt.tzinfo is not None:
            return reference_dt.replace(tzinfo=None)
        elif dt.tzinfo is not None and reference_dt.tzinfo is None:
            return dt.replace(tzinfo=None)
        return reference_dt


@pytest.fixture
def datetime_comparator():
    """Factory fixture for creating DateTimeComparator instances."""
    return DateTimeComparator


# =============================================================================
# AUTH MOCK FIXTURES
# =============================================================================

@pytest.fixture
def mock_auth_context():
    """Pre-built AuthContext for tests needing authenticated requests."""
    from shared.auth.dependencies.schemas.auth_context import AuthContext, Principal, Actor, Subject
    from shared.auth.dependencies.schemas.role_enums import TenantRole, BuRole

    return AuthContext(
        principal=Principal(
            auth_provider_id='test-uid-001',
            user_id='test-user-001',
            email='test@example.com',
            name='Test User',
        ),
        actor=Actor(
            id='test-user-001',
            current_tenant_roles=[TenantRole.ADMIN],
            current_bu_roles=[BuRole.ADMIN],
        ),
        subject=Subject(tenant_id='tenant-test-001', bu_id='bu-test-001'),
    )


@pytest.fixture
def override_auth(mock_auth_context):
    """Override auth dependencies in FastAPI app for testing."""
    from main import app
    from shared.auth.dependencies.auth_dependencies import is_valid_user, get_valid_user

    app.dependency_overrides[is_valid_user] = lambda: mock_auth_context
    app.dependency_overrides[get_valid_user] = lambda: mock_auth_context
    yield mock_auth_context
    app.dependency_overrides.clear()
