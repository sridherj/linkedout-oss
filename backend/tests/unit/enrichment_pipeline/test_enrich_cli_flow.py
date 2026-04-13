# SPDX-License-Identifier: Apache-2.0
"""End-to-end CLI flow tests for ``linkedout enrich`` with mocked bulk pipeline.

Tests cover the full dry-run → enrich cycle, credit exhaustion handling
(via bulk pipeline's stopped_reason), and the zero-unenriched-profiles edge case.
"""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from linkedout.commands.enrich import enrich_command


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


def _mock_config(cost_per=0.004):
    cfg = MagicMock()
    cfg.enrichment.cost_per_profile_usd = cost_per
    cfg.enrichment.skip_embeddings = False
    return cfg


@dataclass
class _FakeEnrichmentResult:
    total_profiles: int
    enriched: int
    failed: int
    batches_completed: int
    batches_total: int
    stopped_reason: str | None = None


class TestDryRunThenEnrich:
    """Run --dry-run to see counts, then run --limit 5 with mocked pipeline."""

    def test_dry_run_then_enrich(self, runner):
        profiles = [(f'cp_{i}', f'https://linkedin.com/in/user{i}') for i in range(10)]

        # Step 1: dry-run to see counts
        with patch('linkedout.commands.enrich.cli_db_manager', return_value=_mock_db_manager(profiles)), \
             patch('linkedout.commands.enrich.get_config', return_value=_mock_config()):
            dry_result = runner.invoke(enrich_command, ['--dry-run'])

        assert dry_result.exit_code == 0
        assert '10 unenriched profiles found' in dry_result.output
        assert '$0.04' in dry_result.output  # 10 * 0.004

        # Step 2: enrich with --limit 5 (mock the bulk pipeline)
        mock_db = _mock_db_manager(profiles)
        fake_result = _FakeEnrichmentResult(
            total_profiles=5, enriched=5, failed=0,
            batches_completed=1, batches_total=1,
        )

        with patch('linkedout.commands.enrich.cli_db_manager', return_value=mock_db), \
             patch('linkedout.commands.enrich.get_config', return_value=_mock_config()), \
             patch('linkedout.commands.enrich.get_platform_apify_key', return_value='fake_key'), \
             patch('linkedout.enrichment_pipeline.bulk_enrichment.enrich_profiles', return_value=fake_result) as mock_ep, \
             patch('linkedout.commands.enrich.record_metric'), \
             patch('linkedout.commands.enrich.OperationReport') as mock_report:
            mock_report.return_value.save.return_value = MagicMock(
                relative_to=MagicMock(return_value='linkedout-data/reports/enrich.json')
            )
            enrich_result = runner.invoke(enrich_command, ['--limit', '5'])

        assert enrich_result.exit_code == 0
        assert mock_ep.call_count == 1
        # --limit 5 means only 5 profiles passed to pipeline
        assert len(mock_ep.call_args.kwargs['profiles']) == 5
        assert 'Enrichment complete: 5 enriched' in enrich_result.output
        assert '$0.02' in enrich_result.output  # 5 * 0.004
        assert 'compute-affinity' in enrich_result.output


class TestCreditExhaustionStopsCleanly:
    """Mock bulk pipeline returning all_keys_exhausted, verify partial summary."""

    def test_credit_exhaustion_stops_cleanly(self, runner):
        profiles = [(f'cp_{i}', f'https://linkedin.com/in/user{i}') for i in range(10)]
        fake_result = _FakeEnrichmentResult(
            total_profiles=10, enriched=2, failed=8,
            batches_completed=1, batches_total=1,
            stopped_reason="all_keys_exhausted",
        )

        with patch('linkedout.commands.enrich.cli_db_manager', return_value=_mock_db_manager(profiles)), \
             patch('linkedout.commands.enrich.get_config', return_value=_mock_config()), \
             patch('linkedout.commands.enrich.get_platform_apify_key', return_value='fake_key'), \
             patch('linkedout.enrichment_pipeline.bulk_enrichment.enrich_profiles', return_value=fake_result), \
             patch('linkedout.commands.enrich.record_metric'), \
             patch('linkedout.commands.enrich.OperationReport') as mock_report:
            mock_report.return_value.save.return_value = MagicMock(
                relative_to=MagicMock(return_value='linkedout-data/reports/enrich.json')
            )
            result = runner.invoke(enrich_command, ['--limit', '10'])

        assert result.exit_code == 0
        assert 'all API keys exhausted' in result.output
        assert 'Enrichment complete: 2 enriched' in result.output


class TestAllProfilesEnriched:
    """When 0 unenriched profiles exist, verify 'All profiles are enriched' message."""

    def test_all_profiles_enriched(self, runner):
        with patch('linkedout.commands.enrich.cli_db_manager', return_value=_mock_db_manager([])), \
             patch('linkedout.commands.enrich.get_config', return_value=_mock_config()):
            result = runner.invoke(enrich_command, [])

        assert result.exit_code == 0
        assert 'All profiles are enriched' in result.output
