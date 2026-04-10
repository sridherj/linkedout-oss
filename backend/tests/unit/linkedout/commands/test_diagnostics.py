# SPDX-License-Identifier: Apache-2.0
"""Tests for the diagnostics command — health status and issues."""
from __future__ import annotations

from unittest.mock import patch

from shared.utilities.health_checks import compute_issues


class TestComputeIssuesInDiagnostics:
    """Tests for compute_issues() as used by diagnostics."""

    def _healthy_stats(self):
        return {
            'system_tenant_exists': True,
            'system_bu_exists': True,
            'system_user_exists': True,
            'owner_profile_exists': True,
            'profiles_total': 100,
            'profiles_without_embeddings': 0,
            'profiles_unenriched': 0,
            'connections_without_affinity': 0,
        }

    def test_health_status_healthy_on_clean_system(self):
        """Badge HEALTHY, all counts 0 on clean system."""
        stats = self._healthy_stats()
        issues = compute_issues(stats, [])
        assert issues == []

    def test_health_status_action_required_on_critical(self):
        """Badge ACTION_REQUIRED when there's a CRITICAL issue."""
        stats = self._healthy_stats()
        stats['system_tenant_exists'] = False
        issues = compute_issues(stats, [])
        severities = {i['severity'] for i in issues}
        assert 'CRITICAL' in severities

    def test_health_status_needs_attention_on_warning(self):
        """Badge NEEDS_ATTENTION when there's a WARNING but no CRITICAL."""
        stats = self._healthy_stats()
        stats['profiles_without_embeddings'] = 10
        issues = compute_issues(stats, [])
        severities = {i['severity'] for i in issues}
        assert 'WARNING' in severities
        assert 'CRITICAL' not in severities


class TestBuildReport:
    """Tests for _build_report() output structure."""

    @patch('linkedout.commands.diagnostics._collect_health_checks')
    @patch('linkedout.commands.diagnostics._collect_db_stats')
    @patch('linkedout.commands.diagnostics._collect_config_info')
    @patch('linkedout.commands.diagnostics._collect_system_info')
    def test_build_report_includes_issues_and_status(
        self, mock_sys, mock_config, mock_db, mock_checks,
    ):
        """_build_report() includes health_status and issues keys."""
        mock_sys.return_value = {}
        mock_config.return_value = {}
        mock_db.return_value = {
            'connected': True,
            'system_tenant_exists': True,
            'system_bu_exists': True,
            'system_user_exists': True,
            'owner_profile_exists': True,
            'profiles_total': 10,
            'profiles_without_embeddings': 0,
            'profiles_unenriched': 0,
            'connections_without_affinity': 0,
        }
        mock_checks.return_value = []

        from linkedout.commands.diagnostics import _build_report
        report = _build_report()

        assert 'health_status' in report
        assert 'issues' in report
        assert report['health_status']['badge'] == 'HEALTHY'
        assert isinstance(report['issues'], list)
