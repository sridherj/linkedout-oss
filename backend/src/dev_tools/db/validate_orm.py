# SPDX-License-Identifier: Apache-2.0
"""
ORM Validation Script

This script validates that all SQLAlchemy entities and relationships are properly configured.
Run this after generating migrations or when adding new entities to catch ORM issues early.

Usage:
    python dev_tools/db/validate_orm.py
"""

import sys
import os
from pathlib import Path
import importlib

import traceback
from datetime import datetime

from sqlalchemy import inspect
from sqlalchemy.orm import configure_mappers

from shared.utilities.logger import get_logger
from shared.config import get_config
# Import all entities to ensure they're registered
# Organization domain
from organization.entities.tenant_entity import TenantEntity
from organization.entities.bu_entity import BuEntity
from organization.entities.app_user_entity import AppUserEntity
from organization.entities.app_user_tenant_role_entity import AppUserTenantRoleEntity


# Common agent infrastructure
from common.entities.agent_run_entity import AgentRunEntity

# LinkedOut domain
from linkedout.company.entities.company_entity import CompanyEntity
from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
from linkedout.connection.entities.connection_entity import ConnectionEntity
from linkedout.role_alias.entities.role_alias_entity import RoleAliasEntity
from linkedout.experience.entities.experience_entity import ExperienceEntity
from linkedout.education.entities.education_entity import EducationEntity
from linkedout.profile_skill.entities.profile_skill_entity import ProfileSkillEntity
from linkedout.import_job.entities.import_job_entity import ImportJobEntity
from linkedout.enrichment_event.entities.enrichment_event_entity import EnrichmentEventEntity
from linkedout.search_session.entities.search_session_entity import SearchSessionEntity
from linkedout.search_tag.entities.search_tag_entity import SearchTagEntity
from linkedout.contact_source.entities.contact_source_entity import ContactSourceEntity
from linkedout.company_alias.entities.company_alias_entity import CompanyAliasEntity

# Organization domain
from organization.enrichment_config.entities.enrichment_config_entity import EnrichmentConfigEntity

# Initialize logger
logger = get_logger(__name__)

# All entity classes to validate
ALL_ENTITIES = [
    # Organization domain
    TenantEntity,
    BuEntity,
    AppUserEntity,
    AppUserTenantRoleEntity,
    # Common agent infrastructure
    AgentRunEntity,
    # LinkedOut domain
    CompanyEntity,
    ConnectionEntity,
    CrawledProfileEntity,
    RoleAliasEntity,
    ExperienceEntity,
    EducationEntity,
    ProfileSkillEntity,
    ImportJobEntity,
    EnrichmentEventEntity,
    ContactSourceEntity,
    CompanyAliasEntity,
    # Organization domain
    EnrichmentConfigEntity,
]


def validate_entity_imports():
    """Validate that all entities can be imported successfully."""
    logger.info("✓ Validating entity imports...")

    errors = []

    for entity_class in ALL_ENTITIES:
        try:
            # Check that the entity has basic required attributes
            if not hasattr(entity_class, '__tablename__'):
                errors.append(f"{entity_class.__name__} missing __tablename__ attribute")

            if not hasattr(entity_class, '__mapper__'):
                errors.append(f"{entity_class.__name__} missing __mapper__ (not properly configured)")

            logger.debug(f"  ✓ {entity_class.__name__} imported successfully")

        except Exception as e:
            errors.append(f"Failed to validate {entity_class.__name__}: {str(e)}")

    if errors:
        logger.error("❌ Entity import validation failed:")
        for error in errors:
            logger.error(f"  - {error}")
        return False

    logger.info(f"✓ All {len(ALL_ENTITIES)} entities imported successfully")
    return True


def validate_mapper_configuration():
    """Validate that all mappers can be configured without errors."""
    logger.info("✓ Validating mapper configuration...")

    try:
        # This will trigger configuration of all mappers and relationships
        configure_mappers()
        logger.info("✓ All mappers configured successfully")
        return True

    except Exception as e:
        logger.error(f"❌ Mapper configuration failed: {str(e)}")
        logger.error(traceback.format_exc())
        return False


def validate_relationships():
    """Validate that all relationships are properly configured."""
    logger.info("✓ Validating entity relationships...")

    errors = []

    for entity_class in ALL_ENTITIES:
        try:
            mapper = inspect(entity_class)
            entity_name = entity_class.__name__

            # Check each relationship
            for relationship_name, relationship_property in mapper.relationships.items():
                try:
                    # Try to access the relationship target
                    target_class = relationship_property.mapper.class_

                    # Check if back_populates is configured correctly
                    if hasattr(relationship_property, 'back_populates') and relationship_property.back_populates:
                        back_populates_name = relationship_property.back_populates

                        # Check if the target entity has the corresponding relationship
                        target_mapper = inspect(target_class)
                        if back_populates_name not in target_mapper.relationships:
                            errors.append(
                                f"{entity_name}.{relationship_name} -> {target_class.__name__}.{back_populates_name} "
                                f"(back_populates relationship not found)"
                            )
                        else:
                            # Check if the back reference points back to this entity
                            back_relationship = target_mapper.relationships[back_populates_name]
                            if back_relationship.mapper.class_ != entity_class:
                                errors.append(
                                    f"{entity_name}.{relationship_name} -> {target_class.__name__}.{back_populates_name} "
                                    f"(back_populates points to wrong entity: {back_relationship.mapper.class_.__name__})"
                                )

                    logger.debug(f"  ✓ {entity_name}.{relationship_name} -> {target_class.__name__}")

                except Exception as e:
                    errors.append(f"{entity_name}.{relationship_name}: {str(e)}")

        except Exception as e:
            errors.append(f"Failed to inspect {entity_name}: {str(e)}")

    if errors:
        logger.error("❌ Relationship validation failed:")
        for error in errors:
            logger.error(f"  - {error}")
        return False

    logger.info("✓ All relationships validated successfully")
    return True


def validate_foreign_keys():
    """Validate that all foreign key relationships are properly defined."""
    logger.info("✓ Validating foreign key relationships...")

    errors = []

    for entity_class in ALL_ENTITIES:
        try:
            mapper = inspect(entity_class)
            entity_name = entity_class.__name__

            # Check foreign key columns
            for column in mapper.columns:
                if column.foreign_keys:
                    for fk in column.foreign_keys:
                        try:
                            # Validate that the referenced table/column exists in our model
                            referenced_table = fk.column.table.name
                            referenced_column = fk.column.name

                            # Find the entity that corresponds to this table
                            referenced_entity = None
                            for other_entity in ALL_ENTITIES:
                                if hasattr(other_entity, '__tablename__') and other_entity.__tablename__ == referenced_table:
                                    referenced_entity = other_entity
                                    break

                            if referenced_entity is None:
                                errors.append(
                                    f"{entity_name}.{column.name} references {referenced_table}.{referenced_column} "
                                    f"but no entity found for table '{referenced_table}'"
                                )
                            else:
                                # Check if the referenced column exists
                                referenced_mapper = inspect(referenced_entity)
                                if referenced_column not in [col.name for col in referenced_mapper.columns]:
                                    errors.append(
                                        f"{entity_name}.{column.name} references {referenced_table}.{referenced_column} "
                                        f"but column '{referenced_column}' not found in {referenced_entity.__name__}"
                                    )

                            logger.debug(f"  ✓ {entity_name}.{column.name} -> {referenced_table}.{referenced_column}")

                        except Exception as e:
                            errors.append(f"{entity_name}.{column.name} FK validation error: {str(e)}")

        except Exception as e:
            errors.append(f"Failed to validate FKs for {entity_name}: {str(e)}")

    if errors:
        logger.error("❌ Foreign key validation failed:")
        for error in errors:
            logger.error(f"  - {error}")
        return False

    logger.info("✓ All foreign keys validated successfully")
    return True


def validate_package_exports():
    """Validate that all entities are exported from their package __init__.py."""
    logger.info("✓ Validating package exports...")

    ENTITY_PACKAGES = [
        'organization.entities',
        'common.entities',
        'linkedout.company.entities',
        'linkedout.connection.entities',
        'linkedout.crawled_profile.entities',
        'linkedout.experience.entities',
        'linkedout.role_alias.entities',
        'linkedout.import_job.entities',
        'linkedout.enrichment_event.entities',
        'linkedout.search_session.entities',
        'linkedout.search_tag.entities',
        'linkedout.contact_source.entities',
        'linkedout.company_alias.entities',
        'linkedout.education.entities',
        'linkedout.profile_skill.entities',
        'organization.enrichment_config.entities',
    ]

    errors = []

    for entity_class in ALL_ENTITIES:
        entity_module = entity_class.__module__
        parent_package = entity_module.rsplit('.', 1)[0]

        if parent_package not in ENTITY_PACKAGES:
            errors.append(
                f"{entity_class.__name__} is in module '{entity_module}' whose package "
                f"'{parent_package}' is not in ENTITY_PACKAGES — add it to db_session_manager.py"
            )
            continue

        try:
            pkg = importlib.import_module(parent_package)
        except ImportError as e:
            errors.append(f"Could not import package '{parent_package}': {e}")
            continue

        if not hasattr(pkg, entity_class.__name__):
            errors.append(
                f"{entity_class.__name__} is NOT exported from {parent_package}/__init__.py — "
                f"it won't be registered at runtime by db_session_manager"
            )

    if errors:
        logger.error("❌ Package export validation failed:")
        for error in errors:
            logger.error(f"  - {error}")
        return False

    logger.info(f"✓ All {len(ALL_ENTITIES)} entities are properly exported from their packages")
    return True


def generate_relationship_report():
    """Generate a detailed report of all entity relationships."""
    logger.info("📊 Generating relationship report...")

    report = []
    report.append(f"ORM Relationship Report - Generated {datetime.now().isoformat()}")
    report.append("=" * 80)

    for entity_class in ALL_ENTITIES:
        try:
            mapper = inspect(entity_class)
            entity_name = entity_class.__name__
            table_name = getattr(entity_class, '__tablename__', 'N/A')

            report.append(f"\n{entity_name} (table: {table_name})")
            report.append("-" * 40)

            if mapper.relationships:
                for rel_name, rel_prop in mapper.relationships.items():
                    target_class = rel_prop.mapper.class_
                    back_populates = getattr(rel_prop, 'back_populates', None)

                    if back_populates:
                        report.append(f"  {rel_name} -> {target_class.__name__} (back_populates: {back_populates})")
                    else:
                        report.append(f"  {rel_name} -> {target_class.__name__} (no back_populates)")
            else:
                report.append("  No relationships")

        except Exception as e:
            report.append(f"  ERROR: {str(e)}")

    report_text = "\n".join(report)

    # Save report to file
    report_file = "orm_relationship_report.txt"
    with open(report_file, 'w') as f:
        f.write(report_text)

    logger.info(f"📄 Relationship report saved to {report_file}")
    return report_text


def main():
    """Main validation function."""
    logger.info("🔍 Starting ORM validation...")
    logger.info(f"Database URL: {get_config().database_url}")

    # Track validation results
    results = {
        'entity_imports': False,
        'mapper_configuration': False,
        'relationships': False,
        'foreign_keys': False,
        'package_exports': False,
    }

    # Run all validations
    results['entity_imports'] = validate_entity_imports()
    results['mapper_configuration'] = validate_mapper_configuration()
    results['relationships'] = validate_relationships()
    results['foreign_keys'] = validate_foreign_keys()
    results['package_exports'] = validate_package_exports()

    # Generate report
    generate_relationship_report()

    # Summary
    passed_count = sum(results.values())
    total = len(results)

    logger.info(f'\n🎯 Validation Summary: {passed_count}/{total} checks passed')

    for check, passed in results.items():
        status = '✅ PASS' if passed else '❌ FAIL'
        logger.info(f'  {check}: {status}')

    if passed_count == total:
        logger.info('🎉 All ORM validations passed! Your entity configuration is correct.')
        return 0
    else:
        logger.error('💥 Some ORM validations failed. Please fix the issues above.')
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
