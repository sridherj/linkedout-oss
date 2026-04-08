# SPDX-License-Identifier: Apache-2.0
import uuid
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

class TestEducationControllerIntegration:

    @pytest.fixture
    def app_user(self, seeded_data: dict):
        return seeded_data['app_user'][0].id

    @pytest.fixture
    def crawled_profile(self, test_client: TestClient, app_user: str):
        test_url = f"https://linkedin.com/in/test-{uuid.uuid4()}"
        payload = {
            'linkedin_url': test_url,
            'data_source': 'test_script',
            'first_name': 'TestProfileForEdu',
            'source_app_user_id': app_user
        }
        res = test_client.post('/crawled-profiles', json=payload, headers={'X-App-User-Id': app_user})
        return res.json()['crawled_profile']['id']

    def test_create_education(self, test_client: TestClient, crawled_profile: str):
        payload = {
            'crawled_profile_id': crawled_profile,
            'school_name': 'Test University',
            'degree': 'B.S.',
            'start_year': 2010,
            'end_year': 2014
        }
        res = test_client.post('/educations', json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data['education']['school_name'] == 'Test University'

    def test_get_education_by_id(self, test_client: TestClient, crawled_profile: str, app_user: str):
        payload = {
            'crawled_profile_id': crawled_profile,
            'school_name': 'Test University 2'
        }
        create_res = test_client.post('/educations', json=payload)
        entity_id = create_res.json()['education']['id']

        res = test_client.get(f'/educations/{entity_id}', headers={'X-App-User-Id': app_user})
        assert res.status_code == 200
        assert res.json()['education']['id'] == entity_id

    def test_update_education(self, test_client: TestClient, crawled_profile: str):
        payload = {
            'crawled_profile_id': crawled_profile,
            'school_name': 'Old School'
        }
        create_res = test_client.post('/educations', json=payload)
        entity_id = create_res.json()['education']['id']

        res = test_client.patch(
            f'/educations/{entity_id}',
            json={'school_name': 'New School'}
        )
        assert res.status_code == 200
        assert res.json()['education']['school_name'] == 'New School'

    def test_delete_education(self, test_client: TestClient, crawled_profile: str):
        payload = {
            'crawled_profile_id': crawled_profile,
            'school_name': 'Temp School'
        }
        create_res = test_client.post('/educations', json=payload)
        entity_id = create_res.json()['education']['id']

        res = test_client.delete(f'/educations/{entity_id}')
        assert res.status_code == 204
