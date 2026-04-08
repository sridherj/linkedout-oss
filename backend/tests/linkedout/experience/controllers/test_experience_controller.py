# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for Experience controller endpoints."""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec
from fastapi.testclient import TestClient

from main import app
from linkedout.experience.controllers.experience_controller import (
    _get_experience_service,
    _get_write_experience_service,
)
from linkedout.experience.services.experience_service import ExperienceService
from linkedout.experience.schemas.experience_schema import ExperienceSchema


BASE_URL = '/experiences'


@pytest.fixture
def mock_experience_schema():
    return ExperienceSchema(
        id='exp_test123',
        crawled_profile_id='cp_test123',
        position='Software Engineer',
        company_name='Acme Corp',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_service():
    return create_autospec(ExperienceService, instance=True, spec_set=True)


@pytest.fixture
def test_client(mock_service):
    """Create a TestClient with mock service injected via dependency_overrides."""
    def _override():
        yield mock_service

    app.dependency_overrides[_get_experience_service] = _override
    app.dependency_overrides[_get_write_experience_service] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestListExperiencesEndpoint:
    def test_list_success(self, test_client, mock_service, mock_experience_schema):
        mock_service.list_experiences.return_value = ([mock_experience_schema], 1)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
        assert len(data['experiences']) == 1
        assert data['experiences'][0]['id'] == 'exp_test123'

    def test_list_empty(self, test_client, mock_service):
        mock_service.list_experiences.return_value = ([], 0)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        assert response.json()['total'] == 0
        assert response.json()['experiences'] == []

    def test_list_with_filters(self, test_client, mock_service, mock_experience_schema):
        mock_service.list_experiences.return_value = ([mock_experience_schema], 1)
        response = test_client.get(
            BASE_URL,
            params={'limit': 20, 'offset': 0, 'crawled_profile_id': 'cp_test123'},
        )
        assert response.status_code == 200
        mock_service.list_experiences.assert_called_once()


class TestGetExperienceByIdEndpoint:
    def test_get_success(self, test_client, mock_service, mock_experience_schema):
        mock_service.get_experience_by_id.return_value = mock_experience_schema
        response = test_client.get(f'{BASE_URL}/exp_test123')
        assert response.status_code == 200
        assert response.json()['experience']['id'] == 'exp_test123'

    def test_get_not_found(self, test_client, mock_service):
        mock_service.get_experience_by_id.return_value = None
        response = test_client.get(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


class TestCreateExperienceEndpoint:
    def test_create_success(self, test_client, mock_service, mock_experience_schema):
        mock_service.create_experience.return_value = mock_experience_schema
        response = test_client.post(
            BASE_URL,
            json={'crawled_profile_id': 'cp_test123', 'position': 'Software Engineer'},
        )
        assert response.status_code == 201
        assert response.json()['experience']['id'] == 'exp_test123'

    def test_create_missing_required_returns_422(self, test_client, mock_service):
        response = test_client.post(BASE_URL, json={})
        assert response.status_code == 422


class TestUpdateExperienceEndpoint:
    def test_update_success(self, test_client, mock_service, mock_experience_schema):
        mock_service.update_experience.return_value = mock_experience_schema
        response = test_client.patch(
            f'{BASE_URL}/exp_test123', json={'position': 'Senior Engineer'}
        )
        assert response.status_code == 200
        assert response.json()['experience']['id'] == 'exp_test123'

    def test_update_not_found(self, test_client, mock_service):
        mock_service.update_experience.side_effect = ValueError('not found')
        response = test_client.patch(
            f'{BASE_URL}/nonexistent', json={'position': 'Senior Engineer'}
        )
        assert response.status_code == 404


class TestDeleteExperienceEndpoint:
    def test_delete_success(self, test_client, mock_service):
        mock_service.delete_experience_by_id.return_value = None
        response = test_client.delete(f'{BASE_URL}/exp_test123')
        assert response.status_code == 204

    def test_delete_not_found(self, test_client, mock_service):
        mock_service.delete_experience_by_id.side_effect = ValueError('not found')
        response = test_client.delete(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


class TestBulkCreateExperiencesEndpoint:
    def test_bulk_create_success(self, test_client, mock_service, mock_experience_schema):
        mock_service.create_experiences.return_value = [mock_experience_schema]
        response = test_client.post(
            f'{BASE_URL}/bulk',
            json={
                'experiences': [
                    {'crawled_profile_id': 'cp_test123', 'position': 'Software Engineer'},
                    {'crawled_profile_id': 'cp_test123', 'position': 'Product Manager'},
                ]
            },
        )
        assert response.status_code == 201
        assert len(response.json()['experiences']) == 1
