# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for RoleAliasRepository."""
import pytest
from unittest.mock import Mock

from sqlalchemy.orm import Session

from linkedout.role_alias.entities.role_alias_entity import RoleAliasEntity
from linkedout.role_alias.repositories.role_alias_repository import RoleAliasRepository
from tests.seed_db import SeedDb, TableName


class TestRoleAliasRepositoryWiring:
    def test_can_instantiate_with_session(self):
        repo = RoleAliasRepository(Mock(spec=Session))
        assert repo is not None

    def test_has_crud_methods(self):
        repo = RoleAliasRepository(Mock(spec=Session))
        assert hasattr(repo, 'list_with_filters')
        assert hasattr(repo, 'count_with_filters')
        assert hasattr(repo, 'create')
        assert hasattr(repo, 'get_by_id')
        assert hasattr(repo, 'update')
        assert hasattr(repo, 'delete')
        assert callable(repo.list_with_filters)
        assert callable(repo.count_with_filters)
        assert callable(repo.create)
        assert callable(repo.get_by_id)
        assert callable(repo.update)
        assert callable(repo.delete)


INTEGRATION_SEED_CONFIG = SeedDb.SeedConfig(
    tables_to_populate=[TableName.TENANT, TableName.BU],
    tenant_count=1, bu_count_per_tenant=1,
)


@pytest.mark.seed_config(INTEGRATION_SEED_CONFIG)
class TestRoleAliasRepositoryIntegration:
    @pytest.fixture(scope='class')
    def class_db_resources(self, class_scoped_isolated_db_session):
        return class_scoped_isolated_db_session

    @pytest.fixture(scope='class')
    def db_session(self, class_db_resources):
        session, _ = class_db_resources
        return session

    @pytest.fixture
    def repository(self, db_session):
        return RoleAliasRepository(db_session)

    def test_create_generates_id_with_prefix(self, repository, db_session):
        entity = RoleAliasEntity(
            alias_title='Software Engineer',
            canonical_title='Software Engineer',
            seniority_level='Mid',
            function_area='Engineering',
        )
        created = repository.create(entity)
        db_session.commit()
        assert created.id is not None
        assert created.id.startswith('ra_')

    def test_list_with_ilike_filter(self, repository, db_session):
        # Create a second entity to test filtering
        entity = RoleAliasEntity(
            alias_title='Data Scientist',
            canonical_title='Data Scientist',
            seniority_level='Senior',
            function_area='Data',
        )
        repository.create(entity)
        db_session.commit()

        results = repository.list_with_filters(alias_title='Software')
        assert len(results) >= 1
        assert all('Software' in r.alias_title for r in results)

    def test_count_with_filters(self, repository):
        count = repository.count_with_filters(function_area='Engineering')
        assert count >= 1

    def test_get_by_id(self, repository, db_session):
        entity = RoleAliasEntity(
            alias_title='Product Manager',
            canonical_title='Product Manager',
        )
        created = repository.create(entity)
        db_session.commit()

        found = repository.get_by_id(created.id)
        assert found is not None
        assert found.alias_title == 'Product Manager'

    def test_get_by_id_not_found(self, repository):
        found = repository.get_by_id('ra_nonexistent')
        assert found is None
