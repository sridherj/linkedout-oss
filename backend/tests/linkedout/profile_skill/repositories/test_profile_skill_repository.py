# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for ProfileSkillRepository."""
import pytest
from unittest.mock import Mock

from sqlalchemy.orm import Session

from linkedout.profile_skill.entities.profile_skill_entity import ProfileSkillEntity
from linkedout.profile_skill.repositories.profile_skill_repository import ProfileSkillRepository
from tests.seed_db import SeedDb, TableName


class TestProfileSkillRepositoryWiring:
    def test_can_instantiate(self):
        repo = ProfileSkillRepository(Mock(spec=Session))
        assert repo is not None

    def test_has_crud_methods(self):
        repo = ProfileSkillRepository(Mock(spec=Session))
        assert callable(getattr(repo, 'list_with_filters', None))
        assert callable(getattr(repo, 'count_with_filters', None))
        assert callable(getattr(repo, 'create', None))
        assert callable(getattr(repo, 'get_by_id', None))
        assert callable(getattr(repo, 'update', None))
        assert callable(getattr(repo, 'delete', None))


INTEGRATION_SEED_CONFIG = SeedDb.SeedConfig(
    tables_to_populate=[TableName.TENANT, TableName.BU, TableName.COMPANY],
    tenant_count=1, bu_count_per_tenant=1,
    company_count=0,
)


@pytest.mark.seed_config(INTEGRATION_SEED_CONFIG)
class TestProfileSkillRepositoryIntegration:
    @pytest.fixture(scope='class')
    def class_db_resources(self, class_scoped_isolated_db_session):
        return class_scoped_isolated_db_session

    @pytest.fixture(scope='class')
    def db_session(self, class_db_resources):
        session, _ = class_db_resources
        return session

    @pytest.fixture(scope='class')
    def crawled_profile(self, db_session):
        from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
        profile = CrawledProfileEntity(
            linkedin_url='https://linkedin.com/in/test-psk-profile',
            data_source='test',
        )
        db_session.add(profile)
        db_session.flush()
        return profile

    @pytest.fixture
    def repository(self, db_session):
        return ProfileSkillRepository(db_session)

    def test_create_generates_id_with_prefix(self, repository, db_session, crawled_profile):
        entity = ProfileSkillEntity(
            crawled_profile_id=crawled_profile.id,
            skill_name='Python',
        )
        created = repository.create(entity)
        db_session.commit()
        assert created.id is not None
        assert created.id.startswith('psk_')

    def test_list_with_profile_filter(self, repository, crawled_profile):
        results = repository.list_with_filters(crawled_profile_id=crawled_profile.id)
        assert len(results) >= 1

    def test_get_by_id(self, repository, crawled_profile):
        entity = ProfileSkillEntity(
            crawled_profile_id=crawled_profile.id,
            skill_name='JavaScript',
        )
        created = repository.create(entity)
        fetched = repository.get_by_id(created.id)
        assert fetched is not None
        assert fetched.id == created.id

    def test_count_with_filters(self, repository):
        count = repository.count_with_filters()
        assert count >= 1
