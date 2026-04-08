# SPDX-License-Identifier: Apache-2.0
"""
Database Seeding Script

Seeds the database with sample data for development and testing.
Uses BaseSeeder and EntityFactory for consistent data generation.

Usage:
    python -m src.dev_tools.db.seed
"""

import sys
import traceback
from sqlalchemy import select

from shared.infra.db.db_session_manager import DbSessionType, db_session_manager
from shared.test_utils.entity_factories import EntityFactory
from shared.test_utils.seeders.seed_config import DevSeedConfig
from shared.test_utils.seeders.base_seeder import BaseSeeder
from shared.utilities.logger import get_logger

# Import TenantEntity to check existence
from organization.entities.tenant_entity import TenantEntity

logger = get_logger(__name__)


def main():
    """Main seeding function."""
    logger.info('Starting database seeding...')

    try:
        with db_session_manager.get_session(DbSessionType.WRITE) as session:
            # Check if database is already seeded
            # We use TenantEntity as a proxy for "is seeded"
            if session.execute(select(TenantEntity)).first():
                logger.info('Database appears to be already seeded (Tenants exist). Skipping.')
                return 0

            # Initialize factory and seeder
            factory = EntityFactory(session)
            config = DevSeedConfig()
            seeder = BaseSeeder(session, factory)

            # Run seeding
            seeder.seed(config)

            logger.info('Database seeding completed successfully!')
            return 0

    except Exception as e:
        logger.error(f'Database seeding failed: {str(e)}')
        logger.error(traceback.format_exc())
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
