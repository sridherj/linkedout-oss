# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for Education controller endpoints."""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec
from fastapi.testclient import TestClient

from main import app
from linkedout.education.controllers.education_controller import (
    _get_education_service,
    _get_write_education_service,
)
from linkedout.education.services.education_service import EducationService
from linkedout.education.schemas.education_schema import EducationSchema


BASE_URL = '/educations'


@pytest.fixture
def mock_education_schema():
    return EducationSchema(
        id='edu_test123',
        crawled_profile_id='cp_test123',
        school_name='MIT',
        degree='BS',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_service():
    return create_autospec(EducationService, instance=True, spec_set=True)


@pytest.fixture
def test_client(mock_service):
    """Create a TestClient with mock service injected via dependency_overrides."""
    def _override():
        yield mock_service

    app.dependency_overrides[_get_education_service] = _override
    app.dependency_overrides[_get_write_education_service] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestListEducationsEndpoint:
    def test_list_success(self, test_client, mock_service, mock_education_schema):
        mock_service.list_educations.return_value = ([mock_education_schema], 1)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
        assert len(data['educations']) == 1
        assert data['educations'][0]['id'] == 'edu_test123'

    def test_list_empty(self, test_client, mock_service):
        mock_service.list_educations.return_value = ([], 0)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        assert response.json()['total'] == 0
        assert response.json()['educations'] == []

    def test_list_with_filters(self, test_client, mock_service, mock_education_schema):
        mock_service.list_educations.return_value = ([mock_education_schema], 1)
        response = test_client.get(
            BASE_URL,
            params={'limit': 20, 'offset': 0, 'crawled_profile_id': 'cp_test123'},
        )
        assert response.status_code == 200
        mock_service.list_educations.assert_called_once()


class TestGetEducationByIdEndpoint:
    def test_get_success(self, test_client, mock_service, mock_education_schema):
        mock_service.get_education_by_id.return_value = mock_education_schema
        response = test_client.get(f'{BASE_URL}/edu_test123')
        assert response.status_code == 200
        assert response.json()['education']['id'] == 'edu_test123'

    def test_get_not_found(self, test_client, mock_service):
        mock_service.get_education_by_id.return_value = None
        response = test_client.get(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


class TestCreateEducationEndpoint:
    def test_create_success(self, test_client, mock_service, mock_education_schema):
        mock_service.create_education.return_value = mock_education_schema
        response = test_client.post(
            BASE_URL,
            json={'crawled_profile_id': 'cp_test123', 'school_name': 'MIT'},
        )
        assert response.status_code == 201
        assert response.json()['education']['id'] == 'edu_test123'

    def test_create_missing_required_returns_422(self, test_client, mock_service):
        response = test_client.post(BASE_URL, json={})
        assert response.status_code == 422


class TestUpdateEducationEndpoint:
    def test_update_success(self, test_client, mock_service, mock_education_schema):
        mock_service.update_education.return_value = mock_education_schema
        response = test_client.patch(
            f'{BASE_URL}/edu_test123', json={'degree': 'MS'}
        )
        assert response.status_code == 200
        assert response.json()['education']['id'] == 'edu_test123'

    def test_update_not_found(self, test_client, mock_service):
        mock_service.update_education.side_effect = ValueError('not found')
        response = test_client.patch(
            f'{BASE_URL}/nonexistent', json={'degree': 'MS'}
        )
        assert response.status_code == 404


class TestDeleteEducationEndpoint:
    def test_delete_success(self, test_client, mock_service):
        mock_service.delete_education_by_id.return_value = None
        response = test_client.delete(f'{BASE_URL}/edu_test123')
        assert response.status_code == 204

    def test_delete_not_found(self, test_client, mock_service):
        mock_service.delete_education_by_id.side_effect = ValueError('not found')
        response = test_client.delete(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


class TestBulkCreateEducationsEndpoint:
    def test_bulk_create_success(self, test_client, mock_service, mock_education_schema):
        mock_service.create_educations.return_value = [mock_education_schema]
        response = test_client.post(
            f'{BASE_URL}/bulk',
            json={
                'educations': [
                    {'crawled_profile_id': 'cp_test123', 'school_name': 'MIT'},
                    {'crawled_profile_id': 'cp_test123', 'school_name': 'Stanford'},
                ]
            },
        )
        assert response.status_code == 201
        assert len(response.json()['educations']) == 1
