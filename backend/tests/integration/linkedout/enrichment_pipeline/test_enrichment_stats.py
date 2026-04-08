# SPDX-License-Identifier: Apache-2.0
"""Integration tests for enrichment stats endpoint."""
import uuid

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


class TestEnrichmentStats:
    """Tests for GET /enrichment/stats."""

    @pytest.fixture
    def app_user(self, seeded_data: dict):
        return seeded_data['app_user'][0]

    @pytest.fixture
    def crawled_profile(self, test_client: TestClient, app_user):
        test_url = f'https://linkedin.com/in/stats-test-{uuid.uuid4()}'
        payload = {
            'linkedin_url': test_url,
            'data_source': 'test_script',
            'first_name': 'StatsTestProfile',
            'source_app_user_id': app_user.id,
        }
        res = test_client.post('/crawled-profiles', json=payload, headers={'X-App-User-Id': app_user.id})
        return res.json()['crawled_profile']['id']

    @pytest.fixture
    def events_url(self, test_tenant_id: str, test_bu_id: str):
        return f'/tenants/{test_tenant_id}/bus/{test_bu_id}/enrichment-events'

    @pytest.fixture
    def stats_url(self, test_tenant_id: str, test_bu_id: str):
        return f'/tenants/{test_tenant_id}/bus/{test_bu_id}/enrichment/stats'

    def test_enrichment_stats_with_events(
        self, test_client: TestClient, app_user, crawled_profile: str,
        events_url: str, stats_url: str,
    ):
        """After enrichment events exist → stats aggregate correctly."""
        # Create some enrichment events of different types
        events = [
            {'event_type': 'crawled', 'enrichment_mode': 'platform', 'cost_estimate_usd': 0.004},
            {'event_type': 'crawled', 'enrichment_mode': 'platform', 'cost_estimate_usd': 0.004},
            {'event_type': 'cache_hit', 'enrichment_mode': 'platform', 'cost_estimate_usd': 0.0},
            {'event_type': 'failed', 'enrichment_mode': 'byok', 'cost_estimate_usd': 0.004},
            {'event_type': 'queued', 'enrichment_mode': 'platform', 'cost_estimate_usd': 0.004},
        ]

        for event in events:
            payload = {
                'app_user_id': app_user.id,
                'crawled_profile_id': crawled_profile,
                **event,
            }
            res = test_client.post(events_url, json=payload)
            assert res.status_code == 201, res.text

        # Now get stats
        res = test_client.get(stats_url)
        assert res.status_code == 200
        stats = res.json()

        # Validate aggregates (at minimum the events we just created)
        assert stats['total_enrichments'] >= 5
        assert stats['cache_hits'] >= 1
        assert stats['profiles_enriched'] >= 2
        assert stats['profiles_pending'] >= 1
        assert stats['profiles_failed'] >= 1
        assert stats['total_cost_usd'] >= 0.012
        assert stats['period'] == 'last_30_days'
        assert 0.0 <= stats['cache_hit_rate'] <= 1.0

    def test_enrichment_stats_empty(self, test_client: TestClient, test_bu_id: str):
        """Stats for a tenant with no events returns zeros."""
        url = f'/tenants/tnt_empty_{uuid.uuid4().hex[:8]}/bus/{test_bu_id}/enrichment/stats'
        res = test_client.get(url)
        assert res.status_code == 200
        stats = res.json()
        assert stats['total_enrichments'] == 0
        assert stats['cache_hits'] == 0
        assert stats['cache_hit_rate'] == 0.0
        assert stats['total_cost_usd'] == 0.0
