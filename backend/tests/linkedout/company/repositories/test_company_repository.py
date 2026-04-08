# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for CompanyRepository."""
import pytest
from unittest.mock import Mock

from sqlalchemy.orm import Session

from linkedout.company.entities.company_entity import CompanyEntity
from linkedout.company.repositories.company_repository import CompanyRepository
from tests.seed_db import SeedDb, TableName


class TestCompanyRepositoryWiring:
    def test_can_instantiate(self):
        repo = CompanyRepository(Mock(spec=Session))
        assert repo is not None

    def test_has_crud_methods(self):
        repo = CompanyRepository(Mock(spec=Session))
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
class TestCompanyRepositoryIntegration:
    @pytest.fixture(scope='class')
    def class_db_resources(self, class_scoped_isolated_db_session):
        return class_scoped_isolated_db_session

    @pytest.fixture(scope='class')
    def db_session(self, class_db_resources):
        session, _ = class_db_resources
        return session

    @pytest.fixture
    def repository(self, db_session):
        return CompanyRepository(db_session)

    def test_create_generates_id_with_prefix(self, repository, db_session):
        entity = CompanyEntity(
            canonical_name='Acme Corp',
            normalized_name='acme corp',
        )
        created = repository.create(entity)
        db_session.commit()
        assert created.id is not None
        assert created.id.startswith('co_')

    def test_list_with_ilike_filter(self, repository):
        results = repository.list_with_filters(canonical_name='Acme')
        assert len(results) >= 1

    def test_get_by_id(self, repository):
        # Create a company first
        entity = CompanyEntity(
            canonical_name='Lookup Corp',
            normalized_name='lookup corp',
        )
        created = repository.create(entity)
        fetched = repository.get_by_id(created.id)
        assert fetched is not None
        assert fetched.id == created.id

    def test_count_with_filters(self, repository):
        count = repository.count_with_filters()
        assert count >= 1
