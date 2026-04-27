# SPDX-License-Identifier: Apache-2.0
"""Integration tests for SearchSession API endpoints.

SearchSession is scoped to Tenant and BU.
"""
import pytest
import uuid
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


class TestSearchSessionControllerIntegration:

    @pytest.fixture
    def app_user(self, seeded_data: dict):
        return seeded_data['app_user'][0].id

    @pytest.fixture
    def app_user_2(self, seeded_data: dict):
        return seeded_data['app_user'][1].id

    def _base_url(self, tenant_id: str, bu_id: str) -> str:
        return f'/tenants/{tenant_id}/bus/{bu_id}/search-sessions'

    def test_create_search_session_success(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
    ):
        # Arrange
        suffix = uuid.uuid4().hex[:8]
        payload = {
            'app_user_id': app_user,
            'initial_query': f'find python engineers {suffix}',
        }

        # Act
        response = test_client.post(self._base_url(test_tenant_id, test_bu_id), json=payload)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert 'search_session' in data
        session = data['search_session']
        assert session['id'].startswith('ss_')
        assert session['app_user_id'] == app_user
        assert session['initial_query'] == payload['initial_query']
        assert session['turn_count'] == 1
        assert session['is_saved'] is False

    def test_create_search_session_with_all_fields(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
    ):
        # Arrange
        suffix = uuid.uuid4().hex[:8]
        last_active_at = '2024-01-15T12:34:56'
        payload = {
            'app_user_id': app_user,
            'initial_query': f'senior backend engineers {suffix}',
            'turn_count': 3,
            'last_active_at': last_active_at,
        }

        # Act
        response = test_client.post(self._base_url(test_tenant_id, test_bu_id), json=payload)

        # Assert
        assert response.status_code == 201
        session = response.json()['search_session']
        assert session['app_user_id'] == app_user
        assert session['initial_query'] == payload['initial_query']
        assert session['turn_count'] == 3
        assert session['last_active_at'] is not None
        assert session['last_active_at'].startswith('2024-01-15T12:34:56')

    def test_create_search_session_missing_required_returns_422(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
    ):
        # Act
        response = test_client.post(self._base_url(test_tenant_id, test_bu_id), json={})

        # Assert
        assert response.status_code == 422

    def test_bulk_create_search_sessions(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
    ):
        # Arrange
        suffix = uuid.uuid4().hex[:8]
        payload = {
            'search_sessions': [
                {
                    'app_user_id': app_user,
                    'initial_query': f'bulk session 1 {suffix}',
                },
                {
                    'app_user_id': app_user,
                    'initial_query': f'bulk session 2 {suffix}',
                },
            ]
        }

        # Act
        response = test_client.post(
            f'{self._base_url(test_tenant_id, test_bu_id)}/bulk',
            json=payload,
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert 'search_sessions' in data
        assert len(data['search_sessions']) == 2

    def test_get_search_session_by_id(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
    ):
        # Arrange
        suffix = uuid.uuid4().hex[:8]
        create_payload = {
            'app_user_id': app_user,
            'initial_query': f'get-by-id query {suffix}',
        }
        create_resp = test_client.post(self._base_url(test_tenant_id, test_bu_id), json=create_payload)
        assert create_resp.status_code == 201
        session_id = create_resp.json()['search_session']['id']

        # Act
        response = test_client.get(
            f'{self._base_url(test_tenant_id, test_bu_id)}/{session_id}',
            headers={'X-App-User-Id': app_user},
        )

        # Assert
        assert response.status_code == 200
        session = response.json()['search_session']
        assert session['id'] == session_id
        assert session['initial_query'] == create_payload['initial_query']
        assert session['app_user_id'] == app_user

    def test_get_search_session_not_found(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
    ):
        # Act
        response = test_client.get(
            f'{self._base_url(test_tenant_id, test_bu_id)}/ss_nonexistent',
            headers={'X-App-User-Id': app_user},
        )

        # Assert
        assert response.status_code == 404

    def test_list_search_sessions_returns_created(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
    ):
        # Arrange
        suffix = uuid.uuid4().hex[:8]
        ids = []
        for i in range(2):
            resp = test_client.post(self._base_url(test_tenant_id, test_bu_id), json={
                'app_user_id': app_user,
                'initial_query': f'list test {suffix} #{i}',
            })
            assert resp.status_code == 201
            ids.append(resp.json()['search_session']['id'])

        # Act
        response = test_client.get(
            self._base_url(test_tenant_id, test_bu_id),
            headers={'X-App-User-Id': app_user},
            params={'limit': 100},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data['total'] >= 2
        returned_ids = {s['id'] for s in data['search_sessions']}
        for created_id in ids:
            assert created_id in returned_ids

    def test_list_search_sessions_filter_by_app_user_id(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
        app_user_2: str,
    ):
        # Arrange
        suffix = uuid.uuid4().hex[:8]
        user0_resp = test_client.post(self._base_url(test_tenant_id, test_bu_id), json={
            'app_user_id': app_user,
            'initial_query': f'filter user0 {suffix}',
        })
        assert user0_resp.status_code == 201
        user0_id = user0_resp.json()['search_session']['id']

        user1_resp = test_client.post(self._base_url(test_tenant_id, test_bu_id), json={
            'app_user_id': app_user_2,
            'initial_query': f'filter user1 {suffix}',
        })
        assert user1_resp.status_code == 201
        user1_id = user1_resp.json()['search_session']['id']

        # Act
        response = test_client.get(
            self._base_url(test_tenant_id, test_bu_id),
            headers={'X-App-User-Id': app_user},
            params={'app_user_id': app_user, 'limit': 100},
        )

        # Assert
        assert response.status_code == 200
        sessions = response.json()['search_sessions']
        for session in sessions:
            assert session['app_user_id'] == app_user
        returned_ids = {s['id'] for s in sessions}
        assert user0_id in returned_ids
        assert user1_id not in returned_ids

    def test_list_search_sessions_pagination(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
    ):
        # Arrange
        suffix = uuid.uuid4().hex[:8]
        for i in range(3):
            resp = test_client.post(self._base_url(test_tenant_id, test_bu_id), json={
                'app_user_id': app_user,
                'initial_query': f'pagination {suffix} #{i}',
            })
            assert resp.status_code == 201

        # Act
        response = test_client.get(
            self._base_url(test_tenant_id, test_bu_id),
            headers={'X-App-User-Id': app_user},
            params={'limit': 1},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data['search_sessions']) <= 1
        assert data['total'] >= 3

    def test_update_search_session_turn_count(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
    ):
        # Arrange
        suffix = uuid.uuid4().hex[:8]
        create_resp = test_client.post(self._base_url(test_tenant_id, test_bu_id), json={
            'app_user_id': app_user,
            'initial_query': f'update turn count {suffix}',
        })
        assert create_resp.status_code == 201
        session_id = create_resp.json()['search_session']['id']

        # Act
        response = test_client.patch(
            f'{self._base_url(test_tenant_id, test_bu_id)}/{session_id}',
            json={'turn_count': 5},
        )

        # Assert
        assert response.status_code == 200
        session = response.json()['search_session']
        assert session['turn_count'] == 5

    def test_update_search_session_not_found(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
    ):
        # Act
        response = test_client.patch(
            f'{self._base_url(test_tenant_id, test_bu_id)}/ss_nonexistent',
            json={'turn_count': 2},
        )

        # Assert
        assert response.status_code == 404

    def test_update_search_session_is_saved_not_applied(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
    ):
        # This test documents current behavior: the API schema accepts `is_saved`
        # and `saved_name` on PATCH, but the service's `_update_entity_from_request`
        # does NOT apply those fields, so they are silently ignored.
        # Arrange
        suffix = uuid.uuid4().hex[:8]
        create_resp = test_client.post(self._base_url(test_tenant_id, test_bu_id), json={
            'app_user_id': app_user,
            'initial_query': f'is_saved gap test {suffix}',
        })
        assert create_resp.status_code == 201
        session_id = create_resp.json()['search_session']['id']

        # Act
        patch_resp = test_client.patch(
            f'{self._base_url(test_tenant_id, test_bu_id)}/{session_id}',
            json={'is_saved': True},
        )
        assert patch_resp.status_code == 200

        get_resp = test_client.get(
            f'{self._base_url(test_tenant_id, test_bu_id)}/{session_id}',
            headers={'X-App-User-Id': app_user},
        )

        # Assert
        assert get_resp.status_code == 200
        session = get_resp.json()['search_session']
        assert session['is_saved'] is False, (
            'Documents current behavior: _update_entity_from_request does not '
            'apply `is_saved` even though the API schema accepts it.'
        )

    def test_delete_search_session(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
    ):
        # Arrange
        suffix = uuid.uuid4().hex[:8]
        create_resp = test_client.post(self._base_url(test_tenant_id, test_bu_id), json={
            'app_user_id': app_user,
            'initial_query': f'delete test {suffix}',
        })
        assert create_resp.status_code == 201
        session_id = create_resp.json()['search_session']['id']

        # Act
        delete_resp = test_client.delete(
            f'{self._base_url(test_tenant_id, test_bu_id)}/{session_id}',
        )

        # Assert
        assert delete_resp.status_code == 204

        get_resp = test_client.get(
            f'{self._base_url(test_tenant_id, test_bu_id)}/{session_id}',
            headers={'X-App-User-Id': app_user},
        )
        assert get_resp.status_code == 404

    def test_delete_search_session_not_found(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
    ):
        # Act
        response = test_client.delete(
            f'{self._base_url(test_tenant_id, test_bu_id)}/ss_nonexistent',
        )

        # Assert
        assert response.status_code == 404
