# SPDX-License-Identifier: Apache-2.0
import random
from typing import Dict, List, Any
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from dev_tools.db import fixed_data
from shared.test_utils.entity_factories import EntityFactory
from shared.test_utils.seeders.seed_config import SeedConfig
from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="backend")

class BaseSeeder:
    """
    Base class for seeding database entities.
    Orchestrates the seeding process based on dependencies and configuration.
    """

    # Dependency order: (entity_key, [dependency_keys])
    ENTITY_ORDER = [
        ('tenant', []),
        ('bu', ['tenant']),
        ('agent_run', ['bu']),
        ('app_user', []),
        ('app_user_tenant_role', ['app_user', 'tenant']),
        ('enrichment_config', ['app_user']),
        ('company', []),
        ('company_alias', ['company']),
        ('role_alias', []),
        ('crawled_profile', ['company']),
        ('experience', ['crawled_profile']),
        ('education', ['crawled_profile']),
        ('profile_skill', ['crawled_profile']),
        ('connection', ['app_user', 'crawled_profile', 'bu']),
        ('import_job', ['app_user', 'bu']),
        ('contact_source', ['app_user', 'import_job', 'bu']),
        ('enrichment_event', ['app_user', 'crawled_profile', 'bu']),
    ]

    def __init__(self, session: Session, factory: EntityFactory):
        self.session = session
        self.factory = factory
        self._data: Dict[str, List[Any]] = defaultdict(list)
        self._id_counters: Dict[str, int] = defaultdict(int)

    def seed(self, config: SeedConfig) -> Dict[str, List[Any]]:
        """Run the seeding process."""
        logger.info(f"Starting seed with config: tables={config.tables}")

        for entity_key, _ in self.ENTITY_ORDER:
            if config.should_seed(entity_key):
                method_name = f'_seed_{entity_key}'
                if hasattr(self, method_name):
                    logger.info(f"Seeding {entity_key}...")
                    try:
                        getattr(self, method_name)(config)
                        logger.info(f"  -> Created {len(self._data[entity_key])} {entity_key}s")
                    except Exception as e:
                        logger.error(f"Error seeding {entity_key}: {e}")
                        raise
                else:
                    logger.warning(f"No seeder method found for {entity_key}")

        return self._data

    # =========================================================================
    # ORGANIZATION
    # =========================================================================

    def _seed_tenant(self, config: SeedConfig):
        # 0. System Tenant (always created)
        if config.include_fixed:
            self._data['tenant'].append(self.factory.create_tenant(overrides=fixed_data.SYSTEM_TENANT, add_to_session=True))

        # 1. Fixed Tenant
        if config.include_fixed:
            self._data['tenant'].append(self.factory.create_tenant(overrides=fixed_data.FIXED_TENANT, add_to_session=True))

        # 2. Random Tenants
        count = config.get_count('tenant', 0)
        names = ['Valley Corp', 'Northwest Inc', 'Pacific Ltd']
        for i in range(count):
            name = names[i % len(names)] if i < len(names) else f"Tenant {i+1}"
            tenant = self.factory.create_tenant(
                overrides={
                    'id': f"{config.id_prefix}ten-{i+100}",
                    'name': name,
                    'description': f'{name} operations'
                },
                add_to_session=True
            )
            self._data['tenant'].append(tenant)
        self.session.commit()

    def _seed_bu(self, config: SeedConfig):
        # 0. System BU (always created)
        if config.include_fixed:
            self._data['bu'].append(self.factory.create_bu(
                tenant_id=fixed_data.SYSTEM_BU['tenant_id'],
                overrides=fixed_data.SYSTEM_BU,
                add_to_session=True
            ))

        # 1. Fixed BUs
        if config.include_fixed:
            for bu_override in fixed_data.FIXED_BUS:
                 self._data['bu'].append(self.factory.create_bu(
                     tenant_id=bu_override['tenant_id'],
                     overrides=bu_override,
                     add_to_session=True
                 ))

        # 2. Random BUs per seeded tenant
        count_per_tenant = config.get_count('bu', 0)
        bu_names = ['Engineering', 'Product', 'Operations']

        for tenant in self._data['tenant']:
            if tenant.id == fixed_data.FIXED_TENANT['id']:
                continue

            for i in range(count_per_tenant):
                name = bu_names[i % len(bu_names)]
                bu = self.factory.create_bu(
                    tenant_id=tenant.id,
                    overrides={
                        'id': f"{config.id_prefix}bu-{tenant.id[-3:]}-{i+1}",
                        'name': name,
                        'description': f'{name} for {tenant.name}'
                    },
                    add_to_session=True
                )
                self._data['bu'].append(bu)
        self.session.commit()

    # =========================================================================
    # COMMON AGENT INFRASTRUCTURE
    # =========================================================================

    def _seed_agent_run(self, config: SeedConfig):
        if config.include_fixed:
            for data in fixed_data.FIXED_AGENT_RUNS:
                self._data['agent_run'].append(self.factory.create_agent_run(
                    tenant_id=data['tenant_id'],
                    bu_id=data['bu_id'],
                    overrides=data,
                    add_to_session=True
                ))

        count = config.get_count('agent_run', 0)
        if count > 0 and self._data['bu']:
            bu = self._data['bu'][0]
            for i in range(count):
                run = self.factory.create_agent_run(
                    tenant_id=bu.tenant_id,
                    bu_id=bu.id,
                    overrides={
                        'id': f"{config.id_prefix}arn-{i+100}",
                        'agent_type': 'TASK_TRIAGE',
                    },
                    add_to_session=True
                )
                self._data['agent_run'].append(run)
        self.session.commit()

    def _seed_app_user(self, config: SeedConfig):
        # System admin (always created with fixed data)
        if config.include_fixed:
            self._data['app_user'].append(self.factory.create_app_user(
                overrides=fixed_data.SYSTEM_APP_USER,
                add_to_session=True
            ))

        if config.include_fixed:
            for data in fixed_data.FIXED_APP_USERS:
                self._data['app_user'].append(self.factory.create_app_user(
                    overrides=data,
                    add_to_session=True
                ))
        self.session.commit()

    def _seed_app_user_tenant_role(self, config: SeedConfig):
        if config.include_fixed:
            for data in fixed_data.FIXED_APP_USER_TENANT_ROLES:
                self._data['app_user_tenant_role'].append(
                    self.factory.create_app_user_tenant_role(
                        app_user_id=data['app_user_id'],
                        tenant_id=data['tenant_id'],
                        overrides=data,
                        add_to_session=True
                    )
                )
        self.session.commit()

    def _seed_enrichment_config(self, config: SeedConfig):
        if self._data['app_user']:
            for i, app_user in enumerate(self._data['app_user']):
                ec = self.factory.create_enrichment_config(
                    app_user_id=app_user.id,
                    overrides={
                        'id': f"{config.id_prefix}ec-{i+100}",
                        'enrichment_mode': 'platform',
                    },
                    add_to_session=True
                )
                self._data['enrichment_config'].append(ec)
        self.session.commit()

    # =========================================================================
    # LINKEDOUT DOMAIN
    # =========================================================================

    def _seed_company(self, config: SeedConfig):
        if config.include_fixed:
            for data in fixed_data.FIXED_COMPANIES:
                self._data['company'].append(self.factory.create_company(
                    overrides=data,
                    add_to_session=True
                ))

        count = config.get_count('company', 0)
        company_names = ['Gamma Corp', 'Delta Inc', 'Epsilon Ltd']
        for i in range(count):
            name = company_names[i % len(company_names)]
            self._data['company'].append(self.factory.create_company(
                overrides={
                    'id': f"{config.id_prefix}co-{i+100}",
                    'canonical_name': name,
                    'normalized_name': name.lower(),
                },
                add_to_session=True
            ))
        self.session.commit()

    def _seed_role_alias(self, config: SeedConfig):
        if config.include_fixed:
            for data in fixed_data.FIXED_ROLE_ALIASES:
                self._data['role_alias'].append(self.factory.create_role_alias(
                    overrides=data,
                    add_to_session=True
                ))

        count = config.get_count('role_alias', 0)
        titles = [
            ('Software Engineer', 'Software Engineer', 'Mid', 'Engineering'),
            ('SWE', 'Software Engineer', 'Mid', 'Engineering'),
            ('VP of Engineering', 'VP Engineering', 'VP', 'Engineering'),
        ]
        for i in range(count):
            alias, canonical, seniority, area = titles[i % len(titles)]
            self._data['role_alias'].append(self.factory.create_role_alias(
                overrides={
                    'id': f"{config.id_prefix}ra-{i+100}",
                    'alias_title': f'{alias} {i}',
                    'canonical_title': canonical,
                    'seniority_level': seniority,
                    'function_area': area,
                },
                add_to_session=True
            ))
        self.session.commit()

    def _seed_company_alias(self, config: SeedConfig):
        if self._data['company']:
            company = self._data['company'][0]
            count = config.get_count('company_alias', 0)
            for i in range(count):
                self._data['company_alias'].append(self.factory.create_company_alias(
                    company_id=company.id,
                    overrides={
                        'id': f"{config.id_prefix}ca-{i+100}",
                        'alias_name': f'Alias {i+1}',
                    },
                    add_to_session=True
                ))
        self.session.commit()

    def _seed_crawled_profile(self, config: SeedConfig):
        count = config.get_count('crawled_profile', 0)
        company_id = self._data['company'][0].id if self._data['company'] else None
        for i in range(count):
            overrides = {
                'id': f"{config.id_prefix}cp-{i+100}",
                'linkedin_url': f'https://linkedin.com/in/seed-user-{i+100}',
                'public_identifier': f'seed-user-{i+100}',
                'first_name': f'Seed{i}',
                'last_name': f'User{i}',
                'full_name': f'Seed{i} User{i}',
            }
            if company_id:
                overrides['company_id'] = company_id
            self._data['crawled_profile'].append(self.factory.create_crawled_profile(
                overrides=overrides,
                add_to_session=True
            ))
        self.session.commit()

    def _seed_experience(self, config: SeedConfig):
        count = config.get_count('experience', 0)
        if count > 0 and self._data['crawled_profile']:
            profile = self._data['crawled_profile'][0]
            for i in range(count):
                self._data['experience'].append(self.factory.create_experience(
                    crawled_profile_id=profile.id,
                    overrides={
                        'id': f"{config.id_prefix}exp-{i+100}",
                        'position': f'Engineer {i+1}',
                        'company_name': f'Seed Company {i+1}',
                    },
                    add_to_session=True
                ))
        self.session.commit()

    def _seed_education(self, config: SeedConfig):
        count = config.get_count('education', 0)
        if count > 0 and self._data['crawled_profile']:
            profile = self._data['crawled_profile'][0]
            for i in range(count):
                self._data['education'].append(self.factory.create_education(
                    crawled_profile_id=profile.id,
                    overrides={
                        'id': f"{config.id_prefix}edu-{i+100}",
                        'school_name': f'University {i+1}',
                    },
                    add_to_session=True
                ))
        self.session.commit()

    def _seed_profile_skill(self, config: SeedConfig):
        count = config.get_count('profile_skill', 0)
        if count > 0 and self._data['crawled_profile']:
            profile = self._data['crawled_profile'][0]
            skills = ['Python', 'FastAPI', 'PostgreSQL', 'React', 'Docker']
            for i in range(count):
                self._data['profile_skill'].append(self.factory.create_profile_skill(
                    crawled_profile_id=profile.id,
                    overrides={
                        'id': f"{config.id_prefix}psk-{i+100}",
                        'skill_name': skills[i % len(skills)],
                    },
                    add_to_session=True
                ))
        self.session.commit()

    def _seed_connection(self, config: SeedConfig):
        count = config.get_count('connection', 0)
        if count > 0 and self._data['app_user'] and self._data['crawled_profile'] and self._data['bu']:
            bu = next((b for b in self._data['bu'] if b.id != fixed_data.SYSTEM_BU['id']), self._data['bu'][0])
            app_user = next((u for u in self._data['app_user'] if u.id != fixed_data.SYSTEM_APP_USER['id']), self._data['app_user'][0])
            for i in range(min(count, len(self._data['crawled_profile']))):
                profile = self._data['crawled_profile'][i]
                self._data['connection'].append(self.factory.create_connection(
                    tenant_id=bu.tenant_id,
                    bu_id=bu.id,
                    app_user_id=app_user.id,
                    crawled_profile_id=profile.id,
                    overrides={
                        'id': f"{config.id_prefix}conn-{i+100}",
                    },
                    add_to_session=True
                ))
        self.session.commit()

    def _seed_import_job(self, config: SeedConfig):
        count = config.get_count('import_job', 0)
        if count > 0 and self._data['app_user'] and self._data['bu']:
            bu = next((b for b in self._data['bu'] if b.id != fixed_data.SYSTEM_BU['id']), self._data['bu'][0])
            app_user = next((u for u in self._data['app_user'] if u.id != fixed_data.SYSTEM_APP_USER['id']), self._data['app_user'][0])
            for i in range(count):
                self._data['import_job'].append(self.factory.create_import_job(
                    tenant_id=bu.tenant_id,
                    bu_id=bu.id,
                    app_user_id=app_user.id,
                    overrides={
                        'id': f"{config.id_prefix}ij-{i+100}",
                        'source_type': 'linkedin_csv',
                        'status': 'completed',
                    },
                    add_to_session=True
                ))
        self.session.commit()

    def _seed_contact_source(self, config: SeedConfig):
        count = config.get_count('contact_source', 0)
        if count > 0 and self._data['app_user'] and self._data['import_job'] and self._data['bu']:
            bu = next((b for b in self._data['bu'] if b.id != fixed_data.SYSTEM_BU['id']), self._data['bu'][0])
            app_user = next((u for u in self._data['app_user'] if u.id != fixed_data.SYSTEM_APP_USER['id']), self._data['app_user'][0])
            import_job = self._data['import_job'][0]
            for i in range(count):
                self._data['contact_source'].append(self.factory.create_contact_source(
                    tenant_id=bu.tenant_id,
                    bu_id=bu.id,
                    app_user_id=app_user.id,
                    import_job_id=import_job.id,
                    overrides={
                        'id': f"{config.id_prefix}cs-{i+100}",
                    },
                    add_to_session=True
                ))
        self.session.commit()

    def _seed_enrichment_event(self, config: SeedConfig):
        count = config.get_count('enrichment_event', 0)
        if count > 0 and self._data['app_user'] and self._data['crawled_profile'] and self._data['bu']:
            bu = next((b for b in self._data['bu'] if b.id != fixed_data.SYSTEM_BU['id']), self._data['bu'][0])
            app_user = next((u for u in self._data['app_user'] if u.id != fixed_data.SYSTEM_APP_USER['id']), self._data['app_user'][0])
            profile = self._data['crawled_profile'][0]
            for i in range(count):
                self._data['enrichment_event'].append(self.factory.create_enrichment_event(
                    tenant_id=bu.tenant_id,
                    bu_id=bu.id,
                    app_user_id=app_user.id,
                    crawled_profile_id=profile.id,
                    overrides={
                        'id': f"{config.id_prefix}ee-{i+100}",
                    },
                    add_to_session=True
                ))
        self.session.commit()

