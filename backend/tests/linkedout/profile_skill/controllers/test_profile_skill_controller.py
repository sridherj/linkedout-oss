# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for ProfileSkill controller endpoints."""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec
from fastapi.testclient import TestClient

from main import app
from linkedout.profile_skill.controllers.profile_skill_controller import (
    _get_profile_skill_service,
    _get_write_profile_skill_service,
)
from linkedout.profile_skill.services.profile_skill_service import ProfileSkillService
from linkedout.profile_skill.schemas.profile_skill_schema import ProfileSkillSchema


BASE_URL = '/profile-skills'


@pytest.fixture
def mock_schema():
    return ProfileSkillSchema(
        id='psk_test123',
        crawled_profile_id='cp_test123',
        skill_name='Python',
        endorsement_count=5,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_service():
    return create_autospec(ProfileSkillService, instance=True, spec_set=True)


@pytest.fixture
def test_client(mock_service):
    def _override():
        yield mock_service

    app.dependency_overrides[_get_profile_skill_service] = _override
    app.dependency_overrides[_get_write_profile_skill_service] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestListProfileSkillsEndpoint:
    def test_list_success(self, test_client, mock_service, mock_schema):
        mock_service.list_profile_skills.return_value = ([mock_schema], 1)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
        assert len(data['profile_skills']) == 1

    def test_list_empty(self, test_client, mock_service):
        mock_service.list_profile_skills.return_value = ([], 0)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        assert response.json()['total'] == 0


class TestGetProfileSkillByIdEndpoint:
    def test_get_success(self, test_client, mock_service, mock_schema):
        mock_service.get_profile_skill_by_id.return_value = mock_schema
        response = test_client.get(f'{BASE_URL}/psk_test123')
        assert response.status_code == 200

    def test_get_not_found(self, test_client, mock_service):
        mock_service.get_profile_skill_by_id.return_value = None
        response = test_client.get(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


class TestCreateProfileSkillEndpoint:
    def test_create_success(self, test_client, mock_service, mock_schema):
        mock_service.create_profile_skill.return_value = mock_schema
        response = test_client.post(
            BASE_URL,
            json={'crawled_profile_id': 'cp_test123', 'skill_name': 'Python'},
        )
        assert response.status_code == 201

    def test_create_missing_required_returns_422(self, test_client, mock_service):
        response = test_client.post(BASE_URL, json={})
        assert response.status_code == 422


class TestUpdateProfileSkillEndpoint:
    def test_update_success(self, test_client, mock_service, mock_schema):
        mock_service.update_profile_skill.return_value = mock_schema
        response = test_client.patch(
            f'{BASE_URL}/psk_test123', json={'endorsement_count': 10}
        )
        assert response.status_code == 200

    def test_update_not_found(self, test_client, mock_service):
        mock_service.update_profile_skill.side_effect = ValueError('not found')
        response = test_client.patch(
            f'{BASE_URL}/nonexistent', json={'endorsement_count': 10}
        )
        assert response.status_code == 404


class TestDeleteProfileSkillEndpoint:
    def test_delete_success(self, test_client, mock_service):
        mock_service.delete_profile_skill_by_id.return_value = None
        response = test_client.delete(f'{BASE_URL}/psk_test123')
        assert response.status_code == 204

    def test_delete_not_found(self, test_client, mock_service):
        mock_service.delete_profile_skill_by_id.side_effect = ValueError('not found')
        response = test_client.delete(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


class TestBulkCreateProfileSkillsEndpoint:
    def test_bulk_create_success(self, test_client, mock_service, mock_schema):
        mock_service.create_profile_skills.return_value = [mock_schema]
        response = test_client.post(
            f'{BASE_URL}/bulk',
            json={
                'profile_skills': [
                    {'crawled_profile_id': 'cp_test123', 'skill_name': 'Python'},
                    {'crawled_profile_id': 'cp_test123', 'skill_name': 'Java'},
                ]
            },
        )
        assert response.status_code == 201
