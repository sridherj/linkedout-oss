# SPDX-License-Identifier: Apache-2.0
import uuid
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

class TestExperienceControllerIntegration:

    @pytest.fixture
    def app_user(self, seeded_data: dict):
        return seeded_data['app_user'][0]

    @pytest.fixture
    def crawled_profile(self, test_client: TestClient, app_user):
        test_url = f"https://linkedin.com/in/test-{uuid.uuid4()}"
        payload = {
            'linkedin_url': test_url,
            'data_source': 'test_script',
            'first_name': 'TestProfileForExperience',
            'source_app_user_id': app_user.id
        }
        res = test_client.post('/crawled-profiles', json=payload, headers={'X-App-User-Id': app_user.id})
        return res.json()['crawled_profile']['id']

    @pytest.fixture
    def base_url(self):
        return "/experiences"

    def test_create_experience(self, test_client: TestClient, crawled_profile: str, base_url: str):
        payload = {
            'crawled_profile_id': crawled_profile,
            'position': 'Software Engineer',
            'company_name': 'TestCorp',
            'employment_type': 'Full-time'
        }
        res = test_client.post(base_url, json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data['experience']['position'] == 'Software Engineer'
        assert data['experience']['company_name'] == 'TestCorp'

    def test_get_experience_by_id(self, test_client: TestClient, crawled_profile: str, base_url: str, app_user):
        payload = {
            'crawled_profile_id': crawled_profile,
            'position': 'Senior Engineer'
        }
        create_res = test_client.post(base_url, json=payload)
        entity_id = create_res.json()['experience']['id']

        res = test_client.get(f"{base_url}/{entity_id}", headers={'X-App-User-Id': app_user.id})
        assert res.status_code == 200
        assert res.json()['experience']['id'] == entity_id

    def test_update_experience(self, test_client: TestClient, crawled_profile: str, base_url: str):
        payload = {
            'crawled_profile_id': crawled_profile,
            'position': 'Engineer'
        }
        create_res = test_client.post(base_url, json=payload)
        entity_id = create_res.json()['experience']['id']

        res = test_client.patch(
            f"{base_url}/{entity_id}",
            json={'position': 'Lead Engineer'}
        )
        assert res.status_code == 200
        assert res.json()['experience']['position'] == 'Lead Engineer'

    def test_delete_experience(self, test_client: TestClient, crawled_profile: str, base_url: str):
        payload = {
            'crawled_profile_id': crawled_profile,
            'position': 'To Delete'
        }
        create_res = test_client.post(base_url, json=payload)
        entity_id = create_res.json()['experience']['id']

        res = test_client.delete(f"{base_url}/{entity_id}")
        assert res.status_code == 204
