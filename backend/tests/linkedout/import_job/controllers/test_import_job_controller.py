# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for ImportJob controller endpoints."""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec
from fastapi.testclient import TestClient

from main import app
from linkedout.import_job.controllers.import_job_controller import (
    _get_import_job_service,
    _get_write_import_job_service,
)
from linkedout.import_job.services.import_job_service import ImportJobService
from linkedout.import_job.schemas.import_job_schema import ImportJobSchema


BASE_URL = '/tenants/t_1/bus/bu_1/import-jobs'


@pytest.fixture
def mock_import_job_schema():
    return ImportJobSchema(
        id='ij_test123',
        tenant_id='t_1',
        bu_id='bu_1',
        app_user_id='au_1',
        source_type='linkedin_csv',
        status='pending',
        total_records=0,
        parsed_count=0,
        matched_count=0,
        new_count=0,
        failed_count=0,
        enrichment_queued=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_service():
    return create_autospec(ImportJobService, instance=True, spec_set=True)


@pytest.fixture
def test_client(mock_service):
    def _override():
        yield mock_service

    app.dependency_overrides[_get_import_job_service] = _override
    app.dependency_overrides[_get_write_import_job_service] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestListImportJobsEndpoint:
    def test_list_success(self, test_client, mock_service, mock_import_job_schema):
        mock_service.list_entities.return_value = ([mock_import_job_schema], 1)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
        assert len(data['import_jobs']) == 1
        assert data['import_jobs'][0]['id'] == 'ij_test123'

    def test_list_empty(self, test_client, mock_service):
        mock_service.list_entities.return_value = ([], 0)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        assert response.json()['total'] == 0
        assert response.json()['import_jobs'] == []


class TestGetImportJobByIdEndpoint:
    def test_get_success(self, test_client, mock_service, mock_import_job_schema):
        mock_service.get_entity_by_id.return_value = mock_import_job_schema
        response = test_client.get(f'{BASE_URL}/ij_test123')
        assert response.status_code == 200
        assert response.json()['import_job']['id'] == 'ij_test123'

    def test_get_not_found(self, test_client, mock_service):
        mock_service.get_entity_by_id.return_value = None
        response = test_client.get(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


class TestCreateImportJobEndpoint:
    def test_create_success(self, test_client, mock_service, mock_import_job_schema):
        mock_service.create_entity.return_value = mock_import_job_schema
        response = test_client.post(
            BASE_URL,
            json={'app_user_id': 'au_1', 'source_type': 'linkedin_csv'},
        )
        assert response.status_code == 201
        assert response.json()['import_job']['id'] == 'ij_test123'

    def test_create_missing_required_returns_422(self, test_client, mock_service):
        response = test_client.post(BASE_URL, json={})
        assert response.status_code == 422


class TestUpdateImportJobEndpoint:
    def test_update_success(self, test_client, mock_service, mock_import_job_schema):
        mock_service.update_entity.return_value = mock_import_job_schema
        response = test_client.patch(
            f'{BASE_URL}/ij_test123',
            json={'status': 'parsing'},
        )
        assert response.status_code == 200
        assert response.json()['import_job']['id'] == 'ij_test123'

    def test_update_not_found(self, test_client, mock_service):
        mock_service.update_entity.side_effect = ValueError('not found')
        response = test_client.patch(
            f'{BASE_URL}/nonexistent',
            json={'status': 'parsing'},
        )
        assert response.status_code == 404


class TestDeleteImportJobEndpoint:
    def test_delete_success(self, test_client, mock_service):
        mock_service.delete_entity_by_id.return_value = None
        response = test_client.delete(f'{BASE_URL}/ij_test123')
        assert response.status_code == 204

    def test_delete_not_found(self, test_client, mock_service):
        mock_service.delete_entity_by_id.side_effect = ValueError('not found')
        response = test_client.delete(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


class TestBulkCreateImportJobsEndpoint:
    def test_bulk_create_success(self, test_client, mock_service, mock_import_job_schema):
        mock_service.create_entities_bulk.return_value = [mock_import_job_schema]
        response = test_client.post(
            f'{BASE_URL}/bulk',
            json={
                'import_jobs': [
                    {'app_user_id': 'au_1', 'source_type': 'linkedin_csv'},
                    {'app_user_id': 'au_1', 'source_type': 'google_contacts'},
                ]
            },
        )
        assert response.status_code == 201
        assert len(response.json()['import_jobs']) == 1
