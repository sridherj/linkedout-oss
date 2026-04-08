# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for CompanyService.

Verifies that CompanyService is correctly wired.
Company is a shared entity (no tenant/BU), following the Tenant pattern.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec

from sqlalchemy.orm import Session

from linkedout.company.entities.company_entity import CompanyEntity
from linkedout.company.repositories.company_repository import CompanyRepository
from linkedout.company.services.company_service import CompanyService
from linkedout.company.schemas.company_schema import CompanySchema
from linkedout.company.schemas.company_api_schema import (
    ListCompaniesRequestSchema,
    CreateCompanyRequestSchema,
    UpdateCompanyRequestSchema,
)


@pytest.fixture
def mock_session():
    return create_autospec(Session, instance=True, spec_set=True)


@pytest.fixture
def mock_repository():
    return create_autospec(CompanyRepository, instance=True, spec_set=True)


@pytest.fixture
def service(mock_session, mock_repository):
    svc = CompanyService(mock_session)
    svc._repository = mock_repository
    return svc


@pytest.fixture
def mock_entity():
    entity = CompanyEntity(
        canonical_name='Acme Corp',
        normalized_name='acme corp',
        domain='acme.com',
        industry='Technology',
    )
    entity.id = 'co_test123'
    entity.network_connection_count = 0
    entity.created_at = datetime.now(timezone.utc)
    entity.updated_at = datetime.now(timezone.utc)
    return entity


class TestCompanyServiceWiring:
    def test_can_instantiate(self, mock_session):
        svc = CompanyService(mock_session)
        assert svc is not None

    def test_has_repository(self, service):
        assert service._repository is not None

    def test_has_crud_methods(self):
        svc = CompanyService(create_autospec(Session, instance=True))
        assert callable(getattr(svc, 'list_companies', None))
        assert callable(getattr(svc, 'create_company', None))
        assert callable(getattr(svc, 'create_companies', None))
        assert callable(getattr(svc, 'update_company', None))
        assert callable(getattr(svc, 'get_company_by_id', None))
        assert callable(getattr(svc, 'delete_company_by_id', None))


class TestCompanyServiceListCompanies:
    def test_calls_repository(self, service, mock_repository, mock_entity):
        mock_repository.list_with_filters.return_value = [mock_entity]
        mock_repository.count_with_filters.return_value = 1

        req = ListCompaniesRequestSchema()
        companies, total = service.list_companies(req)

        assert total == 1
        assert len(companies) == 1
        assert isinstance(companies[0], CompanySchema)
        mock_repository.list_with_filters.assert_called_once()
        mock_repository.count_with_filters.assert_called_once()

    def test_handles_empty(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        req = ListCompaniesRequestSchema()
        companies, total = service.list_companies(req)

        assert total == 0
        assert companies == []


class TestCompanyServiceCreateCompany:
    def test_creates_entity(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateCompanyRequestSchema(
            canonical_name='Acme Corp',
            normalized_name='acme corp',
            domain='acme.com',
        )
        result = service.create_company(req)

        assert isinstance(result, CompanySchema)
        assert result.canonical_name == 'Acme Corp'
        mock_repository.create.assert_called_once()


class TestCompanyServiceUpdateCompany:
    def test_updates_provided_fields(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        req = UpdateCompanyRequestSchema(
            company_id='co_test123',
            industry='Finance',
        )
        result = service.update_company(req)

        assert isinstance(result, CompanySchema)
        mock_repository.get_by_id.assert_called_once_with('co_test123')

    def test_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        req = UpdateCompanyRequestSchema(
            company_id='co_nonexistent',
            industry='Finance',
        )
        with pytest.raises(ValueError, match='Company not found'):
            service.update_company(req)
