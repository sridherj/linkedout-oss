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

    def _base_url(self, tenant_id: str, bu_id: str) -> str:
        return f'/tenants/{tenant_id}/bus/{bu_id}/search-turns'

    def _create_turn(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        session_id: str,
        turn_number: int = 1,
        **extra,
    ) -> dict:
        suffix = uuid.uuid4().hex[:8]
        payload = {
            'session_id': session_id,
            'turn_number': turn_number,
            'user_query': f'q {suffix}',
            **extra,
        }
        resp = test_client.post(self._base_url(test_tenant_id, test_bu_id), json=payload)
        assert resp.status_code == 201
        return resp.json()['search_turn']

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
        response = test_client.post(self._base_url(test_tenant_id, test_bu_id), json=payload)

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
        response = test_client.post(self._base_url(test_tenant_id, test_bu_id), json=payload)

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
        response = test_client.post(self._base_url(test_tenant_id, test_bu_id), json={})

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
            f'{self._base_url(test_tenant_id, test_bu_id)}/bulk',
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
        created = self._create_turn(
            test_client, test_tenant_id, test_bu_id, search_session_id
        )
        turn_id = created['id']

        # Act
        response = test_client.get(
            f'{self._base_url(test_tenant_id, test_bu_id)}/{turn_id}',
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data['search_turn']['id'] == turn_id
        assert data['search_turn']['session_id'] == search_session_id

    def test_get_search_turn_not_found(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
    ):
        # Act
        response = test_client.get(
            f'{self._base_url(test_tenant_id, test_bu_id)}/sturn_nonexistent',
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

        # Create a turn in each session
        turn_in_first_session = self._create_turn(
            test_client, test_tenant_id, test_bu_id, search_session_id
        )
        turn_in_second_session = self._create_turn(
            test_client, test_tenant_id, test_bu_id, second_session_id
        )

        # Act
        response = test_client.get(
            self._base_url(test_tenant_id, test_bu_id),
            params={'session_id': search_session_id},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        returned_ids = {t['id'] for t in data['search_turns']}
        assert turn_in_first_session['id'] in returned_ids
        assert turn_in_second_session['id'] not in returned_ids
        for turn in data['search_turns']:
            assert turn['session_id'] == search_session_id

    def test_list_search_turns_pagination(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        search_session_id: str,
    ):
        # Arrange — create 3 turns in this session
        created_ids = []
        for n in (1, 2, 3):
            turn = self._create_turn(
                test_client, test_tenant_id, test_bu_id, search_session_id, turn_number=n
            )
            created_ids.append(turn['id'])

        # Act — fetch page 1 and page 2 with limit=1, scoped to this session
        page_1 = test_client.get(
            self._base_url(test_tenant_id, test_bu_id),
            params={'session_id': search_session_id, 'limit': 1, 'offset': 0},
        )
        page_2 = test_client.get(
            self._base_url(test_tenant_id, test_bu_id),
            params={'session_id': search_session_id, 'limit': 1, 'offset': 1},
        )

        # Assert — pagination returns exactly one distinct item per page
        assert page_1.status_code == 200
        assert page_2.status_code == 200
        page_1_turns = page_1.json()['search_turns']
        page_2_turns = page_2.json()['search_turns']
        assert len(page_1_turns) == 1
        assert len(page_2_turns) == 1
        assert page_1_turns[0]['id'] != page_2_turns[0]['id']
        for turn in (page_1_turns[0], page_2_turns[0]):
            assert turn['id'] in created_ids

    def test_list_turns_by_session_nested_endpoint(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        search_session_id: str,
    ):
        # Arrange — create 3 turns
        for n in (1, 2, 3):
            self._create_turn(
                test_client, test_tenant_id, test_bu_id, search_session_id, turn_number=n
            )

        # Act
        response = test_client.get(
            f'{self._base_url(test_tenant_id, test_bu_id)}/by-session/{search_session_id}',
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
        created = self._create_turn(
            test_client,
            test_tenant_id,
            test_bu_id,
            search_session_id,
            summary='Original summary',
        )
        turn_id = created['id']

        # Act
        response = test_client.patch(
            f'{self._base_url(test_tenant_id, test_bu_id)}/{turn_id}',
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
            f'{self._base_url(test_tenant_id, test_bu_id)}/sturn_nonexistent',
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
        created = self._create_turn(
            test_client, test_tenant_id, test_bu_id, search_session_id
        )
        turn_id = created['id']

        # Act
        response = test_client.delete(
            f'{self._base_url(test_tenant_id, test_bu_id)}/{turn_id}',
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
            f'{self._base_url(test_tenant_id, test_bu_id)}/sturn_nonexistent',
        )

        # Assert
        assert response.status_code == 404
