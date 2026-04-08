# SPDX-License-Identifier: Apache-2.0
import uuid
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

class TestCrawledProfileControllerIntegration:

    @pytest.fixture
    def app_user(self, seeded_data: dict):
        return seeded_data['app_user'][0].id

    def test_create_crawled_profile(self, test_client: TestClient, app_user: str):
        test_url = f"https://linkedin.com/in/test-{uuid.uuid4()}"
        payload = {
            'linkedin_url': test_url,
            'data_source': 'test_script',
            'first_name': 'Test',
            'last_name': 'Profile',
            'source_app_user_id': app_user
        }
        res = test_client.post('/crawled-profiles', json=payload, headers={'X-App-User-Id': app_user})
        assert res.status_code == 201
        data = res.json()
        assert data['crawled_profile']['linkedin_url'] == test_url

    def test_get_crawled_profile_by_id(self, test_client: TestClient, app_user: str):
        test_url = f"https://linkedin.com/in/test-{uuid.uuid4()}"
        payload = {
            'linkedin_url': test_url,
            'data_source': 'test_script',
            'first_name': 'Test2',
            'source_app_user_id': app_user
        }
        create_res = test_client.post('/crawled-profiles', json=payload, headers={'X-App-User-Id': app_user})
        entity_id = create_res.json()['crawled_profile']['id']

        res = test_client.get(f'/crawled-profiles/{entity_id}', headers={'X-App-User-Id': app_user})
        assert res.status_code == 200
        assert res.json()['crawled_profile']['id'] == entity_id

    def test_update_crawled_profile(self, test_client: TestClient, app_user: str):
        test_url = f"https://linkedin.com/in/test-{uuid.uuid4()}"
        payload = {
            'linkedin_url': test_url,
            'data_source': 'test_script',
            'first_name': 'UpdateMe',
            'source_app_user_id': app_user
        }
        create_res = test_client.post('/crawled-profiles', json=payload, headers={'X-App-User-Id': app_user})
        entity_id = create_res.json()['crawled_profile']['id']

        res = test_client.patch(
            f'/crawled-profiles/{entity_id}',
            json={'first_name': 'Updated'},
            headers={'X-App-User-Id': app_user}
        )
        assert res.status_code == 200
        assert res.json()['crawled_profile']['first_name'] == 'Updated'

    def test_delete_crawled_profile(self, test_client: TestClient, app_user: str):
        test_url = f"https://linkedin.com/in/test-{uuid.uuid4()}"
        payload = {
            'linkedin_url': test_url,
            'data_source': 'test_script',
            'first_name': 'DeleteMe',
            'source_app_user_id': app_user
        }
        create_res = test_client.post('/crawled-profiles', json=payload, headers={'X-App-User-Id': app_user})
        entity_id = create_res.json()['crawled_profile']['id']

        res = test_client.delete(f'/crawled-profiles/{entity_id}', headers={'X-App-User-Id': app_user})
        assert res.status_code == 204
