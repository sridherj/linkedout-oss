# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for EnrichmentConfig controller endpoints."""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec
from fastapi.testclient import TestClient

from main import app
from organization.enrichment_config.controllers.enrichment_config_controller import (
    _get_service,
    _get_write_service,
)
from organization.enrichment_config.services.enrichment_config_service import EnrichmentConfigService
from organization.enrichment_config.schemas.enrichment_config_schema import EnrichmentConfigSchema


BASE_URL = '/enrichment-configs'


@pytest.fixture
def mock_schema():
    return EnrichmentConfigSchema(
        id='ec_test123',
        app_user_id='usr_test123',
        enrichment_mode='platform',
        apify_key_encrypted=None,
        apify_key_hint=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_service():
    return create_autospec(EnrichmentConfigService, instance=True, spec_set=True)


@pytest.fixture
def test_client(mock_service):
    def _override():
        yield mock_service

    app.dependency_overrides[_get_service] = _override
    app.dependency_overrides[_get_write_service] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestListEnrichmentConfigsEndpoint:
    def test_list_success(self, test_client, mock_service, mock_schema):
        mock_service.list_enrichment_configs.return_value = ([mock_schema], 1)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
        assert len(data['enrichment_configs']) == 1
        assert data['enrichment_configs'][0]['id'] == 'ec_test123'

    def test_list_empty(self, test_client, mock_service):
        mock_service.list_enrichment_configs.return_value = ([], 0)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        assert response.json()['total'] == 0
        assert response.json()['enrichment_configs'] == []


class TestGetEnrichmentConfigByIdEndpoint:
    def test_get_success(self, test_client, mock_service, mock_schema):
        mock_service.get_enrichment_config_by_id.return_value = mock_schema
        response = test_client.get(f'{BASE_URL}/ec_test123')
        assert response.status_code == 200
        assert response.json()['enrichment_config']['id'] == 'ec_test123'

    def test_get_not_found(self, test_client, mock_service):
        mock_service.get_enrichment_config_by_id.return_value = None
        response = test_client.get(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


class TestCreateEnrichmentConfigEndpoint:
    def test_create_success(self, test_client, mock_service, mock_schema):
        mock_service.create_enrichment_config.return_value = mock_schema
        response = test_client.post(
            BASE_URL,
            json={'app_user_id': 'usr_test123', 'enrichment_mode': 'platform'},
        )
        assert response.status_code == 201
        assert response.json()['enrichment_config']['id'] == 'ec_test123'

    def test_create_missing_required_returns_422(self, test_client, mock_service):
        response = test_client.post(BASE_URL, json={})
        assert response.status_code == 422


class TestUpdateEnrichmentConfigEndpoint:
    def test_update_success(self, test_client, mock_service, mock_schema):
        mock_service.update_enrichment_config.return_value = mock_schema
        response = test_client.patch(
            f'{BASE_URL}/ec_test123', json={'enrichment_mode': 'byok'}
        )
        assert response.status_code == 200
        assert response.json()['enrichment_config']['id'] == 'ec_test123'

    def test_update_not_found(self, test_client, mock_service):
        mock_service.update_enrichment_config.side_effect = ValueError('not found')
        response = test_client.patch(
            f'{BASE_URL}/nonexistent', json={'enrichment_mode': 'byok'}
        )
        assert response.status_code == 404


class TestDeleteEnrichmentConfigEndpoint:
    def test_delete_success(self, test_client, mock_service):
        mock_service.delete_enrichment_config_by_id.return_value = None
        response = test_client.delete(f'{BASE_URL}/ec_test123')
        assert response.status_code == 204

    def test_delete_not_found(self, test_client, mock_service):
        mock_service.delete_enrichment_config_by_id.side_effect = ValueError('not found')
        response = test_client.delete(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404
