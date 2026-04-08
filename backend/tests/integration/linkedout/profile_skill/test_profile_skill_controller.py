# SPDX-License-Identifier: Apache-2.0
import uuid
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

class TestProfileSkillControllerIntegration:

    @pytest.fixture
    def app_user(self, seeded_data: dict):
        return seeded_data['app_user'][0]

    @pytest.fixture
    def crawled_profile(self, test_client: TestClient, app_user):
        test_url = f"https://linkedin.com/in/test-{uuid.uuid4()}"
        payload = {
            'linkedin_url': test_url,
            'data_source': 'test_script',
            'first_name': 'TestProfileForSkill',
            'source_app_user_id': app_user.id
        }
        res = test_client.post('/crawled-profiles', json=payload, headers={'X-App-User-Id': app_user.id})
        return res.json()['crawled_profile']['id']

    @pytest.fixture
    def base_url(self):
        return "/profile-skills"

    def test_create_profile_skill(self, test_client: TestClient, crawled_profile: str, base_url: str):
        payload = {
            'crawled_profile_id': crawled_profile,
            'skill_name': 'Python',
            'endorsement_count': 10
        }
        res = test_client.post(base_url, json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data['profile_skill']['skill_name'] == 'Python'
        assert data['profile_skill']['endorsement_count'] == 10

    def test_get_profile_skill_by_id(self, test_client: TestClient, crawled_profile: str, base_url: str, app_user):
        payload = {
            'crawled_profile_id': crawled_profile,
            'skill_name': 'Java'
        }
        create_res = test_client.post(base_url, json=payload)
        entity_id = create_res.json()['profile_skill']['id']

        res = test_client.get(f"{base_url}/{entity_id}", headers={'X-App-User-Id': app_user.id})
        assert res.status_code == 200
        assert res.json()['profile_skill']['id'] == entity_id

    def test_update_profile_skill(self, test_client: TestClient, crawled_profile: str, base_url: str):
        payload = {
            'crawled_profile_id': crawled_profile,
            'skill_name': 'C++'
        }
        create_res = test_client.post(base_url, json=payload)
        entity_id = create_res.json()['profile_skill']['id']

        res = test_client.patch(
            f"{base_url}/{entity_id}",
            json={'endorsement_count': 42}
        )
        assert res.status_code == 200
        assert res.json()['profile_skill']['endorsement_count'] == 42

    def test_delete_profile_skill(self, test_client: TestClient, crawled_profile: str, base_url: str):
        payload = {
            'crawled_profile_id': crawled_profile,
            'skill_name': 'Ruby'
        }
        create_res = test_client.post(base_url, json=payload)
        entity_id = create_res.json()['profile_skill']['id']

        res = test_client.delete(f"{base_url}/{entity_id}")
        assert res.status_code == 204
