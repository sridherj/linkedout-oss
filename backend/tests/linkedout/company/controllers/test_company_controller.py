# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for Company controller endpoints.

Company is a shared entity (no tenant/BU scoping).
Tests verify endpoints are reachable and return correct status codes.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec
from fastapi.testclient import TestClient

from main import app
from linkedout.company.controllers.company_controller import (
    _get_company_service,
    _get_write_company_service,
)
from linkedout.company.services.company_service import CompanyService
from linkedout.company.schemas.company_schema import CompanySchema


BASE_URL = '/companies'


@pytest.fixture
def mock_company_schema():
    return CompanySchema(
        id='co_test123',
        canonical_name='Acme Corp',
        normalized_name='acme corp',
        domain='acme.com',
        industry='Technology',
        network_connection_count=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_service():
    return create_autospec(CompanyService, instance=True, spec_set=True)


@pytest.fixture
def test_client(mock_service):
    """Create a TestClient with mock service injected via dependency_overrides."""
    def _override():
        yield mock_service

    app.dependency_overrides[_get_company_service] = _override
    app.dependency_overrides[_get_write_company_service] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


# =============================================================================
# LIST ENDPOINT
# =============================================================================


class TestListCompaniesEndpoint:
    def test_list_success(self, test_client, mock_service, mock_company_schema):
        mock_service.list_companies.return_value = ([mock_company_schema], 1)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
        assert len(data['companies']) == 1
        assert data['companies'][0]['id'] == 'co_test123'

    def test_list_empty(self, test_client, mock_service):
        mock_service.list_companies.return_value = ([], 0)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        assert response.json()['total'] == 0
        assert response.json()['companies'] == []

    def test_list_with_filters(self, test_client, mock_service, mock_company_schema):
        mock_service.list_companies.return_value = ([mock_company_schema], 1)
        response = test_client.get(
            BASE_URL,
            params={'limit': 20, 'offset': 0, 'industry': 'Technology'},
        )
        assert response.status_code == 200
        mock_service.list_companies.assert_called_once()


# =============================================================================
# GET BY ID ENDPOINT
# =============================================================================


class TestGetCompanyByIdEndpoint:
    def test_get_success(self, test_client, mock_service, mock_company_schema):
        mock_service.get_company_by_id.return_value = mock_company_schema
        response = test_client.get(f'{BASE_URL}/co_test123')
        assert response.status_code == 200
        assert response.json()['company']['id'] == 'co_test123'

    def test_get_not_found(self, test_client, mock_service):
        mock_service.get_company_by_id.return_value = None
        response = test_client.get(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


# =============================================================================
# CREATE ENDPOINT
# =============================================================================


class TestCreateCompanyEndpoint:
    def test_create_success(self, test_client, mock_service, mock_company_schema):
        mock_service.create_company.return_value = mock_company_schema
        response = test_client.post(
            BASE_URL,
            json={'canonical_name': 'Acme Corp', 'normalized_name': 'acme corp'},
        )
        assert response.status_code == 201
        assert response.json()['company']['id'] == 'co_test123'

    def test_create_missing_required_returns_422(self, test_client, mock_service):
        response = test_client.post(BASE_URL, json={})
        assert response.status_code == 422


# =============================================================================
# UPDATE ENDPOINT
# =============================================================================


class TestUpdateCompanyEndpoint:
    def test_update_success(self, test_client, mock_service, mock_company_schema):
        mock_service.update_company.return_value = mock_company_schema
        response = test_client.patch(
            f'{BASE_URL}/co_test123', json={'industry': 'Finance'}
        )
        assert response.status_code == 200
        assert response.json()['company']['id'] == 'co_test123'

    def test_update_not_found(self, test_client, mock_service):
        mock_service.update_company.side_effect = ValueError('not found')
        response = test_client.patch(
            f'{BASE_URL}/nonexistent', json={'industry': 'Finance'}
        )
        assert response.status_code == 404


# =============================================================================
# DELETE ENDPOINT
# =============================================================================


class TestDeleteCompanyEndpoint:
    def test_delete_success(self, test_client, mock_service):
        mock_service.delete_company_by_id.return_value = None
        response = test_client.delete(f'{BASE_URL}/co_test123')
        assert response.status_code == 204

    def test_delete_not_found(self, test_client, mock_service):
        mock_service.delete_company_by_id.side_effect = ValueError('not found')
        response = test_client.delete(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


# =============================================================================
# BULK CREATE ENDPOINT
# =============================================================================


class TestBulkCreateCompaniesEndpoint:
    def test_bulk_create_success(self, test_client, mock_service, mock_company_schema):
        mock_service.create_companies.return_value = [mock_company_schema]
        response = test_client.post(
            f'{BASE_URL}/bulk',
            json={
                'companies': [
                    {'canonical_name': 'Acme Corp', 'normalized_name': 'acme corp'},
                    {'canonical_name': 'Beta Inc', 'normalized_name': 'beta inc'},
                ]
            },
        )
        assert response.status_code == 201
        assert len(response.json()['companies']) == 1
