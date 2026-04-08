# SPDX-License-Identifier: Apache-2.0
"""Integration tests for Company API endpoints."""

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


class TestCompanyControllerIntegration:

    def test_list_companies_empty(self, test_client: TestClient):
        response = test_client.get('/companies')
        assert response.status_code == 200
        data = response.json()
        assert 'companies' in data

    def test_create_company_success(self, test_client: TestClient):
        payload = {'canonical_name': 'Test Integration Corp', 'normalized_name': 'test integration corp'}
        response = test_client.post('/companies', json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data['company']['canonical_name'] == 'Test Integration Corp'
        assert data['company']['network_connection_count'] == 0

    def test_get_company_by_id_returns_company(self, test_client: TestClient):
        create_resp = test_client.post('/companies', json={'canonical_name': 'Get Corp', 'normalized_name': 'get corp'})
        company_id = create_resp.json()['company']['id']

        response = test_client.get(f'/companies/{company_id}')
        assert response.status_code == 200
        data = response.json()
        assert data['company']['id'] == company_id

    def test_update_company_success(self, test_client: TestClient):
        create_resp = test_client.post('/companies', json={'canonical_name': 'Upd Corp', 'normalized_name': 'upd corp'})
        company_id = create_resp.json()['company']['id']

        response = test_client.patch(f'/companies/{company_id}', json={'industry': 'Tech'})

        assert response.status_code == 200
        data = response.json()
        assert data['company']['industry'] == 'Tech'

    def test_delete_company_success(self, test_client: TestClient):
        create_resp = test_client.post('/companies', json={'canonical_name': 'Del Corp', 'normalized_name': 'del corp'})
        company_id = create_resp.json()['company']['id']

        response = test_client.delete(f'/companies/{company_id}')
        assert response.status_code == 204
