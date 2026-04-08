# SPDX-License-Identifier: Apache-2.0
"""
Test Database Seeding Utilities.

Provides SeedDb class for seeding test databases with configurable data.
Used by conftest.py fixtures for both shared and isolated database testing.

This module is now a wrapper around the shared BaseSeeder implementation,
maintained for backward compatibility with existing tests.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from shared.test_utils.entity_factories import EntityFactory
from shared.test_utils.seeders.seed_config import SeedConfig as BaseSeedConfig
from shared.test_utils.seeders.base_seeder import BaseSeeder
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class TableName(str, Enum):
    """Enum for table names used in seeding configuration."""
    # Organization entities (always seeded first)
    TENANT = 'tenant'
    BU = 'bu'
    # Common agent infrastructure
    AGENT_RUN = 'agent_run'
    # Project management entities
    LABEL = 'label'
    PRIORITY = 'priority'
    PROJECT = 'project'
    TASK = 'task'
    APP_USER = 'app_user'
    APP_USER_TENANT_ROLE = 'app_user_tenant_role'
    ENRICHMENT_CONFIG = 'enrichment_config'
    # LinkedOut domain
    COMPANY = 'company'
    ROLE_ALIAS = 'role_alias'

    @classmethod
    def get_all(cls) -> List['TableName']:
        """Get all table names."""
        return list(cls)


class SeedDb:
    """
    Seed the database with test entities.
    Wrapper around BaseSeeder for compatibility.
    """

    class SeedConfig:
        """
        Configuration for the seeding process.
        Maps legacy config parameters to BaseSeedConfig.
        """
        ALL_TABLES = [t for t in TableName]

        def __init__(
            self,
            custom_engine: Optional[Engine] = None,
            tables_to_populate: Optional[List[TableName]] = None,
            tenant_count: int = 3,
            bu_count_per_tenant: int = 2,
            label_count: int = 3,
            priority_count: int = 4,
            project_count: int = 2,
            task_count: int = 3,
            app_user_count: int = 2,
            app_user_tenant_role_count: int = 2,
            enrichment_config_count: int = 2,
            agent_run_count: int = 2,
            company_count: int = 2,
            role_alias_count: int = 2,
            # Accept and ignore legacy rcm kwargs for compatibility
            **kwargs,
        ):
            self.custom_engine: Optional[Engine] = custom_engine
            self.tables_to_populate: Optional[List[TableName]] = tables_to_populate

            # Counts mapping
            self.counts = {
                TableName.TENANT.value: tenant_count,
                TableName.BU.value: bu_count_per_tenant,
                TableName.AGENT_RUN.value: agent_run_count,
                TableName.LABEL.value: label_count,
                TableName.PRIORITY.value: priority_count,
                TableName.PROJECT.value: project_count,
                TableName.TASK.value: task_count,
                TableName.APP_USER.value: app_user_count,
                TableName.APP_USER_TENANT_ROLE.value: app_user_tenant_role_count,
                TableName.ENRICHMENT_CONFIG.value: enrichment_config_count,
                TableName.COMPANY.value: company_count,
                TableName.ROLE_ALIAS.value: role_alias_count,
            }

        def to_base_config(self) -> BaseSeedConfig:
            """Convert to BaseSeedConfig."""
            tables = [t.value for t in self.tables_to_populate] if self.tables_to_populate else ['*']
            return BaseSeedConfig(tables=tables, counts=self.counts)

    def __init__(self):
        self._session: Optional[Session] = None
        self._factory: Optional[EntityFactory] = None
        self._config: 'SeedDb.SeedConfig' = SeedDb.SeedConfig()

    def init(self, config: Optional['SeedDb.SeedConfig'] = None):
        """
        Initialize the SeedDb instance.

        Args:
            config: Configuration for seeding. Uses defaults if not provided.
        """
        if config:
            self._config = config

        if not self._config.custom_engine:
            raise ValueError('SeedDb requires a custom_engine in the config')

        logger.debug(f'SeedDb initialized with engine: {self._config.custom_engine}')

    def seed_data(self) -> Dict[TableName, List[Any]]:
        """
        Seed the database with test data based on configuration.

        Returns:
            Dict[TableName, List[Any]]: Dictionary mapping table names to lists of created entities.
        """
        logger.info('Starting database seeding...')
        SessionLocal = sessionmaker(bind=self._config.custom_engine)

        data_map: Dict[TableName, List[Any]] = {table: [] for table in TableName}

        with SessionLocal() as session:
            self._session = session
            factory = EntityFactory(session)
            self._factory = factory

            base_config = self._config.to_base_config()
            seeder = BaseSeeder(session, factory)

            # Seed everything
            raw_data = seeder.seed(base_config)

            # Map raw data strings to TableName enums
            for table in TableName:
                if table.value in raw_data:
                    data_map[table] = raw_data[table.value]

            logger.info('Seeding complete.')

        return data_map
