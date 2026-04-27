# SPDX-License-Identifier: Apache-2.0
"""Integration tests for SearchTag API endpoints.

SearchTag is scoped to Tenant and BU.
"""
import pytest
import uuid
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


class TestSearchTagControllerIntegration:

    @pytest.fixture
    def app_user(self, seeded_data: dict):
        return seeded_data['app_user'][0].id

    @pytest.fixture
    def search_session_id(self, test_client: TestClient, test_tenant_id: str, test_bu_id: str, app_user: str):
        """Create a search session to use as parent for tags."""
        return self._create_search_session(test_client, test_tenant_id, test_bu_id, app_user)

    @pytest.fixture
    def crawled_profile_id(self, test_client: TestClient, app_user: str):
        """Create a crawled profile to tag."""
        return self._create_crawled_profile(test_client, app_user)

    def _base_url(self, tenant_id: str, bu_id: str) -> str:
        return f'/tenants/{tenant_id}/bus/{bu_id}/search-tags'

    def _create_crawled_profile(self, test_client: TestClient, app_user: str) -> str:
        suffix = uuid.uuid4().hex[:8]
        resp = test_client.post(
            '/crawled-profiles',
            json={
                'linkedin_url': f'https://linkedin.com/in/tag_test_{suffix}',
                'data_source': 'linkedin',
                'source_app_user_id': app_user,
            },
            headers={'X-App-User-Id': app_user},
        )
        assert resp.status_code == 201
        return resp.json()['crawled_profile']['id']

    def _create_search_session(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
    ) -> str:
        suffix = uuid.uuid4().hex[:8]
        resp = test_client.post(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/search-sessions',
            json={
                'app_user_id': app_user,
                'initial_query': f'test query for tags {suffix}',
            },
        )
        assert resp.status_code == 201
        return resp.json()['search_session']['id']

    def _create_tag(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
        session_id: str,
        crawled_profile_id: str,
        tag_name: str,
    ) -> dict:
        resp = test_client.post(
            self._base_url(test_tenant_id, test_bu_id),
            json={
                'app_user_id': app_user,
                'session_id': session_id,
                'crawled_profile_id': crawled_profile_id,
                'tag_name': tag_name,
            },
        )
        assert resp.status_code == 201
        return resp.json()['search_tag']

    def test_create_search_tag_success(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
        search_session_id: str,
        crawled_profile_id: str,
    ):
        # Arrange
        payload = {
            'app_user_id': app_user,
            'session_id': search_session_id,
            'crawled_profile_id': crawled_profile_id,
            'tag_name': 'Important Lead',
        }

        # Act
        response = test_client.post(self._base_url(test_tenant_id, test_bu_id), json=payload)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert 'search_tag' in data
        tag = data['search_tag']
        assert tag['id'].startswith('stag_')
        assert tag['app_user_id'] == app_user
        assert tag['session_id'] == search_session_id
        assert tag['crawled_profile_id'] == crawled_profile_id
        assert tag['tag_name'] == 'Important Lead'

    def test_create_search_tag_missing_required_returns_422(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
    ):
        # Arrange / Act
        response = test_client.post(self._base_url(test_tenant_id, test_bu_id), json={})

        # Assert
        assert response.status_code == 422

    def test_bulk_create_search_tags(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
        search_session_id: str,
        crawled_profile_id: str,
    ):
        # Arrange
        second_profile_id = self._create_crawled_profile(test_client, app_user)
        payload = {
            'search_tags': [
                {
                    'app_user_id': app_user,
                    'session_id': search_session_id,
                    'crawled_profile_id': crawled_profile_id,
                    'tag_name': 'Bulk Tag One',
                },
                {
                    'app_user_id': app_user,
                    'session_id': search_session_id,
                    'crawled_profile_id': second_profile_id,
                    'tag_name': 'Bulk Tag Two',
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
        assert 'search_tags' in data
        assert len(data['search_tags']) == 2

    def test_get_search_tag_by_id(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
        search_session_id: str,
        crawled_profile_id: str,
    ):
        # Arrange
        created = self._create_tag(
            test_client,
            test_tenant_id,
            test_bu_id,
            app_user,
            search_session_id,
            crawled_profile_id,
            'Get By Id Tag',
        )
        tag_id = created['id']

        # Act
        response = test_client.get(
            f'{self._base_url(test_tenant_id, test_bu_id)}/{tag_id}',
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data['search_tag']['id'] == tag_id
        assert data['search_tag']['tag_name'] == 'Get By Id Tag'
        assert data['search_tag']['session_id'] == search_session_id
        assert data['search_tag']['crawled_profile_id'] == crawled_profile_id

    def test_get_search_tag_not_found(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
    ):
        # Act
        response = test_client.get(
            f'{self._base_url(test_tenant_id, test_bu_id)}/stag_nonexistent',
        )

        # Assert
        assert response.status_code == 404

    def test_list_search_tags_filter_by_session_id(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
        search_session_id: str,
        crawled_profile_id: str,
    ):
        # Arrange
        other_session_id = self._create_search_session(
            test_client, test_tenant_id, test_bu_id, app_user
        )
        tag_in_session = self._create_tag(
            test_client,
            test_tenant_id,
            test_bu_id,
            app_user,
            search_session_id,
            crawled_profile_id,
            'In Session',
        )
        self._create_tag(
            test_client,
            test_tenant_id,
            test_bu_id,
            app_user,
            other_session_id,
            crawled_profile_id,
            'Other Session',
        )

        # Act
        response = test_client.get(
            self._base_url(test_tenant_id, test_bu_id),
            params={'session_id': search_session_id},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        returned_ids = [t['id'] for t in data['search_tags']]
        assert tag_in_session['id'] in returned_ids
        for tag in data['search_tags']:
            assert tag['session_id'] == search_session_id

    def test_list_search_tags_filter_by_crawled_profile_id(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
        search_session_id: str,
        crawled_profile_id: str,
    ):
        # Arrange
        other_profile_id = self._create_crawled_profile(test_client, app_user)
        tag_for_profile = self._create_tag(
            test_client,
            test_tenant_id,
            test_bu_id,
            app_user,
            search_session_id,
            crawled_profile_id,
            'Profile Tag',
        )
        self._create_tag(
            test_client,
            test_tenant_id,
            test_bu_id,
            app_user,
            search_session_id,
            other_profile_id,
            'Other Profile Tag',
        )

        # Act
        response = test_client.get(
            self._base_url(test_tenant_id, test_bu_id),
            params={'crawled_profile_id': crawled_profile_id},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        returned_ids = [t['id'] for t in data['search_tags']]
        assert tag_for_profile['id'] in returned_ids
        for tag in data['search_tags']:
            assert tag['crawled_profile_id'] == crawled_profile_id

    def test_list_search_tags_filter_by_tag_name_ilike(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
        search_session_id: str,
        crawled_profile_id: str,
    ):
        # Arrange
        important_tag = self._create_tag(
            test_client,
            test_tenant_id,
            test_bu_id,
            app_user,
            search_session_id,
            crawled_profile_id,
            'Important Lead',
        )
        followup_tag = self._create_tag(
            test_client,
            test_tenant_id,
            test_bu_id,
            app_user,
            search_session_id,
            crawled_profile_id,
            'Follow Up',
        )

        # Act
        response = test_client.get(
            self._base_url(test_tenant_id, test_bu_id),
            params={'tag_name': 'important'},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        returned_ids = [t['id'] for t in data['search_tags']]
        assert important_tag['id'] in returned_ids
        assert followup_tag['id'] not in returned_ids
        for tag in data['search_tags']:
            assert 'important' in tag['tag_name'].lower()

    def test_list_search_tags_pagination(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
        search_session_id: str,
        crawled_profile_id: str,
    ):
        # Arrange — create 3 tags scoped to a fresh session so we can isolate them
        isolated_session_id = self._create_search_session(
            test_client, test_tenant_id, test_bu_id, app_user
        )
        created_ids = []
        for i in range(3):
            tag = self._create_tag(
                test_client,
                test_tenant_id,
                test_bu_id,
                app_user,
                isolated_session_id,
                crawled_profile_id,
                f'Pagination Tag {i}',
            )
            created_ids.append(tag['id'])

        # Act — fetch page 1 (limit=1) and page 2 (limit=1, offset=1) for the
        # isolated session
        page_1 = test_client.get(
            self._base_url(test_tenant_id, test_bu_id),
            params={'session_id': isolated_session_id, 'limit': 1, 'offset': 0},
        )
        page_2 = test_client.get(
            self._base_url(test_tenant_id, test_bu_id),
            params={'session_id': isolated_session_id, 'limit': 1, 'offset': 1},
        )

        # Assert — both pages return exactly one item, the items differ, and
        # both belong to the isolated session
        assert page_1.status_code == 200
        assert page_2.status_code == 200
        page_1_tags = page_1.json()['search_tags']
        page_2_tags = page_2.json()['search_tags']
        assert len(page_1_tags) == 1
        assert len(page_2_tags) == 1
        assert page_1_tags[0]['id'] != page_2_tags[0]['id']
        for tag in (page_1_tags[0], page_2_tags[0]):
            assert tag['id'] in created_ids

    def test_update_search_tag_name(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
        search_session_id: str,
        crawled_profile_id: str,
    ):
        # Arrange
        created = self._create_tag(
            test_client,
            test_tenant_id,
            test_bu_id,
            app_user,
            search_session_id,
            crawled_profile_id,
            'Original Tag',
        )
        tag_id = created['id']

        # Act
        response = test_client.patch(
            f'{self._base_url(test_tenant_id, test_bu_id)}/{tag_id}',
            json={'tag_name': 'Updated Tag'},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data['search_tag']['id'] == tag_id
        assert data['search_tag']['tag_name'] == 'Updated Tag'

    def test_update_search_tag_not_found(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
    ):
        # Act
        response = test_client.patch(
            f'{self._base_url(test_tenant_id, test_bu_id)}/stag_nonexistent',
            json={'tag_name': 'Should Not Apply'},
        )

        # Assert
        assert response.status_code == 404

    def test_delete_search_tag(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
        app_user: str,
        search_session_id: str,
        crawled_profile_id: str,
    ):
        # Arrange
        created = self._create_tag(
            test_client,
            test_tenant_id,
            test_bu_id,
            app_user,
            search_session_id,
            crawled_profile_id,
            'To Be Deleted',
        )
        tag_id = created['id']

        # Act
        response = test_client.delete(
            f'{self._base_url(test_tenant_id, test_bu_id)}/{tag_id}',
        )

        # Assert
        assert response.status_code == 204

    def test_delete_search_tag_not_found(
        self,
        test_client: TestClient,
        test_tenant_id: str,
        test_bu_id: str,
    ):
        # Act
        response = test_client.delete(
            f'{self._base_url(test_tenant_id, test_bu_id)}/stag_nonexistent',
        )

        # Assert
        assert response.status_code == 404
