# SPDX-License-Identifier: Apache-2.0
"""Live integration test for enrich endpoint — real DB + real embeddings."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text


@pytest.mark.live_llm
class TestEnrichLiveIntegration:
    """Full enrichment flow: real Postgres, real EmbeddingProvider, no mocks."""

    @pytest.fixture
    def app_user(self, seeded_data: dict):
        return seeded_data['app_user'][0].id

    @pytest.fixture
    def headers(self, app_user: str):
        return {'X-App-User-Id': app_user}

    @pytest.fixture
    def created_profile(self, test_client: TestClient, headers: dict):
        payload = {
            'linkedin_url': f'https://linkedin.com/in/enrich-live-{uuid.uuid4()}',
            'data_source': 'test_script',
            'first_name': 'Live',
            'last_name': 'EnrichTest',
            'full_name': 'Live EnrichTest',
            'headline': 'Senior Engineer at BigCorp',
            'source_app_user_id': headers['X-App-User-Id'],
        }
        res = test_client.post('/crawled-profiles', json=payload, headers=headers)
        assert res.status_code == 201
        return res.json()['crawled_profile']

    def test_enrich_creates_rows_and_real_embedding(
        self, test_client: TestClient, headers: dict, created_profile: dict,
        integration_db_session,
    ):
        """Enrich with real EmbeddingProvider: structured rows + real embedding vector."""
        profile_id = created_profile['id']

        payload = {
            'experiences': [
                {
                    'position': 'Senior Software Engineer',
                    'company_name': 'Google',
                    'company_linkedin_url': 'https://www.linkedin.com/company/google',
                    'start_year': 2020,
                    'start_month': 6,
                    'is_current': True,
                    'location': 'Mountain View, CA',
                    'description': 'Working on distributed systems and ML infrastructure',
                },
                {
                    'position': 'Software Engineer',
                    'company_name': 'Microsoft',
                    'start_year': 2017,
                    'start_month': 1,
                    'end_year': 2020,
                    'end_month': 5,
                },
            ],
            'educations': [
                {
                    'school_name': 'Stanford University',
                    'degree': 'MS',
                    'field_of_study': 'Computer Science',
                    'start_year': 2015,
                    'end_year': 2017,
                },
            ],
            'skills': ['Python', 'Distributed Systems', 'Machine Learning', 'Kubernetes'],
        }

        res = test_client.post(
            f'/crawled-profiles/{profile_id}/enrich',
            json=payload,
            headers=headers,
        )

        assert res.status_code == 200
        data = res.json()
        assert data['experiences_created'] == 2
        assert data['educations_created'] == 1
        assert data['skills_created'] == 4

        # Verify profile state in DB
        row = integration_db_session.execute(
            text("""
                SELECT has_enriched_data,
                       embedding_openai IS NOT NULL as has_embedding,
                       search_vector IS NOT NULL as has_search_vector,
                       search_vector
                FROM crawled_profile WHERE id = :pid
            """),
            {'pid': profile_id},
        ).mappings().one()

        assert row['has_enriched_data'] is True
        assert row['has_embedding'] is True, 'Real embedding should be generated'
        assert row['has_search_vector'] is True

        # search_vector should contain key terms
        sv = row['search_vector']
        assert 'Google' in sv
        assert 'Senior Software Engineer' in sv
        assert 'Live EnrichTest' in sv

        # Verify experience rows
        exps = integration_db_session.execute(
            text("SELECT position, company_name FROM experience WHERE crawled_profile_id = :pid ORDER BY start_year"),
            {'pid': profile_id},
        ).mappings().all()
        assert len(exps) == 2
        assert exps[0]['company_name'] == 'Microsoft'
        assert exps[1]['company_name'] == 'Google'

        # Verify education rows
        edus = integration_db_session.execute(
            text("SELECT school_name, degree FROM education WHERE crawled_profile_id = :pid"),
            {'pid': profile_id},
        ).mappings().all()
        assert len(edus) == 1
        assert edus[0]['school_name'] == 'Stanford University'

        # Verify skill rows
        skills = integration_db_session.execute(
            text("SELECT skill_name FROM profile_skill WHERE crawled_profile_id = :pid ORDER BY skill_name"),
            {'pid': profile_id},
        ).mappings().all()
        assert len(skills) == 4
        skill_names = [s['skill_name'] for s in skills]
        assert 'Python' in skill_names
        assert 'Machine Learning' in skill_names
