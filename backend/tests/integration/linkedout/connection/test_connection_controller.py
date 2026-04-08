# SPDX-License-Identifier: Apache-2.0
"""Integration tests for Connection API endpoints.

Connection is scoped to Tenant and BU.
"""
import pytest
import uuid
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


class TestConnectionControllerIntegration:

    @pytest.fixture
    def app_user(self, seeded_data: dict):
        return seeded_data['app_user'][0].id

    @pytest.fixture
    def crawled_profile(self, test_client: TestClient, app_user: str):
        suffix = uuid.uuid4().hex[:8]
        resp = test_client.post('/crawled-profiles', json={
            'network_id': f'conn_test_profile_{suffix}',
            'name': 'Test Profile',
            'linkedin_url': f'https://linkedin.com/in/conn_test_{suffix}',
            'data_source': 'linkedin',
            'source_app_user_id': app_user
        }, headers={'X-App-User-Id': app_user})
        return resp.json()['crawled_profile']['id']

    def test_list_connections_empty(self, test_client: TestClient, test_tenant_id: str, test_bu_id: str, app_user: str):
        response = test_client.get(f'/tenants/{test_tenant_id}/bus/{test_bu_id}/connections', headers={'X-App-User-Id': app_user})
        assert response.status_code == 200
        assert 'connections' in response.json()

    def test_create_connection_success(self, test_client: TestClient, test_tenant_id: str, test_bu_id: str, app_user: str, crawled_profile: str):
        payload = {
            'app_user_id': app_user,
            'crawled_profile_id': crawled_profile,
            'dunbar_tier': 'active'
        }
        response = test_client.post(f'/tenants/{test_tenant_id}/bus/{test_bu_id}/connections', json=payload)
        
        assert response.status_code == 201
        data = response.json()
        assert data['connection']['app_user_id'] == app_user
        assert data['connection']['crawled_profile_id'] == crawled_profile
        assert data['connection']['dunbar_tier'] == 'active'

    def test_get_connection_by_id(self, test_client: TestClient, test_tenant_id: str, test_bu_id: str, app_user: str, crawled_profile: str):
        payload = {
            'app_user_id': app_user,
            'crawled_profile_id': crawled_profile,
            'dunbar_tier': 'active'
        }
        create_resp = test_client.post(f'/tenants/{test_tenant_id}/bus/{test_bu_id}/connections', json=payload)
        conn_id = create_resp.json()['connection']['id']

        response = test_client.get(f'/tenants/{test_tenant_id}/bus/{test_bu_id}/connections/{conn_id}', headers={'X-App-User-Id': app_user})
        assert response.status_code == 200
        data = response.json()
        assert data['connection']['id'] == conn_id

    def test_update_connection(self, test_client: TestClient, test_tenant_id: str, test_bu_id: str, app_user: str, crawled_profile: str):
        payload = {
            'app_user_id': app_user,
            'crawled_profile_id': crawled_profile,
            'dunbar_tier': 'active'
        }
        create_resp = test_client.post(f'/tenants/{test_tenant_id}/bus/{test_bu_id}/connections', json=payload)
        conn_id = create_resp.json()['connection']['id']

        response = test_client.patch(f'/tenants/{test_tenant_id}/bus/{test_bu_id}/connections/{conn_id}', json={
            'affinity_score': 85.5
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data['connection']['affinity_score'] == 85.5

    def test_duplicate_connection_rejected(self, test_client: TestClient, test_tenant_id: str, test_bu_id: str, app_user: str, crawled_profile: str):
        payload = {
            'app_user_id': app_user,
            'crawled_profile_id': crawled_profile,
        }
        first = test_client.post(f'/tenants/{test_tenant_id}/bus/{test_bu_id}/connections', json=payload)
        assert first.status_code == 201

        second = test_client.post(f'/tenants/{test_tenant_id}/bus/{test_bu_id}/connections', json=payload)
        assert second.status_code == 409

    def test_delete_connection(self, test_client: TestClient, test_tenant_id: str, test_bu_id: str, app_user: str, crawled_profile: str):
        payload = {
            'app_user_id': app_user,
            'crawled_profile_id': crawled_profile,
        }
        create_resp = test_client.post(f'/tenants/{test_tenant_id}/bus/{test_bu_id}/connections', json=payload)
        conn_id = create_resp.json()['connection']['id']

        response = test_client.delete(f'/tenants/{test_tenant_id}/bus/{test_bu_id}/connections/{conn_id}')
        assert response.status_code == 204
