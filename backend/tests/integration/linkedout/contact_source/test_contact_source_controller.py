# SPDX-License-Identifier: Apache-2.0
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

class TestContactSourceControllerIntegration:

    @pytest.fixture
    def app_user(self, seeded_data: dict):
        return seeded_data['app_user'][0].id

    @pytest.fixture
    def import_job(self, test_client: TestClient, test_tenant_id: str, test_bu_id: str, app_user: str):
        # We need to discover the exact payload needed for import_job
        resp = test_client.post(f'/tenants/{test_tenant_id}/bus/{test_bu_id}/import-jobs', json={
            'app_user_id': app_user,
            'source_type': 'linkedin_csv',
            'status': 'pending',
            'total_records': 0
        })
        return resp.json()['import_job']['id']

    def test_create_contact_source_success(
        self, test_client: TestClient, test_tenant_id: str, test_bu_id: str, app_user: str, import_job: str
    ):
        payload = {
            'app_user_id': app_user,
            'import_job_id': import_job,
            'source_type': 'linkedin_csv',
            'source_file_name': 'test.csv',
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@example.com'
        }
        res = test_client.post(f'/tenants/{test_tenant_id}/bus/{test_bu_id}/contact-sources', json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data['contact_source']['first_name'] == 'John'

    def test_get_contact_source_by_id(
        self, test_client: TestClient, test_tenant_id: str, test_bu_id: str, app_user: str, import_job: str
    ):
        payload = {
            'app_user_id': app_user,
            'import_job_id': import_job,
            'source_type': 'linkedin_csv',
            'first_name': 'GetMe'
        }
        create_res = test_client.post(f'/tenants/{test_tenant_id}/bus/{test_bu_id}/contact-sources', json=payload)
        entity_id = create_res.json()['contact_source']['id']

        res = test_client.get(f'/tenants/{test_tenant_id}/bus/{test_bu_id}/contact-sources/{entity_id}')
        assert res.status_code == 200
        assert res.json()['contact_source']['id'] == entity_id

    def test_update_contact_source(
        self, test_client: TestClient, test_tenant_id: str, test_bu_id: str, app_user: str, import_job: str
    ):
        payload = {
            'app_user_id': app_user,
            'import_job_id': import_job,
            'source_type': 'linkedin_csv',
            'first_name': 'UpdateMe'
        }
        create_res = test_client.post(f'/tenants/{test_tenant_id}/bus/{test_bu_id}/contact-sources', json=payload)
        entity_id = create_res.json()['contact_source']['id']

        res = test_client.patch(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/contact-sources/{entity_id}',
            json={'first_name': 'Updated'}
        )
        assert res.status_code == 200
        assert res.json()['contact_source']['first_name'] == 'Updated'

    def test_delete_contact_source(
        self, test_client: TestClient, test_tenant_id: str, test_bu_id: str, app_user: str, import_job: str
    ):
        payload = {
            'app_user_id': app_user,
            'import_job_id': import_job,
            'source_type': 'linkedin_csv',
            'first_name': 'DeleteMe'
        }
        create_res = test_client.post(f'/tenants/{test_tenant_id}/bus/{test_bu_id}/contact-sources', json=payload)
        entity_id = create_res.json()['contact_source']['id']

        res = test_client.delete(f'/tenants/{test_tenant_id}/bus/{test_bu_id}/contact-sources/{entity_id}')
        assert res.status_code == 204
