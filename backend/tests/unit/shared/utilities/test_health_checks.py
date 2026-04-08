# SPDX-License-Identifier: Apache-2.0
"""Tests for the health check functions."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from shared.utilities.health_checks import (
    HealthCheckResult,
    check_api_keys,
    check_db_connection,
    check_disk_space,
    check_embedding_model,
    get_db_stats,
)


class TestHealthCheckResult:
    """Tests for the HealthCheckResult dataclass."""

    def test_fields_set_correctly(self):
        """All fields are stored and accessible."""
        result = HealthCheckResult(check='test', status='pass', detail='ok')
        assert result.check == 'test'
        assert result.status == 'pass'
        assert result.detail == 'ok'

    def test_detail_defaults_to_empty(self):
        """Detail defaults to empty string when not provided."""
        result = HealthCheckResult(check='test', status='fail')
        assert result.detail == ''


class TestCheckDbConnection:
    """Tests for check_db_connection()."""

    @patch('shared.config.get_config')
    def test_returns_fail_when_no_database_url(self, mock_config):
        """Returns fail when database_url is empty."""
        mock_config.return_value.database_url = ''
        result = check_db_connection()
        assert result.check == 'db_connection'
        assert result.status == 'fail'
        assert 'not configured' in result.detail

    @patch('shared.infra.db.db_session_manager.DbSessionManager')
    @patch('shared.config.get_config')
    def test_returns_pass_on_successful_connection(self, mock_config, mock_db_cls):
        """Returns pass when SELECT 1 succeeds."""
        mock_config.return_value.database_url = 'postgresql://localhost/test'
        mock_session = MagicMock()
        mock_instance = MagicMock()
        mock_instance.get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_instance.get_session.return_value.__exit__ = MagicMock(return_value=False)
        mock_db_cls.return_value = mock_instance

        result = check_db_connection()
        assert result.check == 'db_connection'
        assert result.status == 'pass'

    def test_returns_fail_on_exception(self):
        """Returns fail (not exception) when connection fails."""
        with patch(
            'shared.config.get_config',
            side_effect=Exception('connection refused'),
        ):
            result = check_db_connection()
            assert result.check == 'db_connection'
            assert result.status == 'fail'
            assert 'connection refused' in result.detail


class TestCheckEmbeddingModel:
    """Tests for check_embedding_model()."""

    @patch('shared.config.get_config')
    def test_openai_with_key_returns_pass(self, mock_config):
        """Returns pass when openai provider has API key configured."""
        mock_config.return_value.embedding.provider = 'openai'
        mock_config.return_value.openai_api_key = 'sk-test'
        mock_config.return_value.embedding.model = 'text-embedding-3-small'

        result = check_embedding_model()
        assert result.status == 'pass'
        assert 'openai' in result.detail

    @patch('shared.config.get_config')
    def test_openai_without_key_returns_skip(self, mock_config):
        """Returns skip when openai provider lacks API key."""
        mock_config.return_value.embedding.provider = 'openai'
        mock_config.return_value.openai_api_key = None

        result = check_embedding_model()
        assert result.status == 'skip'
        assert 'not configured' in result.detail

    @patch('shared.config.get_config')
    def test_local_provider_returns_pass(self, mock_config):
        """Returns pass for local embedding provider."""
        mock_config.return_value.embedding.provider = 'local'
        mock_config.return_value.embedding.model = 'nomic-embed-text-v1.5'

        result = check_embedding_model()
        assert result.status == 'pass'
        assert 'local' in result.detail

    def test_returns_fail_on_exception(self):
        """Returns fail (not exception) on config error."""
        with patch(
            'shared.config.get_config',
            side_effect=Exception('config error'),
        ):
            result = check_embedding_model()
            assert result.status == 'fail'


class TestCheckApiKeys:
    """Tests for check_api_keys()."""

    @patch('shared.config.get_config')
    def test_returns_list_of_results(self, mock_config):
        """Returns a list of HealthCheckResult, one per key."""
        mock_config.return_value.openai_api_key = 'sk-test'
        mock_config.return_value.apify_api_key = None

        results = check_api_keys()
        assert isinstance(results, list)
        assert len(results) == 2

    @patch('shared.config.get_config')
    def test_never_returns_actual_key_values(self, mock_config):
        """API key values are never exposed -- only configured/not configured."""
        mock_config.return_value.openai_api_key = 'sk-secret-key-12345'
        mock_config.return_value.apify_api_key = 'apify-secret-token-67890'

        results = check_api_keys()
        for result in results:
            assert 'sk-secret' not in result.detail
            assert 'apify-secret' not in result.detail
            assert result.detail in ('configured', 'not configured')

    @patch('shared.config.get_config')
    def test_configured_key_shows_pass(self, mock_config):
        """Configured key returns pass status."""
        mock_config.return_value.openai_api_key = 'sk-test'
        mock_config.return_value.apify_api_key = None

        results = check_api_keys()
        openai_result = next(r for r in results if r.check == 'api_key_openai')
        apify_result = next(r for r in results if r.check == 'api_key_apify')

        assert openai_result.status == 'pass'
        assert openai_result.detail == 'configured'
        assert apify_result.status == 'skip'
        assert apify_result.detail == 'not configured'

    def test_returns_fail_on_exception(self):
        """Returns fail (not exception) on config error."""
        with patch(
            'shared.config.get_config',
            side_effect=Exception('config error'),
        ):
            results = check_api_keys()
            assert len(results) == 1
            assert results[0].status == 'fail'


class TestCheckDiskSpace:
    """Tests for check_disk_space()."""

    def test_returns_health_check_result(self):
        """Returns a HealthCheckResult with disk info."""
        result = check_disk_space()
        assert isinstance(result, HealthCheckResult)
        assert result.check == 'disk_space'
        assert result.status in ('pass', 'fail')
        assert 'GB' in result.detail

    @patch('shared.utilities.health_checks.shutil.disk_usage')
    def test_pass_when_plenty_of_space(self, mock_usage):
        """Returns pass when >1 GB free."""
        mock_usage.return_value = MagicMock(free=50 * 1024 ** 3)  # 50 GB
        result = check_disk_space()
        assert result.status == 'pass'
        assert '50.0' in result.detail

    @patch('shared.utilities.health_checks.shutil.disk_usage')
    def test_fail_when_low_space(self, mock_usage):
        """Returns fail when <1 GB free."""
        mock_usage.return_value = MagicMock(free=500 * 1024 ** 2)  # 500 MB
        result = check_disk_space()
        assert result.status == 'fail'
        assert '< 1 GB' in result.detail


class TestGetDbStats:
    """Tests for get_db_stats()."""

    def test_returns_expected_dict_structure(self):
        """Returns a dict with all expected keys when given a mock session."""
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar.return_value = 0
        # Mock the alembic version query to avoid exception path
        mock_first = MagicMock()
        mock_first.return_value = None
        mock_session.execute.return_value.first = mock_first

        stats = get_db_stats(session=mock_session)
        expected_keys = {
            'profiles_total',
            'profiles_with_embeddings',
            'profiles_without_embeddings',
            'companies_total',
            'connections_total',
            'last_enrichment',
            'schema_version',
        }
        assert expected_keys == set(stats.keys())

    def test_returns_defaults_when_no_session_and_no_db(self):
        """Returns zero-valued dict when no session given and DB is unavailable."""
        with patch(
            'shared.infra.db.db_session_manager.DbSessionManager',
            side_effect=Exception('no db'),
        ):
            stats = get_db_stats()
            assert stats['profiles_total'] == 0
            assert stats['companies_total'] == 0
            assert stats['connections_total'] == 0
            assert stats['last_enrichment'] is None
            assert stats['schema_version'] is None
