# SPDX-License-Identifier: Apache-2.0
"""Tests for ``linkedout config show``."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from linkedout.commands.config import config_show

MOCK_TARGET = 'shared.config.get_config'


def _mock_settings(**overrides):
    """Build a mock LinkedOutSettings with sensible defaults."""
    defaults = {
        'database_url': 'postgresql://user:pass@localhost/db',
        'data_dir': '/home/test/linkedout-data',
        'demo_mode': False,
        'backend_port': 8001,
        'openai_api_key': 'sk-test-key',
        'apify_api_key': None,
    }
    defaults.update(overrides)

    settings = MagicMock()
    settings.embedding.provider = 'openai'
    settings.embedding.model = 'text-embedding-3-small'
    for k, v in defaults.items():
        setattr(settings, k, v)
    return settings


class TestConfigShowText:
    """Text output tests."""

    @patch(MOCK_TARGET)
    def test_config_show_text_output(self, mock_get_config):
        mock_get_config.return_value = _mock_settings()
        runner = CliRunner()
        result = runner.invoke(config_show)
        assert result.exit_code == 0
        assert 'embedding_provider: openai' in result.output
        assert 'embedding_model: text-embedding-3-small' in result.output
        assert 'data_dir:' in result.output
        assert 'demo_mode:' in result.output
        assert 'backend_port: 8001' in result.output

    @patch(MOCK_TARGET)
    def test_config_show_redacts_database_url(self, mock_get_config):
        mock_get_config.return_value = _mock_settings()
        runner = CliRunner()
        result = runner.invoke(config_show)
        assert result.exit_code == 0
        assert '***' in result.output
        assert 'user:pass' not in result.output

    @patch(MOCK_TARGET)
    def test_config_show_api_key_status(self, mock_get_config):
        mock_get_config.return_value = _mock_settings()
        runner = CliRunner()
        result = runner.invoke(config_show)
        assert result.exit_code == 0
        assert 'api_keys.openai: configured' in result.output
        assert 'api_keys.apify: not configured' in result.output


class TestConfigShowJson:
    """JSON output tests."""

    @patch(MOCK_TARGET)
    def test_config_show_json_output(self, mock_get_config):
        mock_get_config.return_value = _mock_settings()
        runner = CliRunner()
        result = runner.invoke(config_show, ['--json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert 'embedding_provider' in data
        assert 'embedding_model' in data
        assert 'database_url' in data
        assert 'data_dir' in data
        assert 'demo_mode' in data
        assert 'backend_port' in data
        assert 'api_keys' in data

    @patch(MOCK_TARGET)
    def test_config_show_json_redacts_database_url(self, mock_get_config):
        mock_get_config.return_value = _mock_settings()
        runner = CliRunner()
        result = runner.invoke(config_show, ['--json'])
        data = json.loads(result.output)
        assert data['database_url'] == '***'

    @patch(MOCK_TARGET)
    def test_config_show_json_api_key_status(self, mock_get_config):
        mock_get_config.return_value = _mock_settings()
        runner = CliRunner()
        result = runner.invoke(config_show, ['--json'])
        data = json.loads(result.output)
        assert data['api_keys']['openai'] == 'configured'
        assert data['api_keys']['apify'] == 'not configured'

    @patch(MOCK_TARGET)
    def test_config_show_no_database_url_shows_not_configured(self, mock_get_config):
        mock_get_config.return_value = _mock_settings(database_url='')
        runner = CliRunner()
        result = runner.invoke(config_show, ['--json'])
        data = json.loads(result.output)
        assert data['database_url'] == 'not configured'
