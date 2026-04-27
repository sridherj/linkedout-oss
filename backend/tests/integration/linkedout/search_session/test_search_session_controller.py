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

    def _create_session(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
        initial_query: str | None = None,
    ) -> dict:
        suffix = uuid.uuid4().hex[:8]
        resp = test_client.post(
            self._base_url(test_tenant_id, test_bu_id),
            json={
                'app_user_id': app_user,
                'initial_query': initial_query or f'session {suffix}',
            },
        )
        assert resp.status_code == 201
        return resp.json()['search_session']

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
        initial_query = f'get-by-id query {suffix}'
        created = self._create_session(
            test_client, test_tenant_id, test_bu_id, app_user, initial_query=initial_query
        )
        session_id = created['id']

        # Act
        response = test_client.get(
            f'{self._base_url(test_tenant_id, test_bu_id)}/{session_id}',
        )

        # Assert
        assert response.status_code == 200
        session = response.json()['search_session']
        assert session['id'] == session_id
        assert session['initial_query'] == initial_query
        assert session['app_user_id'] == app_user

    def test_get_search_session_not_found(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
    ):
        # Act
        response = test_client.get(
            f'{self._base_url(test_tenant_id, test_bu_id)}/ss_nonexistent',
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
        ids = [
            self._create_session(
                test_client, test_tenant_id, test_bu_id, app_user,
                initial_query=f'list test {suffix} #{i}',
            )['id']
            for i in range(2)
        ]

        # Act
        response = test_client.get(
            self._base_url(test_tenant_id, test_bu_id),
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
        app_user_session_id = self._create_session(
            test_client, test_tenant_id, test_bu_id, app_user,
            initial_query=f'filter user a {suffix}',
        )['id']
        app_user_2_session_id = self._create_session(
            test_client, test_tenant_id, test_bu_id, app_user_2,
            initial_query=f'filter user b {suffix}',
        )['id']

        # Act
        response = test_client.get(
            self._base_url(test_tenant_id, test_bu_id),
            params={'app_user_id': app_user, 'limit': 100},
        )

        # Assert
        assert response.status_code == 200
        sessions = response.json()['search_sessions']
        for session in sessions:
            assert session['app_user_id'] == app_user
        returned_ids = {s['id'] for s in sessions}
        assert app_user_session_id in returned_ids
        assert app_user_2_session_id not in returned_ids

    def test_list_search_sessions_pagination(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
    ):
        # Arrange — create 3 sessions
        suffix = uuid.uuid4().hex[:8]
        for i in range(3):
            self._create_session(
                test_client, test_tenant_id, test_bu_id, app_user,
                initial_query=f'pagination {suffix} #{i}',
            )

        # Act — fetch page 1 and page 2 with limit=1
        page_1 = test_client.get(
            self._base_url(test_tenant_id, test_bu_id),
            params={'limit': 1, 'offset': 0},
        )
        page_2 = test_client.get(
            self._base_url(test_tenant_id, test_bu_id),
            params={'limit': 1, 'offset': 1},
        )

        # Assert — pagination returns exactly one item per page and the items
        # differ between pages
        assert page_1.status_code == 200
        assert page_2.status_code == 200
        page_1_data = page_1.json()
        page_2_data = page_2.json()
        assert len(page_1_data['search_sessions']) == 1
        assert len(page_2_data['search_sessions']) == 1
        assert page_1_data['search_sessions'][0]['id'] != page_2_data['search_sessions'][0]['id']
        assert page_1_data['total'] >= 3

    def test_update_search_session_turn_count(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
    ):
        # Arrange
        session_id = self._create_session(
            test_client, test_tenant_id, test_bu_id, app_user,
        )['id']

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

    def test_update_search_session_is_saved(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
    ):
        # Arrange
        session_id = self._create_session(
            test_client, test_tenant_id, test_bu_id, app_user,
        )['id']

        # Act — save the session with a name
        patch_resp = test_client.patch(
            f'{self._base_url(test_tenant_id, test_bu_id)}/{session_id}',
            json={'is_saved': True, 'saved_name': 'My Saved Search'},
        )
        assert patch_resp.status_code == 200

        get_resp = test_client.get(
            f'{self._base_url(test_tenant_id, test_bu_id)}/{session_id}',
        )

        # Assert
        assert get_resp.status_code == 200
        session = get_resp.json()['search_session']
        assert session['is_saved'] is True
        assert session['saved_name'] == 'My Saved Search'

    def test_update_search_session_unsave(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
    ):
        # Arrange — create a session and save it
        session_id = self._create_session(
            test_client, test_tenant_id, test_bu_id, app_user,
        )['id']
        test_client.patch(
            f'{self._base_url(test_tenant_id, test_bu_id)}/{session_id}',
            json={'is_saved': True, 'saved_name': 'Temporary Save'},
        )

        # Act — unsave it
        patch_resp = test_client.patch(
            f'{self._base_url(test_tenant_id, test_bu_id)}/{session_id}',
            json={'is_saved': False},
        )
        assert patch_resp.status_code == 200

        # Assert
        session = patch_resp.json()['search_session']
        assert session['is_saved'] is False

    def test_delete_search_session(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
    ):
        # Arrange
        session_id = self._create_session(
            test_client, test_tenant_id, test_bu_id, app_user,
        )['id']

        # Act
        delete_resp = test_client.delete(
            f'{self._base_url(test_tenant_id, test_bu_id)}/{session_id}',
        )

        # Assert
        assert delete_resp.status_code == 204

        get_resp = test_client.get(
            f'{self._base_url(test_tenant_id, test_bu_id)}/{session_id}',
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
