# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for Connection controller endpoints."""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec
from fastapi.testclient import TestClient

from main import app
from linkedout.connection.controllers.connection_controller import (
    _get_connection_service,
    _get_write_connection_service,
)
from linkedout.connection.services.connection_service import ConnectionService
from linkedout.connection.schemas.connection_schema import ConnectionSchema


BASE_URL = '/tenants/t_1/bus/bu_1/connections'


@pytest.fixture
def mock_connection_schema():
    return ConnectionSchema(
        id='conn_test123',
        tenant_id='t_1',
        bu_id='bu_1',
        app_user_id='au_1',
        crawled_profile_id='cp_1',
        affinity_score=0.85,
        dunbar_tier='active',
        affinity_source_count=0,
        affinity_recency=0,
        affinity_career_overlap=0,
        affinity_mutual_connections=0,
        affinity_version=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_service():
    return create_autospec(ConnectionService, instance=True, spec_set=True)


@pytest.fixture
def test_client(mock_service):
    def _override():
        yield mock_service

    app.dependency_overrides[_get_connection_service] = _override
    app.dependency_overrides[_get_write_connection_service] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestListConnectionsEndpoint:
    def test_list_success(self, test_client, mock_service, mock_connection_schema):
        mock_service.list_entities.return_value = ([mock_connection_schema], 1)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
        assert len(data['connections']) == 1
        assert data['connections'][0]['id'] == 'conn_test123'

    def test_list_empty(self, test_client, mock_service):
        mock_service.list_entities.return_value = ([], 0)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        assert response.json()['total'] == 0
        assert response.json()['connections'] == []


class TestGetConnectionByIdEndpoint:
    def test_get_success(self, test_client, mock_service, mock_connection_schema):
        mock_service.get_entity_by_id.return_value = mock_connection_schema
        response = test_client.get(f'{BASE_URL}/conn_test123')
        assert response.status_code == 200
        assert response.json()['connection']['id'] == 'conn_test123'

    def test_get_not_found(self, test_client, mock_service):
        mock_service.get_entity_by_id.return_value = None
        response = test_client.get(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


class TestCreateConnectionEndpoint:
    def test_create_success(self, test_client, mock_service, mock_connection_schema):
        mock_service.create_entity.return_value = mock_connection_schema
        response = test_client.post(
            BASE_URL,
            json={'app_user_id': 'au_1', 'crawled_profile_id': 'cp_1'},
        )
        assert response.status_code == 201
        assert response.json()['connection']['id'] == 'conn_test123'

    def test_create_missing_required_returns_422(self, test_client, mock_service):
        response = test_client.post(BASE_URL, json={})
        assert response.status_code == 422


class TestUpdateConnectionEndpoint:
    def test_update_success(self, test_client, mock_service, mock_connection_schema):
        mock_service.update_entity.return_value = mock_connection_schema
        response = test_client.patch(
            f'{BASE_URL}/conn_test123',
            json={'dunbar_tier': 'inner_circle'},
        )
        assert response.status_code == 200
        assert response.json()['connection']['id'] == 'conn_test123'

    def test_update_not_found(self, test_client, mock_service):
        mock_service.update_entity.side_effect = ValueError('not found')
        response = test_client.patch(
            f'{BASE_URL}/nonexistent',
            json={'dunbar_tier': 'active'},
        )
        assert response.status_code == 404


class TestDeleteConnectionEndpoint:
    def test_delete_success(self, test_client, mock_service):
        mock_service.delete_entity_by_id.return_value = None
        response = test_client.delete(f'{BASE_URL}/conn_test123')
        assert response.status_code == 204

    def test_delete_not_found(self, test_client, mock_service):
        mock_service.delete_entity_by_id.side_effect = ValueError('not found')
        response = test_client.delete(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


class TestBulkCreateConnectionsEndpoint:
    def test_bulk_create_success(self, test_client, mock_service, mock_connection_schema):
        mock_service.create_entities_bulk.return_value = [mock_connection_schema]
        response = test_client.post(
            f'{BASE_URL}/bulk',
            json={
                'connections': [
                    {'app_user_id': 'au_1', 'crawled_profile_id': 'cp_1'},
                    {'app_user_id': 'au_1', 'crawled_profile_id': 'cp_2'},
                ]
            },
        )
        assert response.status_code == 201
        assert len(response.json()['connections']) == 1
