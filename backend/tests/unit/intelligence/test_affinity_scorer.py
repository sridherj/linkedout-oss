# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the AffinityScorer."""
from datetime import date, datetime, timezone
from math import log2
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from common.entities.base_entity import BaseEntity
from linkedout.company.entities.company_entity import CompanyEntity
from linkedout.connection.entities.connection_entity import ConnectionEntity
from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
from linkedout.experience.entities.experience_entity import ExperienceEntity
from linkedout.intelligence.scoring.affinity_scorer import (
    AFFINITY_VERSION,
    EXTERNAL_SOURCE_TYPES,
    SENIORITY_DEFAULT_BOOST,
    AffinityScorer,
    _assign_dunbar_tier,
    _compute_affinity,
    _compute_career_overlap,
    _compute_external_contact_score,
    _compute_recency,
    _normalize_source_count,
    _seniority_boost,
    overlap_months,
    size_factor,
)
from shared.config.settings import ScoringConfig
from organization.entities.app_user_entity import AppUserEntity


# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------

class TestNormalizeSourceCount:
    def test_zero_sources(self):
        assert _normalize_source_count(0) == 0.0

    def test_negative_sources(self):
        assert _normalize_source_count(-1) == 0.0

    def test_one_source(self):
        assert _normalize_source_count(1) == 0.2

    def test_two_sources(self):
        assert _normalize_source_count(2) == 0.5

    def test_three_sources(self):
        assert _normalize_source_count(3) == 0.8

    def test_four_or_more_sources(self):
        assert _normalize_source_count(4) == 1.0
        assert _normalize_source_count(10) == 1.0


class TestComputeRecency:
    def test_none_connected_at(self):
        assert _compute_recency(None) == 0.0

    def test_less_than_one_year(self):
        ref = date(2026, 3, 28)
        connected = date(2025, 6, 1)
        assert _compute_recency(connected, ref) == 1.0

    def test_one_to_three_years(self):
        ref = date(2026, 3, 28)
        connected = date(2024, 1, 1)  # ~2.2 years
        assert _compute_recency(connected, ref) == 0.7

    def test_three_to_five_years(self):
        ref = date(2026, 3, 28)
        connected = date(2022, 1, 1)  # ~4.2 years
        assert _compute_recency(connected, ref) == 0.4

    def test_five_plus_years(self):
        ref = date(2026, 3, 28)
        connected = date(2020, 1, 1)  # ~6.2 years
        assert _compute_recency(connected, ref) == 0.2

    def test_same_day(self):
        ref = date(2026, 3, 28)
        assert _compute_recency(ref, ref) == 1.0


class TestSizeFactor:
    def test_small_company_scores_higher(self):
        assert size_factor(10) > size_factor(50000)

    def test_none_uses_default_500(self):
        assert size_factor(None) == size_factor(500)

    def test_zero_uses_default_500(self):
        assert size_factor(0) == size_factor(500)

    def test_known_value(self):
        # size_factor(10) = 1.0 / log2(12)
        expected = 1.0 / log2(12)
        assert abs(size_factor(10) - expected) < 1e-10

    def test_large_company_small_factor(self):
        # 50000 employees -> small factor
        assert size_factor(50000) < 0.1

    def test_tiny_company_large_factor(self):
        # 5 employees -> large factor
        assert size_factor(5) > 0.3


class TestOverlapMonths:
    def test_full_overlap(self):
        # Both at same company Jan 2020 - Jan 2022 = 24 months
        months = overlap_months(
            date(2020, 1, 1), date(2022, 1, 1),
            date(2020, 1, 1), date(2022, 1, 1),
        )
        assert months == 24.0

    def test_partial_overlap(self):
        # A: 2020-01 to 2022-01, B: 2021-01 to 2023-01
        # overlap: 2021-01 to 2022-01 = 12 months
        months = overlap_months(
            date(2020, 1, 1), date(2022, 1, 1),
            date(2021, 1, 1), date(2023, 1, 1),
        )
        assert months == 12.0

    def test_no_overlap(self):
        months = overlap_months(
            date(2020, 1, 1), date(2021, 1, 1),
            date(2022, 1, 1), date(2023, 1, 1),
        )
        assert months == 0.0

    def test_none_start_a_returns_zero(self):
        assert overlap_months(None, date(2022, 1, 1), date(2020, 1, 1), date(2022, 1, 1)) == 0.0

    def test_none_start_b_returns_zero(self):
        assert overlap_months(date(2020, 1, 1), date(2022, 1, 1), None, date(2022, 1, 1)) == 0.0

    def test_none_end_treated_as_today(self):
        # A: 2024-01-01 to today, B: 2024-01-01 to today
        today = date.today()
        expected = float((today.year - 2024) * 12 + (today.month - 1))
        months = overlap_months(
            date(2024, 1, 1), None,
            date(2024, 1, 1), None,
        )
        assert months == expected

    def test_adjacent_no_overlap(self):
        # End date equals start date -> no overlap
        months = overlap_months(
            date(2020, 1, 1), date(2021, 1, 1),
            date(2021, 1, 1), date(2022, 1, 1),
        )
        assert months == 0.0


class TestComputeCareerOverlap:
    def test_no_connection_experiences(self):
        assert _compute_career_overlap([], [{'company_id': 'c1', 'start_date': date(2020, 1, 1), 'end_date': date(2022, 1, 1)}], {}) == 0.0

    def test_no_user_experiences(self):
        assert _compute_career_overlap([{'company_id': 'c1', 'start_date': date(2020, 1, 1), 'end_date': date(2022, 1, 1)}], [], {}) == 0.0

    def test_no_matching_companies(self):
        conn_exps = [{'company_id': 'c1', 'start_date': date(2020, 1, 1), 'end_date': date(2022, 1, 1)}]
        user_exps = [{'company_id': 'c2', 'start_date': date(2020, 1, 1), 'end_date': date(2022, 1, 1)}]
        assert _compute_career_overlap(conn_exps, user_exps, {}) == 0.0

    def test_small_company_24_months_high_score(self):
        # 10-person company, 24 months overlap
        # size_factor(10) = 1/log2(12) ≈ 0.279
        # total = 24 * 0.279 ≈ 6.7
        # career = min(6.7 / 36.0, 1.0) ≈ 0.186
        conn_exps = [{'company_id': 'c1', 'start_date': date(2020, 1, 1), 'end_date': date(2022, 1, 1)}]
        user_exps = [{'company_id': 'c1', 'start_date': date(2020, 1, 1), 'end_date': date(2022, 1, 1)}]
        sizes = {'c1': 10}
        result = _compute_career_overlap(conn_exps, user_exps, sizes)
        assert result > 0.15

    def test_large_company_24_months_low_score(self):
        # 50K-person company, 24 months overlap
        # size_factor(50000) = 1/log2(50002) ≈ 0.064
        # total = 24 * 0.064 ≈ 1.53
        # career = min(1.53 / 36.0, 1.0) ≈ 0.043
        conn_exps = [{'company_id': 'c1', 'start_date': date(2020, 1, 1), 'end_date': date(2022, 1, 1)}]
        user_exps = [{'company_id': 'c1', 'start_date': date(2020, 1, 1), 'end_date': date(2022, 1, 1)}]
        sizes = {'c1': 50000}
        result = _compute_career_overlap(conn_exps, user_exps, sizes)
        assert result < 0.1

    def test_small_much_higher_than_large(self):
        conn_exps = [{'company_id': 'c1', 'start_date': date(2020, 1, 1), 'end_date': date(2022, 1, 1)}]
        user_exps = [{'company_id': 'c1', 'start_date': date(2020, 1, 1), 'end_date': date(2022, 1, 1)}]
        small = _compute_career_overlap(conn_exps, user_exps, {'c1': 10})
        large = _compute_career_overlap(conn_exps, user_exps, {'c1': 50000})
        assert small > large * 3  # dramatically higher

    def test_normalization_cap(self):
        # Huge overlap should cap at 1.0
        conn_exps = [{'company_id': 'c1', 'start_date': date(2010, 1, 1), 'end_date': date(2025, 1, 1)}]
        user_exps = [{'company_id': 'c1', 'start_date': date(2010, 1, 1), 'end_date': date(2025, 1, 1)}]
        sizes = {'c1': 5}  # tiny company, big factor
        result = _compute_career_overlap(conn_exps, user_exps, sizes)
        assert result == 1.0

    def test_no_dates_returns_zero(self):
        # Both have matching company but no start dates
        conn_exps = [{'company_id': 'c1', 'start_date': None, 'end_date': None}]
        user_exps = [{'company_id': 'c1', 'start_date': None, 'end_date': None}]
        assert _compute_career_overlap(conn_exps, user_exps, {'c1': 10}) == 0.0

    def test_unknown_company_size_uses_default(self):
        # company_sizes doesn't have c1 -> defaults to 500
        conn_exps = [{'company_id': 'c1', 'start_date': date(2020, 1, 1), 'end_date': date(2022, 1, 1)}]
        user_exps = [{'company_id': 'c1', 'start_date': date(2020, 1, 1), 'end_date': date(2022, 1, 1)}]
        result = _compute_career_overlap(conn_exps, user_exps, {})
        expected_factor = size_factor(None)  # defaults to 500
        expected = min(24 * expected_factor / 36.0, 1.0)
        assert abs(result - expected) < 0.001


class TestSeniorityBoost:
    def test_founder_boost(self):
        assert _seniority_boost('founder', 'mid') == 3.0

    def test_intern_boost(self):
        assert _seniority_boost('intern', 'intern') == 0.7

    def test_higher_seniority_wins(self):
        # User is founder, connection is intern -> founder's 3.0 wins
        assert _seniority_boost('founder', 'intern') == 3.0
        # Reversed: same result
        assert _seniority_boost('intern', 'founder') == 3.0

    def test_missing_seniority_defaults_to_1(self):
        assert _seniority_boost(None, None) == SENIORITY_DEFAULT_BOOST
        assert _seniority_boost(None, 'mid') == SENIORITY_DEFAULT_BOOST
        assert _seniority_boost('mid', None) == SENIORITY_DEFAULT_BOOST

    def test_unknown_seniority_defaults_to_1(self):
        assert _seniority_boost('unknown_level', 'mid') == SENIORITY_DEFAULT_BOOST

    def test_all_levels_present(self):
        expected_levels = {'founder', 'c_suite', 'vp', 'director', 'manager', 'lead', 'senior', 'mid', 'junior', 'intern'}
        assert set(ScoringConfig().seniority_boosts.keys()) == expected_levels


class TestCareerOverlapWithSeniority:
    def test_founder_boost_increases_overlap(self):
        """Founder at same company should score much higher than mid-level."""
        conn_exps = [{'company_id': 'c1', 'start_date': date(2020, 1, 1), 'end_date': date(2024, 1, 1), 'seniority_level': 'mid'}]
        user_exps = [{'company_id': 'c1', 'start_date': date(2020, 1, 1), 'end_date': date(2024, 1, 1), 'seniority_level': 'founder'}]
        sizes = {'c1': 350}
        result_with_boost = _compute_career_overlap(conn_exps, user_exps, sizes)

        # Without seniority (mid-level default)
        conn_exps_no_sen = [{'company_id': 'c1', 'start_date': date(2020, 1, 1), 'end_date': date(2024, 1, 1)}]
        user_exps_no_sen = [{'company_id': 'c1', 'start_date': date(2020, 1, 1), 'end_date': date(2024, 1, 1)}]
        result_without_boost = _compute_career_overlap(conn_exps_no_sen, user_exps_no_sen, sizes)

        assert result_with_boost == pytest.approx(result_without_boost * 3.0, rel=0.01)

    def test_intern_reduces_overlap(self):
        """Two interns at same company should score lower than default."""
        conn_exps = [{'company_id': 'c1', 'start_date': date(2020, 1, 1), 'end_date': date(2022, 1, 1), 'seniority_level': 'intern'}]
        user_exps = [{'company_id': 'c1', 'start_date': date(2020, 1, 1), 'end_date': date(2022, 1, 1), 'seniority_level': 'intern'}]
        sizes = {'c1': 100}
        result = _compute_career_overlap(conn_exps, user_exps, sizes)

        conn_exps_mid = [{'company_id': 'c1', 'start_date': date(2020, 1, 1), 'end_date': date(2022, 1, 1), 'seniority_level': 'mid'}]
        user_exps_mid = [{'company_id': 'c1', 'start_date': date(2020, 1, 1), 'end_date': date(2022, 1, 1), 'seniority_level': 'mid'}]
        result_mid = _compute_career_overlap(conn_exps_mid, user_exps_mid, sizes)

        assert result < result_mid

    def test_missing_seniority_no_change(self):
        """Missing seniority_level should behave like mid (boost=1.0)."""
        conn_exps = [{'company_id': 'c1', 'start_date': date(2020, 1, 1), 'end_date': date(2022, 1, 1)}]
        user_exps = [{'company_id': 'c1', 'start_date': date(2020, 1, 1), 'end_date': date(2022, 1, 1)}]
        sizes = {'c1': 100}
        result_none = _compute_career_overlap(conn_exps, user_exps, sizes)

        conn_exps_mid = [{'company_id': 'c1', 'start_date': date(2020, 1, 1), 'end_date': date(2022, 1, 1), 'seniority_level': 'mid'}]
        user_exps_mid = [{'company_id': 'c1', 'start_date': date(2020, 1, 1), 'end_date': date(2022, 1, 1), 'seniority_level': 'mid'}]
        result_mid = _compute_career_overlap(conn_exps_mid, user_exps_mid, sizes)

        assert result_none == result_mid

    def test_nabhan_scenario(self):
        """Reproduce the Nabhan scenario: 46 months at 350-person company, user is founder."""
        conn_exps = [{'company_id': 'crio', 'start_date': date(2018, 6, 1), 'end_date': date(2022, 4, 1), 'seniority_level': 'mid'}]
        user_exps = [{'company_id': 'crio', 'start_date': date(2018, 6, 1), 'end_date': date(2022, 4, 1), 'seniority_level': 'founder'}]
        sizes = {'crio': 350}
        result = _compute_career_overlap(conn_exps, user_exps, sizes)
        # With founder boost (3.0), should be significantly higher than 0.151
        assert result > 0.4


class TestComputeAffinity:
    def test_all_zeros(self):
        assert _compute_affinity(0.0, 0.0, 0.0, 0.0, 0.0) == 0.0

    def test_all_max(self):
        # 1.0*0.40 + 1.0*0.25 + 1.0*0.15 + 1.0*0.10 + 1.0*0.10 = 1.0 -> 100.0
        assert _compute_affinity(1.0, 1.0, 1.0, 1.0, 1.0) == 100.0

    def test_known_values(self):
        # career=0.5*0.40 + ext=0.8*0.25 + emb=0.6*0.15 + src=0.2*0.10 + rec=0.7*0.10
        # = 0.20 + 0.20 + 0.09 + 0.02 + 0.07 = 0.58 -> 58.0
        assert _compute_affinity(0.2, 0.7, 0.5, 0.8, 0.6) == 58.0

    def test_only_source_and_recency(self):
        # With no career/external/embedding, max = src*0.10 + rec*0.10 = 0.20 -> 20.0
        assert _compute_affinity(1.0, 1.0, 0.0, 0.0, 0.0) == 20.0

    def test_v2_weights_sum_to_one(self):
        sc = ScoringConfig()
        total = sc.weight_career_overlap + sc.weight_external_contact + sc.weight_embedding_similarity + sc.weight_source_count + sc.weight_recency
        assert abs(total - 1.0) < 1e-10


class TestAssignDunbarTier:
    def test_inner_circle(self):
        for rank in [1, 5, 15]:
            assert _assign_dunbar_tier(rank) == 'inner_circle'

    def test_active(self):
        for rank in [16, 30, 50]:
            assert _assign_dunbar_tier(rank) == 'active'

    def test_familiar(self):
        for rank in [51, 100, 150]:
            assert _assign_dunbar_tier(rank) == 'familiar'

    def test_acquaintance(self):
        for rank in [151, 500, 10000]:
            assert _assign_dunbar_tier(rank) == 'acquaintance'


# ---------------------------------------------------------------------------
# Integration tests with SQLite
# ---------------------------------------------------------------------------

@pytest.fixture
def sqlite_session():
    """Create an in-memory SQLite session with all required tables.

    Mocks get_embedding_provider to avoid requiring OPENAI_API_KEY in unit tests.
    """
    engine = create_engine('sqlite://', echo=False)
    BaseEntity.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    mock_provider = MagicMock()
    mock_provider.model_name.return_value = 'text-embedding-3-small'
    with patch(
        'linkedout.intelligence.scoring.affinity_scorer.get_embedding_provider',
        return_value=mock_provider,
    ):
        yield session
    session.close()


def _make_app_user(session: Session, user_id: str, own_crawled_profile_id: str = None) -> AppUserEntity:
    u = AppUserEntity()
    u.id = user_id
    u.email = f'{user_id}@test.com'
    u.own_crawled_profile_id = own_crawled_profile_id
    session.add(u)
    return u


def _make_profile(session: Session, profile_id: str, source_user_id: str = None) -> CrawledProfileEntity:
    p = CrawledProfileEntity()
    p.id = profile_id
    p.linkedin_url = f'https://linkedin.com/in/{profile_id}'
    p.data_source = 'test'
    p.source_app_user_id = source_user_id
    session.add(p)
    return p


def _make_connection(
    session: Session,
    conn_id: str,
    app_user_id: str,
    profile_id: str,
    sources: list[str] = None,
    connected_at: date = None,
) -> ConnectionEntity:
    c = ConnectionEntity()
    c.id = conn_id
    c.app_user_id = app_user_id
    c.crawled_profile_id = profile_id
    c.tenant_id = 'tenant_1'
    c.bu_id = 'bu_1'
    # SQLite doesn't support ARRAY, store as None; sources is used via len()
    # For SQLite compat, we'll patch the sources property
    c.connected_at = connected_at
    c._test_sources = sources
    session.add(c)
    return c


def _make_experience(
    session: Session,
    profile_id: str,
    company_id: str,
    start_date: date = None,
    end_date: date = None,
) -> ExperienceEntity:
    e = ExperienceEntity()
    e.id = f'exp_{profile_id}_{company_id}'
    e.crawled_profile_id = profile_id
    e.company_id = company_id
    e.start_date = start_date
    e.end_date = end_date
    session.add(e)
    return e


def _make_company(
    session: Session,
    company_id: str,
    name: str,
    estimated_employee_count: int = None,
) -> CompanyEntity:
    c = CompanyEntity()
    c.id = company_id
    c.canonical_name = name
    c.normalized_name = name.lower()
    c.estimated_employee_count = estimated_employee_count
    c.network_connection_count = 0
    session.add(c)
    return c


class TestAffinityScorerWithDB:
    def test_no_connections_returns_zero(self, sqlite_session):
        scorer = AffinityScorer(sqlite_session)
        assert scorer.compute_for_user('usr_nonexistent') == 0

    def test_single_connection_scoring(self, sqlite_session):
        _make_profile(sqlite_session, 'cp_1')
        conn = _make_connection(
            sqlite_session, 'conn_1', 'usr_1', 'cp_1',
            sources=['linkedin'], connected_at=date(2025, 6, 1),
        )
        sqlite_session.flush()

        # Patch sources since SQLite doesn't support ARRAY
        ref = date(2026, 3, 28)
        with patch.object(type(conn), 'sources', new_callable=lambda: property(lambda self: self._test_sources)):
            scorer = AffinityScorer(sqlite_session)
            count = scorer.compute_for_user('usr_1', reference_date=ref)

        assert count == 1
        sqlite_session.refresh(conn)
        # 1 source -> 0.2, <1yr -> 1.0, no career/ext/emb -> 0.0
        # V2: 0.2*0.10 + 1.0*0.10 + 0.0*0.40 + 0.0*0.25 + 0.0*0.15 = 0.12 -> 12.0
        assert conn.affinity_score == 12.0
        assert conn.dunbar_tier == 'inner_circle'  # rank 1
        assert conn.affinity_version == AFFINITY_VERSION
        assert conn.affinity_computed_at is not None

    def test_dunbar_tiers_assigned_by_rank(self, sqlite_session):
        """Create 200 connections with varying scores to verify tier assignment."""
        for i in range(200):
            profile_id = f'cp_{i}'
            _make_profile(sqlite_session, profile_id)
            _make_connection(
                sqlite_session, f'conn_{i}', 'usr_1', profile_id,
                sources=['linkedin'] * (4 if i < 15 else 2 if i < 50 else 1),
                connected_at=date(2025, 6, 1) if i < 50 else date(2022, 1, 1),
            )
        sqlite_session.flush()

        ref = date(2026, 3, 28)
        # Patch sources for SQLite
        original_sources = ConnectionEntity.sources

        def patched_sources(self):
            return getattr(self, '_test_sources', None)

        with patch.object(type(sqlite_session.query(ConnectionEntity).first()), 'sources',
                          new_callable=lambda: property(patched_sources)):
            scorer = AffinityScorer(sqlite_session)
            count = scorer.compute_for_user('usr_1', reference_date=ref)

        assert count == 200

        conns = sqlite_session.query(ConnectionEntity).filter_by(app_user_id='usr_1').all()
        # Match internal scorer order: score desc, then id asc (tiebreak)
        sorted_conns = sorted(conns, key=lambda c: (-(c.affinity_score or 0), c.id))

        tiers = [c.dunbar_tier for c in sorted_conns]
        assert tiers[0] == 'inner_circle'
        assert tiers[14] == 'inner_circle'
        assert tiers[15] == 'active'
        assert tiers[49] == 'active'
        assert tiers[50] == 'familiar'
        assert tiers[149] == 'familiar'
        assert tiers[150] == 'acquaintance'

    def test_compute_for_connection_not_found(self, sqlite_session):
        scorer = AffinityScorer(sqlite_session)
        with pytest.raises(ValueError, match="not found"):
            scorer.compute_for_connection('conn_nonexistent')

    def test_career_overlap_with_shared_companies(self, sqlite_session):
        # Create company with small employee count for significant overlap
        _make_company(sqlite_session, 'company_A', 'Company A', estimated_employee_count=10)
        _make_company(sqlite_session, 'company_B', 'Company B', estimated_employee_count=1000)

        # User's own profile linked via own_crawled_profile_id
        _make_app_user(sqlite_session, 'usr_1', own_crawled_profile_id='cp_user')
        _make_profile(sqlite_session, 'cp_user')
        _make_experience(sqlite_session, 'cp_user', 'company_A',
                         start_date=date(2020, 1, 1), end_date=date(2023, 1, 1))

        # Connection's profile with experience at company_A and company_B
        _make_profile(sqlite_session, 'cp_conn1')
        _make_experience(sqlite_session, 'cp_conn1', 'company_A',
                         start_date=date(2020, 1, 1), end_date=date(2023, 1, 1))
        _make_experience(sqlite_session, 'cp_conn1', 'company_B',
                         start_date=date(2021, 1, 1), end_date=date(2024, 1, 1))

        conn = _make_connection(
            sqlite_session, 'conn_1', 'usr_1', 'cp_conn1',
            sources=['linkedin', 'gmail'], connected_at=date(2025, 6, 1),
        )
        sqlite_session.flush()

        ref = date(2026, 3, 28)
        with patch.object(type(conn), 'sources', new_callable=lambda: property(lambda self: self._test_sources)):
            scorer = AffinityScorer(sqlite_session)
            count = scorer.compute_for_user('usr_1', reference_date=ref)

        assert count == 1
        sqlite_session.refresh(conn)
        # Career overlap should be nonzero: 36 months at 10-person company
        assert conn.affinity_career_overlap > 0
        # With size_factor(10) ≈ 0.279, 36 months: total ≈ 10.05, / 36 ≈ 0.279
        assert conn.affinity_career_overlap > 0.2
        assert conn.affinity_score > 0

    def test_no_connected_at_defaults_recency_zero(self, sqlite_session):
        _make_profile(sqlite_session, 'cp_1')
        conn = _make_connection(
            sqlite_session, 'conn_1', 'usr_1', 'cp_1',
            sources=['linkedin'], connected_at=None,
        )
        sqlite_session.flush()

        with patch.object(type(conn), 'sources', new_callable=lambda: property(lambda self: self._test_sources)):
            scorer = AffinityScorer(sqlite_session)
            scorer.compute_for_user('usr_1')

        sqlite_session.refresh(conn)
        assert conn.affinity_recency == 0.0

    def test_no_experience_data_career_overlap_zero(self, sqlite_session):
        _make_profile(sqlite_session, 'cp_1')
        conn = _make_connection(
            sqlite_session, 'conn_1', 'usr_1', 'cp_1',
            sources=['linkedin'], connected_at=date(2025, 6, 1),
        )
        sqlite_session.flush()

        ref = date(2026, 3, 28)
        with patch.object(type(conn), 'sources', new_callable=lambda: property(lambda self: self._test_sources)):
            scorer = AffinityScorer(sqlite_session)
            scorer.compute_for_user('usr_1', reference_date=ref)

        sqlite_session.refresh(conn)
        assert conn.affinity_career_overlap == 0.0

    def test_career_overlap_zero_when_own_profile_not_set(self, sqlite_session):
        """Career overlap is 0 when app_user has no own_crawled_profile_id."""
        _make_company(sqlite_session, 'company_A', 'Company A', estimated_employee_count=10)
        _make_app_user(sqlite_session, 'usr_1', own_crawled_profile_id=None)
        _make_profile(sqlite_session, 'cp_conn1')
        _make_experience(sqlite_session, 'cp_conn1', 'company_A',
                         start_date=date(2020, 1, 1), end_date=date(2023, 1, 1))
        conn = _make_connection(
            sqlite_session, 'conn_1', 'usr_1', 'cp_conn1',
            sources=['linkedin'], connected_at=date(2025, 6, 1),
        )
        sqlite_session.flush()

        ref = date(2026, 3, 28)
        with patch.object(type(conn), 'sources', new_callable=lambda: property(lambda self: self._test_sources)):
            scorer = AffinityScorer(sqlite_session)
            scorer.compute_for_user('usr_1', reference_date=ref)

        sqlite_session.refresh(conn)
        assert conn.affinity_career_overlap == 0.0

    def test_career_overlap_nonzero_when_own_profile_set(self, sqlite_session):
        """Career overlap is computed when own_crawled_profile_id is set on app_user."""
        _make_company(sqlite_session, 'company_A', 'Company A', estimated_employee_count=10)
        _make_app_user(sqlite_session, 'usr_1', own_crawled_profile_id='cp_user')
        _make_profile(sqlite_session, 'cp_user')
        _make_experience(sqlite_session, 'cp_user', 'company_A',
                         start_date=date(2020, 1, 1), end_date=date(2023, 1, 1))

        _make_profile(sqlite_session, 'cp_conn1')
        _make_experience(sqlite_session, 'cp_conn1', 'company_A',
                         start_date=date(2020, 1, 1), end_date=date(2023, 1, 1))
        conn = _make_connection(
            sqlite_session, 'conn_1', 'usr_1', 'cp_conn1',
            sources=['linkedin'], connected_at=date(2025, 6, 1),
        )
        sqlite_session.flush()

        ref = date(2026, 3, 28)
        with patch.object(type(conn), 'sources', new_callable=lambda: property(lambda self: self._test_sources)):
            scorer = AffinityScorer(sqlite_session)
            scorer.compute_for_user('usr_1', reference_date=ref)

        sqlite_session.refresh(conn)
        assert conn.affinity_career_overlap > 0.0

    def test_career_overlap_zero_when_no_dates(self, sqlite_session):
        """Career overlap is 0 when experiences have no start/end dates."""
        _make_company(sqlite_session, 'company_A', 'Company A', estimated_employee_count=10)
        _make_app_user(sqlite_session, 'usr_1', own_crawled_profile_id='cp_user')
        _make_profile(sqlite_session, 'cp_user')
        _make_experience(sqlite_session, 'cp_user', 'company_A')  # no dates

        _make_profile(sqlite_session, 'cp_conn1')
        _make_experience(sqlite_session, 'cp_conn1', 'company_A')  # no dates
        conn = _make_connection(
            sqlite_session, 'conn_1', 'usr_1', 'cp_conn1',
            sources=['linkedin'], connected_at=date(2025, 6, 1),
        )
        sqlite_session.flush()

        ref = date(2026, 3, 28)
        with patch.object(type(conn), 'sources', new_callable=lambda: property(lambda self: self._test_sources)):
            scorer = AffinityScorer(sqlite_session)
            scorer.compute_for_user('usr_1', reference_date=ref)

        sqlite_session.refresh(conn)
        assert conn.affinity_career_overlap == 0.0


# ---------------------------------------------------------------------------
# AppUser entity structural tests
# ---------------------------------------------------------------------------

class TestAppUserEntityColumns:
    def test_has_own_crawled_profile_id(self):
        cols = {c.name for c in AppUserEntity.__table__.columns}
        assert 'own_crawled_profile_id' in cols

    def test_own_crawled_profile_id_is_nullable(self):
        col = AppUserEntity.__table__.c['own_crawled_profile_id']
        assert col.nullable is True

    def test_has_network_preferences(self):
        cols = {c.name for c in AppUserEntity.__table__.columns}
        assert 'network_preferences' in cols

    def test_network_preferences_is_nullable(self):
        col = AppUserEntity.__table__.c['network_preferences']
        assert col.nullable is True


# ---------------------------------------------------------------------------
# Search prompt network_preferences injection
# ---------------------------------------------------------------------------

class TestLoadSystemPrompt:
    def test_network_preferences_injected(self):
        from linkedout.intelligence.agents.search_agent import _load_system_prompt
        prompt = _load_system_prompt('schema here', 'Prefer Crio contacts')
        assert 'Prefer Crio contacts' in prompt

    def test_network_preferences_default_when_none(self):
        from linkedout.intelligence.agents.search_agent import _load_system_prompt
        prompt = _load_system_prompt('schema here', None)
        assert 'No specific preferences set.' in prompt

    def test_network_preferences_default_when_empty(self):
        from linkedout.intelligence.agents.search_agent import _load_system_prompt
        prompt = _load_system_prompt('schema here', '   ')
        assert 'No specific preferences set.' in prompt
