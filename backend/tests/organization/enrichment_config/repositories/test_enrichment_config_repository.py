# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for EnrichmentConfigRepository."""
import pytest
from unittest.mock import Mock

from sqlalchemy.orm import Session

from organization.enrichment_config.entities.enrichment_config_entity import EnrichmentConfigEntity
from organization.enrichment_config.repositories.enrichment_config_repository import EnrichmentConfigRepository
from tests.seed_db import SeedDb, TableName


class TestEnrichmentConfigRepositoryWiring:
    def test_has_list_with_filters(self):
        repo = EnrichmentConfigRepository(Mock(spec=Session))
        assert hasattr(repo, 'list_with_filters')

    def test_has_count_with_filters(self):
        repo = EnrichmentConfigRepository(Mock(spec=Session))
        assert hasattr(repo, 'count_with_filters')

    def test_has_create(self):
        repo = EnrichmentConfigRepository(Mock(spec=Session))
        assert hasattr(repo, 'create')

    def test_has_get_by_id(self):
        repo = EnrichmentConfigRepository(Mock(spec=Session))
        assert hasattr(repo, 'get_by_id')

    def test_has_update(self):
        repo = EnrichmentConfigRepository(Mock(spec=Session))
        assert hasattr(repo, 'update')

    def test_has_delete(self):
        repo = EnrichmentConfigRepository(Mock(spec=Session))
        assert hasattr(repo, 'delete')


INTEGRATION_SEED_CONFIG = SeedDb.SeedConfig(
    tables_to_populate=[TableName.APP_USER],
    app_user_count=1,
)


@pytest.mark.seed_config(INTEGRATION_SEED_CONFIG)
class TestEnrichmentConfigRepositoryIntegration:
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

    @pytest.fixture
    def repository(self, db_session):
        return EnrichmentConfigRepository(db_session)

    def test_create_generates_id_with_prefix(self, repository, db_session, seeded_data):
        app_user = seeded_data[TableName.APP_USER][0]
        entity = EnrichmentConfigEntity(
            app_user_id=app_user.id,
            enrichment_mode='platform',
        )
        created = repository.create(entity)
        db_session.commit()
        assert created.id is not None
        assert created.id.startswith('ec_')

    def test_list_with_app_user_filter(self, repository, db_session, seeded_data):
        app_user = seeded_data[TableName.APP_USER][0]
        results = repository.list_with_filters(app_user_id=app_user.id)
        assert len(results) >= 1

    def test_unique_constraint_on_app_user_id(self, repository, db_session, seeded_data):
        app_user = seeded_data[TableName.APP_USER][0]
        entity2 = EnrichmentConfigEntity(
            app_user_id=app_user.id,
            enrichment_mode='byok',
        )
        with pytest.raises(Exception):
            repository.create(entity2)
            db_session.flush()
