# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for CrawledProfile controller endpoints.

CrawledProfile is a shared entity (no tenant/BU scoping).
Tests verify endpoints are reachable and return correct status codes.
"""
from datetime import datetime, timezone
from unittest.mock import create_autospec
from fastapi.testclient import TestClient

from main import app
from linkedout.crawled_profile.controllers.crawled_profile_controller import (
    _get_crawled_profile_service,
    _get_write_crawled_profile_service,
)
from linkedout.crawled_profile.services.crawled_profile_service import CrawledProfileService
from linkedout.crawled_profile.schemas.crawled_profile_schema import CrawledProfileSchema

import pytest


BASE_URL = '/crawled-profiles'


@pytest.fixture
def mock_crawled_profile_schema():
    return CrawledProfileSchema(
        id='cp_test123',
        linkedin_url='https://linkedin.com/in/johndoe',
        full_name='John Doe',
        data_source='apify',
        has_enriched_data=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_service():
    return create_autospec(CrawledProfileService, instance=True, spec_set=True)


@pytest.fixture
def test_client(mock_service):
    """Create a TestClient with mock service injected via dependency_overrides."""
    def _override():
        yield mock_service

    app.dependency_overrides[_get_crawled_profile_service] = _override
    app.dependency_overrides[_get_write_crawled_profile_service] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


# =============================================================================
# LIST ENDPOINT
# =============================================================================


class TestListCrawledProfilesEndpoint:
    def test_list_success(self, test_client, mock_service, mock_crawled_profile_schema):
        mock_service.list_crawled_profiles.return_value = ([mock_crawled_profile_schema], 1)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
        assert len(data['crawled_profiles']) == 1
        assert data['crawled_profiles'][0]['id'] == 'cp_test123'

    def test_list_empty(self, test_client, mock_service):
        mock_service.list_crawled_profiles.return_value = ([], 0)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        assert response.json()['total'] == 0
        assert response.json()['crawled_profiles'] == []

    def test_list_with_filters(self, test_client, mock_service, mock_crawled_profile_schema):
        mock_service.list_crawled_profiles.return_value = ([mock_crawled_profile_schema], 1)
        response = test_client.get(
            BASE_URL,
            params={'limit': 20, 'offset': 0, 'data_source': 'apify'},
        )
        assert response.status_code == 200
        mock_service.list_crawled_profiles.assert_called_once()


# =============================================================================
# GET BY ID ENDPOINT
# =============================================================================


class TestGetCrawledProfileByIdEndpoint:
    def test_get_success(self, test_client, mock_service, mock_crawled_profile_schema):
        mock_service.get_crawled_profile_by_id.return_value = mock_crawled_profile_schema
        response = test_client.get(f'{BASE_URL}/cp_test123')
        assert response.status_code == 200
        assert response.json()['crawled_profile']['id'] == 'cp_test123'

    def test_get_not_found(self, test_client, mock_service):
        mock_service.get_crawled_profile_by_id.return_value = None
        response = test_client.get(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


# =============================================================================
# CREATE ENDPOINT
# =============================================================================


class TestCreateCrawledProfileEndpoint:
    def test_create_success(self, test_client, mock_service, mock_crawled_profile_schema):
        mock_service.create_crawled_profile.return_value = mock_crawled_profile_schema
        response = test_client.post(
            BASE_URL,
            json={'linkedin_url': 'https://linkedin.com/in/johndoe', 'data_source': 'apify'},
        )
        assert response.status_code == 201
        assert response.json()['crawled_profile']['id'] == 'cp_test123'

    def test_create_missing_required_returns_422(self, test_client, mock_service):
        response = test_client.post(BASE_URL, json={})
        assert response.status_code == 422


# =============================================================================
# UPDATE ENDPOINT
# =============================================================================


class TestUpdateCrawledProfileEndpoint:
    def test_update_success(self, test_client, mock_service, mock_crawled_profile_schema):
        mock_service.update_crawled_profile.return_value = mock_crawled_profile_schema
        response = test_client.patch(
            f'{BASE_URL}/cp_test123', json={'seniority_level': 'Senior'}
        )
        assert response.status_code == 200
        assert response.json()['crawled_profile']['id'] == 'cp_test123'

    def test_update_not_found(self, test_client, mock_service):
        mock_service.update_crawled_profile.side_effect = ValueError('not found')
        response = test_client.patch(
            f'{BASE_URL}/nonexistent', json={'seniority_level': 'Senior'}
        )
        assert response.status_code == 404


# =============================================================================
# DELETE ENDPOINT
# =============================================================================


class TestDeleteCrawledProfileEndpoint:
    def test_delete_success(self, test_client, mock_service):
        mock_service.delete_crawled_profile_by_id.return_value = None
        response = test_client.delete(f'{BASE_URL}/cp_test123')
        assert response.status_code == 204

    def test_delete_not_found(self, test_client, mock_service):
        mock_service.delete_crawled_profile_by_id.side_effect = ValueError('not found')
        response = test_client.delete(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


# =============================================================================
# BULK CREATE ENDPOINT
# =============================================================================


class TestBulkCreateCrawledProfilesEndpoint:
    def test_bulk_create_success(self, test_client, mock_service, mock_crawled_profile_schema):
        mock_service.create_crawled_profiles.return_value = [mock_crawled_profile_schema]
        response = test_client.post(
            f'{BASE_URL}/bulk',
            json={
                'crawled_profiles': [
                    {'linkedin_url': 'https://linkedin.com/in/johndoe', 'data_source': 'apify'},
                    {'linkedin_url': 'https://linkedin.com/in/janedoe', 'data_source': 'netrows'},
                ]
            },
        )
        assert response.status_code == 201
        assert len(response.json()['crawled_profiles']) == 1
