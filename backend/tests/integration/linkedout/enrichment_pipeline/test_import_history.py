# SPDX-License-Identifier: Apache-2.0
"""Integration tests for import history endpoints (via import_jobs_router)."""
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


class TestImportHistory:
    """Tests for GET /import-jobs (list) and GET /import-jobs/{id} (detail)."""

    @pytest.fixture
    def app_user(self, seeded_data: dict):
        return seeded_data['app_user'][0]

    @pytest.fixture
    def base_url(self, test_tenant_id: str, test_bu_id: str):
        return f'/tenants/{test_tenant_id}/bus/{test_bu_id}/import-jobs'

    @pytest.fixture
    def three_import_jobs(self, test_client: TestClient, app_user, base_url: str):
        """Create 3 import jobs and return their IDs."""
        ids = []
        for i in range(3):
            payload = {
                'app_user_id': app_user.id,
                'source_type': 'linkedin_csv',
                'file_name': f'connections_{i}.csv',
                'file_size_bytes': 1000 * (i + 1),
                'status': 'completed',
                'total_records': 10 * (i + 1),
                'parsed_count': 10 * (i + 1),
                'matched_count': 5 * (i + 1),
                'new_count': 5 * (i + 1),
            }
            res = test_client.post(base_url, json=payload)
            assert res.status_code == 201, res.text
            ids.append(res.json()['import_job']['id'])
        return ids

    def test_import_history_list_descending(
        self, test_client: TestClient, base_url: str, three_import_jobs: list[str],
    ):
        """Create 3 import jobs → list returns them in descending order."""
        res = test_client.get(base_url)
        assert res.status_code == 200
        data = res.json()

        jobs = data['import_jobs']
        assert len(jobs) >= 3

        # Most recently created should be first (DESC by created_at)
        job_ids = [j['id'] for j in jobs]
        for job_id in three_import_jobs:
            assert job_id in job_ids

        # Verify descending order by checking created_at
        created_dates = [j['created_at'] for j in jobs]
        assert created_dates == sorted(created_dates, reverse=True)

    def test_import_history_detail(
        self, test_client: TestClient, base_url: str, three_import_jobs: list[str],
    ):
        """Single import job returns full counters."""
        job_id = three_import_jobs[0]
        res = test_client.get(f'{base_url}/{job_id}')
        assert res.status_code == 200
        job = res.json()['import_job']
        assert job['id'] == job_id
        assert job['source_type'] == 'linkedin_csv'
        assert 'total_records' in job
        assert 'parsed_count' in job
        assert 'matched_count' in job
        assert 'new_count' in job
        assert 'failed_count' in job

    def test_import_history_pagination(
        self, test_client: TestClient, base_url: str, three_import_jobs: list[str],
    ):
        """Verify pagination parameters work."""
        res = test_client.get(f'{base_url}?limit=2&offset=0')
        assert res.status_code == 200
        data = res.json()
        assert len(data['import_jobs']) <= 2
        assert data['limit'] == 2
        assert data['offset'] == 0
        assert data['total'] >= 3
