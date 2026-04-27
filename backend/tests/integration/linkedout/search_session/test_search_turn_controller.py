# SPDX-License-Identifier: Apache-2.0
"""Integration tests for SearchTurn API endpoints.

SearchTurn is scoped to Tenant and BU.
"""
import pytest
import uuid
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


class TestSearchTurnControllerIntegration:

    @pytest.fixture
    def app_user(self, seeded_data: dict):
        return seeded_data['app_user'][0].id

    @pytest.fixture
    def search_session_id(self, test_client: TestClient, test_tenant_id: str, test_bu_id: str, app_user: str):
        """Create a search session to use as parent for turns."""
        suffix = uuid.uuid4().hex[:8]
        resp = test_client.post(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/search-sessions',
            json={
                'app_user_id': app_user,
                'initial_query': f'test query for turns {suffix}',
            },
        )
        assert resp.status_code == 201
        return resp.json()['search_session']['id']

    def test_create_search_turn_success(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        search_session_id: str,
    ):
        # Arrange
        suffix = uuid.uuid4().hex[:8]
        payload = {
            'session_id': search_session_id,
            'turn_number': 1,
            'user_query': f'find python engineers {suffix}',
        }

        # Act
        response = test_client.post(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/search-turns',
            json=payload,
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert 'search_turn' in data
        turn = data['search_turn']
        assert turn['id'].startswith('sturn_')
        assert turn['session_id'] == search_session_id
        assert turn['turn_number'] == 1
        assert turn['user_query'] == f'find python engineers {suffix}'

    def test_create_search_turn_with_jsonb_fields(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        search_session_id: str,
    ):
        # Arrange
        payload = {
            'session_id': search_session_id,
            'turn_number': 1,
            'user_query': 'find python engineers',
            'transcript': {'messages': [{'role': 'user', 'content': 'hello'}]},
            'results': [{'profile_id': 'cp_123', 'score': 0.95}],
            'summary': 'Test summary',
        }

        # Act
        response = test_client.post(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/search-turns',
            json=payload,
        )

        # Assert
        assert response.status_code == 201
        turn = response.json()['search_turn']
        assert turn['transcript'] == {'messages': [{'role': 'user', 'content': 'hello'}]}
        assert turn['results'] == [{'profile_id': 'cp_123', 'score': 0.95}]
        assert turn['summary'] == 'Test summary'

    def test_create_search_turn_missing_required_returns_422(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
    ):
        # Act
        response = test_client.post(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/search-turns',
            json={},
        )

        # Assert
        assert response.status_code == 422

    def test_bulk_create_search_turns(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        search_session_id: str,
    ):
        # Arrange
        payload = {
            'search_turns': [
                {
                    'session_id': search_session_id,
                    'turn_number': 1,
                    'user_query': 'first query',
                },
                {
                    'session_id': search_session_id,
                    'turn_number': 2,
                    'user_query': 'second query',
                },
            ],
        }

        # Act
        response = test_client.post(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/search-turns/bulk',
            json=payload,
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert 'search_turns' in data
        assert len(data['search_turns']) == 2

    def test_get_search_turn_by_id(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        search_session_id: str,
    ):
        # Arrange
        create_resp = test_client.post(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/search-turns',
            json={
                'session_id': search_session_id,
                'turn_number': 1,
                'user_query': 'a query',
            },
        )
        assert create_resp.status_code == 201
        turn_id = create_resp.json()['search_turn']['id']

        # Act
        response = test_client.get(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/search-turns/{turn_id}',
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data['search_turn']['id'] == turn_id
        assert data['search_turn']['session_id'] == search_session_id
        assert data['search_turn']['user_query'] == 'a query'

    def test_get_search_turn_not_found(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
    ):
        # Act
        response = test_client.get(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/search-turns/sturn_nonexistent',
        )

        # Assert
        assert response.status_code == 404

    def test_list_search_turns_filter_by_session_id(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
        search_session_id: str,
    ):
        # Arrange — create a second search session
        suffix = uuid.uuid4().hex[:8]
        second_session_resp = test_client.post(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/search-sessions',
            json={
                'app_user_id': app_user,
                'initial_query': f'second session {suffix}',
            },
        )
        assert second_session_resp.status_code == 201
        second_session_id = second_session_resp.json()['search_session']['id']

        # Create a turn in the first session
        r1 = test_client.post(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/search-turns',
            json={
                'session_id': search_session_id,
                'turn_number': 1,
                'user_query': 'first session turn',
            },
        )
        assert r1.status_code == 201
        first_turn_id = r1.json()['search_turn']['id']

        # Create a turn in the second session
        r2 = test_client.post(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/search-turns',
            json={
                'session_id': second_session_id,
                'turn_number': 1,
                'user_query': 'second session turn',
            },
        )
        assert r2.status_code == 201
        second_turn_id = r2.json()['search_turn']['id']

        # Act
        response = test_client.get(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/search-turns',
            params={'session_id': search_session_id},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        returned_ids = {t['id'] for t in data['search_turns']}
        assert first_turn_id in returned_ids
        assert second_turn_id not in returned_ids
        for turn in data['search_turns']:
            assert turn['session_id'] == search_session_id

    def test_list_search_turns_pagination(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        search_session_id: str,
    ):
        # Arrange — create 3 turns
        for n in (1, 2, 3):
            resp = test_client.post(
                f'/tenants/{test_tenant_id}/bus/{test_bu_id}/search-turns',
                json={
                    'session_id': search_session_id,
                    'turn_number': n,
                    'user_query': f'query {n}',
                },
            )
            assert resp.status_code == 201

        # Act
        response = test_client.get(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/search-turns',
            params={'session_id': search_session_id, 'limit': 1},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data['search_turns']) <= 1

    def test_list_turns_by_session_nested_endpoint(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        search_session_id: str,
    ):
        # Arrange — create 3 turns
        for n in (1, 2, 3):
            resp = test_client.post(
                f'/tenants/{test_tenant_id}/bus/{test_bu_id}/search-turns',
                json={
                    'session_id': search_session_id,
                    'turn_number': n,
                    'user_query': f'query {n}',
                },
            )
            assert resp.status_code == 201

        # Act
        response = test_client.get(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/search-turns/by-session/{search_session_id}',
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data['search_turns']) == 3
        turn_numbers = [t['turn_number'] for t in data['search_turns']]
        assert turn_numbers == sorted(turn_numbers)
        assert turn_numbers == [1, 2, 3]

    def test_update_search_turn_summary(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        search_session_id: str,
    ):
        # Arrange
        create_resp = test_client.post(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/search-turns',
            json={
                'session_id': search_session_id,
                'turn_number': 1,
                'user_query': 'a query',
                'summary': 'Original summary',
            },
        )
        assert create_resp.status_code == 201
        turn_id = create_resp.json()['search_turn']['id']

        # Act
        response = test_client.patch(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/search-turns/{turn_id}',
            json={'summary': 'Updated summary'},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data['search_turn']['summary'] == 'Updated summary'

    def test_update_search_turn_not_found(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
    ):
        # Act
        response = test_client.patch(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/search-turns/sturn_nonexistent',
            json={'summary': 'Updated'},
        )

        # Assert
        assert response.status_code == 404

    def test_delete_search_turn(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        search_session_id: str,
    ):
        # Arrange
        create_resp = test_client.post(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/search-turns',
            json={
                'session_id': search_session_id,
                'turn_number': 1,
                'user_query': 'a query',
            },
        )
        assert create_resp.status_code == 201
        turn_id = create_resp.json()['search_turn']['id']

        # Act
        response = test_client.delete(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/search-turns/{turn_id}',
        )

        # Assert
        assert response.status_code == 204

    def test_delete_search_turn_not_found(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
    ):
        # Act
        response = test_client.delete(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/search-turns/sturn_nonexistent',
        )

        # Assert
        assert response.status_code == 404
