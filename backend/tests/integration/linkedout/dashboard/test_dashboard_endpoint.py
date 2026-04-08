# SPDX-License-Identifier: Apache-2.0
"""Integration tests for dashboard endpoint against PostgreSQL."""
import pytest

pytestmark = pytest.mark.integration


class TestDashboardFullResponse:
    """GET /dashboard returns all 7 aggregate sections."""

    def test_full_dashboard(self, test_client, dashboard_test_data):
        data = dashboard_test_data
        url = f"/tenants/{data['tenant'].id}/bus/{data['bu'].id}/dashboard"

        response = test_client.get(url, headers={"X-App-User-Id": data['user_a'].id})

        assert response.status_code == 200
        body = response.json()

        assert body['total_connections'] == 20
        assert 'enrichment_status' in body
        assert 'industry_breakdown' in body
        assert 'seniority_distribution' in body
        assert 'location_top' in body
        assert 'top_companies' in body
        assert 'affinity_tier_distribution' in body
        assert 'network_sources' in body


class TestUserIsolation:
    """Different users see different dashboard data."""

    def test_user_b_sees_own_data(self, test_client, dashboard_test_data):
        data = dashboard_test_data
        url = f"/tenants/{data['tenant'].id}/bus/{data['bu'].id}/dashboard"

        response = test_client.get(url, headers={"X-App-User-Id": data['user_b'].id})

        assert response.status_code == 200
        body = response.json()
        assert body['total_connections'] == 5

    def test_user_a_different_from_user_b(self, test_client, dashboard_test_data):
        data = dashboard_test_data
        url = f"/tenants/{data['tenant'].id}/bus/{data['bu'].id}/dashboard"

        resp_a = test_client.get(url, headers={"X-App-User-Id": data['user_a'].id})
        resp_b = test_client.get(url, headers={"X-App-User-Id": data['user_b'].id})

        assert resp_a.json()['total_connections'] != resp_b.json()['total_connections']


class TestEmptyState:
    """User with no connections gets all zeros."""

    def test_empty_user(self, test_client, dashboard_test_data):
        data = dashboard_test_data
        url = f"/tenants/{data['tenant'].id}/bus/{data['bu'].id}/dashboard"

        response = test_client.get(url, headers={"X-App-User-Id": data['user_c'].id})

        assert response.status_code == 200
        body = response.json()
        assert body['total_connections'] == 0
        assert body['enrichment_status']['enriched'] == 0
        assert body['enrichment_status']['unenriched'] == 0
        assert body['enrichment_status']['enriched_pct'] == 0.0
        assert body['industry_breakdown'] == []
        assert body['network_sources'] == []


class TestEnrichmentAccuracy:
    """Enrichment counts match seeded data."""

    def test_enrichment_counts(self, test_client, dashboard_test_data):
        data = dashboard_test_data
        url = f"/tenants/{data['tenant'].id}/bus/{data['bu'].id}/dashboard"

        response = test_client.get(url, headers={"X-App-User-Id": data['user_a'].id})
        es = response.json()['enrichment_status']

        assert es['enriched'] == 10
        assert es['unenriched'] == 10
        assert es['total'] == 20
        assert es['enriched_pct'] == 50.0


class TestSourceAggregation:
    """Network sources unnest correctly."""

    def test_source_counts(self, test_client, dashboard_test_data):
        data = dashboard_test_data
        url = f"/tenants/{data['tenant'].id}/bus/{data['bu'].id}/dashboard"

        response = test_client.get(url, headers={"X-App-User-Id": data['user_a'].id})
        sources = {s['label']: s['count'] for s in response.json()['network_sources']}

        # All 20 have linkedin, first 10 also have gmail
        assert sources.get('linkedin') == 20
        assert sources.get('gmail') == 10
