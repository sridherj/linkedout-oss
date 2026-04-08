# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for FundingRound controller endpoints."""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec
from fastapi.testclient import TestClient

from main import app
from linkedout.funding.controllers.funding_round_controller import (
    _get_service,
    _get_write_service,
)
from linkedout.funding.services.funding_round_service import FundingRoundService
from linkedout.funding.schemas.funding_round_schema import FundingRoundSchema


BASE_URL = '/funding-rounds'


@pytest.fixture
def mock_schema():
    return FundingRoundSchema(
        id='fr_test123',
        company_id='co_test123',
        round_type='Seed',
        confidence=8,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_service():
    return create_autospec(FundingRoundService, instance=True, spec_set=True)


@pytest.fixture
def test_client(mock_service):
    def _override():
        yield mock_service

    app.dependency_overrides[_get_service] = _override
    app.dependency_overrides[_get_write_service] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestListFundingRoundsEndpoint:
    def test_list_success(self, test_client, mock_service, mock_schema):
        mock_service.list_funding_rounds.return_value = ([mock_schema], 1)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == 1
        assert len(data['funding_rounds']) == 1

    def test_list_empty(self, test_client, mock_service):
        mock_service.list_funding_rounds.return_value = ([], 0)
        response = test_client.get(BASE_URL, params={'limit': 20, 'offset': 0})
        assert response.status_code == 200
        assert response.json()['total'] == 0


class TestGetFundingRoundByIdEndpoint:
    def test_get_success(self, test_client, mock_service, mock_schema):
        mock_service.get_funding_round_by_id.return_value = mock_schema
        response = test_client.get(f'{BASE_URL}/fr_test123')
        assert response.status_code == 200
        assert response.json()['funding_round']['id'] == 'fr_test123'

    def test_get_not_found(self, test_client, mock_service):
        mock_service.get_funding_round_by_id.return_value = None
        response = test_client.get(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404


class TestCreateFundingRoundEndpoint:
    def test_create_success(self, test_client, mock_service, mock_schema):
        mock_service.create_funding_round.return_value = mock_schema
        response = test_client.post(
            BASE_URL,
            json={'company_id': 'co_test123', 'round_type': 'Seed'},
        )
        assert response.status_code == 201
        assert response.json()['funding_round']['id'] == 'fr_test123'

    def test_create_missing_required_returns_422(self, test_client, mock_service):
        response = test_client.post(BASE_URL, json={})
        assert response.status_code == 422


class TestUpdateFundingRoundEndpoint:
    def test_update_success(self, test_client, mock_service, mock_schema):
        mock_service.update_funding_round.return_value = mock_schema
        response = test_client.patch(
            f'{BASE_URL}/fr_test123', json={'confidence': 9}
        )
        assert response.status_code == 200

    def test_update_not_found(self, test_client, mock_service):
        mock_service.update_funding_round.side_effect = ValueError('not found')
        response = test_client.patch(
            f'{BASE_URL}/nonexistent', json={'confidence': 9}
        )
        assert response.status_code == 404


class TestDeleteFundingRoundEndpoint:
    def test_delete_success(self, test_client, mock_service):
        mock_service.delete_funding_round_by_id.return_value = None
        response = test_client.delete(f'{BASE_URL}/fr_test123')
        assert response.status_code == 204

    def test_delete_not_found(self, test_client, mock_service):
        mock_service.delete_funding_round_by_id.side_effect = ValueError('not found')
        response = test_client.delete(f'{BASE_URL}/nonexistent')
        assert response.status_code == 404
