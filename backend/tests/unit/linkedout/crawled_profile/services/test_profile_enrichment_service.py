# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ProfileEnrichmentService."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch, call

import pytest

from linkedout.crawled_profile.schemas.crawled_profile_api_schema import (
    EnrichEducationItem,
    EnrichExperienceItem,
    EnrichProfileRequestSchema,
)
from linkedout.crawled_profile.services.profile_enrichment_service import (
    ProfileEnrichmentService,
)
from linkedout.education.entities.education_entity import EducationEntity
from linkedout.experience.entities.experience_entity import ExperienceEntity
from linkedout.profile_skill.entities.profile_skill_entity import ProfileSkillEntity


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_mock_session():
    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = []
    return session


def _make_mock_profile(profile_id='cp_test_123', full_name='Test User', headline='Engineer'):
    profile = MagicMock()
    profile.id = profile_id
    profile.full_name = full_name
    profile.headline = headline
    profile.about = None
    profile.has_enriched_data = False
    profile.search_vector = None
    profile.embedding_openai = None
    profile.embedding_nomic = None
    profile.embedding_model = None
    profile.embedding_dim = None
    profile.embedding_updated_at = None
    return profile


def _get_added_entities(session, entity_class):
    """Extract entities of a given type from session.add() calls."""
    return [
        call_args[0][0]
        for call_args in session.add.call_args_list
        if isinstance(call_args[0][0], entity_class)
    ]


def _make_request(
    experiences=None, educations=None, skills=None,
) -> EnrichProfileRequestSchema:
    return EnrichProfileRequestSchema(
        experiences=experiences or [],
        educations=educations or [],
        skills=skills or [],
    )


# ── Tests ────────────────────────────────────────────────────────────────


class TestProfileEnrichmentService:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = _make_mock_session()
        self.embedding_provider = MagicMock()
        self.embedding_provider.embed_single.return_value = [0.1] * 1536
        self.embedding_provider.model_name.return_value = 'text-embedding-3-small'
        self.embedding_provider.dimension.return_value = 1536

    _SENTINEL = object()

    def _create_service(self, embedding_provider=_SENTINEL):
        """Create service with mocked repository."""
        ep = self.embedding_provider if embedding_provider is self._SENTINEL else embedding_provider
        svc = ProfileEnrichmentService(self.session, ep)
        return svc

    def _patch_repo_get(self, svc, profile):
        """Patch the repository and session query chain to return the given profile."""
        svc._repository = MagicMock()
        svc._repository.get_by_id.return_value = profile
        # Also stub the session.query() chain used by enrich()
        self.session.query.return_value.filter.return_value.with_for_update.return_value.one_or_none.return_value = profile

    def _patch_role_alias(self, svc, alias_map=None):
        """Patch role alias repo. alias_map: {title: mock_alias} or None for no matches."""
        svc._role_alias_repo = MagicMock()
        if alias_map:
            svc._role_alias_repo.get_by_alias_title.side_effect = lambda t: alias_map.get(t)
        else:
            svc._role_alias_repo.get_by_alias_title.return_value = None

    def test_happy_path_full_enrichment(self):
        """Full enrichment with experiences, educations, skills."""
        svc = self._create_service()
        profile = _make_mock_profile()
        self._patch_repo_get(svc, profile)

        # Set up role alias match for one position
        alias = MagicMock()
        alias.seniority_level = 'Senior'
        alias.function_area = 'Engineering'
        self._patch_role_alias(svc, {'Software Engineer': alias})

        request = _make_request(
            experiences=[
                EnrichExperienceItem(
                    position='Software Engineer',
                    company_name='Acme Corp',
                    start_year=2020, start_month=3,
                    end_year=2023, end_month=6,
                    is_current=False,
                ),
            ],
            educations=[
                EnrichEducationItem(
                    school_name='MIT',
                    degree='BS',
                    field_of_study='CS',
                    start_year=2016, end_year=2020,
                ),
            ],
            skills=['Python', 'FastAPI'],
        )

        result = svc.enrich('cp_test_123', request)

        assert result.experiences_created == 1
        assert result.educations_created == 1
        assert result.skills_created == 2
        assert profile.has_enriched_data is True
        assert profile.search_vector is not None
        assert 'Acme Corp' in profile.search_vector
        assert 'Software Engineer' in profile.search_vector
        # Embedding should be set on the correct column
        assert profile.embedding_openai == [0.1] * 1536
        assert profile.embedding_model == 'text-embedding-3-small'
        assert profile.embedding_dim == 1536

    def test_experience_date_computation(self):
        """Verify start_date and end_date are computed from year/month."""
        svc = self._create_service()
        profile = _make_mock_profile()
        self._patch_repo_get(svc, profile)
        self._patch_role_alias(svc)

        request = _make_request(
            experiences=[
                EnrichExperienceItem(
                    position='Dev',
                    company_name='Co',
                    start_year=2020, start_month=6,
                    end_year=2023, end_month=12,
                    is_current=False,
                ),
            ],
        )

        svc.enrich('cp_test_123', request)

        exps = _get_added_entities(self.session, ExperienceEntity)
        assert len(exps) == 1
        assert exps[0].start_date == date(2020, 6, 1)
        assert exps[0].end_date == date(2023, 12, 1)
        assert exps[0].end_date_text is None  # not current

    def test_current_experience_has_no_end_date(self):
        """Current position: end_date=None, end_date_text='Present'."""
        svc = self._create_service()
        profile = _make_mock_profile()
        self._patch_repo_get(svc, profile)
        self._patch_role_alias(svc)

        request = _make_request(
            experiences=[
                EnrichExperienceItem(
                    position='CTO',
                    company_name='Startup',
                    start_year=2022,
                    is_current=True,
                    end_year=2024,  # should be ignored since is_current
                ),
            ],
        )

        svc.enrich('cp_test_123', request)

        exps = _get_added_entities(self.session, ExperienceEntity)
        assert len(exps) == 1
        assert exps[0].end_date is None
        assert exps[0].end_date_text == 'Present'
        assert exps[0].is_current is True

    def test_role_alias_sets_seniority_and_function(self):
        """Role alias match populates seniority_level and function_area."""
        svc = self._create_service()
        profile = _make_mock_profile()
        self._patch_repo_get(svc, profile)

        alias = MagicMock()
        alias.seniority_level = 'VP'
        alias.function_area = 'Product'
        self._patch_role_alias(svc, {'VP Product': alias})

        request = _make_request(
            experiences=[EnrichExperienceItem(position='VP Product', company_name='BigCo')],
        )

        svc.enrich('cp_test_123', request)

        exps = _get_added_entities(self.session, ExperienceEntity)
        assert len(exps) == 1
        assert exps[0].seniority_level == 'VP'
        assert exps[0].function_area == 'Product'

    def test_no_role_alias_match_leaves_none(self):
        """No alias match: seniority_level and function_area stay None."""
        svc = self._create_service()
        profile = _make_mock_profile()
        self._patch_repo_get(svc, profile)
        self._patch_role_alias(svc)  # no matches

        request = _make_request(
            experiences=[EnrichExperienceItem(position='Unknown Title', company_name='Co')],
        )

        svc.enrich('cp_test_123', request)

        exps = _get_added_entities(self.session, ExperienceEntity)
        assert len(exps) == 1
        assert exps[0].seniority_level is None
        assert exps[0].function_area is None

    def test_embedding_failure_logs_to_jsonl(self, tmp_path):
        """Embedding failure: logs to JSONL, profile still saved."""
        svc = self._create_service()
        profile = _make_mock_profile()
        self._patch_repo_get(svc, profile)
        self._patch_role_alias(svc)

        self.embedding_provider.embed_single.side_effect = RuntimeError('API down')

        request = _make_request(
            experiences=[EnrichExperienceItem(position='Dev', company_name='Co')],
        )

        # Patch the JSONL path to use tmp_path
        jsonl = tmp_path / 'failed.jsonl'
        with patch.object(
            ProfileEnrichmentService, '_log_failed_embedding'
        ) as mock_log:
            result = svc.enrich('cp_test_123', request)

        # Profile still enriched despite embedding failure
        assert result.experiences_created == 1
        assert profile.has_enriched_data is True
        assert profile.embedding_openai is None  # not set
        mock_log.assert_called_once()

    def test_no_embedding_provider_skips_embedding(self):
        """No embedding provider: embedding skipped, no error."""
        svc = self._create_service(embedding_provider=None)
        profile = _make_mock_profile()
        self._patch_repo_get(svc, profile)
        self._patch_role_alias(svc)

        request = _make_request(
            experiences=[EnrichExperienceItem(position='Dev', company_name='Co')],
        )

        result = svc.enrich('cp_test_123', request)

        assert result.experiences_created == 1
        assert profile.embedding_openai is None

    def test_empty_arrays_sets_enriched_true(self):
        """Empty data: has_enriched_data = True, 0 rows (Q9)."""
        svc = self._create_service()
        profile = _make_mock_profile()
        self._patch_repo_get(svc, profile)
        self._patch_role_alias(svc)

        result = svc.enrich('cp_test_123', _make_request())

        assert result.experiences_created == 0
        assert result.educations_created == 0
        assert result.skills_created == 0
        assert profile.has_enriched_data is True

    def test_duplicate_skills_deduplicated(self):
        """Same skill name twice: deduplicated."""
        svc = self._create_service()
        profile = _make_mock_profile()
        self._patch_repo_get(svc, profile)
        self._patch_role_alias(svc)

        request = _make_request(skills=['Python', 'Python', 'FastAPI'])

        result = svc.enrich('cp_test_123', request)

        assert result.skills_created == 2

    def test_profile_not_found_raises_value_error(self):
        """Non-existent profile raises ValueError."""
        svc = self._create_service()
        svc._repository = MagicMock()
        svc._repository.get_by_id.return_value = None
        # Stub the session query chain to return None (profile not found)
        self.session.query.return_value.filter.return_value.with_for_update.return_value.one_or_none.return_value = None

        with pytest.raises(ValueError, match='not found'):
            svc.enrich('cp_nonexistent', _make_request())

    def test_search_vector_rebuilt(self):
        """search_vector includes name, headline, company, position."""
        svc = self._create_service()
        profile = _make_mock_profile(full_name='Alice Smith', headline='PM at BigCo')
        profile.about = 'Experienced PM'
        self._patch_repo_get(svc, profile)
        self._patch_role_alias(svc)

        request = _make_request(
            experiences=[EnrichExperienceItem(position='PM', company_name='BigCo')],
        )

        svc.enrich('cp_test_123', request)

        assert 'Alice Smith' in profile.search_vector
        assert 'PM at BigCo' in profile.search_vector
        assert 'Experienced PM' in profile.search_vector
        assert 'BigCo' in profile.search_vector
        assert 'PM' in profile.search_vector

    def test_education_entity_creation(self):
        """Education entities are created with correct fields."""
        svc = self._create_service()
        profile = _make_mock_profile()
        self._patch_repo_get(svc, profile)
        self._patch_role_alias(svc)

        request = _make_request(
            educations=[
                EnrichEducationItem(
                    school_name='Stanford',
                    degree='MBA',
                    field_of_study='Business',
                    start_year=2018, end_year=2020,
                    description='Focus on entrepreneurship',
                ),
            ],
        )

        svc.enrich('cp_test_123', request)

        edus = _get_added_entities(self.session, EducationEntity)
        assert len(edus) == 1
        assert edus[0].school_name == 'Stanford'
        assert edus[0].degree == 'MBA'
        assert edus[0].field_of_study == 'Business'
        assert edus[0].start_year == 2018
        assert edus[0].end_year == 2020
