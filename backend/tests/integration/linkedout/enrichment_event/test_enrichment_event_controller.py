# SPDX-License-Identifier: Apache-2.0
import uuid
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

class TestEnrichmentEventControllerIntegration:

    @pytest.fixture
    def app_user(self, seeded_data: dict):
        return seeded_data['app_user'][0]

    @pytest.fixture
    def crawled_profile(self, test_client: TestClient, app_user):
        test_url = f"https://linkedin.com/in/test-{uuid.uuid4()}"
        payload = {
            'linkedin_url': test_url,
            'data_source': 'test_script',
            'first_name': 'TestProfileForEnrichment',
            'source_app_user_id': app_user.id
        }
        res = test_client.post('/crawled-profiles', json=payload, headers={'X-App-User-Id': app_user.id})
        return res.json()['crawled_profile']['id']

    @pytest.fixture
    def base_url(self, test_tenant_id: str, test_bu_id: str):
        return f"/tenants/{test_tenant_id}/bus/{test_bu_id}/enrichment-events"

    def test_create_enrichment_event(self, test_client: TestClient, app_user, crawled_profile: str, base_url: str):
        payload = {
            'app_user_id': app_user.id,
            'crawled_profile_id': crawled_profile,
            'event_type': 'crawled',
            'enrichment_mode': 'platform',
            'crawler_name': 'test_crawler',
            'cost_estimate_usd': 0.05
        }
        res = test_client.post(base_url, json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data['enrichment_event']['crawler_name'] == 'test_crawler'
        assert data['enrichment_event']['event_type'] == 'crawled'

    def test_get_enrichment_event_by_id(self, test_client: TestClient, app_user, crawled_profile: str, base_url: str):
        payload = {
            'app_user_id': app_user.id,
            'crawled_profile_id': crawled_profile,
            'event_type': 'cache_hit',
            'enrichment_mode': 'byok'
        }
        create_res = test_client.post(base_url, json=payload)
        entity_id = create_res.json()['enrichment_event']['id']

        res = test_client.get(f"{base_url}/{entity_id}")
        assert res.status_code == 200
        assert res.json()['enrichment_event']['id'] == entity_id

    def test_update_enrichment_event(self, test_client: TestClient, app_user, crawled_profile: str, base_url: str):
        payload = {
            'app_user_id': app_user.id,
            'crawled_profile_id': crawled_profile,
            'event_type': 'crawled',
            'enrichment_mode': 'platform',
            'cost_estimate_usd': 0.01
        }
        create_res = test_client.post(base_url, json=payload)
        entity_id = create_res.json()['enrichment_event']['id']

        res = test_client.patch(
            f"{base_url}/{entity_id}",
            json={'cost_estimate_usd': 0.10}
        )
        assert res.status_code == 200
        assert res.json()['enrichment_event']['cost_estimate_usd'] == 0.10

    def test_delete_enrichment_event(self, test_client: TestClient, app_user, crawled_profile: str, base_url: str):
        payload = {
            'app_user_id': app_user.id,
            'crawled_profile_id': crawled_profile,
            'event_type': 'failed',
            'enrichment_mode': 'platform'
        }
        create_res = test_client.post(base_url, json=payload)
        entity_id = create_res.json()['enrichment_event']['id']

        res = test_client.delete(f"{base_url}/{entity_id}")
        assert res.status_code == 204
