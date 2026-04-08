# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for GrowthSignal controller endpoints."""
import pytest
from datetime import date, datetime, timezone
from unittest.mock import create_autospec
from fastapi.testclient import TestClient

from main import app
from linkedout.funding.controllers.growth_signal_controller import (
    _get_service,
    _get_write_service,
)
from linkedout.funding.services.growth_signal_service import GrowthSignalService
from linkedout.funding.schemas.growth_signal_schema import GrowthSignalSchema


BASE_URL = '/growth-signals'


@pytest.fixture
def mock_schema():
    return GrowthSignalSchema(
        id='gs_test123',
        company_id='co_test123',
        signal_type='arr',
        signal_date=date(2026, 1, 15),
        value_numeric=5000000,
        confidence=7,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_service():
    return create_autospec(GrowthSignalService, instance=True, spec_set=True)


@pytest.fixture
def test_client(mock_service):
    def _override():
        yield mock_service

    app.dependency_overrides[_get_service] = _override
    app.dependency_overrides[_get_write_service] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestListGrowthSignalsEndpoint:
    def test_list_success(self, test_client, mock_service, mock_schema):
        mock_service.list_growth_signals.return_value = ([mock_schema], 1)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
        assert len(data['growth_signals']) == 1

    def test_list_empty(self, test_client, mock_service):
        mock_service.list_growth_signals.return_value = ([], 0)
        response = test_client.get(BASE_URL)
        assert response.status_code == 200
        assert response.json()['total'] == 0


class TestGetGrowthSignalByIdEndpoint:
    def test_get_success(self, test_client, mock_service, mock_schema):
        mock_service.get_growth_signal_by_id.return_value = mock_schema
        response = test_client.get(f'{BASE_URL}/gs_test123')
        assert response.status_code == 200

    def test_get_not_found(self, test_client, mock_service):
        mock_service.get_growth_signal_by_id.return_value = None
        response = test_client.get(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


class TestCreateGrowthSignalEndpoint:
    def test_create_success(self, test_client, mock_service, mock_schema):
        mock_service.create_growth_signal.return_value = mock_schema
        response = test_client.post(
            BASE_URL,
            json={'company_id': 'co_test123', 'signal_type': 'arr', 'signal_date': '2026-01-15'},
        )
        assert response.status_code == 201

    def test_create_missing_required_returns_422(self, test_client, mock_service):
        response = test_client.post(BASE_URL, json={})
        assert response.status_code == 422


class TestDeleteGrowthSignalEndpoint:
    def test_delete_success(self, test_client, mock_service):
        mock_service.delete_growth_signal_by_id.return_value = None
        response = test_client.delete(f'{BASE_URL}/gs_test123')
        assert response.status_code == 204

    def test_delete_not_found(self, test_client, mock_service):
        mock_service.delete_growth_signal_by_id.side_effect = ValueError('not found')
        response = test_client.delete(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404
