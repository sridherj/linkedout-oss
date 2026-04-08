# SPDX-License-Identifier: Apache-2.0
"""
Verify Seed Data Script

Verifies that the database has been properly seeded with data.

Usage:
    python dev_tools/db/verify_seed.py
"""

import sys

from shared.utilities.logger import get_logger
from shared.infra.db.db_session_manager import DbSessionType, db_session_manager

# Organization entities
from organization.entities.tenant_entity import TenantEntity
from organization.entities.bu_entity import BuEntity
from organization.entities.app_user_entity import AppUserEntity
from organization.entities.app_user_tenant_role_entity import AppUserTenantRoleEntity

# Common agent infrastructure
from common.entities.agent_run_entity import AgentRunEntity

logger = get_logger(__name__)


def verify_seed():
    """Verify that the database has been seeded."""
    logger.info("Verifying database seed...")

    with db_session_manager.get_session(DbSessionType.READ) as session:
        # Count all entities
        counts = {
            'Tenants': session.query(TenantEntity).count(),
            'Business Units': session.query(BuEntity).count(),
            'App Users': session.query(AppUserEntity).count(),
            'App User Tenant Roles': session.query(AppUserTenantRoleEntity).count(),
            'Agent Runs': session.query(AgentRunEntity).count(),
        }

        logger.info("")
        logger.info("Entity Counts:")
        for entity, count in counts.items():
            status = "OK" if count > 0 else "EMPTY"
            logger.info(f"  {entity}: {count} [{status}]")

        # Show sample data hierarchy
        logger.info("")
        logger.info("Sample Data Hierarchy:")

        tenants = session.query(TenantEntity).limit(2).all()
        for tenant in tenants:
            logger.info(f"  Tenant: {tenant.name} (ID: {tenant.id})")
            bus = session.query(BuEntity).filter_by(tenant_id=tenant.id).limit(2).all()
            for bu in bus:
                logger.info(f"    BU: {bu.name} (ID: {bu.id})")

        # Verify minimum required data exists
        required_counts = ['Tenants', 'Business Units']
        all_ok = all(counts[key] > 0 for key in required_counts)

        logger.info("")
        if all_ok:
            logger.info("Database verification PASSED!")
        else:
            logger.error("Database verification FAILED - some required entities are missing")

        return all_ok


if __name__ == "__main__":
    success = verify_seed()
    sys.exit(0 if success else 1)
