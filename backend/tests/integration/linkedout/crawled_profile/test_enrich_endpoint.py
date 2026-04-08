# SPDX-License-Identifier: Apache-2.0
"""Integration tests for POST /crawled-profiles/{id}/enrich endpoint."""
import uuid
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


class TestEnrichEndpointIntegration:

    @pytest.fixture
    def app_user(self, seeded_data: dict):
        return seeded_data['app_user'][0].id

    @pytest.fixture
    def headers(self, app_user: str):
        return {'X-App-User-Id': app_user}

    @pytest.fixture
    def created_profile(self, test_client: TestClient, headers: dict):
        """Create a crawled profile for enrichment tests."""
        payload = {
            'linkedin_url': f'https://linkedin.com/in/enrich-test-{uuid.uuid4()}',
            'data_source': 'test_script',
            'first_name': 'Enrich',
            'last_name': 'Test',
            'full_name': 'Enrich Test',
            'headline': 'Software Engineer at TestCo',
            'source_app_user_id': headers['X-App-User-Id'],
        }
        res = test_client.post('/crawled-profiles', json=payload, headers=headers)
        assert res.status_code == 201
        return res.json()['crawled_profile']

    def _enrich_payload(self):
        return {
            'experiences': [
                {
                    'position': 'Software Engineer',
                    'company_name': 'TestCo',
                    'start_year': 2020,
                    'start_month': 3,
                    'end_year': 2023,
                    'end_month': 6,
                    'is_current': False,
                },
            ],
            'educations': [
                {
                    'school_name': 'Test University',
                    'degree': 'BS',
                    'field_of_study': 'Computer Science',
                    'start_year': 2016,
                    'end_year': 2020,
                },
            ],
            'skills': ['Python', 'FastAPI', 'SQLAlchemy'],
        }

    @patch('linkedout.crawled_profile.controllers.crawled_profile_controller.get_embedding_provider')
    def test_enrich_creates_structured_rows(
        self, mock_emb_cls, test_client: TestClient, headers: dict, created_profile: dict,
    ):
        """Enrich creates experience, education, skill rows and sets has_enriched_data."""
        mock_provider = MagicMock()
        mock_provider.embed_single.return_value = [0.1] * 1536
        mock_provider.model_name.return_value = 'text-embedding-3-small'
        mock_provider.dimension.return_value = 1536
        mock_emb_cls.return_value = mock_provider

        profile_id = created_profile['id']
        res = test_client.post(
            f'/crawled-profiles/{profile_id}/enrich',
            json=self._enrich_payload(),
            headers=headers,
        )

        assert res.status_code == 200
        data = res.json()
        assert data['experiences_created'] == 1
        assert data['educations_created'] == 1
        assert data['skills_created'] == 3

        # Verify profile was updated
        profile_res = test_client.get(f'/crawled-profiles/{profile_id}', headers=headers)
        profile = profile_res.json()['crawled_profile']
        assert profile['has_enriched_data'] is True

    @patch('linkedout.crawled_profile.controllers.crawled_profile_controller.get_embedding_provider')
    def test_enrich_idempotent(
        self, mock_emb_cls, test_client: TestClient, headers: dict, created_profile: dict,
    ):
        """Calling enrich twice doesn't double rows."""
        mock_provider = MagicMock()
        mock_provider.embed_single.return_value = [0.1] * 1536
        mock_provider.model_name.return_value = 'text-embedding-3-small'
        mock_provider.dimension.return_value = 1536
        mock_emb_cls.return_value = mock_provider

        profile_id = created_profile['id']
        payload = self._enrich_payload()

        # First call
        res1 = test_client.post(
            f'/crawled-profiles/{profile_id}/enrich', json=payload, headers=headers,
        )
        assert res1.status_code == 200

        # Second call — same data
        res2 = test_client.post(
            f'/crawled-profiles/{profile_id}/enrich', json=payload, headers=headers,
        )
        assert res2.status_code == 200
        data = res2.json()
        assert data['experiences_created'] == 1
        assert data['educations_created'] == 1
        assert data['skills_created'] == 3

    @patch('linkedout.crawled_profile.controllers.crawled_profile_controller.get_embedding_provider')
    def test_enrich_nonexistent_profile_404(
        self, mock_emb_cls, test_client: TestClient, headers: dict,
    ):
        """Non-existent crawled_profile_id returns 404."""
        mock_emb_cls.return_value = MagicMock()

        res = test_client.post(
            '/crawled-profiles/cp_nonexistent_xxx/enrich',
            json={'experiences': [], 'educations': [], 'skills': []},
            headers=headers,
        )
        assert res.status_code == 404

    @patch('linkedout.crawled_profile.controllers.crawled_profile_controller.get_embedding_provider')
    def test_enrich_empty_payload(
        self, mock_emb_cls, test_client: TestClient, headers: dict, created_profile: dict,
    ):
        """Empty arrays: has_enriched_data = true, 0 rows (Q9)."""
        mock_provider = MagicMock()
        mock_provider.embed_single.return_value = [0.1] * 1536
        mock_provider.model_name.return_value = 'text-embedding-3-small'
        mock_provider.dimension.return_value = 1536
        mock_emb_cls.return_value = mock_provider

        profile_id = created_profile['id']
        res = test_client.post(
            f'/crawled-profiles/{profile_id}/enrich',
            json={'experiences': [], 'educations': [], 'skills': []},
            headers=headers,
        )

        assert res.status_code == 200
        data = res.json()
        assert data['experiences_created'] == 0
        assert data['educations_created'] == 0
        assert data['skills_created'] == 0

        # Verify has_enriched_data is still true
        profile_res = test_client.get(f'/crawled-profiles/{profile_id}', headers=headers)
        assert profile_res.json()['crawled_profile']['has_enriched_data'] is True
