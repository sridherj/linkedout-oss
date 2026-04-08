# SPDX-License-Identifier: Apache-2.0
"""Tests for affinity computation setup module."""
from pathlib import Path
from unittest.mock import patch

import pytest

from linkedout.setup.affinity import (
    check_user_profile_exists,
    format_tier_distribution,
    run_affinity_computation,
    setup_affinity,
)
from shared.utilities.operation_report import OperationCounts, OperationReport


class TestCheckUserProfileExists:
    @patch("linkedout.setup.affinity.subprocess.run")
    def test_returns_true_when_profile_exists(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Computing affinity for 1 user(s)...\nDry run -- no changes written."
        mock_run.return_value.stderr = ""

        assert check_user_profile_exists("postgresql://localhost/test") is True

    @patch("linkedout.setup.affinity.subprocess.run")
    def test_returns_false_when_no_profile(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Computing affinity for 0 user(s)...\nDry run -- no changes written."
        mock_run.return_value.stderr = ""

        assert check_user_profile_exists("postgresql://localhost/test") is False

    @patch("linkedout.setup.affinity.subprocess.run")
    def test_returns_false_on_command_failure(self, mock_run):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = "DB connection failed"

        assert check_user_profile_exists("postgresql://localhost/test") is False


class TestRunAffinityComputation:
    @patch("linkedout.setup.affinity.subprocess.run")
    def test_calls_compute_affinity_command(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = (
            "Results:\n"
            "  Connections updated: 3,500\n"
            "  Users processed:    1\n"
        )
        mock_run.return_value.stderr = ""

        report = run_affinity_computation()

        call_args = mock_run.call_args[0][0]
        assert "compute-affinity" in call_args
        assert report.operation == "setup-affinity"

    @patch("linkedout.setup.affinity.subprocess.run")
    def test_report_includes_connection_count(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = (
            "Results:\n"
            "  Connections updated: 2,500\n"
        )
        mock_run.return_value.stderr = ""

        report = run_affinity_computation()

        assert report.counts.succeeded == 2500

    @patch("linkedout.setup.affinity.subprocess.run")
    def test_raises_on_failure(self, mock_run):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Database error"
        mock_run.return_value.stdout = ""

        with pytest.raises(RuntimeError, match="compute-affinity failed"):
            run_affinity_computation()


class TestFormatTierDistribution:
    def test_produces_human_readable_output(self):
        report = OperationReport(
            operation="setup-affinity",
            counts=OperationCounts(total=3000, succeeded=3000),
        )

        result = format_tier_distribution(report)

        assert "3,000" in result
        assert "Inner circle" in result
        assert "Active" in result
        assert "Familiar" in result
        assert "Acquaintance" in result

    def test_includes_tier_explanations(self):
        report = OperationReport(
            operation="setup-affinity",
            counts=OperationCounts(total=100, succeeded=100),
        )

        result = format_tier_distribution(report)

        assert "closest professional" in result
        assert "rank" in result.lower()


class TestSetupAffinity:
    @patch("linkedout.setup.affinity.run_affinity_computation")
    @patch("linkedout.setup.affinity.check_user_profile_exists")
    def test_fails_with_clear_error_when_no_user_profile(
        self, mock_check, mock_run
    ):
        mock_check.return_value = False

        report = setup_affinity(Path("/tmp/test"), "postgresql://localhost/test")

        assert report.counts.failed == 1
        mock_run.assert_not_called()

    @patch("linkedout.setup.affinity.run_affinity_computation")
    @patch("linkedout.setup.affinity.check_user_profile_exists")
    def test_runs_when_profile_exists(self, mock_check, mock_run):
        mock_check.return_value = True
        mock_run.return_value = OperationReport(
            operation="setup-affinity",
            counts=OperationCounts(total=1000, succeeded=1000),
        )

        report = setup_affinity(Path("/tmp/test"), "postgresql://localhost/test")

        assert report.counts.succeeded == 1000
        mock_run.assert_called_once()
