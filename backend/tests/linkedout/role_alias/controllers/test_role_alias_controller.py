# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for RoleAlias controller endpoints.

These tests verify that the RoleAlias controller endpoints are correctly wired
and return the expected HTTP status codes. The mock service is injected via
FastAPI's dependency_overrides mechanism.

Wiring tests verify:
- All endpoints are registered and reachable
- Correct HTTP status codes for success, not-found, and validation errors
- Request/response shapes are correct
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec
from fastapi.testclient import TestClient

from main import app
from linkedout.role_alias.controllers.role_alias_controller import (
    _get_role_alias_service,
    _get_write_role_alias_service,
)
from linkedout.role_alias.services.role_alias_service import RoleAliasService
from linkedout.role_alias.schemas.role_alias_schema import RoleAliasSchema


BASE_URL = '/role-aliases'


@pytest.fixture
def mock_role_alias_schema():
    return RoleAliasSchema(
        id='ra_test123',
        alias_title='Software Engineer',
        canonical_title='Software Engineer',
        seniority_level='Mid',
        function_area='Engineering',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_service():
    return create_autospec(RoleAliasService, instance=True, spec_set=True)


@pytest.fixture
def test_client(mock_service):
    """Create a TestClient with mock service injected via dependency_overrides."""
    def _override():
        yield mock_service

    app.dependency_overrides[_get_role_alias_service] = _override
    app.dependency_overrides[_get_write_role_alias_service] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


# =============================================================================
# LIST ENDPOINT
# =============================================================================


class TestListRoleAliasesEndpoint:
    def test_list_success(self, test_client, mock_service, mock_role_alias_schema):
        mock_service.list_role_aliases.return_value = ([mock_role_alias_schema], 1)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
        assert len(data['role_aliases']) == 1
        assert data['role_aliases'][0]['id'] == 'ra_test123'

    def test_list_empty(self, test_client, mock_service):
        mock_service.list_role_aliases.return_value = ([], 0)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        assert response.json()['total'] == 0
        assert response.json()['role_aliases'] == []


# =============================================================================
# GET BY ID ENDPOINT
# =============================================================================


class TestGetRoleAliasByIdEndpoint:
    def test_get_success(self, test_client, mock_service, mock_role_alias_schema):
        mock_service.get_role_alias_by_id.return_value = mock_role_alias_schema
        response = test_client.get(f'{BASE_URL}/ra_test123')
        assert response.status_code == 200
        assert response.json()['role_alias']['id'] == 'ra_test123'

    def test_get_not_found(self, test_client, mock_service):
        mock_service.get_role_alias_by_id.return_value = None
        response = test_client.get(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


# =============================================================================
# CREATE ENDPOINT
# =============================================================================


class TestCreateRoleAliasEndpoint:
    def test_create_success(self, test_client, mock_service, mock_role_alias_schema):
        mock_service.create_role_alias.return_value = mock_role_alias_schema
        response = test_client.post(
            BASE_URL,
            json={'alias_title': 'SWE', 'canonical_title': 'Software Engineer'},
        )
        assert response.status_code == 201
        assert response.json()['role_alias']['id'] == 'ra_test123'

    def test_create_missing_required_returns_422(self, test_client, mock_service):
        response = test_client.post(BASE_URL, json={})
        assert response.status_code == 422


# =============================================================================
# UPDATE ENDPOINT
# =============================================================================


class TestUpdateRoleAliasEndpoint:
    def test_update_success(self, test_client, mock_service, mock_role_alias_schema):
        mock_service.update_role_alias.return_value = mock_role_alias_schema
        response = test_client.patch(
            f'{BASE_URL}/ra_test123',
            json={'canonical_title': 'Updated Title'},
        )
        assert response.status_code == 200
        assert response.json()['role_alias']['id'] == 'ra_test123'

    def test_update_not_found(self, test_client, mock_service):
        mock_service.update_role_alias.side_effect = ValueError('not found')
        response = test_client.patch(
            f'{BASE_URL}/nonexistent',
            json={'canonical_title': 'x'},
        )
        assert response.status_code == 404


# =============================================================================
# DELETE ENDPOINT
# =============================================================================


class TestDeleteRoleAliasEndpoint:
    def test_delete_success(self, test_client, mock_service):
        mock_service.delete_role_alias_by_id.return_value = None
        response = test_client.delete(f'{BASE_URL}/ra_test123')
        assert response.status_code == 204

    def test_delete_not_found(self, test_client, mock_service):
        mock_service.delete_role_alias_by_id.side_effect = ValueError('not found')
        response = test_client.delete(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


# =============================================================================
# BULK CREATE ENDPOINT
# =============================================================================


class TestBulkCreateRoleAliasesEndpoint:
    def test_bulk_create_success(self, test_client, mock_service, mock_role_alias_schema):
        mock_service.create_role_aliases_bulk.return_value = [mock_role_alias_schema]
        response = test_client.post(
            f'{BASE_URL}/bulk',
            json={
                'role_aliases': [
                    {'alias_title': 'SWE', 'canonical_title': 'Software Engineer'},
                    {'alias_title': 'PM', 'canonical_title': 'Product Manager'},
                ]
            },
        )
        assert response.status_code == 201
        assert len(response.json()['role_aliases']) == 1
