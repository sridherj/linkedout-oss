# SPDX-License-Identifier: Apache-2.0
"""End-to-end CLI flow tests for ``linkedout enrich`` with mocked Apify client.

Tests cover the full dry-run → enrich cycle, credit exhaustion handling,
and the zero-unenriched-profiles edge case.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from linkedout.commands.enrich import enrich_command
from linkedout.enrichment_pipeline.apify_client import ApifyCreditExhaustedError


@pytest.fixture
def runner():
    return CliRunner()


def _mock_db_manager(rows):
    """Create a mock cli_db_manager that returns the given rows for the SELECT query."""
    mock_session = MagicMock()
    mock_session.execute.return_value.fetchall.return_value = rows
    mock_db = MagicMock()
    mock_db.get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)
    return mock_db


def _mock_db_manager_with_writes(rows, write_session):
    """Create a mock that returns read session first, then write sessions."""
    read_session = MagicMock()
    read_session.execute.return_value.fetchall.return_value = rows
    mock_db = MagicMock()
    mock_db.get_session.return_value.__enter__ = MagicMock(
        side_effect=[read_session] + [write_session] * len(rows)
    )
    mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)
    return mock_db


def _mock_config(cost_per=0.004):
    cfg = MagicMock()
    cfg.enrichment.cost_per_profile_usd = cost_per
    return cfg


def _mock_write_session():
    """Create a mock write session that assigns fake IDs on flush."""
    session = MagicMock()
    def flush_side_effect():
        for c in session.add.call_args_list:
            obj = c[0][0]
            if not hasattr(obj, 'id') or obj.id is None:
                obj.id = 'ee_fake_id'
    session.flush.side_effect = flush_side_effect
    return session


class TestDryRunThenEnrich:
    """Run --dry-run to see counts, then run --limit 5 with mocked Apify."""

    def test_dry_run_then_enrich(self, runner):
        profiles = [(f'cp_{i}', f'https://linkedin.com/in/user{i}') for i in range(10)]

        # Step 1: dry-run to see counts
        with patch('linkedout.commands.enrich.cli_db_manager', return_value=_mock_db_manager(profiles)), \
             patch('linkedout.commands.enrich.get_config', return_value=_mock_config()):
            dry_result = runner.invoke(enrich_command, ['--dry-run'])

        assert dry_result.exit_code == 0
        assert '10 unenriched profiles found' in dry_result.output
        assert '$0.04' in dry_result.output  # 10 * 0.004

        # Step 2: enrich with --limit 5
        mock_client = MagicMock()
        mock_client.enrich_profile_sync.return_value = {
            'firstName': 'Test', 'lastName': 'User',
            'linkedinUrl': 'https://linkedin.com/in/test',
        }

        write_session = _mock_write_session()
        mock_db = _mock_db_manager_with_writes(profiles, write_session)

        with patch('linkedout.commands.enrich.cli_db_manager', return_value=mock_db), \
             patch('linkedout.commands.enrich.get_config', return_value=_mock_config()), \
             patch('linkedout.commands.enrich.get_platform_apify_key', return_value='fake_key'), \
             patch('linkedout.commands.enrich.LinkedOutApifyClient', return_value=mock_client), \
             patch('linkedout.commands.enrich.PostEnrichmentService'), \
             patch('linkedout.commands.enrich.record_metric'), \
             patch('linkedout.commands.enrich.OperationReport') as mock_report:
            mock_report.return_value.save.return_value = MagicMock(
                relative_to=MagicMock(return_value='linkedout-data/reports/enrich.json')
            )
            enrich_result = runner.invoke(enrich_command, ['--limit', '5'])

        assert enrich_result.exit_code == 0
        assert mock_client.enrich_profile_sync.call_count == 5
        assert 'Enrichment complete: 5 profiles enriched' in enrich_result.output
        assert '$0.02' in enrich_result.output  # 5 * 0.004
        assert 'linkedout embed' in enrich_result.output
        assert 'linkedout compute-affinity' in enrich_result.output


class TestCreditExhaustionStopsCleanly:
    """Mock Apify raising ApifyCreditExhaustedError, verify enrichment stops with partial summary."""

    def test_credit_exhaustion_stops_cleanly(self, runner):
        profiles = [(f'cp_{i}', f'https://linkedin.com/in/user{i}') for i in range(10)]
        call_count = 0

        def mock_enrich(_url):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return {'firstName': 'Test', 'lastName': 'User'}
            raise ApifyCreditExhaustedError('Credits exhausted', status_code=402)

        mock_client = MagicMock()
        mock_client.enrich_profile_sync.side_effect = mock_enrich

        write_session = _mock_write_session()
        mock_db = _mock_db_manager_with_writes(profiles, write_session)

        with patch('linkedout.commands.enrich.cli_db_manager', return_value=mock_db), \
             patch('linkedout.commands.enrich.get_config', return_value=_mock_config()), \
             patch('linkedout.commands.enrich.get_platform_apify_key', return_value='fake_key'), \
             patch('linkedout.commands.enrich.LinkedOutApifyClient', return_value=mock_client), \
             patch('linkedout.commands.enrich.PostEnrichmentService'), \
             patch('linkedout.commands.enrich.record_metric'), \
             patch('linkedout.commands.enrich.OperationReport') as mock_report:
            mock_report.return_value.save.return_value = MagicMock(
                relative_to=MagicMock(return_value='linkedout-data/reports/enrich.json')
            )
            result = runner.invoke(enrich_command, ['--limit', '10'])

        assert result.exit_code == 0
        # First 2 profiles succeeded, remaining failed with credit exhaustion
        assert 'Enrichment complete: 2 profiles enriched' in result.output
        # All 10 were attempted (2 succeeded, 8 failed due to credit exhaustion)
        assert mock_client.enrich_profile_sync.call_count == 10


class TestAllProfilesEnriched:
    """When 0 unenriched profiles exist, verify 'All profiles are enriched' message."""

    def test_all_profiles_enriched(self, runner):
        with patch('linkedout.commands.enrich.cli_db_manager', return_value=_mock_db_manager([])), \
             patch('linkedout.commands.enrich.get_config', return_value=_mock_config()):
            result = runner.invoke(enrich_command, [])

        assert result.exit_code == 0
        assert 'All profiles are enriched' in result.output
