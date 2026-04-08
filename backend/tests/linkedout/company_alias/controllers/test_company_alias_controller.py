# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for CompanyAlias controller endpoints.

CompanyAlias is a shared entity (no tenant/BU scoping).
Tests verify endpoints are reachable and return correct status codes.
"""
from datetime import datetime, timezone
from unittest.mock import create_autospec
from fastapi.testclient import TestClient

from main import app
from linkedout.company_alias.controllers.company_alias_controller import (
    _get_company_alias_service,
    _get_write_company_alias_service,
)
from linkedout.company_alias.services.company_alias_service import CompanyAliasService
from linkedout.company_alias.schemas.company_alias_schema import CompanyAliasSchema

import pytest


BASE_URL = '/company-aliases'


@pytest.fixture
def mock_company_alias_schema():
    return CompanyAliasSchema(
        id='ca_test123',
        alias_name='Acme',
        company_id='co_test123',
        source='manual',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_service():
    return create_autospec(CompanyAliasService, instance=True, spec_set=True)


@pytest.fixture
def test_client(mock_service):
    """Create a TestClient with mock service injected via dependency_overrides."""
    def _override():
        yield mock_service

    app.dependency_overrides[_get_company_alias_service] = _override
    app.dependency_overrides[_get_write_company_alias_service] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


# =============================================================================
# LIST ENDPOINT
# =============================================================================


class TestListCompanyAliasesEndpoint:
    def test_list_success(self, test_client, mock_service, mock_company_alias_schema):
        mock_service.list_company_aliases.return_value = ([mock_company_alias_schema], 1)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
        assert len(data['company_aliases']) == 1
        assert data['company_aliases'][0]['id'] == 'ca_test123'

    def test_list_empty(self, test_client, mock_service):
        mock_service.list_company_aliases.return_value = ([], 0)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        assert response.json()['total'] == 0
        assert response.json()['company_aliases'] == []

    def test_list_with_filters(self, test_client, mock_service, mock_company_alias_schema):
        mock_service.list_company_aliases.return_value = ([mock_company_alias_schema], 1)
        response = test_client.get(
            BASE_URL,
            params={'limit': 20, 'offset': 0, 'source': 'manual'},
        )
        assert response.status_code == 200
        mock_service.list_company_aliases.assert_called_once()


# =============================================================================
# GET BY ID ENDPOINT
# =============================================================================


class TestGetCompanyAliasByIdEndpoint:
    def test_get_success(self, test_client, mock_service, mock_company_alias_schema):
        mock_service.get_company_alias_by_id.return_value = mock_company_alias_schema
        response = test_client.get(f'{BASE_URL}/ca_test123')
        assert response.status_code == 200
        assert response.json()['company_alias']['id'] == 'ca_test123'

    def test_get_not_found(self, test_client, mock_service):
        mock_service.get_company_alias_by_id.return_value = None
        response = test_client.get(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


# =============================================================================
# CREATE ENDPOINT
# =============================================================================


class TestCreateCompanyAliasEndpoint:
    def test_create_success(self, test_client, mock_service, mock_company_alias_schema):
        mock_service.create_company_alias.return_value = mock_company_alias_schema
        response = test_client.post(
            BASE_URL,
            json={'alias_name': 'Acme', 'company_id': 'co_test123'},
        )
        assert response.status_code == 201
        assert response.json()['company_alias']['id'] == 'ca_test123'

    def test_create_missing_required_returns_422(self, test_client, mock_service):
        response = test_client.post(BASE_URL, json={})
        assert response.status_code == 422


# =============================================================================
# UPDATE ENDPOINT
# =============================================================================


class TestUpdateCompanyAliasEndpoint:
    def test_update_success(self, test_client, mock_service, mock_company_alias_schema):
        mock_service.update_company_alias.return_value = mock_company_alias_schema
        response = test_client.patch(
            f'{BASE_URL}/ca_test123', json={'source': 'llm'}
        )
        assert response.status_code == 200
        assert response.json()['company_alias']['id'] == 'ca_test123'

    def test_update_not_found(self, test_client, mock_service):
        mock_service.update_company_alias.side_effect = ValueError('not found')
        response = test_client.patch(
            f'{BASE_URL}/nonexistent', json={'source': 'llm'}
        )
        assert response.status_code == 404


# =============================================================================
# DELETE ENDPOINT
# =============================================================================


class TestDeleteCompanyAliasEndpoint:
    def test_delete_success(self, test_client, mock_service):
        mock_service.delete_company_alias_by_id.return_value = None
        response = test_client.delete(f'{BASE_URL}/ca_test123')
        assert response.status_code == 204

    def test_delete_not_found(self, test_client, mock_service):
        mock_service.delete_company_alias_by_id.side_effect = ValueError('not found')
        response = test_client.delete(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


# =============================================================================
# BULK CREATE ENDPOINT
# =============================================================================


class TestBulkCreateCompanyAliasesEndpoint:
    def test_bulk_create_success(self, test_client, mock_service, mock_company_alias_schema):
        mock_service.create_company_aliases.return_value = [mock_company_alias_schema]
        response = test_client.post(
            f'{BASE_URL}/bulk',
            json={
                'company_aliases': [
                    {'alias_name': 'Acme', 'company_id': 'co_test123'},
                    {'alias_name': 'Acme Inc', 'company_id': 'co_test123'},
                ]
            },
        )
        assert response.status_code == 201
        assert len(response.json()['company_aliases']) == 1
