# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the ``linkedout enrich`` CLI command.

Tests cover dry-run output, limit option, empty state, missing Apify key,
skip-embeddings flag, progress callback, and summary output format.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

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


def _mock_config(cost_per=0.004, skip_embeddings=True, data_dir=None):
    """Create a mock config with enrichment settings."""
    cfg = MagicMock()
    cfg.enrichment.cost_per_profile_usd = cost_per
    cfg.enrichment.skip_embeddings = skip_embeddings
    # data_dir must be a real path so Path(cfg.data_dir) works
    cfg.data_dir = data_dir or '/tmp/linkedout-test-nonexistent'
    return cfg


def _mock_enrich_result(enriched=0, failed=0, batches_completed=0,
                        batches_total=0, stopped_reason=None):
    """Create a mock EnrichmentResult."""
    result = MagicMock()
    result.enriched = enriched
    result.failed = failed
    result.batches_completed = batches_completed
    result.batches_total = batches_total
    result.stopped_reason = stopped_reason
    return result


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
        """--limit N should only pass N profiles to the pipeline."""
        profiles = [(f'cp_{i}', f'https://linkedin.com/in/user{i}') for i in range(10)]
        mock_result = _mock_enrich_result(enriched=3, batches_completed=1, batches_total=1)

        with patch('linkedout.commands.enrich.cli_db_manager', return_value=_mock_db_manager(profiles)), \
             patch('linkedout.commands.enrich.get_config', return_value=_mock_config()), \
             patch('linkedout.commands.enrich.get_platform_apify_key', return_value='fake_key'), \
             patch('linkedout.enrichment_pipeline.bulk_enrichment.enrich_profiles', return_value=mock_result) as mock_enrich, \
             patch('linkedout.commands.enrich.record_metric'), \
             patch('linkedout.commands.enrich.OperationReport') as mock_report:
            mock_report.return_value.save.return_value = MagicMock(
                relative_to=MagicMock(return_value='linkedout-data/reports/enrich.json')
            )
            result = runner.invoke(enrich_command, ['--limit', '3'])

        assert result.exit_code == 0
        # Verify enrich_profiles was called with only 3 profiles
        call_args = mock_enrich.call_args
        assert len(call_args.kwargs['profiles']) == 3


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


class TestSkipEmbeddings:
    """Verify --skip-embeddings flag behavior."""

    def test_skip_embeddings_next_steps(self, runner):
        """--skip-embeddings should include embed in next steps."""
        profiles = [('cp_1', 'https://linkedin.com/in/alice')]
        mock_result = _mock_enrich_result(enriched=1, batches_completed=1, batches_total=1)

        with patch('linkedout.commands.enrich.cli_db_manager', return_value=_mock_db_manager(profiles)), \
             patch('linkedout.commands.enrich.get_config', return_value=_mock_config()), \
             patch('linkedout.commands.enrich.get_platform_apify_key', return_value='fake_key'), \
             patch('linkedout.enrichment_pipeline.bulk_enrichment.enrich_profiles', return_value=mock_result), \
             patch('linkedout.commands.enrich.record_metric'), \
             patch('linkedout.commands.enrich.OperationReport') as mock_report:
            mock_report.return_value.save.return_value = MagicMock(
                relative_to=MagicMock(return_value='linkedout-data/reports/enrich.json')
            )
            result = runner.invoke(enrich_command, ['--skip-embeddings'])

        assert result.exit_code == 0
        assert 'linkedout embed' in result.output


class TestSummaryOutput:
    """Verify summary output for various pipeline results."""

    def test_all_keys_exhausted(self, runner):
        """Should show 'all API keys exhausted' when pipeline stops for that reason."""
        profiles = [('cp_1', 'https://linkedin.com/in/alice')]
        mock_result = _mock_enrich_result(
            enriched=0, failed=1, batches_completed=0, batches_total=1,
            stopped_reason='all_keys_exhausted',
        )

        with patch('linkedout.commands.enrich.cli_db_manager', return_value=_mock_db_manager(profiles)), \
             patch('linkedout.commands.enrich.get_config', return_value=_mock_config()), \
             patch('linkedout.commands.enrich.get_platform_apify_key', return_value='fake_key'), \
             patch('linkedout.enrichment_pipeline.bulk_enrichment.enrich_profiles', return_value=mock_result), \
             patch('linkedout.commands.enrich.record_metric'), \
             patch('linkedout.commands.enrich.OperationReport') as mock_report:
            mock_report.return_value.save.return_value = MagicMock(
                relative_to=MagicMock(return_value='linkedout-data/reports/enrich.json')
            )
            result = runner.invoke(enrich_command, [])

        assert result.exit_code == 0
        assert 'all API keys exhausted' in result.output

    def test_successful_enrichment_summary(self, runner):
        """Successful run should show enriched/failed counts and batch info."""
        profiles = [(f'cp_{i}', f'https://linkedin.com/in/user{i}') for i in range(5)]
        mock_result = _mock_enrich_result(
            enriched=4, failed=1, batches_completed=1, batches_total=1,
        )

        with patch('linkedout.commands.enrich.cli_db_manager', return_value=_mock_db_manager(profiles)), \
             patch('linkedout.commands.enrich.get_config', return_value=_mock_config()), \
             patch('linkedout.commands.enrich.get_platform_apify_key', return_value='fake_key'), \
             patch('linkedout.enrichment_pipeline.bulk_enrichment.enrich_profiles', return_value=mock_result), \
             patch('linkedout.commands.enrich.record_metric'), \
             patch('linkedout.commands.enrich.OperationReport') as mock_report:
            mock_report.return_value.save.return_value = MagicMock(
                relative_to=MagicMock(return_value='linkedout-data/reports/enrich.json')
            )
            result = runner.invoke(enrich_command, [])

        assert result.exit_code == 0
        assert '4' in result.output
        assert '1/1 batches' in result.output


class TestHelpText:
    """Verify the command help text is useful."""

    def test_help_shows_options(self, runner):
        result = runner.invoke(enrich_command, ['--help'])
        assert result.exit_code == 0
        assert '--limit' in result.output
        assert '--dry-run' in result.output
        assert '--skip-embeddings' in result.output

    def test_help_includes_description(self, runner):
        result = runner.invoke(enrich_command, ['--help'])
        assert 'enrich' in result.output.lower() or 'Apify' in result.output


class TestDryRunRecovery:
    """Verify dry-run reports recoverable batches from prior incomplete runs."""

    def test_dry_run_reports_recoverable_batches(self, runner):
        """Dry-run should report profiles with completed Apify runs awaiting collection."""
        from linkedout.enrichment_pipeline.bulk_enrichment import RecoverySummary
        profiles = [(f'cp_{i}', f'https://linkedin.com/in/user{i}') for i in range(10)]
        recovery = RecoverySummary(recovered=3, failed=0, still_running=0)

        with patch('linkedout.commands.enrich.cli_db_manager', return_value=_mock_db_manager(profiles)), \
             patch('linkedout.commands.enrich.get_config', return_value=_mock_config()), \
             patch('linkedout.commands.enrich.check_recoverable_batches', return_value=recovery):
            result = runner.invoke(enrich_command, ['--dry-run'])

        assert result.exit_code == 0
        assert '10 unenriched profiles found' in result.output
        assert '3 have completed Apify runs awaiting collection' in result.output
        assert '7 need new Apify enrichment' in result.output

    def test_dry_run_no_recoverable(self, runner):
        """Dry-run with no recoverable batches shows standard cost estimate."""
        from linkedout.enrichment_pipeline.bulk_enrichment import RecoverySummary
        profiles = [('cp_1', 'https://linkedin.com/in/alice')]
        recovery = RecoverySummary()

        with patch('linkedout.commands.enrich.cli_db_manager', return_value=_mock_db_manager(profiles)), \
             patch('linkedout.commands.enrich.get_config', return_value=_mock_config()), \
             patch('linkedout.commands.enrich.check_recoverable_batches', return_value=recovery):
            result = runner.invoke(enrich_command, ['--dry-run'])

        assert result.exit_code == 0
        assert 'Dry run: 1 unenriched profiles found' in result.output
        assert 'awaiting collection' not in result.output

    def test_dry_run_reports_still_running(self, runner):
        """Dry-run should report batches still running on Apify."""
        from linkedout.enrichment_pipeline.bulk_enrichment import RecoverySummary
        profiles = [(f'cp_{i}', f'https://linkedin.com/in/user{i}') for i in range(5)]
        recovery = RecoverySummary(recovered=0, still_running=2)

        with patch('linkedout.commands.enrich.cli_db_manager', return_value=_mock_db_manager(profiles)), \
             patch('linkedout.commands.enrich.get_config', return_value=_mock_config()), \
             patch('linkedout.commands.enrich.check_recoverable_batches', return_value=recovery):
            result = runner.invoke(enrich_command, ['--dry-run'])

        assert result.exit_code == 0
        assert '2 in batches still running on Apify' in result.output


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


class TestBuildNextSteps:
    """Test the _build_next_steps helper."""

    def test_with_embeddings(self):
        from linkedout.commands.enrich import _build_next_steps
        steps = _build_next_steps(skip_embeddings=False)
        assert len(steps) == 1
        assert 'affinity' in steps[0]

    def test_without_embeddings(self):
        from linkedout.commands.enrich import _build_next_steps
        steps = _build_next_steps(skip_embeddings=True)
        assert len(steps) == 2
        assert 'embed' in steps[0]
