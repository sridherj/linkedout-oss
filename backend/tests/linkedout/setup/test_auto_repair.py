# SPDX-License-Identifier: Apache-2.0
"""Tests for the gap detection and auto-repair module."""
from unittest.mock import patch

from linkedout.setup.auto_repair import (
    RepairAction,
    analyze_gaps,
    execute_repair,
)
from linkedout.setup.readiness import ReadinessReport


class TestAnalyzeGaps:
    def test_identifies_missing_embeddings_gap(self):
        report = ReadinessReport(
            gaps=[
                {"type": "missing_embeddings", "count": 14, "detail": "14 profiles without embeddings"},
            ],
        )

        actions = analyze_gaps(report)

        assert len(actions) == 1
        assert actions[0].gap_type == "missing_embeddings"
        assert actions[0].default_accept is True
        assert "embed" in actions[0].command

    def test_returns_empty_list_when_no_gaps(self):
        report = ReadinessReport(gaps=[])

        actions = analyze_gaps(report)

        assert actions == []

    def test_identifies_missing_affinity_gap(self):
        report = ReadinessReport(
            gaps=[
                {"type": "missing_affinity", "count": 47, "detail": "47 connections without scores"},
            ],
        )

        actions = analyze_gaps(report)

        assert len(actions) == 1
        assert actions[0].gap_type == "missing_affinity"
        assert "compute-affinity" in actions[0].command

    def test_skips_unknown_gap_types(self):
        report = ReadinessReport(
            gaps=[
                {"type": "unknown_type", "count": 5, "detail": "something unknown"},
            ],
        )

        actions = analyze_gaps(report)

        assert actions == []

    def test_multiple_gaps_produce_multiple_actions(self):
        report = ReadinessReport(
            gaps=[
                {"type": "missing_embeddings", "count": 10, "detail": "..."},
                {"type": "missing_affinity", "count": 5, "detail": "..."},
            ],
        )

        actions = analyze_gaps(report)

        assert len(actions) == 2
        types = {a.gap_type for a in actions}
        assert types == {"missing_embeddings", "missing_affinity"}


class TestRepairActionDefaults:
    def test_missing_embeddings_defaults_to_accept(self):
        report = ReadinessReport(
            gaps=[{"type": "missing_embeddings", "count": 1, "detail": "..."}],
        )
        actions = analyze_gaps(report)

        assert actions[0].default_accept is True

    def test_stale_embeddings_defaults_to_reject(self):
        report = ReadinessReport(
            gaps=[{"type": "stale_embeddings", "count": 200, "detail": "..."}],
        )
        actions = analyze_gaps(report)

        assert actions[0].default_accept is False


class TestExecuteRepair:
    @patch("linkedout.setup.auto_repair.subprocess.run")
    def test_calls_correct_cli_command(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Done"
        mock_run.return_value.stderr = ""

        action = RepairAction(
            gap_type="missing_embeddings",
            description="14 profiles without embeddings",
            command="linkedout embed",
            default_accept=True,
            estimated_time="~2 minutes",
            estimated_cost=None,
        )

        execute_repair(action)

        call_args = mock_run.call_args[0][0]
        assert "embed" in call_args

    @patch("linkedout.setup.auto_repair.subprocess.run")
    def test_returns_success_report(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""

        action = RepairAction(
            gap_type="missing_embeddings",
            description="test",
            command="linkedout embed",
            default_accept=True,
            estimated_time="~2 minutes",
            estimated_cost=None,
        )

        report = execute_repair(action)

        assert report.counts.succeeded == 1
        assert report.counts.failed == 0
        assert report.operation == "repair-missing_embeddings"

    @patch("linkedout.setup.auto_repair.subprocess.run")
    def test_returns_failure_report_on_error(self, mock_run):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "command failed"

        action = RepairAction(
            gap_type="missing_affinity",
            description="test",
            command="linkedout compute-affinity --force",
            default_accept=True,
            estimated_time="~1 minute",
            estimated_cost=None,
        )

        report = execute_repair(action)

        assert report.counts.failed == 1
        assert report.counts.succeeded == 0

    @patch("linkedout.setup.auto_repair.subprocess.run")
    def test_affinity_repair_calls_correct_command(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""

        action = RepairAction(
            gap_type="missing_affinity",
            description="test",
            command="linkedout compute-affinity --force",
            default_accept=True,
            estimated_time="~1 minute",
            estimated_cost=None,
        )

        execute_repair(action)

        call_args = mock_run.call_args[0][0]
        assert "compute-affinity" in call_args
        assert "--force" in call_args
