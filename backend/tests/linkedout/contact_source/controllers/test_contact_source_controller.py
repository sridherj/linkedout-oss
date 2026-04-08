# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for ContactSource controller endpoints."""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec
from fastapi.testclient import TestClient

from main import app
from linkedout.contact_source.controllers.contact_source_controller import (
    _get_contact_source_service,
    _get_write_contact_source_service,
)
from linkedout.contact_source.services.contact_source_service import ContactSourceService
from linkedout.contact_source.schemas.contact_source_schema import ContactSourceSchema


BASE_URL = '/tenants/t_1/bus/bu_1/contact-sources'


@pytest.fixture
def mock_contact_source_schema():
    return ContactSourceSchema(
        id='cs_test123',
        tenant_id='t_1',
        bu_id='bu_1',
        app_user_id='au_1',
        import_job_id='ij_1',
        source_type='linkedin_csv',
        first_name='John',
        last_name='Doe',
        full_name='John Doe',
        email='john@example.com',
        company='Acme Inc',
        title='Engineer',
        dedup_status='pending',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_service():
    return create_autospec(ContactSourceService, instance=True, spec_set=True)


@pytest.fixture
def test_client(mock_service):
    def _override():
        yield mock_service

    app.dependency_overrides[_get_contact_source_service] = _override
    app.dependency_overrides[_get_write_contact_source_service] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestListContactSourcesEndpoint:
    def test_list_success(self, test_client, mock_service, mock_contact_source_schema):
        mock_service.list_entities.return_value = ([mock_contact_source_schema], 1)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
        assert len(data['contact_sources']) == 1
        assert data['contact_sources'][0]['id'] == 'cs_test123'

    def test_list_empty(self, test_client, mock_service):
        mock_service.list_entities.return_value = ([], 0)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        assert response.json()['total'] == 0
        assert response.json()['contact_sources'] == []


class TestGetContactSourceByIdEndpoint:
    def test_get_success(self, test_client, mock_service, mock_contact_source_schema):
        mock_service.get_entity_by_id.return_value = mock_contact_source_schema
        response = test_client.get(f'{BASE_URL}/cs_test123')
        assert response.status_code == 200
        assert response.json()['contact_source']['id'] == 'cs_test123'

    def test_get_not_found(self, test_client, mock_service):
        mock_service.get_entity_by_id.return_value = None
        response = test_client.get(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


class TestCreateContactSourceEndpoint:
    def test_create_success(self, test_client, mock_service, mock_contact_source_schema):
        mock_service.create_entity.return_value = mock_contact_source_schema
        response = test_client.post(
            BASE_URL,
            json={
                'app_user_id': 'au_1',
                'import_job_id': 'ij_1',
                'source_type': 'linkedin_csv',
            },
        )
        assert response.status_code == 201
        assert response.json()['contact_source']['id'] == 'cs_test123'

    def test_create_missing_required_returns_422(self, test_client, mock_service):
        response = test_client.post(BASE_URL, json={})
        assert response.status_code == 422


class TestUpdateContactSourceEndpoint:
    def test_update_success(self, test_client, mock_service, mock_contact_source_schema):
        mock_service.update_entity.return_value = mock_contact_source_schema
        response = test_client.patch(
            f'{BASE_URL}/cs_test123',
            json={'dedup_status': 'matched'},
        )
        assert response.status_code == 200
        assert response.json()['contact_source']['id'] == 'cs_test123'

    def test_update_not_found(self, test_client, mock_service):
        mock_service.update_entity.side_effect = ValueError('not found')
        response = test_client.patch(
            f'{BASE_URL}/nonexistent',
            json={'dedup_status': 'matched'},
        )
        assert response.status_code == 404


class TestDeleteContactSourceEndpoint:
    def test_delete_success(self, test_client, mock_service):
        mock_service.delete_entity_by_id.return_value = None
        response = test_client.delete(f'{BASE_URL}/cs_test123')
        assert response.status_code == 204

    def test_delete_not_found(self, test_client, mock_service):
        mock_service.delete_entity_by_id.side_effect = ValueError('not found')
        response = test_client.delete(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


class TestBulkCreateContactSourcesEndpoint:
    def test_bulk_create_success(self, test_client, mock_service, mock_contact_source_schema):
        mock_service.create_entities_bulk.return_value = [mock_contact_source_schema]
        response = test_client.post(
            f'{BASE_URL}/bulk',
            json={
                'contact_sources': [
                    {'app_user_id': 'au_1', 'import_job_id': 'ij_1', 'source_type': 'linkedin_csv'},
                    {'app_user_id': 'au_1', 'import_job_id': 'ij_1', 'source_type': 'google_contacts'},
                ]
            },
        )
        assert response.status_code == 201
        assert len(response.json()['contact_sources']) == 1
