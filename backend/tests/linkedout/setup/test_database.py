# SPDX-License-Identifier: Apache-2.0
"""Tests for database setup module."""
import stat
from unittest.mock import patch

import yaml

from linkedout.setup.database import (
    _read_existing_database_url,
    generate_agent_context_env,
    generate_password,
    setup_database,
    write_config_yaml,
)


class TestGeneratePassword:
    def test_returns_string_of_at_least_32_chars(self):
        password = generate_password()
        assert isinstance(password, str)
        assert len(password) >= 32

    def test_produces_different_values_each_call(self):
        passwords = {generate_password() for _ in range(10)}
        assert len(passwords) == 10

    def test_is_url_safe(self):
        password = generate_password()
        # URL-safe base64 only uses alphanumeric, dash, and underscore
        assert all(c.isalnum() or c in '-_' for c in password)


class TestWriteConfigYaml:
    def test_creates_valid_yaml_with_database_url(self, tmp_path):
        data_dir = tmp_path / 'linkedout-data'
        url = 'postgresql://linkedout:testpass@localhost:5432/linkedout'

        config_path = write_config_yaml(url, data_dir)

        assert config_path.exists()
        with open(config_path, encoding='utf-8') as f:
            config = yaml.safe_load(f)
        assert config['database_url'] == url

    def test_creates_config_directory_if_missing(self, tmp_path):
        data_dir = tmp_path / 'linkedout-data'
        assert not data_dir.exists()

        write_config_yaml('postgresql://x:y@localhost/db', data_dir)

        assert (data_dir / 'config').is_dir()

    def test_config_has_restricted_permissions(self, tmp_path):
        data_dir = tmp_path / 'linkedout-data'
        config_path = write_config_yaml('postgresql://x:y@localhost/db', data_dir)

        mode = config_path.stat().st_mode
        # Owner read/write only (0600)
        assert mode & stat.S_IRUSR  # owner read
        assert mode & stat.S_IWUSR  # owner write
        assert not (mode & stat.S_IRGRP)  # no group read
        assert not (mode & stat.S_IROTH)  # no other read

    def test_yaml_contains_expected_defaults(self, tmp_path):
        data_dir = tmp_path / 'linkedout-data'
        url = 'postgresql://linkedout:pass@localhost:5432/linkedout'

        config_path = write_config_yaml(url, data_dir)
        with open(config_path, encoding='utf-8') as f:
            config = yaml.safe_load(f)

        assert config['data_dir'] == '~/linkedout-data'
        assert config['log_level'] == 'INFO'
        assert config['embedding_provider'] == 'openai'
        assert config['backend_port'] == 8001


class TestGenerateAgentContextEnv:
    @patch('shared.config.settings.LinkedOutSettings')
    @patch('shared.config.agent_context.generate_agent_context')
    def test_creates_agent_context_file(self, mock_gen, mock_settings_cls, tmp_path):
        data_dir = tmp_path / 'linkedout-data'
        url = 'postgresql://linkedout:pass@localhost:5432/linkedout'
        expected_path = data_dir / 'config' / 'agent-context.env'
        mock_gen.return_value = expected_path

        result = generate_agent_context_env(url, data_dir)

        assert result == expected_path
        mock_settings_cls.assert_called_once()
        mock_gen.assert_called_once()

    @patch('shared.config.settings.LinkedOutSettings')
    @patch('shared.config.agent_context.generate_agent_context')
    def test_passes_database_url_to_settings(self, mock_gen, mock_settings_cls, tmp_path):
        data_dir = tmp_path / 'linkedout-data'
        url = 'postgresql://linkedout:secret@localhost:5432/linkedout'
        mock_gen.return_value = data_dir / 'config' / 'agent-context.env'

        generate_agent_context_env(url, data_dir)

        call_kwargs = mock_settings_cls.call_args
        assert call_kwargs[1]['database_url'] == url
        assert call_kwargs[1]['data_dir'] == str(data_dir)


class TestReadExistingDatabaseUrl:
    def test_returns_none_when_file_missing(self, tmp_path):
        result = _read_existing_database_url(tmp_path / 'nonexistent' / 'config.yaml')
        assert result is None

    def test_returns_none_when_no_password(self, tmp_path):
        config_path = tmp_path / 'config.yaml'
        config_path.write_text('database_url: postgresql://linkedout:@localhost:5432/linkedout\n')
        result = _read_existing_database_url(config_path)
        assert result is None

    def test_returns_url_when_password_present(self, tmp_path):
        url = 'postgresql://linkedout:s3cret@localhost:5432/linkedout'
        config_path = tmp_path / 'config.yaml'
        config_path.write_text(f'database_url: {url}\n')
        result = _read_existing_database_url(config_path)
        assert result == url

    def test_returns_none_on_invalid_yaml(self, tmp_path):
        config_path = tmp_path / 'config.yaml'
        config_path.write_text('{{{{ not valid yaml')
        result = _read_existing_database_url(config_path)
        assert result is None


class TestSetupDatabaseIdempotency:
    @patch('linkedout.setup.database.generate_agent_context_env')
    @patch('linkedout.setup.database.verify_schema', return_value=[])
    @patch('linkedout.setup.database.run_migrations')
    @patch('linkedout.setup.database.write_config_yaml')
    @patch('linkedout.setup.database.set_db_password')
    def test_skips_password_when_config_exists(
        self, mock_set_pw, mock_write, mock_migrate, mock_verify, mock_agent, tmp_path
    ):
        from shared.utilities.operation_report import OperationCounts, OperationReport

        mock_migrate.return_value = OperationReport(
            operation='db-migration',
            counts=OperationCounts(total=0, succeeded=0),
        )
        mock_agent.return_value = tmp_path / 'agent-context.env'

        # Create existing config with password
        data_dir = tmp_path / 'linkedout-data'
        config_dir = data_dir / 'config'
        config_dir.mkdir(parents=True)
        config_path = config_dir / 'config.yaml'
        config_path.write_text(
            'database_url: postgresql://linkedout:existingpw@localhost:5432/linkedout\n'
        )

        report = setup_database(data_dir)

        # Password should NOT have been set since config already had one
        mock_set_pw.assert_not_called()
        assert report.counts.failed == 0
