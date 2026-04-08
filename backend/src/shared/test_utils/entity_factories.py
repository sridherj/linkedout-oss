# SPDX-License-Identifier: Apache-2.0
"""
Shared Entity Factory for creating test data.

This module provides a central place for creating entity instances
for testing purposes (unit tests, integration tests, and seed scripts).
It ensures consistency in entity structure and default values across
different testing environments.
"""
import random
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from shared.utilities.logger import get_logger

# Organization
from organization.entities.tenant_entity import TenantEntity
from organization.entities.bu_entity import BuEntity
from organization.entities.app_user_entity import AppUserEntity
from organization.entities.app_user_tenant_role_entity import AppUserTenantRoleEntity
from organization.enrichment_config.entities.enrichment_config_entity import EnrichmentConfigEntity

# Common agent infrastructure
from common.entities.agent_run_entity import AgentRunEntity

# LinkedOut domain
from linkedout.company.entities.company_entity import CompanyEntity
from linkedout.company_alias.entities.company_alias_entity import CompanyAliasEntity
from linkedout.role_alias.entities.role_alias_entity import RoleAliasEntity
from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
from linkedout.experience.entities.experience_entity import ExperienceEntity
from linkedout.education.entities.education_entity import EducationEntity
from linkedout.profile_skill.entities.profile_skill_entity import ProfileSkillEntity
from linkedout.connection.entities.connection_entity import ConnectionEntity
from linkedout.import_job.entities.import_job_entity import ImportJobEntity
from linkedout.contact_source.entities.contact_source_entity import ContactSourceEntity
from linkedout.enrichment_event.entities.enrichment_event_entity import EnrichmentEventEntity


logger = get_logger(__name__)


class EntityFactory:
    """
    Factory class for creating database entities with consistent defaults.

    Usage:
        factory = EntityFactory(session)
        tenant = factory.create_tenant(overrides={'name': 'My Tenant'})
    """

    def __init__(self, session: Session):
        self.session = session

    def _create_entity(self, model_class, data: Dict[str, Any], overrides: Optional[Dict[str, Any]] = None, auto_commit: bool = False, add_to_session: bool = True):
        """Helper to create, add, and optionally commit an entity."""
        if overrides:
            data.update(overrides)

        entity = model_class(**data)

        if add_to_session:
            self.session.add(entity)
            if auto_commit:
                self.session.commit()
            else:
                self.session.flush()

        return entity

    # =========================================================================
    # ORGANIZATION
    # =========================================================================

    def create_tenant(self, overrides: Optional[Dict[str, Any]] = None, auto_commit: bool = False, add_to_session: bool = True) -> TenantEntity:
        """Create a TenantEntity."""
        data = {
            'name': 'Default Tenant',
            'description': 'Default Tenant Description'
        }
        if overrides and 'id' not in overrides:
             pass
        return self._create_entity(TenantEntity, data, overrides, auto_commit, add_to_session)

    def create_bu(self, tenant_id: str, overrides: Optional[Dict[str, Any]] = None, auto_commit: bool = False, add_to_session: bool = True) -> BuEntity:
        """Create a BuEntity."""
        data = {
            'tenant_id': tenant_id,
            'name': 'Default BU',
            'description': 'Default BU Description'
        }
        return self._create_entity(BuEntity, data, overrides, auto_commit, add_to_session)

    def create_app_user(
        self,
        overrides: Optional[Dict[str, Any]] = None,
        auto_commit: bool = False,
        add_to_session: bool = True
    ) -> AppUserEntity:
        """Create an AppUserEntity."""
        data = {
            'email': f'user{random.randint(1000, 9999)}@test.com',
            'name': 'Test User',
            'auth_provider_id': f'auth0|test{random.randint(10000, 99999)}',
        }
        return self._create_entity(AppUserEntity, data, overrides, auto_commit, add_to_session)

    def create_app_user_tenant_role(
        self,
        app_user_id: str,
        tenant_id: str,
        overrides: Optional[Dict[str, Any]] = None,
        auto_commit: bool = False,
        add_to_session: bool = True
    ) -> AppUserTenantRoleEntity:
        """Create an AppUserTenantRoleEntity."""
        data = {
            'app_user_id': app_user_id,
            'tenant_id': tenant_id,
            'role': 'member',
        }
        return self._create_entity(AppUserTenantRoleEntity, data, overrides, auto_commit, add_to_session)

    def create_enrichment_config(
        self,
        app_user_id: str,
        overrides: Optional[Dict[str, Any]] = None,
        auto_commit: bool = False,
        add_to_session: bool = True
    ) -> EnrichmentConfigEntity:
        """Create an EnrichmentConfigEntity."""
        data = {
            'app_user_id': app_user_id,
            'enrichment_mode': 'platform',
        }
        return self._create_entity(EnrichmentConfigEntity, data, overrides, auto_commit, add_to_session)

    # =========================================================================
    # COMMON AGENT INFRASTRUCTURE
    # =========================================================================

    def create_agent_run(
        self,
        tenant_id: str,
        bu_id: str,
        overrides: Optional[Dict[str, Any]] = None,
        auto_commit: bool = False,
        add_to_session: bool = True
    ) -> AgentRunEntity:
        """Create an AgentRunEntity."""
        data = {
            'tenant_id': tenant_id,
            'bu_id': bu_id,
            'agent_type': 'TASK_TRIAGE',
            'status': 'PENDING',
            'input_params': {'task_id': 'task-001'},
        }
        return self._create_entity(AgentRunEntity, data, overrides, auto_commit, add_to_session)

    # =========================================================================
    # LINKEDOUT DOMAIN
    # =========================================================================

    _company_counter = 0

    def create_company(
        self,
        overrides: Optional[Dict[str, Any]] = None,
        auto_commit: bool = False,
        add_to_session: bool = True
    ) -> CompanyEntity:
        """Create a CompanyEntity (shared, no tenant/BU)."""
        EntityFactory._company_counter += 1
        data = {
            'canonical_name': f'Company {EntityFactory._company_counter}',
            'normalized_name': f'company {EntityFactory._company_counter}',
            'domain': f'company{EntityFactory._company_counter}.com',
            'industry': 'Technology',
            'size_tier': 'mid',
            'network_connection_count': 0,
        }
        return self._create_entity(CompanyEntity, data, overrides, auto_commit, add_to_session)

    _role_alias_counter = 0

    def create_role_alias(
        self,
        overrides: Optional[Dict[str, Any]] = None,
        auto_commit: bool = False,
        add_to_session: bool = True
    ) -> RoleAliasEntity:
        """Create a RoleAliasEntity (shared, no tenant/BU)."""
        EntityFactory._role_alias_counter += 1
        data = {
            'alias_title': f'Role Alias {EntityFactory._role_alias_counter}',
            'canonical_title': f'Canonical Role {EntityFactory._role_alias_counter}',
            'seniority_level': 'Senior',
            'function_area': 'Engineering',
        }
        return self._create_entity(RoleAliasEntity, data, overrides, auto_commit, add_to_session)

    _company_alias_counter = 0

    def create_company_alias(
        self,
        company_id: str = '',
        overrides: Optional[Dict[str, Any]] = None,
        auto_commit: bool = False,
        add_to_session: bool = True
    ) -> CompanyAliasEntity:
        """Create a CompanyAliasEntity (shared, no tenant/BU)."""
        EntityFactory._company_alias_counter += 1
        data = {
            'alias_name': f'Alias {EntityFactory._company_alias_counter}',
            'company_id': company_id,
            'source': 'linkedin',
        }
        return self._create_entity(CompanyAliasEntity, data, overrides, auto_commit, add_to_session)

    _crawled_profile_counter = 0

    def create_crawled_profile(
        self,
        overrides: Optional[Dict[str, Any]] = None,
        auto_commit: bool = False,
        add_to_session: bool = True
    ) -> CrawledProfileEntity:
        """Create a CrawledProfileEntity (shared, no tenant/BU)."""
        EntityFactory._crawled_profile_counter += 1
        n = EntityFactory._crawled_profile_counter
        data = {
            'linkedin_url': f'https://linkedin.com/in/user-{n}',
            'public_identifier': f'user-{n}',
            'first_name': f'First{n}',
            'last_name': f'Last{n}',
            'full_name': f'First{n} Last{n}',
            'headline': f'Engineer at Company {n}',
        }
        return self._create_entity(CrawledProfileEntity, data, overrides, auto_commit, add_to_session)

    _experience_counter = 0

    def create_experience(
        self,
        crawled_profile_id: str = '',
        overrides: Optional[Dict[str, Any]] = None,
        auto_commit: bool = False,
        add_to_session: bool = True
    ) -> ExperienceEntity:
        """Create an ExperienceEntity (shared, no tenant/BU)."""
        EntityFactory._experience_counter += 1
        data = {
            'crawled_profile_id': crawled_profile_id,
            'position': f'Engineer {EntityFactory._experience_counter}',
            'company_name': f'Company {EntityFactory._experience_counter}',
            'is_current': False,
        }
        return self._create_entity(ExperienceEntity, data, overrides, auto_commit, add_to_session)

    _education_counter = 0

    def create_education(
        self,
        crawled_profile_id: str = '',
        overrides: Optional[Dict[str, Any]] = None,
        auto_commit: bool = False,
        add_to_session: bool = True
    ) -> EducationEntity:
        """Create an EducationEntity (shared, no tenant/BU)."""
        EntityFactory._education_counter += 1
        data = {
            'crawled_profile_id': crawled_profile_id,
            'school_name': f'University {EntityFactory._education_counter}',
            'degree': 'BS',
            'field_of_study': 'Computer Science',
        }
        return self._create_entity(EducationEntity, data, overrides, auto_commit, add_to_session)

    _profile_skill_counter = 0

    def create_profile_skill(
        self,
        crawled_profile_id: str = '',
        overrides: Optional[Dict[str, Any]] = None,
        auto_commit: bool = False,
        add_to_session: bool = True
    ) -> ProfileSkillEntity:
        """Create a ProfileSkillEntity (shared, no tenant/BU)."""
        EntityFactory._profile_skill_counter += 1
        data = {
            'crawled_profile_id': crawled_profile_id,
            'skill_name': f'Skill {EntityFactory._profile_skill_counter}',
            'endorsement_count': 0,
        }
        return self._create_entity(ProfileSkillEntity, data, overrides, auto_commit, add_to_session)

    _connection_counter = 0

    def create_connection(
        self,
        tenant_id: str = 'tenant-test-001',
        bu_id: str = 'bu-test-001',
        app_user_id: str = '',
        crawled_profile_id: str = '',
        overrides: Optional[Dict[str, Any]] = None,
        auto_commit: bool = False,
        add_to_session: bool = True
    ) -> ConnectionEntity:
        """Create a ConnectionEntity (scoped to tenant/BU)."""
        EntityFactory._connection_counter += 1
        data = {
            'tenant_id': tenant_id,
            'bu_id': bu_id,
            'app_user_id': app_user_id,
            'crawled_profile_id': crawled_profile_id,
        }
        return self._create_entity(ConnectionEntity, data, overrides, auto_commit, add_to_session)

    _import_job_counter = 0

    def create_import_job(
        self,
        tenant_id: str = 'tenant-test-001',
        bu_id: str = 'bu-test-001',
        app_user_id: str = '',
        overrides: Optional[Dict[str, Any]] = None,
        auto_commit: bool = False,
        add_to_session: bool = True
    ) -> ImportJobEntity:
        """Create an ImportJobEntity (scoped to tenant/BU)."""
        EntityFactory._import_job_counter += 1
        data = {
            'tenant_id': tenant_id,
            'bu_id': bu_id,
            'app_user_id': app_user_id,
            'source_type': 'linkedin_csv',
            'status': 'pending',
        }
        return self._create_entity(ImportJobEntity, data, overrides, auto_commit, add_to_session)

    _contact_source_counter = 0

    def create_contact_source(
        self,
        tenant_id: str = 'tenant-test-001',
        bu_id: str = 'bu-test-001',
        app_user_id: str = '',
        import_job_id: str = '',
        overrides: Optional[Dict[str, Any]] = None,
        auto_commit: bool = False,
        add_to_session: bool = True
    ) -> ContactSourceEntity:
        """Create a ContactSourceEntity (scoped to tenant/BU)."""
        EntityFactory._contact_source_counter += 1
        n = EntityFactory._contact_source_counter
        data = {
            'tenant_id': tenant_id,
            'bu_id': bu_id,
            'app_user_id': app_user_id,
            'import_job_id': import_job_id,
            'source_type': 'linkedin_csv',
            'first_name': f'Contact{n}',
            'last_name': f'Source{n}',
            'dedup_status': 'pending',
        }
        return self._create_entity(ContactSourceEntity, data, overrides, auto_commit, add_to_session)

    _enrichment_event_counter = 0

    def create_enrichment_event(
        self,
        tenant_id: str = 'tenant-test-001',
        bu_id: str = 'bu-test-001',
        app_user_id: str = '',
        crawled_profile_id: str = '',
        overrides: Optional[Dict[str, Any]] = None,
        auto_commit: bool = False,
        add_to_session: bool = True
    ) -> EnrichmentEventEntity:
        """Create an EnrichmentEventEntity (scoped to tenant/BU)."""
        EntityFactory._enrichment_event_counter += 1
        data = {
            'tenant_id': tenant_id,
            'bu_id': bu_id,
            'app_user_id': app_user_id,
            'crawled_profile_id': crawled_profile_id,
            'event_type': 'profile_crawl',
            'enrichment_mode': 'shared_cache',
        }
        return self._create_entity(EnrichmentEventEntity, data, overrides, auto_commit, add_to_session)

