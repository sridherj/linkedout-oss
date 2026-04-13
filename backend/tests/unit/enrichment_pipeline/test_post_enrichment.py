# SPDX-License-Identifier: Apache-2.0
"""Unit tests for PostEnrichmentService."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from linkedout.enrichment_pipeline.post_enrichment import PostEnrichmentService


def _make_apify_profile(**overrides) -> dict:
    """Create a minimal Apify profile response."""
    base = {
        'publicIdentifier': 'johndoe',
        'linkedinUrl': 'https://www.linkedin.com/in/johndoe',
        'firstName': 'John',
        'lastName': 'Doe',
        'headline': 'Senior Engineer at Acme',
        'about': 'Building great things',
        'location': {
            'linkedinText': 'San Francisco, CA',
            'parsed': {
                'city': 'San Francisco',
                'state': 'California',
                'country': 'United States',
                'countryCode': 'US',
            },
        },
        'connectionsCount': 500,
        'followerCount': 600,
        'openToWork': False,
        'premium': True,
        'currentPosition': [
            {
                'companyName': 'Acme Corp',
                'companyLinkedinUrl': 'https://www.linkedin.com/company/acme-corp/',
                'companyId': '12345',
            }
        ],
        'experience': [
            {
                'position': 'Senior Engineer',
                'companyName': 'Acme Corp',
                'companyLinkedinUrl': 'https://www.linkedin.com/company/acme-corp/',
                'companyUniversalName': 'acme-corp',
                'employmentType': 'Full-time',
                'startDate': {'month': 'Jan', 'year': 2020, 'text': 'Jan 2020'},
                'endDate': {'text': 'Present'},
                'location': 'San Francisco',
                'description': 'Building platform services',
            },
            {
                'position': 'Engineer',
                'companyName': 'Startup Inc',
                'startDate': {'month': 'Jun', 'year': 2017, 'text': 'Jun 2017'},
                'endDate': {'month': 'Dec', 'year': 2019, 'text': 'Dec 2019'},
            },
        ],
        'education': [
            {
                'schoolName': 'MIT',
                'degree': 'BS',
                'fieldOfStudy': 'Computer Science',
                'startDate': {'year': 2013},
                'endDate': {'year': 2017},
            }
        ],
        'skills': [
            {'name': 'Python'},
            {'name': 'FastAPI'},
            {'name': 'PostgreSQL'},
        ],
        'profilePicture': {
            'url': 'https://media.licdn.com/photo.jpg',
        },
    }
    base.update(overrides)
    return base


class TestPostEnrichmentService:
    """Tests for the PostEnrichmentService processing pipeline."""

    def _make_service(self, session=None, embedding_provider=None):
        session = session or MagicMock()
        # Mock _preload_companies to avoid DB calls
        with patch.object(PostEnrichmentService, '_preload_companies'):
            svc = PostEnrichmentService(session, embedding_provider)
        svc._company_by_canonical = {}
        return svc

    def _make_profile_mock(self):
        """Create a profile mock with string attributes for search_vector compatibility."""
        profile = MagicMock()
        profile.has_enriched_data = False
        profile.id = 'cp_001'
        profile.full_name = None
        profile.headline = None
        profile.about = None
        profile.search_vector = None
        profile.embedding = None
        return profile

    @patch('linkedout.enrichment_pipeline.post_enrichment.ProfileEnrichmentService')
    def test_updates_crawled_profile_fields(self, mock_enrich_cls):
        session = MagicMock()
        profile = self._make_profile_mock()

        session.execute.return_value.scalar_one_or_none.side_effect = [
            profile,  # First call: find profile by linkedin_url
            MagicMock(),  # enrichment event lookup
        ]

        svc = self._make_service(session)
        data = _make_apify_profile()

        svc.process_enrichment_result(data, 'ee_001', 'https://www.linkedin.com/in/johndoe')

        assert profile.first_name == 'John'
        assert profile.last_name == 'Doe'
        assert profile.full_name == 'John Doe'
        assert profile.headline == 'Senior Engineer at Acme'
        assert profile.has_enriched_data is True
        assert profile.data_source == 'apify'
        assert profile.raw_profile is not None

    @patch('linkedout.enrichment_pipeline.post_enrichment.ProfileEnrichmentService')
    def test_delegates_to_enrich(self, mock_enrich_cls):
        """Verify process_enrichment_result delegates to ProfileEnrichmentService.enrich()."""
        session = MagicMock()
        profile = self._make_profile_mock()

        session.execute.return_value.scalar_one_or_none.side_effect = [
            profile, MagicMock(),
        ]

        mock_enrich_instance = MagicMock()
        mock_enrich_cls.return_value = mock_enrich_instance

        svc = self._make_service(session)
        data = _make_apify_profile()

        svc.process_enrichment_result(data, 'ee_001', 'https://www.linkedin.com/in/johndoe')

        # enrich() was called with profile id and the schema
        mock_enrich_instance.enrich.assert_called_once()
        args = mock_enrich_instance.enrich.call_args
        assert args[0][0] == 'cp_001'  # profile_id
        enrich_request = args[0][1]
        assert len(enrich_request.experiences) == 2
        assert len(enrich_request.educations) == 1
        assert len(enrich_request.skills) == 3

    @patch('linkedout.enrichment_pipeline.post_enrichment.ProfileEnrichmentService')
    def test_to_enrich_schema_produces_correct_experiences(self, mock_enrich_cls):
        """Verify _to_enrich_schema maps experience fields correctly."""
        svc = self._make_service()
        data = _make_apify_profile()

        result = svc._to_enrich_schema(data)
        assert len(result.experiences) == 2
        assert result.experiences[0].position == 'Senior Engineer'
        assert result.experiences[0].company_name == 'Acme Corp'
        assert result.experiences[0].is_current is True
        assert result.experiences[1].position == 'Engineer'

    @patch('linkedout.enrichment_pipeline.post_enrichment.ProfileEnrichmentService')
    def test_to_enrich_schema_maps_education(self, mock_enrich_cls):
        svc = self._make_service()
        data = _make_apify_profile()

        result = svc._to_enrich_schema(data)
        assert len(result.educations) == 1
        assert result.educations[0].school_name == 'MIT'
        assert result.educations[0].degree == 'BS'

    @patch('linkedout.enrichment_pipeline.post_enrichment.ProfileEnrichmentService')
    def test_to_enrich_schema_deduplicates_skills(self, mock_enrich_cls):
        svc = self._make_service()
        data = _make_apify_profile(
            skills=[{'name': 'Python'}, {'name': 'Python'}, {'name': 'Go'}],
            topSkills=['Python', 'Rust'],
        )

        result = svc._to_enrich_schema(data)
        # Python should appear once despite being in both skills and topSkills
        assert result.skills.count('Python') == 1
        assert 'Go' in result.skills
        assert 'Rust' in result.skills

    def test_cache_hit_skips_enrichment(self):
        session = MagicMock()
        profile = MagicMock()
        profile.has_enriched_data = True
        profile.last_crawled_at = datetime.now(timezone.utc) - timedelta(days=30)
        profile.id = 'cp_001'

        # First call returns the profile, second is event update
        mock_event = MagicMock()
        session.execute.return_value.scalar_one_or_none.side_effect = [
            profile, mock_event,
        ]

        svc = self._make_service(session)
        data = _make_apify_profile()

        svc.process_enrichment_result(data, 'ee_001', 'https://www.linkedin.com/in/johndoe')

        # Should NOT have updated the profile fields
        assert mock_event.event_type == 'cache_hit'

    @patch('linkedout.enrichment_pipeline.post_enrichment.ProfileEnrichmentService')
    @patch('linkedout.enrichment_pipeline.post_enrichment.resolve_company')
    def test_resolve_company_called_from_update_crawled_profile(self, mock_resolve, mock_enrich_cls):
        """Verify _update_crawled_profile uses the shared resolve_company utility."""
        session = MagicMock()
        profile = self._make_profile_mock()

        session.execute.return_value.scalar_one_or_none.side_effect = [
            profile, MagicMock(),
        ]

        mock_resolve.return_value = 'co_123'

        svc = self._make_service(session)
        data = _make_apify_profile()

        svc.process_enrichment_result(data, 'ee_001', 'https://www.linkedin.com/in/johndoe')

        mock_resolve.assert_called_once()
        assert profile.company_id == 'co_123'


class TestURLRedirectUpdate:
    """Tests for URL update behavior when Apify returns a redirected canonical URL (T6-T8)."""

    def _make_service(self, session=None, embedding_provider=None):
        session = session or MagicMock()
        with patch.object(PostEnrichmentService, '_preload_companies'):
            svc = PostEnrichmentService(session, embedding_provider)
        svc._company_by_canonical = {}
        return svc

    def _make_profile_mock(self, linkedin_url='https://www.linkedin.com/in/johndoe'):
        profile = MagicMock()
        profile.has_enriched_data = False
        profile.id = 'cp_001'
        profile.linkedin_url = linkedin_url
        profile.previous_linkedin_url = None
        profile.full_name = None
        profile.headline = None
        profile.about = None
        profile.search_vector = None
        profile.embedding = None
        return profile

    @patch('linkedout.enrichment_pipeline.post_enrichment.ProfileEnrichmentService')
    def test_t6_url_update_on_redirect(self, mock_enrich_cls):
        """T6: canonical_url differs from current — previous_linkedin_url set, linkedin_url updated."""
        session = MagicMock()
        profile = self._make_profile_mock('https://www.linkedin.com/in/vikas-khatana-web-developer')

        # First execute: find profile, second: check for unique conflict (None = no conflict),
        # third: enrichment event
        session.execute.return_value.scalar_one_or_none.side_effect = [
            profile,  # find profile by linkedin_url
            None,     # unique constraint check — no conflict
            MagicMock(),  # enrichment event
        ]

        svc = self._make_service(session)
        data = _make_apify_profile(linkedinUrl='https://www.linkedin.com/in/vikas-khatana')

        svc.process_enrichment_result(
            data, 'ee_001', 'https://www.linkedin.com/in/vikas-khatana-web-developer',
            canonical_url='https://www.linkedin.com/in/vikas-khatana',
        )

        assert profile.previous_linkedin_url == 'https://www.linkedin.com/in/vikas-khatana-web-developer'
        assert profile.linkedin_url == 'https://www.linkedin.com/in/vikas-khatana'

    @patch('linkedout.enrichment_pipeline.post_enrichment.ProfileEnrichmentService')
    def test_t7_no_redirect_previous_url_stays_none(self, mock_enrich_cls):
        """T7: No canonical_url — previous_linkedin_url unchanged (None)."""
        session = MagicMock()
        profile = self._make_profile_mock()

        session.execute.return_value.scalar_one_or_none.side_effect = [
            profile, MagicMock(),
        ]

        svc = self._make_service(session)
        data = _make_apify_profile()

        svc.process_enrichment_result(data, 'ee_001', 'https://www.linkedin.com/in/johndoe')

        assert profile.previous_linkedin_url is None

    @patch('linkedout.enrichment_pipeline.post_enrichment.ProfileEnrichmentService')
    def test_t8_unique_constraint_conflict_skips_update(self, mock_enrich_cls):
        """T8: Another profile already has the canonical URL — URL update skipped."""
        session = MagicMock()
        profile = self._make_profile_mock('https://www.linkedin.com/in/old-slug')

        # First execute: find profile, second: unique constraint check (conflict!),
        # third: enrichment event
        session.execute.return_value.scalar_one_or_none.side_effect = [
            profile,       # find profile by linkedin_url
            'cp_other',    # unique constraint check — conflict exists
            MagicMock(),   # enrichment event
        ]

        svc = self._make_service(session)
        data = _make_apify_profile()

        svc.process_enrichment_result(
            data, 'ee_001', 'https://www.linkedin.com/in/old-slug',
            canonical_url='https://www.linkedin.com/in/new-slug',
        )

        # URL should NOT have been updated
        assert profile.linkedin_url == 'https://www.linkedin.com/in/old-slug'
        assert profile.previous_linkedin_url is None
        # Profile should still be enriched (not skipped)
        assert profile.has_enriched_data is True


class TestEmbeddingTextFormat:
    """Test the embedding text builder from EmbeddingClient."""

    def test_build_embedding_text_full(self):
        from utilities.llm_manager.embedding_client import EmbeddingClient

        profile = {
            'full_name': 'Jane Smith',
            'headline': 'CTO at StartupX',
            'about': 'Building the future',
            'experiences': [
                {'company_name': 'StartupX', 'title': 'CTO'},
                {'company_name': 'BigCo', 'title': 'VP Eng'},
            ],
        }
        text = EmbeddingClient.build_embedding_text(profile)
        assert 'Jane Smith' in text
        assert 'CTO at StartupX' in text
        assert 'Experience: StartupX - CTO, BigCo - VP Eng' in text

    def test_build_embedding_text_minimal(self):
        from utilities.llm_manager.embedding_client import EmbeddingClient

        profile = {'full_name': 'John'}
        text = EmbeddingClient.build_embedding_text(profile)
        assert text == 'John'
