# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for SearchSession controller endpoints."""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec
from fastapi.testclient import TestClient

from main import app
from linkedout.search_session.controllers.search_session_controller import (
    _get_search_session_service,
    _get_write_search_session_service,
)
from linkedout.search_session.services.search_session_service import SearchSessionService
from linkedout.search_session.schemas.search_session_schema import SearchSessionSchema


BASE_URL = '/tenants/t_1/bus/bu_1/search-sessions'


@pytest.fixture
def mock_search_session_schema():
    return SearchSessionSchema(
        id='ss_test123',
        tenant_id='t_1',
        bu_id='bu_1',
        app_user_id='au_1',
        initial_query='find senior engineers',
        turn_count=1,
        last_active_at=datetime.now(timezone.utc),
        is_saved=False,
        saved_name=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_service():
    return create_autospec(SearchSessionService, instance=True, spec_set=True)


@pytest.fixture
def test_client(mock_service):
    def _override():
        yield mock_service

    app.dependency_overrides[_get_search_session_service] = _override
    app.dependency_overrides[_get_write_search_session_service] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestListSearchSessionsEndpoint:
    def test_list_success(self, test_client, mock_service, mock_search_session_schema):
        mock_service.list_entities.return_value = ([mock_search_session_schema], 1)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
        assert len(data['search_sessions']) == 1
        assert data['search_sessions'][0]['id'] == 'ss_test123'

    def test_list_empty(self, test_client, mock_service):
        mock_service.list_entities.return_value = ([], 0)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        assert response.json()['total'] == 0
        assert response.json()['search_sessions'] == []


class TestGetSearchSessionByIdEndpoint:
    def test_get_success(self, test_client, mock_service, mock_search_session_schema):
        mock_service.get_entity_by_id.return_value = mock_search_session_schema
        response = test_client.get(f'{BASE_URL}/ss_test123')
        assert response.status_code == 200
        assert response.json()['search_session']['id'] == 'ss_test123'

    def test_get_not_found(self, test_client, mock_service):
        mock_service.get_entity_by_id.return_value = None
        response = test_client.get(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


class TestCreateSearchSessionEndpoint:
    def test_create_success(self, test_client, mock_service, mock_search_session_schema):
        mock_service.create_entity.return_value = mock_search_session_schema
        response = test_client.post(
            BASE_URL,
            json={'app_user_id': 'au_1', 'initial_query': 'find senior engineers'},
        )
        assert response.status_code == 201
        assert response.json()['search_session']['id'] == 'ss_test123'

    def test_create_missing_required_returns_422(self, test_client, mock_service):
        response = test_client.post(BASE_URL, json={})
        assert response.status_code == 422


class TestUpdateSearchSessionEndpoint:
    def test_update_success(self, test_client, mock_service, mock_search_session_schema):
        mock_service.update_entity.return_value = mock_search_session_schema
        response = test_client.patch(
            f'{BASE_URL}/ss_test123',
            json={'turn_count': 5},
        )
        assert response.status_code == 200
        assert response.json()['search_session']['id'] == 'ss_test123'

    def test_update_not_found(self, test_client, mock_service):
        mock_service.update_entity.side_effect = ValueError('not found')
        response = test_client.patch(
            f'{BASE_URL}/nonexistent',
            json={'turn_count': 5},
        )
        assert response.status_code == 404


class TestDeleteSearchSessionEndpoint:
    def test_delete_success(self, test_client, mock_service):
        mock_service.delete_entity_by_id.return_value = None
        response = test_client.delete(f'{BASE_URL}/ss_test123')
        assert response.status_code == 204

    def test_delete_not_found(self, test_client, mock_service):
        mock_service.delete_entity_by_id.side_effect = ValueError('not found')
        response = test_client.delete(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


class TestBulkCreateSearchSessionsEndpoint:
    def test_bulk_create_success(self, test_client, mock_service, mock_search_session_schema):
        mock_service.create_entities_bulk.return_value = [mock_search_session_schema]
        response = test_client.post(
            f'{BASE_URL}/bulk',
            json={
                'search_sessions': [
                    {'app_user_id': 'au_1', 'initial_query': 'query 1'},
                    {'app_user_id': 'au_1', 'initial_query': 'query 2'},
                ]
            },
        )
        assert response.status_code == 201
        assert len(response.json()['search_sessions']) == 1
