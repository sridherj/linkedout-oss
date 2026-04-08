# SPDX-License-Identifier: Apache-2.0
"""Integration tests for Tenant API endpoints.

Tests all CRUD operations for the Tenant controller against
a real PostgreSQL database.
"""

import pytest

from fastapi.testclient import TestClient

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestTenantControllerIntegration:
    """Integration tests for Tenant API endpoints."""

    # =========================================================================
    # LIST TESTS
    # =========================================================================

    def test_list_tenants_returns_seeded_data(
        self,
        test_client: TestClient,
        seeded_data: dict,
    ):
        """Verify GET /tenants returns seeded tenant."""
        response = test_client.get('/tenants')

        assert response.status_code == 200
        data = response.json()

        assert 'tenants' in data
        assert data['total'] >= 1

        # Verify seeded tenant is in response
        tenant_ids = [t['id'] for t in data['tenants']]
        seeded_tenant_id = seeded_data['tenant'][0].id
        assert seeded_tenant_id in tenant_ids

    def test_list_tenants_with_search_filter(
        self,
        test_client: TestClient,
        seeded_data: dict,
    ):
        """Verify GET /tenants with search filter works."""
        search_term = seeded_data['tenant'][0].name[0:5]
        response = test_client.get('/tenants', params={'search': search_term})

        assert response.status_code == 200
        data = response.json()

        # Should find our integration test tenant
        assert data['total'] >= 1
        for tenant in data['tenants']:
            assert search_term in tenant['name']

    def test_list_tenants_with_pagination(
        self,
        test_client: TestClient,
    ):
        """Verify GET /tenants respects limit and offset."""
        response = test_client.get('/tenants', params={'limit': 1, 'offset': 0})

        assert response.status_code == 200
        data = response.json()

        assert len(data['tenants']) <= 1
        assert data['limit'] == 1
        assert data['offset'] == 0

    # =========================================================================
    # GET BY ID TESTS
    # =========================================================================

    def test_get_tenant_by_id_returns_tenant(
        self,
        test_client: TestClient,
        seeded_data: dict,
    ):
        """Verify GET /tenants/{tenant_id} returns correct tenant."""
        tenant_id = seeded_data['tenant'][0].id

        response = test_client.get(f'/tenants/{tenant_id}')

        assert response.status_code == 200
        data = response.json()

        assert 'tenant' in data
        assert data['tenant']['id'] == tenant_id
        assert data['tenant']['name'] == seeded_data['tenant'][0].name

    def test_get_tenant_by_id_not_found(
        self,
        test_client: TestClient,
    ):
        """Verify GET /tenants/{tenant_id} returns 404 for unknown ID."""
        response = test_client.get('/tenants/nonexistent_tenant_id')

        assert response.status_code == 404

    # =========================================================================
    # CREATE TESTS
    # =========================================================================

    def test_create_tenant_success(
        self,
        test_client: TestClient,
    ):
        """Verify POST /tenants creates a new tenant."""
        payload = {
            'name': 'New Integration Test Tenant',
            'description': 'Created by integration test',
        }

        response = test_client.post('/tenants', json=payload)

        assert response.status_code == 201
        data = response.json()

        assert 'tenant' in data
        assert data['tenant']['name'] == payload['name']
        assert data['tenant']['description'] == payload['description']
        assert data['tenant']['id'] is not None
        # Tenant IDs should start with 'tenant_' prefix
        assert data['tenant']['id'].startswith('tenant_')

    def test_create_tenant_minimal_fields(
        self,
        test_client: TestClient,
    ):
        """Verify POST /tenants works with only required fields."""
        payload = {
            'name': 'Minimal Tenant',
        }

        response = test_client.post('/tenants', json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data['tenant']['name'] == 'Minimal Tenant'

    def test_create_tenants_bulk(
        self,
        test_client: TestClient,
    ):
        """Verify POST /tenants/bulk creates multiple tenants."""
        payload = {
            'tenants': [
                {'name': 'Bulk Tenant 1'},
                {'name': 'Bulk Tenant 2'},
            ]
        }

        response = test_client.post('/tenants/bulk', json=payload)

        assert response.status_code == 201
        data = response.json()

        assert 'tenants' in data
        assert len(data['tenants']) == 2

    # =========================================================================
    # UPDATE TESTS
    # =========================================================================

    def test_update_tenant_success(
        self,
        test_client: TestClient,
    ):
        """Verify PATCH /tenants/{tenant_id} updates tenant."""
        # First create a tenant to update
        create_response = test_client.post(
            '/tenants',
            json={'name': 'Tenant To Update', 'description': 'Original'}
        )
        tenant_id = create_response.json()['tenant']['id']

        # Update the tenant
        update_payload = {
            'description': 'Updated description',
        }
        response = test_client.patch(f'/tenants/{tenant_id}', json=update_payload)

        assert response.status_code == 200
        data = response.json()

        assert data['tenant']['id'] == tenant_id
        assert data['tenant']['description'] == 'Updated description'
        # Name should remain unchanged
        assert data['tenant']['name'] == 'Tenant To Update'

    def test_update_tenant_not_found(
        self,
        test_client: TestClient,
    ):
        """Verify PATCH /tenants/{tenant_id} returns 404 for unknown ID."""
        response = test_client.patch(
            '/tenants/nonexistent_tenant_id',
            json={'description': 'Should fail'}
        )

        assert response.status_code == 404

    # =========================================================================
    # DELETE TESTS
    # =========================================================================

    def test_delete_tenant_success(
        self,
        test_client: TestClient,
    ):
        """Verify DELETE /tenants/{tenant_id} deletes tenant."""
        # First create a tenant to delete
        create_response = test_client.post(
            '/tenants',
            json={'name': 'Tenant To Delete'}
        )
        tenant_id = create_response.json()['tenant']['id']

        # Delete the tenant
        response = test_client.delete(f'/tenants/{tenant_id}')

        assert response.status_code == 204

        # Verify it's deleted
        get_response = test_client.get(f'/tenants/{tenant_id}')
        assert get_response.status_code == 404

    def test_delete_tenant_not_found(
        self,
        test_client: TestClient,
    ):
        """Verify DELETE /tenants/{tenant_id} returns 404 for unknown ID."""
        response = test_client.delete('/tenants/nonexistent_tenant_id')

        assert response.status_code == 404
