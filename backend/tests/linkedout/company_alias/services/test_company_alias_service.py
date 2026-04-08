# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for CompanyAliasService.

CompanyAlias is a shared entity (no tenant/BU), following the Company pattern.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec

from sqlalchemy.orm import Session

from linkedout.company_alias.entities.company_alias_entity import CompanyAliasEntity
from linkedout.company_alias.repositories.company_alias_repository import CompanyAliasRepository
from linkedout.company_alias.services.company_alias_service import CompanyAliasService
from linkedout.company_alias.schemas.company_alias_schema import CompanyAliasSchema
from linkedout.company_alias.schemas.company_alias_api_schema import (
    ListCompanyAliasesRequestSchema,
    CreateCompanyAliasRequestSchema,
    UpdateCompanyAliasRequestSchema,
)


@pytest.fixture
def mock_session():
    return create_autospec(Session, instance=True, spec_set=True)


@pytest.fixture
def mock_repository():
    return create_autospec(CompanyAliasRepository, instance=True, spec_set=True)


@pytest.fixture
def service(mock_session, mock_repository):
    svc = CompanyAliasService(mock_session)
    svc._repository = mock_repository
    return svc


@pytest.fixture
def mock_entity():
    entity = CompanyAliasEntity(
        alias_name='Acme',
        company_id='co_test123',
        source='manual',
    )
    entity.id = 'ca_test123'
    entity.created_at = datetime.now(timezone.utc)
    entity.updated_at = datetime.now(timezone.utc)
    return entity


class TestCompanyAliasServiceWiring:
    def test_can_instantiate(self, mock_session):
        svc = CompanyAliasService(mock_session)
        assert svc is not None

    def test_has_repository(self, service):
        assert service._repository is not None

    def test_has_crud_methods(self):
        svc = CompanyAliasService(create_autospec(Session, instance=True))
        assert callable(getattr(svc, 'list_company_aliases', None))
        assert callable(getattr(svc, 'create_company_alias', None))
        assert callable(getattr(svc, 'create_company_aliases', None))
        assert callable(getattr(svc, 'update_company_alias', None))
        assert callable(getattr(svc, 'get_company_alias_by_id', None))
        assert callable(getattr(svc, 'delete_company_alias_by_id', None))


class TestCompanyAliasServiceListCompanyAliases:
    def test_calls_repository(self, service, mock_repository, mock_entity):
        mock_repository.list_with_filters.return_value = [mock_entity]
        mock_repository.count_with_filters.return_value = 1

        req = ListCompanyAliasesRequestSchema()
        company_aliases, total = service.list_company_aliases(req)

        assert total == 1
        assert len(company_aliases) == 1
        assert isinstance(company_aliases[0], CompanyAliasSchema)
        mock_repository.list_with_filters.assert_called_once()
        mock_repository.count_with_filters.assert_called_once()

    def test_handles_empty(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        req = ListCompanyAliasesRequestSchema()
        company_aliases, total = service.list_company_aliases(req)

        assert total == 0
        assert company_aliases == []


class TestCompanyAliasServiceCreateCompanyAlias:
    def test_creates_entity(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateCompanyAliasRequestSchema(
            alias_name='Acme',
            company_id='co_test123',
            source='manual',
        )
        result = service.create_company_alias(req)

        assert isinstance(result, CompanyAliasSchema)
        assert result.alias_name == 'Acme'
        mock_repository.create.assert_called_once()


class TestCompanyAliasServiceUpdateCompanyAlias:
    def test_updates_provided_fields(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        req = UpdateCompanyAliasRequestSchema(
            company_alias_id='ca_test123',
            source='llm',
        )
        result = service.update_company_alias(req)

        assert isinstance(result, CompanyAliasSchema)
        mock_repository.get_by_id.assert_called_once_with('ca_test123')

    def test_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        req = UpdateCompanyAliasRequestSchema(
            company_alias_id='ca_nonexistent',
            source='llm',
        )
        with pytest.raises(ValueError, match='Company alias not found'):
            service.update_company_alias(req)
