# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for SearchTag API endpoints (CRUDRouterFactory pattern)."""
import pytest
from datetime import datetime, timezone
from typing import Generator
from unittest.mock import Mock, create_autospec
from fastapi.testclient import TestClient

from main import app
from linkedout.search_tag.services.search_tag_service import SearchTagService
from linkedout.search_tag.schemas.search_tag_schema import SearchTagSchema
from linkedout.search_tag.controllers.search_tag_controller import (
    _get_search_tag_service,
    _get_write_search_tag_service,
)


BASE_URL = '/tenants/t_1/bus/bu_1/search-tags'


@pytest.fixture
def mock_search_tag_schema() -> SearchTagSchema:
    return SearchTagSchema(
        id='stag_test123',
        tenant_id='t_1',
        bu_id='bu_1',
        app_user_id='au_1',
        session_id='ss_1',
        crawled_profile_id='cp_1',
        tag_name='engineering',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_service() -> Mock:
    return create_autospec(SearchTagService, instance=True, spec_set=True)


@pytest.fixture
def override_dependencies(mock_service: Mock) -> Generator[None, None, None]:
    def _get_mock_service():
        yield mock_service

    app.dependency_overrides[_get_search_tag_service] = _get_mock_service
    app.dependency_overrides[_get_write_search_tag_service] = _get_mock_service
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def test_client(override_dependencies: None) -> TestClient:
    return TestClient(app)


class TestListSearchTagsEndpointWiring:
    def test_list_endpoint_exists_and_responds(
        self, test_client, mock_service, mock_search_tag_schema,
    ):
        mock_service.list_entities.return_value = ([mock_search_tag_schema], 1)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        data = response.json()
        assert 'search_tags' in data
        assert 'total' in data
        assert data['total'] == 1

    def test_list_endpoint_calls_service(self, test_client, mock_service):
        mock_service.list_entities.return_value = ([], 0)
        test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        mock_service.list_entities.assert_called_once()

    def test_list_empty(self, test_client, mock_service):
        mock_service.list_entities.return_value = ([], 0)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        assert response.json()['total'] == 0
        assert response.json()['search_tags'] == []


class TestGetSearchTagByIdEndpointWiring:
    def test_get_success(self, test_client, mock_service, mock_search_tag_schema):
        mock_service.get_entity_by_id.return_value = mock_search_tag_schema
        response = test_client.get(f'{BASE_URL}/stag_test123')
        assert response.status_code == 200
        assert response.json()['search_tag']['id'] == 'stag_test123'

    def test_get_not_found(self, test_client, mock_service):
        mock_service.get_entity_by_id.return_value = None
        response = test_client.get(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


class TestCreateSearchTagEndpointWiring:
    def test_create_success(self, test_client, mock_service, mock_search_tag_schema):
        mock_service.create_entity.return_value = mock_search_tag_schema
        response = test_client.post(
            BASE_URL,
            json={
                'app_user_id': 'au_1',
                'session_id': 'ss_1',
                'crawled_profile_id': 'cp_1',
                'tag_name': 'engineering',
            },
        )
        assert response.status_code == 201
        assert response.json()['search_tag']['id'] == 'stag_test123'

    def test_create_missing_required_returns_422(self, test_client, mock_service):
        response = test_client.post(BASE_URL, json={})
        assert response.status_code == 422
        mock_service.create_entity.assert_not_called()


class TestUpdateSearchTagEndpointWiring:
    def test_update_success(self, test_client, mock_service, mock_search_tag_schema):
        mock_service.update_entity.return_value = mock_search_tag_schema
        response = test_client.patch(
            f'{BASE_URL}/stag_test123',
            json={'tag_name': 'design'},
        )
        assert response.status_code == 200
        assert response.json()['search_tag']['id'] == 'stag_test123'

    def test_update_not_found(self, test_client, mock_service):
        mock_service.update_entity.side_effect = ValueError('not found')
        response = test_client.patch(
            f'{BASE_URL}/nonexistent',
            json={'tag_name': 'design'},
        )
        assert response.status_code == 404


class TestDeleteSearchTagEndpointWiring:
    def test_delete_success(self, test_client, mock_service):
        mock_service.delete_entity_by_id.return_value = None
        response = test_client.delete(f'{BASE_URL}/stag_test123')
        assert response.status_code == 204

    def test_delete_not_found(self, test_client, mock_service):
        mock_service.delete_entity_by_id.side_effect = ValueError('not found')
        response = test_client.delete(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


class TestBulkCreateSearchTagsEndpointWiring:
    def test_bulk_create_success(self, test_client, mock_service, mock_search_tag_schema):
        mock_service.create_entities_bulk.return_value = [mock_search_tag_schema]
        response = test_client.post(
            f'{BASE_URL}/bulk',
            json={
                'search_tags': [
                    {
                        'app_user_id': 'au_1',
                        'session_id': 'ss_1',
                        'crawled_profile_id': 'cp_1',
                        'tag_name': 'engineering',
                    },
                    {
                        'app_user_id': 'au_1',
                        'session_id': 'ss_1',
                        'crawled_profile_id': 'cp_2',
                        'tag_name': 'design',
                    },
                ]
            },
        )
        assert response.status_code == 201
        assert 'search_tags' in response.json()
