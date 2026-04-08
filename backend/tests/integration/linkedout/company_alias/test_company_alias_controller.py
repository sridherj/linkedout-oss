# SPDX-License-Identifier: Apache-2.0
"""Integration tests for CompanyAlias API endpoints."""

import pytest
import uuid
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


class TestCompanyAliasControllerIntegration:
    @pytest.fixture
    def company_id(self, test_client: TestClient) -> str:
        # Create a company first to satisfy foreign key constraint
        suffix = uuid.uuid4().hex[:8]
        payload = {'canonical_name': f'Alias Target Corp {suffix}', 'normalized_name': f'alias target corp {suffix}'}
        resp = test_client.post('/companies', json=payload)
        return resp.json()['company']['id']

    def test_list_company_aliases_empty(self, test_client: TestClient):
        response = test_client.get('/company-aliases')
        assert response.status_code == 200
        data = response.json()
        assert 'company_aliases' in data

    def test_create_company_alias_success(self, test_client: TestClient, company_id: str):
        payload = {
            'alias_name': 'Old Target Name',
            'company_id': company_id,
            'source': 'manual'
        }
        response = test_client.post('/company-aliases', json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data['company_alias']['alias_name'] == 'Old Target Name'
        assert data['company_alias']['company_id'] == company_id

    def test_get_company_alias_by_id(self, test_client: TestClient, company_id: str):
        create_resp = test_client.post('/company-aliases', json={
            'alias_name': 'Get Test Alias',
            'company_id': company_id
        })
        alias_id = create_resp.json()['company_alias']['id']

        response = test_client.get(f'/company-aliases/{alias_id}')
        assert response.status_code == 200
        data = response.json()
        assert data['company_alias']['id'] == alias_id

    def test_update_company_alias(self, test_client: TestClient, company_id: str):
        create_resp = test_client.post('/company-aliases', json={
            'alias_name': 'Update Me',
            'company_id': company_id
        })
        alias_id = create_resp.json()['company_alias']['id']

        response = test_client.patch(f'/company-aliases/{alias_id}', json={'source': 'API'})

        assert response.status_code == 200
        data = response.json()
        assert data['company_alias']['source'] == 'API'

    def test_delete_company_alias(self, test_client: TestClient, company_id: str):
        create_resp = test_client.post('/company-aliases', json={
            'alias_name': 'Delete Me',
            'company_id': company_id
        })
        alias_id = create_resp.json()['company_alias']['id']

        response = test_client.delete(f'/company-aliases/{alias_id}')
        assert response.status_code == 204
