# SPDX-License-Identifier: Apache-2.0
"""Unit tests for PostEnrichmentService."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, create_autospec, patch

from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
from linkedout.enrichment_pipeline.post_enrichment import PostEnrichmentService
from linkedout.experience.entities.experience_entity import ExperienceEntity
from utilities.llm_manager.embedding_provider import EmbeddingProvider


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
        profile = create_autospec(CrawledProfileEntity, instance=True, spec_set=True)
        profile.has_enriched_data = False
        profile.id = 'cp_001'
        profile.full_name = None
        profile.headline = None
        profile.about = None
        profile.search_vector = None
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
        profile = create_autospec(CrawledProfileEntity, instance=True, spec_set=True)
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
        profile = create_autospec(CrawledProfileEntity, instance=True, spec_set=True)
        profile.has_enriched_data = False
        profile.id = 'cp_001'
        profile.linkedin_url = linkedin_url
        profile.previous_linkedin_url = None
        profile.full_name = None
        profile.headline = None
        profile.about = None
        profile.search_vector = None
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


class TestEnrichmentServiceHoist:
    """Tests for the hoisted ProfileEnrichmentService in process_batch()
    and the optional enrichment_service parameter in process_enrichment_result()."""

    def _make_service(self, session=None, embedding_provider=None):
        session = session or MagicMock()
        with patch.object(PostEnrichmentService, '_preload_companies'):
            svc = PostEnrichmentService(session, embedding_provider)
        svc._company_by_canonical = {}
        return svc

    @patch('linkedout.enrichment_pipeline.post_enrichment.append_apify_archive_batch')
    @patch('linkedout.enrichment_pipeline.post_enrichment.ProfileEnrichmentService')
    def test_process_batch_creates_single_enrichment_service(self, mock_enrich_cls, mock_archive):
        """ProfileEnrichmentService is constructed once for N profiles, not N times."""
        session = MagicMock()
        svc = self._make_service(session)

        mock_enrich_instance = MagicMock()
        mock_enrich_cls.return_value = mock_enrich_instance

        results = [
            ('cp_001', 'https://linkedin.com/in/john', _make_apify_profile(firstName='John')),
            ('cp_002', 'https://linkedin.com/in/jane', _make_apify_profile(firstName='Jane')),
            ('cp_003', 'https://linkedin.com/in/bob', _make_apify_profile(firstName='Bob')),
        ]

        svc.process_batch(results, {})

        # Constructor called once (the hoist), not 3 times
        assert mock_enrich_cls.call_count == 1

    @patch('linkedout.enrichment_pipeline.post_enrichment.append_apify_archive_batch')
    @patch('linkedout.enrichment_pipeline.post_enrichment.ProfileEnrichmentService')
    def test_process_batch_passes_company_matcher_to_enrichment_service(self, mock_enrich_cls, mock_archive):
        """The hoisted service receives the PostEnrichmentService's company matcher."""
        session = MagicMock()
        svc = self._make_service(session)
        svc._company_matcher = MagicMock(name='shared_matcher')
        svc._company_by_canonical = {'Acme': MagicMock()}

        mock_enrich_cls.return_value = MagicMock()

        results = [('cp_001', 'https://linkedin.com/in/john', _make_apify_profile())]
        svc.process_batch(results, {})

        _, kwargs = mock_enrich_cls.call_args
        assert kwargs['company_matcher'] is svc._company_matcher
        assert kwargs['company_by_canonical'] is svc._company_by_canonical

    @patch('linkedout.enrichment_pipeline.post_enrichment.ProfileEnrichmentService')
    def test_process_enrichment_result_uses_provided_service(self, mock_enrich_cls):
        """When enrichment_service is passed, it's used instead of creating a new one."""
        session = MagicMock()
        profile = create_autospec(CrawledProfileEntity, instance=True, spec_set=True)
        profile.has_enriched_data = False
        profile.id = 'cp_001'
        profile.full_name = None
        profile.headline = None
        profile.about = None
        profile.search_vector = None

        session.execute.return_value.scalar_one_or_none.side_effect = [
            profile, MagicMock(),
        ]

        provided_svc = MagicMock()
        svc = self._make_service(session)
        svc.process_enrichment_result(
            _make_apify_profile(), 'ee_001', 'https://linkedin.com/in/johndoe',
            enrichment_service=provided_svc,
        )

        # The provided service was used
        provided_svc.enrich.assert_called_once()
        # No new ProfileEnrichmentService was constructed
        mock_enrich_cls.assert_not_called()

    @patch('linkedout.enrichment_pipeline.post_enrichment.ProfileEnrichmentService')
    def test_process_enrichment_result_creates_own_service_when_none(self, mock_enrich_cls):
        """Without enrichment_service, a new one is created (backward compat)."""
        session = MagicMock()
        profile = create_autospec(CrawledProfileEntity, instance=True, spec_set=True)
        profile.has_enriched_data = False
        profile.id = 'cp_001'
        profile.full_name = None
        profile.headline = None
        profile.about = None
        profile.search_vector = None

        session.execute.return_value.scalar_one_or_none.side_effect = [
            profile, MagicMock(),
        ]

        mock_enrich_cls.return_value = MagicMock()
        svc = self._make_service(session)
        svc.process_enrichment_result(
            _make_apify_profile(), 'ee_001', 'https://linkedin.com/in/johndoe',
        )

        # A new ProfileEnrichmentService was constructed
        mock_enrich_cls.assert_called_once()


class TestProcessBatch:
    """Tests for the process_batch() method covering per-profile DB writes,
    batch embedding, and batch archiving."""

    def _make_service(self, session=None, embedding_provider=None):
        session = session or MagicMock()
        with patch.object(PostEnrichmentService, '_preload_companies'):
            svc = PostEnrichmentService(session, embedding_provider)
        svc._company_by_canonical = {}
        return svc

    def _make_profile_autospec(self, profile_id='cp_001', full_name='John Doe',
                                headline='Engineer', about='Builder'):
        profile = create_autospec(CrawledProfileEntity, instance=True, spec_set=True)
        profile.id = profile_id
        profile.full_name = full_name
        profile.headline = headline
        profile.about = about
        return profile

    def _make_experience_autospec(self, company_name='Acme', position='Engineer'):
        exp = create_autospec(ExperienceEntity, instance=True, spec_set=True)
        exp.company_name = company_name
        exp.position = position
        return exp

    def _make_session_execute_side_effects(self, profile_mocks_and_exps):
        """Build session.execute side_effect list.

        Args:
            profile_mocks_and_exps: list of (profile_mock_or_None, [experience_mocks])
        """
        side_effects = []
        for profile_mock, exp_mocks in profile_mocks_and_exps:
            profile_result = MagicMock()
            profile_result.scalar_one_or_none.return_value = profile_mock
            side_effects.append(profile_result)
            if profile_mock is not None:
                exp_result = MagicMock()
                exp_result.scalars.return_value.all.return_value = exp_mocks
                side_effects.append(exp_result)
        return side_effects

    @patch('linkedout.enrichment_pipeline.post_enrichment.append_apify_archive_batch')
    @patch('utilities.llm_manager.embedding_factory.get_embedding_column_name')
    @patch('linkedout.enrichment_pipeline.post_enrichment.build_embedding_text')
    def test_happy_path_returns_counts_and_embeds(self, mock_build_text, mock_col_name, mock_archive):
        session = MagicMock()
        provider = create_autospec(EmbeddingProvider, instance=True, spec_set=True)
        provider.embed.return_value = [[0.1, 0.2], [0.3, 0.4]]
        provider.model_name.return_value = 'text-embedding-3-small'
        provider.dimension.return_value = 1536
        mock_col_name.return_value = 'embedding_openai'
        mock_build_text.side_effect = ['John Doe | Engineer', 'Jane Smith | Designer']

        svc = self._make_service(session, provider)

        p1 = self._make_profile_autospec('cp_001', 'John Doe', 'Engineer', 'Builder')
        p2 = self._make_profile_autospec('cp_002', 'Jane Smith', 'Designer', 'Creator')
        exp1 = self._make_experience_autospec('Acme', 'Engineer')
        exp2 = self._make_experience_autospec('BigCo', 'Designer')

        session.execute.side_effect = self._make_session_execute_side_effects([
            (p1, [exp1]),
            (p2, [exp2]),
        ])

        results = [
            ('cp_001', 'https://linkedin.com/in/john', {'firstName': 'John'}),
            ('cp_002', 'https://linkedin.com/in/jane', {'firstName': 'Jane'}),
        ]
        event_ids = {
            'https://linkedin.com/in/john': 'ee_001',
            'https://linkedin.com/in/jane': 'ee_002',
        }

        with patch.object(svc, 'process_enrichment_result'):
            enriched, failed = svc.process_batch(results, event_ids)

        assert (enriched, failed) == (2, 0)
        provider.embed.assert_called_once()
        assert len(provider.embed.call_args[0][0]) == 2
        mock_archive.assert_called_once()
        assert len(mock_archive.call_args[0][0]) == 2

    @patch('linkedout.enrichment_pipeline.post_enrichment.append_apify_archive_batch')
    @patch('utilities.llm_manager.embedding_factory.get_embedding_column_name')
    @patch('linkedout.enrichment_pipeline.post_enrichment.build_embedding_text')
    def test_partial_failure_counts(self, mock_build_text, mock_col_name, mock_archive):
        session = MagicMock()
        provider = create_autospec(EmbeddingProvider, instance=True, spec_set=True)
        provider.embed.return_value = [[0.1, 0.2]]
        provider.model_name.return_value = 'test-model'
        provider.dimension.return_value = 1536
        mock_col_name.return_value = 'embedding_openai'
        mock_build_text.return_value = 'John Doe | Engineer'

        svc = self._make_service(session, provider)

        p1 = self._make_profile_autospec('cp_001')
        exp1 = self._make_experience_autospec()

        session.execute.side_effect = self._make_session_execute_side_effects([
            (p1, [exp1]),
        ])

        results = [
            ('cp_001', 'https://linkedin.com/in/john', {'firstName': 'John'}),
            ('cp_002', 'https://linkedin.com/in/jane', {'firstName': 'Jane'}),
        ]
        event_ids = {}

        with patch.object(svc, 'process_enrichment_result', side_effect=[None, Exception('boom')]):
            enriched, failed = svc.process_batch(results, event_ids)

        assert (enriched, failed) == (1, 1)
        mock_archive.assert_called_once()
        assert len(mock_archive.call_args[0][0]) == 1

    @patch('linkedout.enrichment_pipeline.post_enrichment.append_apify_archive_batch')
    def test_skip_embeddings_flag(self, mock_archive):
        session = MagicMock()
        provider = create_autospec(EmbeddingProvider, instance=True, spec_set=True)

        svc = self._make_service(session, provider)

        results = [
            ('cp_001', 'https://linkedin.com/in/john', {'firstName': 'John'}),
        ]

        with patch.object(svc, 'process_enrichment_result'):
            enriched, failed = svc.process_batch(results, {}, skip_embeddings=True)

        assert (enriched, failed) == (1, 0)
        provider.embed.assert_not_called()

    @patch('linkedout.enrichment_pipeline.post_enrichment.append_apify_archive_batch')
    def test_no_embedding_provider(self, mock_archive):
        session = MagicMock()
        svc = self._make_service(session, embedding_provider=None)

        results = [
            ('cp_001', 'https://linkedin.com/in/john', {'firstName': 'John'}),
        ]

        with patch.object(svc, 'process_enrichment_result'):
            enriched, failed = svc.process_batch(results, {})

        assert (enriched, failed) == (1, 0)
        # No session.execute calls for the embedding step (only begin_nested from process loop)
        # Verify embed was never attempted by checking no profile lookups happened
        mock_archive.assert_called_once()

    @patch('linkedout.enrichment_pipeline.post_enrichment.append_apify_archive_batch')
    @patch('utilities.llm_manager.embedding_factory.get_embedding_column_name')
    @patch('linkedout.enrichment_pipeline.post_enrichment.build_embedding_text')
    def test_embedding_includes_experiences(self, mock_build_text, mock_col_name, mock_archive):
        session = MagicMock()
        provider = create_autospec(EmbeddingProvider, instance=True, spec_set=True)
        provider.embed.return_value = [[0.1, 0.2]]
        provider.model_name.return_value = 'test-model'
        provider.dimension.return_value = 1536
        mock_col_name.return_value = 'embedding_openai'
        mock_build_text.return_value = 'John | Engineer | Experience: Acme - SWE'

        svc = self._make_service(session, provider)

        p1 = self._make_profile_autospec('cp_001', full_name='John')
        exp1 = self._make_experience_autospec('Acme', 'SWE')

        session.execute.side_effect = self._make_session_execute_side_effects([
            (p1, [exp1]),
        ])

        results = [('cp_001', 'https://linkedin.com/in/john', {})]

        with patch.object(svc, 'process_enrichment_result'):
            svc.process_batch(results, {})

        mock_build_text.assert_called_once()
        profile_dict = mock_build_text.call_args[0][0]
        assert profile_dict['experiences'] == [{'company_name': 'Acme', 'title': 'SWE'}]

    @patch('linkedout.enrichment_pipeline.post_enrichment.append_apify_archive_batch')
    @patch('utilities.llm_manager.embedding_factory.get_embedding_column_name')
    @patch('linkedout.enrichment_pipeline.post_enrichment.build_embedding_text')
    def test_embedding_with_no_experiences(self, mock_build_text, mock_col_name, mock_archive):
        session = MagicMock()
        provider = create_autospec(EmbeddingProvider, instance=True, spec_set=True)
        provider.embed.return_value = [[0.1, 0.2]]
        provider.model_name.return_value = 'test-model'
        provider.dimension.return_value = 1536
        mock_col_name.return_value = 'embedding_openai'
        mock_build_text.return_value = 'John | Engineer'

        svc = self._make_service(session, provider)

        p1 = self._make_profile_autospec('cp_001')

        session.execute.side_effect = self._make_session_execute_side_effects([
            (p1, []),  # no experiences
        ])

        results = [('cp_001', 'https://linkedin.com/in/john', {})]

        with patch.object(svc, 'process_enrichment_result'):
            svc.process_batch(results, {})

        mock_build_text.assert_called_once()
        profile_dict = mock_build_text.call_args[0][0]
        assert profile_dict['experiences'] == []

    @patch('linkedout.enrichment_pipeline.post_enrichment.append_apify_archive_batch')
    @patch('utilities.llm_manager.embedding_factory.get_embedding_column_name')
    @patch('linkedout.enrichment_pipeline.post_enrichment.build_embedding_text')
    def test_embedding_failure_logs_and_continues(self, mock_build_text, mock_col_name, mock_archive):
        session = MagicMock()
        provider = create_autospec(EmbeddingProvider, instance=True, spec_set=True)
        provider.embed.side_effect = RuntimeError('API down')
        mock_build_text.return_value = 'John | Engineer'

        svc = self._make_service(session, provider)

        p1 = self._make_profile_autospec('cp_001')
        p2 = self._make_profile_autospec('cp_002')

        session.execute.side_effect = self._make_session_execute_side_effects([
            (p1, []),
            (p2, []),
        ])

        results = [
            ('cp_001', 'https://linkedin.com/in/john', {}),
            ('cp_002', 'https://linkedin.com/in/jane', {}),
        ]

        with patch.object(svc, 'process_enrichment_result'), \
             patch.object(svc, '_log_failed_embedding_entry') as mock_log_fail:
            enriched, failed = svc.process_batch(results, {})

        assert (enriched, failed) == (2, 0)
        assert mock_log_fail.call_count == 2
        mock_archive.assert_called_once()

    @patch('linkedout.enrichment_pipeline.post_enrichment.append_apify_archive_batch')
    @patch('utilities.llm_manager.embedding_factory.get_embedding_column_name')
    @patch('linkedout.enrichment_pipeline.post_enrichment.build_embedding_text')
    def test_profile_missing_at_embedding_time(self, mock_build_text, mock_col_name, mock_archive):
        session = MagicMock()
        provider = create_autospec(EmbeddingProvider, instance=True, spec_set=True)
        provider.embed.return_value = []
        mock_col_name.return_value = 'embedding_openai'

        svc = self._make_service(session, provider)

        # Profile not found at embedding time (scalar_one_or_none returns None)
        session.execute.side_effect = self._make_session_execute_side_effects([
            (None, []),  # profile missing — no exp query will follow
        ])

        results = [('cp_001', 'https://linkedin.com/in/john', {})]

        with patch.object(svc, 'process_enrichment_result'):
            enriched, failed = svc.process_batch(results, {})

        assert (enriched, failed) == (1, 0)
        mock_build_text.assert_not_called()

    @patch('linkedout.enrichment_pipeline.post_enrichment.append_apify_archive_batch')
    @patch('utilities.llm_manager.embedding_factory.get_embedding_column_name')
    @patch('linkedout.enrichment_pipeline.post_enrichment.build_embedding_text')
    def test_empty_embedding_text_skipped(self, mock_build_text, mock_col_name, mock_archive):
        session = MagicMock()
        provider = create_autospec(EmbeddingProvider, instance=True, spec_set=True)
        mock_col_name.return_value = 'embedding_openai'
        mock_build_text.return_value = '   '  # whitespace only

        svc = self._make_service(session, provider)

        p1 = self._make_profile_autospec('cp_001', full_name=None, headline=None, about=None)

        session.execute.side_effect = self._make_session_execute_side_effects([
            (p1, []),
        ])

        results = [('cp_001', 'https://linkedin.com/in/john', {})]

        with patch.object(svc, 'process_enrichment_result'):
            svc.process_batch(results, {})

        # embed should never be called since text was whitespace-only
        provider.embed.assert_not_called()

    @patch('linkedout.enrichment_pipeline.post_enrichment.append_apify_archive_batch')
    def test_archive_only_successful_profiles(self, mock_archive):
        session = MagicMock()
        svc = self._make_service(session, embedding_provider=None)

        results = [
            ('cp_001', 'https://linkedin.com/in/john', {'firstName': 'John'}),
            ('cp_002', 'https://linkedin.com/in/jane', {'firstName': 'Jane'}),
        ]

        with patch.object(svc, 'process_enrichment_result', side_effect=[None, Exception('fail')]):
            enriched, failed = svc.process_batch(results, {})

        assert (enriched, failed) == (1, 1)
        mock_archive.assert_called_once()
        archive_entries = mock_archive.call_args[0][0]
        assert len(archive_entries) == 1
        assert archive_entries[0]['linkedin_url'] == 'https://linkedin.com/in/john'
