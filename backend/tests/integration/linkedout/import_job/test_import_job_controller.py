# SPDX-License-Identifier: Apache-2.0
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

class TestImportJobControllerIntegration:

    @pytest.fixture
    def app_user(self, seeded_data: dict):
        return seeded_data['app_user'][0]

    @pytest.fixture
    def base_url(self, test_tenant_id: str, test_bu_id: str):
        return f"/tenants/{test_tenant_id}/bus/{test_bu_id}/import-jobs"

    def test_create_import_job(self, test_client: TestClient, app_user, base_url: str):
        payload = {
            'app_user_id': app_user.id,
            'source_type': 'linkedin_csv',
            'file_name': 'contacts.csv',
            'file_size_bytes': 1024,
            'status': 'pending'
        }
        res = test_client.post(base_url, json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data['import_job']['source_type'] == 'linkedin_csv'
        assert data['import_job']['file_name'] == 'contacts.csv'

    def test_get_import_job_by_id(self, test_client: TestClient, app_user, base_url: str):
        payload = {
            'app_user_id': app_user.id,
            'source_type': 'google_contacts'
        }
        create_res = test_client.post(base_url, json=payload)
        entity_id = create_res.json()['import_job']['id']

        res = test_client.get(f"{base_url}/{entity_id}")
        assert res.status_code == 200
        assert res.json()['import_job']['id'] == entity_id

    def test_update_import_job(self, test_client: TestClient, app_user, base_url: str):
        payload = {
            'app_user_id': app_user.id,
            'source_type': 'icloud'
        }
        create_res = test_client.post(base_url, json=payload)
        entity_id = create_res.json()['import_job']['id']

        res = test_client.patch(
            f"{base_url}/{entity_id}",
            json={'status': 'completed', 'total_records': 100}
        )
        assert res.status_code == 200
        assert res.json()['import_job']['status'] == 'completed'
        assert res.json()['import_job']['total_records'] == 100

    def test_delete_import_job(self, test_client: TestClient, app_user, base_url: str):
        payload = {
            'app_user_id': app_user.id,
            'source_type': 'office'
        }
        create_res = test_client.post(base_url, json=payload)
        entity_id = create_res.json()['import_job']['id']

        res = test_client.delete(f"{base_url}/{entity_id}")
        assert res.status_code == 204
