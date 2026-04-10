# SPDX-License-Identifier: Apache-2.0
"""Database session manager for centralized session handling."""
from enum import StrEnum
from typing import Generator
import contextlib

from sqlalchemy import Engine, text
from sqlalchemy.orm import sessionmaker, Session

from shared.utilities.logger import logger


# Import all entity packages to ensure SQLAlchemy discovers all entity classes
# The # noqa prevents linters from complaining about unused imports
import organization.entities  # noqa
import common.entities  # noqa

# LinkedOut domain entities
import linkedout.company.entities  # noqa
import linkedout.company_alias.entities  # noqa
import linkedout.role_alias.entities  # noqa
import linkedout.crawled_profile.entities  # noqa
import linkedout.experience.entities  # noqa
import linkedout.education.entities  # noqa
import linkedout.profile_skill.entities  # noqa
import linkedout.connection.entities  # noqa
import linkedout.import_job.entities  # noqa
import linkedout.contact_source.entities  # noqa
import linkedout.enrichment_event.entities  # noqa
import linkedout.funding.entities  # noqa
import linkedout.search_session.entities  # noqa
import linkedout.search_tag.entities  # noqa

# Organization domain - enrichment config
import organization.enrichment_config.entities  # noqa


class DbSessionType(StrEnum):
    """
    Type of database session.
    
    READ: Read-only session (automatically rolls back changes)
    WRITE: Write-enabled session (commits on success, rolls back on error)
    """
    READ = 'read'
    WRITE = 'write'


class DbSessionManager:
    """Database session manager with injected engine.

    Engine is provided at construction time. FastAPI apps create the manager
    in lifespan; CLI commands use ``cli_db_manager()``; tests create their
    own manager per fixture.

    RLS support: pass ``app_user_id`` to ``get_session()`` to set
    ``app.current_user_id`` for the transaction.
    """

    def __init__(self, engine: Engine) -> None:
        """Create a session manager bound to the given engine.

        Args:
            engine: SQLAlchemy engine to bind sessions to.
        """
        self._engine: Engine = engine
        self._SessionLocal = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
        )

    def get_raw_session(self, session_type: DbSessionType = DbSessionType.WRITE) -> Session:
        """
        Get a raw database session for manual transaction management.
        
        WARNING: When using this method, you are responsible for:
        - Committing or rolling back transactions
        - Closing the session when done
        
        Args:
            session_type: The type of session to get
            
        Returns:
            A raw SQLAlchemy Session object
        """
        logger.info(f'Creating raw {session_type} session for manual management')
        return self._SessionLocal()

    def _try_set_transaction_read_only(self, db: Session) -> None:
        """Internal helper to set transaction to read-only."""
        dialect_name = db.get_bind().dialect.name
        if dialect_name == 'postgresql':
            try:
                db.execute(text('SET TRANSACTION READ ONLY;'))
                logger.debug('Set session transaction to READ ONLY for PostgreSQL')
            except Exception as e:
                logger.warning(f'Could not set session to READ ONLY for PostgreSQL: {e}')
        elif dialect_name == 'sqlite':
            try:
                db.execute(text('PRAGMA query_only = ON;'))
                logger.debug('Set session to query_only=ON for SQLite')
            except Exception as e:
                logger.warning(f'Could not set session to query_only=ON for SQLite: {e}')

    def _try_set_transaction_write(self, db: Session) -> None:
        """Internal helper to set transaction to write (reset read-only)."""
        dialect_name = db.get_bind().dialect.name
        if dialect_name == 'sqlite':
            try:
                db.execute(text('PRAGMA query_only = OFF;'))
                logger.debug('Set session to query_only=OFF for SQLite')
            except Exception as e:
                logger.warning(f'Could not set session to query_only=OFF for SQLite: {e}')

    @contextlib.contextmanager
    def get_session(
        self,
        session_type: DbSessionType = DbSessionType.READ,
        app_user_id: str | None = None,
    ) -> Generator[Session, None, None]:
        """
        Provide a database session as a context manager.

        Args:
            session_type: The type of session to get (READ or WRITE)
            app_user_id: When provided, sets ``app.current_user_id`` for the
                transaction so RLS policies can enforce tenant isolation.

        Yields:
            A database session
        """
        logger.debug(f'Requesting {session_type} session for context manager')

        db: Session | None = None
        try:
            db = self._SessionLocal()
            logger.debug(f'Acquired {session_type} session: {db}')

            if session_type == DbSessionType.READ:
                self._try_set_transaction_read_only(db)
            elif session_type == DbSessionType.WRITE:
                self._try_set_transaction_write(db)

            # Set RLS context when app_user_id is provided
            if app_user_id:
                self._try_set_rls_user(db, app_user_id)

            yield db

            if session_type == DbSessionType.WRITE:
                logger.debug(f'Committing write session: {db}')
                db.commit()
            else:
                logger.debug(f'Rolling back read session: {db}')
                db.rollback()
        except Exception:
            logger.error(f'Exception during {session_type} session', exc_info=True)
            if db:
                logger.debug('Rolling back session due to exception')
                db.rollback()
            raise
        finally:
            if db:
                logger.debug(f'Closing {session_type} session: {db}')
                db.close()

    def _try_set_rls_user(self, db: Session, app_user_id: str) -> None:
        """Set app.current_user_id for RLS policies (transaction-scoped)."""
        dialect_name = db.get_bind().dialect.name
        if dialect_name == 'postgresql':
            db.execute(
                text("SELECT set_config('app.current_user_id', :uid, true)"),
                {"uid": str(app_user_id)},
            )


