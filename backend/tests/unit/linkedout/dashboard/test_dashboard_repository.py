# SPDX-License-Identifier: Apache-2.0
"""Unit tests for DashboardRepository using SQLite in-memory DB."""
import sys
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "src"))

from common.entities.base_entity import Base
from linkedout.connection.entities.connection_entity import ConnectionEntity
from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
from linkedout.dashboard.repository import DashboardRepository
from organization.entities.app_user_entity import AppUserEntity

# Import enough entities so Base.metadata covers FK targets
import organization.entities  # noqa
import linkedout.company.entities.company_entity  # noqa

TENANT = "t1"
BU = "b1"


@pytest.fixture()
def sqlite_session():
    """In-memory SQLite session with all tables created."""
    engine = create_engine("sqlite://", echo=False)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture()
def user_a(sqlite_session):
    u = AppUserEntity(email="a@test.com", name="User A", auth_provider_id="auth|a")
    sqlite_session.add(u)
    sqlite_session.flush()
    return u


@pytest.fixture()
def user_b(sqlite_session):
    u = AppUserEntity(email="b@test.com", name="User B", auth_provider_id="auth|b")
    sqlite_session.add(u)
    sqlite_session.flush()
    return u


def _make_profile(sqlite_session, idx, *, enriched=True, function_area=None,
                  seniority_level=None, location_city=None, company_name=None):
    p = CrawledProfileEntity(
        linkedin_url=f"https://linkedin.com/in/test-{idx}",
        public_identifier=f"test-{idx}",
        full_name=f"Person {idx}",
        data_source="test",
        has_enriched_data=enriched,
        function_area=function_area,
        seniority_level=seniority_level,
        location_city=location_city,
        current_company_name=company_name,
    )
    sqlite_session.add(p)
    sqlite_session.flush()
    return p


def _make_connection(sqlite_session, user, profile, *, tenant=TENANT, bu=BU,
                     dunbar_tier=None, sources=None):
    c = ConnectionEntity(
        tenant_id=tenant,
        bu_id=bu,
        app_user_id=user.id,
        crawled_profile_id=profile.id,
        connected_at=date(2025, 1, 1),
        dunbar_tier=dunbar_tier,
        sources=sources,
    )
    sqlite_session.add(c)
    sqlite_session.flush()
    return c


class TestEnrichmentStatus:
    def test_mixed_enrichment(self, sqlite_session, user_a):
        for i in range(6):
            p = _make_profile(sqlite_session, f"enrich-{i}", enriched=(i < 4))
            _make_connection(sqlite_session, user_a, p)
        sqlite_session.commit()

        repo = DashboardRepository(sqlite_session)
        rows = repo.get_enrichment_status(TENANT, BU, user_a.id)
        result = {has_enriched: cnt for has_enriched, cnt in rows}

        assert result[True] == 4
        assert result[False] == 2


class TestTopNLimit:
    def test_industry_returns_max_10(self, sqlite_session, user_a):
        for i in range(12):
            p = _make_profile(sqlite_session, f"ind-{i}", function_area=f"Industry{i}")
            _make_connection(sqlite_session, user_a, p)
        sqlite_session.commit()

        repo = DashboardRepository(sqlite_session)
        rows = repo.get_industry_breakdown(TENANT, BU, user_a.id)

        assert len(rows) <= 10


class TestNullExclusion:
    def test_null_location_excluded(self, sqlite_session, user_a):
        p1 = _make_profile(sqlite_session, "loc-1", location_city="SF")
        p2 = _make_profile(sqlite_session, "loc-2", location_city=None)
        _make_connection(sqlite_session, user_a, p1)
        _make_connection(sqlite_session, user_a, p2)
        sqlite_session.commit()

        repo = DashboardRepository(sqlite_session)
        rows = repo.get_location_top(TENANT, BU, user_a.id)
        labels = [r[0] for r in rows]

        assert "SF" in labels
        assert None not in labels

    def test_null_company_excluded(self, sqlite_session, user_a):
        p1 = _make_profile(sqlite_session, "comp-1", company_name="Google")
        p2 = _make_profile(sqlite_session, "comp-2", company_name=None)
        _make_connection(sqlite_session, user_a, p1)
        _make_connection(sqlite_session, user_a, p2)
        sqlite_session.commit()

        repo = DashboardRepository(sqlite_session)
        rows = repo.get_top_companies(TENANT, BU, user_a.id)
        labels = [r[0] for r in rows]

        assert "Google" in labels
        assert None not in labels


class TestUserScoping:
    def test_user_a_sees_only_own_data(self, sqlite_session, user_a, user_b):
        for i in range(3):
            p = _make_profile(sqlite_session, f"scope-a-{i}")
            _make_connection(sqlite_session, user_a, p)
        for i in range(2):
            p = _make_profile(sqlite_session, f"scope-b-{i}")
            _make_connection(sqlite_session, user_b, p)
        sqlite_session.commit()

        repo = DashboardRepository(sqlite_session)

        assert repo.get_total_connections(TENANT, BU, user_a.id) == 3
        assert repo.get_total_connections(TENANT, BU, user_b.id) == 2


class TestRawSeniority:
    def test_null_seniority_returned_as_none(self, sqlite_session, user_a):
        p1 = _make_profile(sqlite_session, "sen-1", seniority_level=None)
        p2 = _make_profile(sqlite_session, "sen-2", seniority_level=None)
        p3 = _make_profile(sqlite_session, "sen-3", seniority_level="Senior")
        _make_connection(sqlite_session, user_a, p1)
        _make_connection(sqlite_session, user_a, p2)
        _make_connection(sqlite_session, user_a, p3)
        sqlite_session.commit()

        repo = DashboardRepository(sqlite_session)
        rows = repo.get_seniority_distribution(TENANT, BU, user_a.id)
        result = {label: cnt for label, cnt in rows}

        assert result.get(None) == 2
        assert result.get("Senior") == 1
