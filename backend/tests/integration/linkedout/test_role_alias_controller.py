# SPDX-License-Identifier: Apache-2.0
"""Integration tests for RoleAlias API endpoints.

Tests all CRUD operations for the RoleAlias controller against
a real PostgreSQL database.
"""

import pytest

from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


class TestRoleAliasControllerIntegration:
    """Integration tests for RoleAlias API endpoints."""

    # =========================================================================
    # LIST TESTS
    # =========================================================================

    def test_list_role_aliases_returns_seeded_data(
        self, test_client: TestClient, seeded_data: dict,
    ):
        response = test_client.get('/role-aliases')
        assert response.status_code == 200
        data = response.json()
        assert 'role_aliases' in data
        assert data['total'] >= 1

        role_alias_ids = [ra['id'] for ra in data['role_aliases']]
        seeded_id = seeded_data['role_alias'][0].id
        assert seeded_id in role_alias_ids

    def test_list_role_aliases_with_alias_title_filter(
        self, test_client: TestClient, seeded_data: dict,
    ):
        seeded_ra = seeded_data['role_alias'][0]
        response = test_client.get(
            '/role-aliases',
            params={'alias_title': seeded_ra.alias_title}
        )
        assert response.status_code == 200
        data = response.json()
        assert data['total'] >= 1

    def test_list_role_aliases_pagination(
        self, test_client: TestClient,
    ):
        response = test_client.get(
            '/role-aliases',
            params={'limit': 1, 'offset': 0}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data['role_aliases']) <= 1

    # =========================================================================
    # GET BY ID TESTS
    # =========================================================================

    def test_get_role_alias_by_id_success(
        self, test_client: TestClient, seeded_data: dict,
    ):
        role_alias_id = seeded_data['role_alias'][0].id
        response = test_client.get(f'/role-aliases/{role_alias_id}')
        assert response.status_code == 200
        data = response.json()
        assert 'role_alias' in data
        assert data['role_alias']['id'] == role_alias_id

    def test_get_role_alias_by_id_not_found(
        self, test_client: TestClient,
    ):
        response = test_client.get('/role-aliases/ra_nonexistent')
        assert response.status_code == 404

    # =========================================================================
    # CREATE TESTS
    # =========================================================================

    def test_create_role_alias_success(
        self, test_client: TestClient,
    ):
        response = test_client.post(
            '/role-aliases',
            json={
                'alias_title': 'integration-test-alias',
                'canonical_title': 'Integration Test Title',
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert 'role_alias' in data
        assert data['role_alias']['alias_title'] == 'integration-test-alias'
        assert data['role_alias']['id'].startswith('ra_')

    def test_create_role_alias_minimal(
        self, test_client: TestClient,
    ):
        response = test_client.post(
            '/role-aliases',
            json={
                'alias_title': 'minimal-alias',
                'canonical_title': 'Minimal Title',
            },
        )
        assert response.status_code == 201

    def test_create_role_alias_missing_required(
        self, test_client: TestClient,
    ):
        response = test_client.post(
            '/role-aliases',
            json={'seniority_level': 'Senior'},
        )
        assert response.status_code == 422

    def test_create_role_aliases_bulk(
        self, test_client: TestClient,
    ):
        response = test_client.post(
            '/role-aliases/bulk',
            json={
                'role_aliases': [
                    {'alias_title': 'bulk-alias-1', 'canonical_title': 'Bulk Title 1'},
                    {'alias_title': 'bulk-alias-2', 'canonical_title': 'Bulk Title 2'},
                ]
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert 'role_aliases' in data
        assert len(data['role_aliases']) == 2

    # =========================================================================
    # UPDATE TESTS
    # =========================================================================

    def test_update_role_alias_success(
        self, test_client: TestClient, seeded_data: dict,
    ):
        role_alias_id = seeded_data['role_alias'][0].id
        response = test_client.patch(
            f'/role-aliases/{role_alias_id}',
            json={'canonical_title': 'updated-canonical-title'},
        )
        assert response.status_code == 200
        data = response.json()
        assert data['role_alias']['canonical_title'] == 'updated-canonical-title'

    def test_update_role_alias_not_found(
        self, test_client: TestClient,
    ):
        response = test_client.patch(
            '/role-aliases/ra_nonexistent',
            json={'canonical_title': 'x'},
        )
        assert response.status_code == 404

    # =========================================================================
    # DELETE TESTS
    # =========================================================================

    def test_delete_role_alias_success(
        self, test_client: TestClient,
    ):
        # Create a role alias to delete
        create_resp = test_client.post(
            '/role-aliases',
            json={
                'alias_title': 'to-delete-alias',
                'canonical_title': 'To Delete',
            },
        )
        role_alias_id = create_resp.json()['role_alias']['id']

        response = test_client.delete(f'/role-aliases/{role_alias_id}')
        assert response.status_code == 204

    def test_delete_role_alias_not_found(
        self, test_client: TestClient,
    ):
        response = test_client.delete('/role-aliases/ra_nonexistent')
        assert response.status_code == 404
