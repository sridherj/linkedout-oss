# SPDX-License-Identifier: Apache-2.0
"""Integration tests for BU (Business Unit) API endpoints.

Tests all CRUD operations for the BU controller against
a real PostgreSQL database.
"""

import pytest

from fastapi.testclient import TestClient

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestBuControllerIntegration:
    """Integration tests for BU API endpoints."""

    # =========================================================================
    # LIST TESTS
    # =========================================================================

    def test_list_bus_returns_seeded_data(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        seeded_data: dict,
    ):
        """Verify GET /tenants/{tenant_id}/bus returns seeded BU."""
        response = test_client.get(f'/tenants/{test_tenant_id}/bus')

        assert response.status_code == 200
        data = response.json()

        assert 'bus' in data
        assert data['total'] >= 1

        # Verify seeded BU is in response
        bu_ids = [bu['id'] for bu in data['bus']]
        seeded_bu_id = next(bu.id for bu in seeded_data['bu'] if bu.tenant_id == test_tenant_id)
        assert seeded_bu_id in bu_ids

    def test_list_bus_with_search_filter(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        seeded_data: dict,
    ):
        """Verify GET /tenants/{tenant_id}/bus with search filter works."""
        search_term = next(bu.name for bu in seeded_data['bu'] if bu.tenant_id == test_tenant_id)[0:4]
        response = test_client.get(
            f'/tenants/{test_tenant_id}/bus',
            params={'search': search_term}
        )

        assert response.status_code == 200
        data = response.json()

        # Should find our integration test BU
        assert data['total'] >= 1
        for bu in data['bus']:
            assert search_term.lower() in bu['name'].lower()

    def test_list_bus_with_pagination(
        self,
        test_client: TestClient,
        test_tenant_id: str,
    ):
        """Verify GET /tenants/{tenant_id}/bus respects limit and offset."""
        response = test_client.get(
            f'/tenants/{test_tenant_id}/bus',
            params={'limit': 1, 'offset': 0}
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data['bus']) <= 1
        assert data['limit'] == 1
        assert data['offset'] == 0

    def test_list_bus_with_sort_by_name(
        self,
        test_client: TestClient,
        test_tenant_id: str,
    ):
        """Verify GET /tenants/{tenant_id}/bus sorts by name correctly."""
        response = test_client.get(
            f'/tenants/{test_tenant_id}/bus',
            params={'sort_by': 'name', 'sort_order': 'asc'}
        )

        assert response.status_code == 200
        data = response.json()

        if len(data['bus']) > 1:
            names = [bu['name'] for bu in data['bus']]
            assert names == sorted(names)

    # =========================================================================
    # GET BY ID TESTS
    # =========================================================================

    def test_get_bu_by_id_returns_bu(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        seeded_data: dict,
    ):
        """Verify GET /tenants/{tenant_id}/bus/{bu_id} returns correct BU."""
        seeded_bu = next(bu for bu in seeded_data['bu'] if bu.tenant_id == test_tenant_id)
        bu_id = seeded_bu.id

        response = test_client.get(f'/tenants/{test_tenant_id}/bus/{bu_id}')

        assert response.status_code == 200
        data = response.json()

        assert 'bu' in data
        assert data['bu']['id'] == bu_id
        assert data['bu']['name'] == seeded_bu.name
        assert data['bu']['tenant_id'] == test_tenant_id

    def test_get_bu_by_id_not_found(
        self,
        test_client: TestClient,
        test_tenant_id: str,
    ):
        """Verify GET /tenants/{tenant_id}/bus/{bu_id} returns 404 for unknown ID."""
        response = test_client.get(
            f'/tenants/{test_tenant_id}/bus/nonexistent_bu_id'
        )

        assert response.status_code == 404

    # =========================================================================
    # CREATE TESTS
    # =========================================================================

    def test_create_bu_success(
        self,
        test_client: TestClient,
        test_tenant_id: str,
    ):
        """Verify POST /tenants/{tenant_id}/bus creates a new BU."""
        payload = {
            'name': 'New Integration Test BU',
            'description': 'Created by integration test',
        }

        response = test_client.post(
            f'/tenants/{test_tenant_id}/bus',
            json=payload
        )

        assert response.status_code == 201
        data = response.json()

        assert 'bu' in data
        assert data['bu']['name'] == payload['name']
        assert data['bu']['description'] == payload['description']
        assert data['bu']['id'] is not None
        assert data['bu']['tenant_id'] == test_tenant_id
        # BU IDs should start with 'bu_' prefix
        assert data['bu']['id'].startswith('bu_')

    def test_create_bu_minimal_fields(
        self,
        test_client: TestClient,
        test_tenant_id: str,
    ):
        """Verify POST /tenants/{tenant_id}/bus works with only required fields."""
        payload = {
            'name': 'Minimal BU',
        }

        response = test_client.post(
            f'/tenants/{test_tenant_id}/bus',
            json=payload
        )

        assert response.status_code == 201
        data = response.json()
        assert data['bu']['name'] == 'Minimal BU'
        assert data['bu']['description'] is None

    def test_create_bus_bulk(
        self,
        test_client: TestClient,
        test_tenant_id: str,
    ):
        """Verify POST /tenants/{tenant_id}/bus/bulk creates multiple BUs."""
        payload = {
            'bus': [
                {'name': 'Bulk BU 1', 'description': 'First bulk BU'},
                {'name': 'Bulk BU 2', 'description': 'Second bulk BU'},
            ]
        }

        response = test_client.post(
            f'/tenants/{test_tenant_id}/bus/bulk',
            json=payload
        )

        assert response.status_code == 201
        data = response.json()

        assert 'bus' in data
        assert len(data['bus']) == 2
        assert data['bus'][0]['name'] == 'Bulk BU 1'
        assert data['bus'][1]['name'] == 'Bulk BU 2'

    def test_create_bu_missing_required_field(
        self,
        test_client: TestClient,
        test_tenant_id: str,
    ):
        """Verify POST /tenants/{tenant_id}/bus returns 422 for missing required field."""
        payload = {
            'description': 'Missing name field',
        }

        response = test_client.post(
            f'/tenants/{test_tenant_id}/bus',
            json=payload
        )

        assert response.status_code == 422

    # =========================================================================
    # UPDATE TESTS
    # =========================================================================

    def test_update_bu_success(
        self,
        test_client: TestClient,
        test_tenant_id: str,
    ):
        """Verify PATCH /tenants/{tenant_id}/bus/{bu_id} updates BU."""
        # First create a BU to update
        create_response = test_client.post(
            f'/tenants/{test_tenant_id}/bus',
            json={'name': 'BU To Update', 'description': 'Original'}
        )
        bu_id = create_response.json()['bu']['id']

        # Update the BU
        update_payload = {
            'description': 'Updated description',
        }
        response = test_client.patch(
            f'/tenants/{test_tenant_id}/bus/{bu_id}',
            json=update_payload
        )

        assert response.status_code == 200
        data = response.json()

        assert data['bu']['id'] == bu_id
        assert data['bu']['description'] == 'Updated description'
        # Name should remain unchanged
        assert data['bu']['name'] == 'BU To Update'

    def test_update_bu_name(
        self,
        test_client: TestClient,
        test_tenant_id: str,
    ):
        """Verify PATCH /tenants/{tenant_id}/bus/{bu_id} can update name."""
        # First create a BU to update
        create_response = test_client.post(
            f'/tenants/{test_tenant_id}/bus',
            json={'name': 'Original Name', 'description': 'Test BU'}
        )
        bu_id = create_response.json()['bu']['id']

        # Update the name
        update_payload = {
            'name': 'Updated Name',
        }
        response = test_client.patch(
            f'/tenants/{test_tenant_id}/bus/{bu_id}',
            json=update_payload
        )

        assert response.status_code == 200
        data = response.json()

        assert data['bu']['id'] == bu_id
        assert data['bu']['name'] == 'Updated Name'
        # Description should remain unchanged
        assert data['bu']['description'] == 'Test BU'

    def test_update_bu_not_found(
        self,
        test_client: TestClient,
        test_tenant_id: str,
    ):
        """Verify PATCH /tenants/{tenant_id}/bus/{bu_id} returns 404 for unknown ID."""
        response = test_client.patch(
            f'/tenants/{test_tenant_id}/bus/nonexistent_bu_id',
            json={'description': 'Should fail'}
        )

        assert response.status_code == 404

    # =========================================================================
    # DELETE TESTS
    # =========================================================================

    def test_delete_bu_success(
        self,
        test_client: TestClient,
        test_tenant_id: str,
    ):
        """Verify DELETE /tenants/{tenant_id}/bus/{bu_id} deletes BU."""
        # First create a BU to delete
        create_response = test_client.post(
            f'/tenants/{test_tenant_id}/bus',
            json={'name': 'BU To Delete'}
        )
        bu_id = create_response.json()['bu']['id']

        # Delete the BU
        response = test_client.delete(f'/tenants/{test_tenant_id}/bus/{bu_id}')

        assert response.status_code == 204

        # Verify it's deleted
        get_response = test_client.get(
            f'/tenants/{test_tenant_id}/bus/{bu_id}'
        )
        assert get_response.status_code == 404

    def test_delete_bu_not_found(
        self,
        test_client: TestClient,
        test_tenant_id: str,
    ):
        """Verify DELETE /tenants/{tenant_id}/bus/{bu_id} returns 404 for unknown ID."""
        response = test_client.delete(
            f'/tenants/{test_tenant_id}/bus/nonexistent_bu_id'
        )

        assert response.status_code == 404
