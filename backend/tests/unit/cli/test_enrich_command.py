# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the ``linkedout enrich`` CLI command.

Tests cover dry-run output, limit option, empty state, missing Apify key,
signal handler (Ctrl+C), and progress line format.
"""
from __future__ import annotations

import signal
from unittest.mock import MagicMock, patch, call

import pytest
from click.testing import CliRunner

from linkedout.commands.enrich import enrich_command


@pytest.fixture
def runner():
    """Create a Click CliRunner for testing CLI commands."""
    return CliRunner()


def _mock_db_manager(rows):
    """Create a mock cli_db_manager that returns the given rows for SELECT."""
    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.return_value = rows
    mock_db = MagicMock()
    mock_db.get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)
    return mock_db


def _mock_config(cost_per=0.004):
    """Create a mock config with enrichment settings."""
    cfg = MagicMock()
    cfg.enrichment.cost_per_profile_usd = cost_per
    return cfg


class TestDryRun:
    """Verify dry-run output format."""

    def test_dry_run_shows_count_and_cost(self, runner):
        """--dry-run should show unenriched count and cost estimate."""
        profiles = [('cp_1', 'https://linkedin.com/in/alice'),
                    ('cp_2', 'https://linkedin.com/in/bob')]

        with patch('linkedout.commands.enrich.cli_db_manager', return_value=_mock_db_manager(profiles)), \
             patch('linkedout.commands.enrich.get_config', return_value=_mock_config()):
            result = runner.invoke(enrich_command, ['--dry-run'])

        assert result.exit_code == 0
        assert 'Dry run: 2 unenriched profiles found' in result.output
        assert '$0.01' in result.output  # 2 * 0.004 = 0.008, rounded to 0.01
        assert 'linkedout enrich' in result.output

    def test_dry_run_large_count(self, runner):
        """Dry-run with many profiles shows formatted cost."""
        profiles = [(f'cp_{i}', f'https://linkedin.com/in/user{i}') for i in range(13574)]

        with patch('linkedout.commands.enrich.cli_db_manager', return_value=_mock_db_manager(profiles)), \
             patch('linkedout.commands.enrich.get_config', return_value=_mock_config()):
            result = runner.invoke(enrich_command, ['--dry-run'])

        assert result.exit_code == 0
        assert '13,574' in result.output
        assert '$54.30' in result.output


class TestLimitOption:
    """Verify --limit restricts the number of profiles enriched."""

    def test_limit_restricts_enrichment_count(self, runner):
        """--limit N should only enrich N profiles."""
        profiles = [(f'cp_{i}', f'https://linkedin.com/in/user{i}') for i in range(10)]
        enriched_count = 0

        def mock_enrich_sync(url):
            nonlocal enriched_count
            enriched_count += 1
            return {'firstName': 'Test', 'lastName': 'User'}

        mock_client = MagicMock()
        mock_client.enrich_profile_sync.side_effect = mock_enrich_sync

        mock_write_session = MagicMock()
        # Make flush set a fake id on the event
        def flush_side_effect():
            for c in mock_write_session.add.call_args_list:
                obj = c[0][0]
                if not hasattr(obj, 'id') or obj.id is None:
                    obj.id = 'ee_fake_001'
        mock_write_session.flush.side_effect = flush_side_effect

        mock_db = MagicMock()
        # First call is READ (query), subsequent are WRITE (per-profile)
        read_session = MagicMock()
        read_session.execute.return_value.fetchall.return_value = profiles

        mock_db.get_session.return_value.__enter__ = MagicMock(side_effect=[read_session] + [mock_write_session] * 3)
        mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)

        with patch('linkedout.commands.enrich.cli_db_manager', return_value=mock_db), \
             patch('linkedout.commands.enrich.get_config', return_value=_mock_config()), \
             patch('linkedout.commands.enrich.get_platform_apify_key', return_value='fake_key'), \
             patch('linkedout.commands.enrich.LinkedOutApifyClient', return_value=mock_client), \
             patch('linkedout.commands.enrich.PostEnrichmentService') as mock_pes, \
             patch('linkedout.commands.enrich.record_metric'), \
             patch('linkedout.commands.enrich.OperationReport') as mock_report:
            mock_report.return_value.save.return_value = MagicMock(
                relative_to=MagicMock(return_value='linkedout-data/reports/enrich.json')
            )
            result = runner.invoke(enrich_command, ['--limit', '3'])

        assert result.exit_code == 0
        assert enriched_count == 3


class TestEmptyState:
    """Verify behavior when all profiles are already enriched."""

    def test_zero_unenriched_exits_cleanly(self, runner):
        """No unenriched profiles should print a clear message."""
        with patch('linkedout.commands.enrich.cli_db_manager', return_value=_mock_db_manager([])), \
             patch('linkedout.commands.enrich.get_config', return_value=_mock_config()):
            result = runner.invoke(enrich_command, [])

        assert result.exit_code == 0
        assert 'All profiles are enriched' in result.output


class TestMissingApifyKey:
    """Verify clean error message when Apify key is not configured."""

    def test_missing_key_shows_instructions(self, runner):
        """Missing Apify key should show setup instructions, not a traceback."""
        profiles = [('cp_1', 'https://linkedin.com/in/alice')]

        with patch('linkedout.commands.enrich.cli_db_manager', return_value=_mock_db_manager(profiles)), \
             patch('linkedout.commands.enrich.get_config', return_value=_mock_config()), \
             patch('linkedout.commands.enrich.get_platform_apify_key', side_effect=ValueError('No key')):
            result = runner.invoke(enrich_command, [])

        assert result.exit_code == 1
        assert 'No Apify API key configured' in result.output
        assert 'APIFY_API_KEY' in result.output
        assert 'secrets.yaml' in result.output


class TestSignalHandler:
    """Verify Ctrl+C produces a clean exit with partial progress."""

    def test_interrupt_shows_partial_progress(self, runner):
        """Ctrl+C during enrichment should show partial progress summary."""
        profiles = [(f'cp_{i}', f'https://linkedin.com/in/user{i}') for i in range(100)]
        call_count = 0

        def mock_enrich(url):
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                # Simulate Ctrl+C by raising KeyboardInterrupt via signal handler
                import os
                os.kill(os.getpid(), signal.SIGINT)
            return {'firstName': 'Test'}

        mock_client = MagicMock()
        mock_client.enrich_profile_sync.side_effect = mock_enrich

        mock_write_session = MagicMock()
        def flush_side_effect():
            for c in mock_write_session.add.call_args_list:
                obj = c[0][0]
                if not hasattr(obj, 'id') or obj.id is None:
                    obj.id = 'ee_fake'
        mock_write_session.flush.side_effect = flush_side_effect

        mock_db = MagicMock()
        read_session = MagicMock()
        read_session.execute.return_value.fetchall.return_value = profiles

        mock_db.get_session.return_value.__enter__ = MagicMock(
            side_effect=[read_session] + [mock_write_session] * 100
        )
        mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)

        with patch('linkedout.commands.enrich.cli_db_manager', return_value=mock_db), \
             patch('linkedout.commands.enrich.get_config', return_value=_mock_config()), \
             patch('linkedout.commands.enrich.get_platform_apify_key', return_value='fake_key'), \
             patch('linkedout.commands.enrich.LinkedOutApifyClient', return_value=mock_client), \
             patch('linkedout.commands.enrich.PostEnrichmentService') as mock_pes, \
             patch('linkedout.commands.enrich.record_metric'), \
             patch('linkedout.commands.enrich.OperationReport'):
            result = runner.invoke(enrich_command, [])

        assert 'Interrupted' in result.output


class TestProgressLineFormat:
    """Verify progress lines follow the expected format."""

    def test_progress_lines_emitted(self, runner):
        """Progress lines should appear with count, percentage, cost, and timing."""
        # Create exactly 25 profiles so we get one progress line at the boundary
        profiles = [(f'cp_{i}', f'https://linkedin.com/in/user{i}') for i in range(25)]

        mock_client = MagicMock()
        mock_client.enrich_profile_sync.return_value = {'firstName': 'Test'}

        mock_write_session = MagicMock()
        def flush_side_effect():
            for c in mock_write_session.add.call_args_list:
                obj = c[0][0]
                if not hasattr(obj, 'id') or obj.id is None:
                    obj.id = 'ee_fake'
        mock_write_session.flush.side_effect = flush_side_effect

        mock_db = MagicMock()
        read_session = MagicMock()
        read_session.execute.return_value.fetchall.return_value = profiles

        mock_db.get_session.return_value.__enter__ = MagicMock(
            side_effect=[read_session] + [mock_write_session] * 25
        )
        mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)

        with patch('linkedout.commands.enrich.cli_db_manager', return_value=mock_db), \
             patch('linkedout.commands.enrich.get_config', return_value=_mock_config()), \
             patch('linkedout.commands.enrich.get_platform_apify_key', return_value='fake_key'), \
             patch('linkedout.commands.enrich.LinkedOutApifyClient', return_value=mock_client), \
             patch('linkedout.commands.enrich.PostEnrichmentService') as mock_pes, \
             patch('linkedout.commands.enrich.record_metric'), \
             patch('linkedout.commands.enrich.OperationReport') as mock_report:
            mock_report.return_value.save.return_value = MagicMock(
                relative_to=MagicMock(return_value='linkedout-data/reports/enrich.json')
            )
            result = runner.invoke(enrich_command, [])

        assert result.exit_code == 0
        # Should contain progress line with 25/25 and percentage
        assert '25/25' in result.output
        assert '100.0%' in result.output
        assert 'spent' in result.output


class TestHelpText:
    """Verify the command help text is useful."""

    def test_help_shows_options(self, runner):
        result = runner.invoke(enrich_command, ['--help'])
        assert result.exit_code == 0
        assert '--limit' in result.output
        assert '--dry-run' in result.output

    def test_help_includes_description(self, runner):
        result = runner.invoke(enrich_command, ['--help'])
        assert 'enrich' in result.output.lower() or 'Apify' in result.output


class TestFormatDuration:
    """Test the _format_duration helper."""

    def test_seconds(self):
        from linkedout.commands.enrich import _format_duration
        assert _format_duration(45) == "45s"

    def test_minutes(self):
        from linkedout.commands.enrich import _format_duration
        assert _format_duration(125) == "2m 5s"

    def test_hours(self):
        from linkedout.commands.enrich import _format_duration
        assert _format_duration(3661) == "1h 1m"
