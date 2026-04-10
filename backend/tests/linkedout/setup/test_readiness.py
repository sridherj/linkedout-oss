# SPDX-License-Identifier: Apache-2.0
"""Tests for the readiness report module."""
import json
from pathlib import Path
from unittest.mock import patch

from linkedout.setup.readiness import (
    ReadinessReport,
    collect_readiness_data,
    compute_coverage,
    detect_gaps,
    format_console_report,
    save_report,
    suggest_next_steps,
)


class TestQueryDbCounts:
    @patch("shared.utilities.health_checks.get_db_stats")
    def test_query_db_counts_maps_from_health_checks(self, mock_get_stats):
        """Verify field mapping from get_db_stats to readiness counts."""
        from linkedout.setup.readiness import _query_db_counts
        from unittest.mock import MagicMock

        mock_get_stats.return_value = {
            'profiles_total': 100,
            'profiles_with_embeddings': 80,
            'profiles_without_embeddings': 20,
            'companies_total': 50,
            'connections_total': 200,
            'connections_with_affinity': 150,
            'connections_without_affinity': 50,
        }
        log = MagicMock()
        counts = _query_db_counts(log)

        assert counts['profiles_loaded'] == 100
        assert counts['profiles_with_embeddings'] == 80
        assert counts['profiles_without_embeddings'] == 20
        assert counts['companies_loaded'] == 50
        assert counts['connections_total'] == 200
        assert counts['connections_with_affinity'] == 150
        assert counts['connections_without_affinity'] == 50

    @patch("shared.utilities.health_checks.get_db_stats", side_effect=ImportError("no module"))
    def test_query_db_counts_handles_import_error(self, mock_get_stats):
        """Graceful fallback when health_checks import fails."""
        from linkedout.setup.readiness import _query_db_counts
        from unittest.mock import MagicMock

        log = MagicMock()
        counts = _query_db_counts(log)
        assert counts['profiles_loaded'] == 0
        assert counts['connections_total'] == 0

    @patch("shared.utilities.health_checks.check_db_connection")
    def test_check_db_connected_uses_health_check(self, mock_check):
        """Direct call to check_db_connection, no subprocess."""
        from linkedout.setup.readiness import _check_db_connected
        from shared.utilities.health_checks import HealthCheckResult

        mock_check.return_value = HealthCheckResult(check='db_connection', status='pass')
        assert _check_db_connected() is True

        mock_check.return_value = HealthCheckResult(check='db_connection', status='fail')
        assert _check_db_connected() is False


class TestCollectReadinessData:
    @patch("linkedout.setup.readiness._check_skills")
    @patch("linkedout.setup.readiness._check_config")
    @patch("linkedout.setup.readiness._query_db_counts")
    def test_returns_dict_with_expected_keys(
        self, mock_counts, mock_config, mock_skills
    ):
        mock_counts.return_value = {"profiles_loaded": 100}
        mock_config.return_value = {"embedding_provider": "openai"}
        mock_skills.return_value = {}

        result = collect_readiness_data("postgresql://localhost/test", Path("/tmp/data"))

        assert "counts" in result
        assert "config" in result
        assert "skills" in result


class TestComputeCoverage:
    def test_calculates_correct_percentages(self):
        data = {
            "counts": {
                "profiles_loaded": 1000,
                "profiles_with_embeddings": 997,
                "connections_total": 500,
                "connections_with_affinity": 500,
                "connections_company_matched": 480,
            }
        }

        result = compute_coverage(data)

        assert result["embedding_coverage_pct"] == 99.7
        assert result["affinity_coverage_pct"] == 100.0
        assert result["company_match_pct"] == 96.0

    def test_handles_zero_profiles(self):
        data = {
            "counts": {
                "profiles_loaded": 0,
                "profiles_with_embeddings": 0,
                "connections_total": 0,
                "connections_with_affinity": 0,
                "connections_company_matched": 0,
            }
        }

        result = compute_coverage(data)

        assert result["embedding_coverage_pct"] == 0.0
        assert result["affinity_coverage_pct"] == 0.0
        assert result["company_match_pct"] == 0.0

    def test_partial_coverage(self):
        data = {
            "counts": {
                "profiles_loaded": 200,
                "profiles_with_embeddings": 100,
                "connections_total": 200,
                "connections_with_affinity": 150,
                "connections_company_matched": 180,
            }
        }

        result = compute_coverage(data)

        assert result["embedding_coverage_pct"] == 50.0
        assert result["affinity_coverage_pct"] == 75.0
        assert result["company_match_pct"] == 90.0


class TestDetectGaps:
    def test_identifies_missing_embeddings(self):
        data = {
            "counts": {
                "profiles_without_embeddings": 14,
                "connections_without_affinity": 0,
                "companies_missing_aliases": 0,
            }
        }

        result = detect_gaps(data)

        assert len(result) == 1
        assert result[0]["type"] == "missing_embeddings"
        assert result[0]["count"] == 14
        assert "14" in result[0]["detail"]

    def test_returns_empty_list_when_no_gaps(self):
        data = {
            "counts": {
                "profiles_without_embeddings": 0,
                "connections_without_affinity": 0,
                "companies_missing_aliases": 0,
            }
        }

        result = detect_gaps(data)

        assert result == []

    def test_identifies_multiple_gaps(self):
        data = {
            "counts": {
                "profiles_without_embeddings": 10,
                "connections_without_affinity": 5,
                "companies_missing_aliases": 100,
            }
        }

        result = detect_gaps(data)

        assert len(result) == 3
        types = {g["type"] for g in result}
        assert types == {
            "missing_embeddings",
            "missing_affinity",
            "missing_company_aliases",
        }


class TestSuggestNextSteps:
    def test_suggests_embed_for_missing_embeddings(self):
        gaps = [{"type": "missing_embeddings", "count": 14, "detail": "..."}]

        result = suggest_next_steps(gaps)

        assert any("linkedout embed" in s for s in result)
        assert any("14" in s for s in result)

    def test_always_suggests_trying_tool(self):
        result = suggest_next_steps([])

        assert any("/linkedout" in s for s in result)

    def test_suggests_extension_when_no_embedding_gap(self):
        result = suggest_next_steps([])

        assert any("Chrome extension" in s for s in result)


class TestFormatConsoleReport:
    def test_produces_box_drawing_output(self):
        report = ReadinessReport(
            timestamp="2026-04-07T14:30:00Z",
            counts={
                "profiles_loaded": 4012,
                "profiles_with_embeddings": 3998,
                "companies_loaded": 52000,
                "connections_company_matched": 3691,
                "connections_total": 3870,
                "connections_with_affinity": 3870,
            },
            coverage={
                "embedding_coverage_pct": 99.7,
                "affinity_coverage_pct": 100.0,
                "company_match_pct": 95.9,
            },
            config={
                "embedding_provider": "openai",
                "data_dir": "~/linkedout-data/",
                "db_connected": True,
                "openai_key_configured": True,
                "apify_key_configured": False,
                "agent_context_env_exists": True,
            },
            skills={
                "Claude Code": {"installed": True, "skill_count": 4},
            },
            gaps=[
                {"type": "missing_embeddings", "count": 14, "detail": "14 profiles without embeddings"},
            ],
            next_steps=["Run `linkedout embed` to cover remaining 14 profiles"],
        )

        result = format_console_report(report)

        # Check box-drawing characters
        assert "\u2554" in result  # ╔
        assert "\u2557" in result  # ╗
        assert "\u255a" in result  # ╚
        assert "\u255d" in result  # ╝
        assert "Readiness" in result
        assert "4,012" in result
        assert "99.7%" in result
        assert "Gaps" in result
        assert "\u26a0" in result  # ⚠

    def test_no_gaps_shows_get_started(self):
        report = ReadinessReport(
            timestamp="2026-04-07T14:30:00Z",
            counts={
                "profiles_loaded": 100,
                "profiles_with_embeddings": 100,
                "companies_loaded": 500,
                "connections_company_matched": 50,
                "connections_total": 50,
                "connections_with_affinity": 50,
            },
            coverage={
                "embedding_coverage_pct": 100.0,
                "affinity_coverage_pct": 100.0,
                "company_match_pct": 100.0,
            },
            config={
                "embedding_provider": "local",
                "data_dir": "~/linkedout-data/",
                "db_connected": True,
                "openai_key_configured": False,
                "apify_key_configured": False,
                "agent_context_env_exists": True,
            },
            skills={},
            gaps=[],
            next_steps=["Try: /linkedout"],
        )

        result = format_console_report(report)

        assert "No gaps found" in result
        assert "Get Started" in result


class TestSaveReport:
    def test_writes_valid_json(self, tmp_path):
        report = ReadinessReport(
            timestamp="2026-04-07T14:30:00Z",
            counts={"profiles_loaded": 100},
            coverage={"embedding_coverage_pct": 100.0},
            config={"embedding_provider": "openai", "db_connected": True},
            gaps=[],
            next_steps=[],
        )

        filepath = save_report(report, tmp_path)

        assert filepath.exists()
        assert filepath.suffix == ".json"

        data = json.loads(filepath.read_text(encoding="utf-8"))
        assert data["operation"] == "setup-readiness"
        assert data["counts"]["profiles_loaded"] == 100

    def test_creates_reports_directory(self, tmp_path):
        report = ReadinessReport(
            timestamp="2026-04-07T14:30:00Z",
            counts={},
            coverage={},
            config={},
            gaps=[],
            next_steps=[],
        )

        data_dir = tmp_path / "nonexistent"
        filepath = save_report(report, data_dir)

        assert filepath.exists()
        assert (data_dir / "reports").is_dir()

    def test_report_contains_all_fields(self, tmp_path):
        report = ReadinessReport(
            timestamp="2026-04-07T14:30:00Z",
            counts={"profiles_loaded": 50},
            coverage={"embedding_coverage_pct": 95.0},
            config={"embedding_provider": "local", "openai_key_configured": False},
            skills={"Claude Code": {"installed": True}},
            gaps=[{"type": "missing_embeddings", "count": 5, "detail": "5 missing"}],
            next_steps=["Run linkedout embed"],
        )

        filepath = save_report(report, tmp_path)
        data = json.loads(filepath.read_text(encoding="utf-8"))

        assert "operation" in data
        assert "timestamp" in data
        assert "linkedout_version" in data
        assert "counts" in data
        assert "coverage" in data
        assert "config" in data
        assert "gaps" in data
        assert "next_steps" in data

    def test_no_api_keys_in_report(self, tmp_path):
        report = ReadinessReport(
            timestamp="2026-04-07T14:30:00Z",
            counts={},
            coverage={},
            config={
                "embedding_provider": "openai",
                "openai_key_configured": True,
                "db_connected": True,
            },
            gaps=[],
            next_steps=[],
        )

        filepath = save_report(report, tmp_path)
        content = filepath.read_text(encoding="utf-8")

        assert "sk-" not in content
        assert "password" not in content.lower()
