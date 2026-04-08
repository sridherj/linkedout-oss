# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the profile detail and enrichment tools."""
from datetime import date
from unittest.mock import MagicMock

import pytest

from linkedout.intelligence.tools.profile_tool import get_profile_detail, request_enrichment


def _make_mock_session(profile_row, exp_rows=None, edu_rows=None, skill_rows=None):
    """Build a mock session with configurable query results.

    The profile_tool issues 4 sequential queries:
    1. Core profile + connection
    2. Experiences
    3. Education
    4. Skills
    """
    session = MagicMock()
    results = []

    # 1. Core profile query
    mock_core = MagicMock()
    mock_core.fetchone.return_value = profile_row
    results.append(mock_core)

    # 2. Experiences
    mock_exp = MagicMock()
    mock_exp.fetchall.return_value = exp_rows or []
    results.append(mock_exp)

    # 3. Education
    mock_edu = MagicMock()
    mock_edu.fetchall.return_value = edu_rows or []
    results.append(mock_edu)

    # 4. Skills
    mock_skill = MagicMock()
    mock_skill.fetchall.return_value = skill_rows or []
    results.append(mock_skill)

    session.execute.side_effect = results
    return session


def _make_profile_row(**overrides):
    """Build a mock row object for the core profile query."""
    defaults = {
        "connection_id": "conn_abc123",
        "crawled_profile_id": "cp_xyz789",
        "full_name": "Jane Doe",
        "headline": "Senior Engineer at Acme",
        "current_position": "Senior Engineer",
        "current_company_name": "Acme Corp",
        "location_city": "San Francisco",
        "location_country": "US",
        "linkedin_url": "https://linkedin.com/in/janedoe",
        "profile_image_url": "https://example.com/photo.jpg",
        "has_enriched_data": True,
        "about": "Experienced engineer.",
        "connected_at": date(2023, 6, 15),
        "tags": "engineering,ai",
        "sources": ["LinkedIn"],
        "affinity_score": 78.5,
        "dunbar_tier": "active",
        "affinity_recency": 60.0,
        "affinity_career_overlap": 45.0,
        "affinity_mutual_connections": 30.0,
        "affinity_external_contact": 10.0,
        "affinity_embedding_similarity": 55.0,
    }
    defaults.update(overrides)
    row = MagicMock()
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


def _make_exp_row(position="Engineer", company="Acme", start=None, end=None, is_current=False, industry=None, size_tier=None):
    row = MagicMock()
    row.position = position
    row.company_name = company
    row.start_date = start
    row.end_date = end
    row.is_current = is_current
    row.industry = industry
    row.size_tier = size_tier
    return row


def _make_edu_row(school="MIT", degree="BS", field="CS", start_year=2014, end_year=2018):
    row = MagicMock()
    row.school_name = school
    row.degree = degree
    row.field_of_study = field
    row.start_year = start_year
    row.end_year = end_year
    return row


def _make_skill_row(name="Python"):
    row = MagicMock()
    row.skill_name = name
    return row


class TestGetProfileDetail:
    def test_returns_core_identity(self):
        profile = _make_profile_row()
        session = _make_mock_session(profile)

        result = get_profile_detail("conn_abc123", session)

        assert result["connection_id"] == "conn_abc123"
        assert result["crawled_profile_id"] == "cp_xyz789"
        assert result["full_name"] == "Jane Doe"
        assert result["headline"] == "Senior Engineer at Acme"

    def test_location_built_from_city_and_country(self):
        profile = _make_profile_row(location_city="Bangalore", location_country="India")
        session = _make_mock_session(profile)

        result = get_profile_detail("conn_abc123", session)

        assert result["location"] == "Bangalore, India"

    def test_location_city_only(self):
        profile = _make_profile_row(location_city="London", location_country=None)
        session = _make_mock_session(profile)

        result = get_profile_detail("conn_abc123", session)

        assert result["location"] == "London"

    def test_affinity_breakdown(self):
        profile = _make_profile_row(affinity_score=78.5, dunbar_tier="active")
        session = _make_mock_session(profile)

        result = get_profile_detail("conn_abc123", session)

        affinity = result["affinity"]
        assert affinity["score"] == 78.5
        assert affinity["tier"] == "active"
        assert affinity["tier_description"] == "Top 50 — people you actively engage with"
        assert len(affinity["sub_scores"]) == 5
        names = {s["name"] for s in affinity["sub_scores"]}
        assert "recency" in names
        assert "career_overlap" in names

    def test_experiences_returned(self):
        profile = _make_profile_row()
        exp = _make_exp_row("Staff Engineer", "Google", date(2020, 1, 1), None, True, "Technology", "large")
        session = _make_mock_session(profile, exp_rows=[exp])

        result = get_profile_detail("conn_abc123", session)

        assert len(result["experiences"]) == 1
        assert result["experiences"][0]["role"] == "Staff Engineer"
        assert result["experiences"][0]["company"] == "Google"
        assert result["experiences"][0]["is_current"] is True

    def test_duration_computed_for_current_role(self):
        profile = _make_profile_row()
        exp = _make_exp_row("Engineer", "Acme", date(2023, 1, 1), None, True)
        session = _make_mock_session(profile, exp_rows=[exp])

        result = get_profile_detail("conn_abc123", session)

        assert result["experiences"][0]["duration_months"] is not None
        assert result["experiences"][0]["duration_months"] > 0

    def test_education_returned(self):
        profile = _make_profile_row()
        edu = _make_edu_row("Stanford", "MS", "Computer Science", 2018, 2020)
        session = _make_mock_session(profile, edu_rows=[edu])

        result = get_profile_detail("conn_abc123", session)

        assert len(result["education"]) == 1
        assert result["education"][0]["school"] == "Stanford"
        assert result["education"][0]["degree"] == "MS"

    def test_skills_with_query_highlighting(self):
        profile = _make_profile_row()
        skills = [_make_skill_row("Python"), _make_skill_row("Machine Learning"), _make_skill_row("Java")]
        session = _make_mock_session(profile, skill_rows=skills)

        result = get_profile_detail("conn_abc123", session, query="machine learning engineer")

        python_skill = next(s for s in result["skills"] if s["name"] == "Python")
        ml_skill = next(s for s in result["skills"] if s["name"] == "Machine Learning")
        java_skill = next(s for s in result["skills"] if s["name"] == "Java")

        assert ml_skill["is_featured"] is True
        assert python_skill["is_featured"] is False
        assert java_skill["is_featured"] is False

    def test_skills_no_query_all_unfeatured(self):
        profile = _make_profile_row()
        skills = [_make_skill_row("Python")]
        session = _make_mock_session(profile, skill_rows=skills)

        result = get_profile_detail("conn_abc123", session)

        assert result["skills"][0]["is_featured"] is False

    def test_tags_parsed_from_csv(self):
        profile = _make_profile_row(tags="ai,backend,startup")
        session = _make_mock_session(profile)

        result = get_profile_detail("conn_abc123", session)

        assert result["tags"] == ["ai", "backend", "startup"]

    def test_empty_tags_returns_empty_list(self):
        profile = _make_profile_row(tags=None)
        session = _make_mock_session(profile)

        result = get_profile_detail("conn_abc123", session)

        assert result["tags"] == []

    def test_connection_not_found(self):
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        session.execute.return_value = mock_result

        result = get_profile_detail("conn_nonexistent", session)

        assert "error" in result

    def test_empty_connection_id(self):
        session = MagicMock()
        result = get_profile_detail("", session)
        assert "error" in result

    def test_connected_at_stringified(self):
        profile = _make_profile_row(connected_at=date(2022, 3, 10))
        session = _make_mock_session(profile)

        result = get_profile_detail("conn_abc123", session)

        assert result["connected_at"] == "2022-03-10"

    def test_connection_source_from_sources_array(self):
        profile = _make_profile_row(sources=["LinkedIn", "Google Contacts"])
        session = _make_mock_session(profile)

        result = get_profile_detail("conn_abc123", session)

        assert result["connection_source"] == "LinkedIn"


class TestRequestEnrichment:
    def _make_session_with_row(self, row):
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = row
        session.execute.return_value = mock_result
        return session

    def test_not_enriched_profile(self):
        row = MagicMock()
        row.id = "conn_abc123"
        row.full_name = "Jane Doe"
        row.has_enriched_data = False
        row.linkedin_url = "https://linkedin.com/in/janedoe"
        row.last_crawled_at = None

        session = self._make_session_with_row(row)
        result = request_enrichment("conn_abc123", session)

        assert result["status"] == "not_enriched"
        assert result["requires_user_confirmation"] is True
        assert "basic data" in result["message"]

    def test_already_enriched_profile(self):
        row = MagicMock()
        row.id = "conn_abc123"
        row.full_name = "Jane Doe"
        row.has_enriched_data = True
        row.linkedin_url = "https://linkedin.com/in/janedoe"
        row.last_crawled_at = "2025-12-01T10:00:00Z"

        session = self._make_session_with_row(row)
        result = request_enrichment("conn_abc123", session)

        assert result["status"] == "already_enriched"
        assert result["requires_user_confirmation"] is True
        assert "re-crawl" in result["message"]

    def test_connection_not_found(self):
        session = self._make_session_with_row(None)
        result = request_enrichment("conn_missing", session)

        assert "error" in result

    def test_empty_connection_id(self):
        session = MagicMock()
        result = request_enrichment("", session)
        assert "error" in result
