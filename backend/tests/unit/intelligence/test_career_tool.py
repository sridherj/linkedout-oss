# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the career pattern analysis and role alias tools."""
from datetime import date
from unittest.mock import MagicMock

import pytest

from linkedout.intelligence.tools.career_tool import (
    _analyze_experiences,
    analyze_career_pattern,
    lookup_role_aliases,
)


class TestAnalyzeCareerPattern:
    def _mock_session(self, rows=None):
        session = MagicMock()
        result = MagicMock()
        result.fetchall.return_value = rows or []
        session.execute.return_value = result
        return session

    def test_empty_ids_returns_error(self):
        session = MagicMock()
        result = analyze_career_pattern([], session)
        assert "error" in result

    def test_missing_profile_returns_error_entry(self):
        session = self._mock_session(rows=[])
        result = analyze_career_pattern(["cp_nonexistent"], session)
        assert len(result["profiles"]) == 1
        assert "error" in result["profiles"][0]

    def test_caps_at_20_profiles(self):
        session = self._mock_session(rows=[])
        ids = [f"cp_{i}" for i in range(30)]
        result = analyze_career_pattern(ids, session)
        # Should only process 20, returning error for each (no data)
        assert len(result["profiles"]) == 20

    def test_returns_structured_profile_analysis(self):
        rows = [
            # (profile_id, full_name, position, company_name, seniority_level,
            #  start_date, end_date, is_current, industry, size_tier, employee_count)
            ("cp_1", "Alice", "SDE", "TCS", "junior",
             date(2018, 1, 1), date(2020, 6, 1), None, "IT Outsourcing", "enterprise", 500000),
            ("cp_1", "Alice", "Senior SDE", "Google", "senior",
             date(2020, 7, 1), None, True, "Internet", "enterprise", 180000),
        ]
        session = self._mock_session(rows=rows)
        result = analyze_career_pattern(["cp_1"], session)
        profile = result["profiles"][0]
        assert profile["id"] == "cp_1"
        assert profile["name"] == "Alice"
        assert profile["role_count"] == 2
        assert "avg_tenure_years" in profile
        assert "seniority_progression" in profile
        assert "company_transitions" in profile
        assert "career_velocity" in profile
        assert isinstance(profile["seniority_progression"], list)


class TestAnalyzeExperiences:
    def test_empty_experiences(self):
        result = _analyze_experiences([])
        assert result["avg_tenure_years"] is None
        assert result["role_count"] == 0

    def test_single_current_role(self):
        exps = [{
            "position": "Engineer",
            "company_name": "Google",
            "seniority_level": "senior",
            "start_date": date(2023, 1, 1),
            "end_date": None,
            "is_current": True,
            "industry": "Internet",
            "size_tier": "enterprise",
            "employee_count": 180000,
        }]
        result = _analyze_experiences(exps)
        assert result["current_role_duration_years"] is not None
        assert result["current_role_duration_years"] > 0
        assert "senior" in result["seniority_progression"]

    def test_seniority_progression_tracks_order(self):
        exps = [
            {"position": "Junior Dev", "company_name": "A", "seniority_level": "junior",
             "start_date": date(2015, 1, 1), "end_date": date(2017, 1, 1), "is_current": None,
             "industry": None, "size_tier": None, "employee_count": None},
            {"position": "Senior Dev", "company_name": "B", "seniority_level": "senior",
             "start_date": date(2017, 1, 1), "end_date": date(2020, 1, 1), "is_current": None,
             "industry": None, "size_tier": None, "employee_count": None},
            {"position": "Lead", "company_name": "C", "seniority_level": "lead",
             "start_date": date(2020, 1, 1), "end_date": None, "is_current": True,
             "industry": None, "size_tier": None, "employee_count": None},
        ]
        result = _analyze_experiences(exps)
        assert result["seniority_progression"] == ["junior", "senior", "lead"]
        assert result["career_velocity"] > 0

    def test_company_type_transitions(self):
        exps = [
            {"position": "Dev", "company_name": "TCS", "seniority_level": "junior",
             "start_date": date(2015, 1, 1), "end_date": date(2018, 1, 1), "is_current": None,
             "industry": "IT Outsourcing", "size_tier": "enterprise", "employee_count": 500000},
            {"position": "SDE", "company_name": "CoolStartup", "seniority_level": "senior",
             "start_date": date(2018, 1, 1), "end_date": None, "is_current": True,
             "industry": "Software", "size_tier": "small", "employee_count": 30},
        ]
        result = _analyze_experiences(exps)
        assert "services" in result["company_transitions"]
        assert "startup" in result["company_transitions"]


class TestLookupRoleAliases:
    def _mock_session(self, rows=None):
        session = MagicMock()
        result = MagicMock()
        result.fetchall.return_value = rows or []
        session.execute.return_value = result
        return session

    def test_empty_query_returns_error(self):
        session = MagicMock()
        result = lookup_role_aliases("", session)
        assert "error" in result

    def test_returns_structured_matches(self):
        rows = [
            ("Sr. Software Engineer", "Senior Software Engineer", "senior", "engineering"),
            ("Senior SDE", "Senior Software Engineer", "senior", "engineering"),
        ]
        session = self._mock_session(rows=rows)
        result = lookup_role_aliases("senior engineer", session)
        assert result["query"] == "senior engineer"
        assert result["match_count"] == 2
        assert len(result["matches"]) == 2
        match = result["matches"][0]
        assert "alias_title" in match
        assert "canonical_title" in match
        assert "seniority_level" in match
        assert "function_area" in match

    def test_no_matches(self):
        session = self._mock_session(rows=[])
        result = lookup_role_aliases("nonexistent role xyz", session)
        assert result["match_count"] == 0
        assert result["matches"] == []
