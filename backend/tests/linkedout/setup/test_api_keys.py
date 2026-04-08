# SPDX-License-Identifier: Apache-2.0
"""Tests for API key collection module."""
import logging
import stat
from unittest.mock import MagicMock, patch

import yaml

from linkedout.setup.api_keys import (
    _read_existing_secrets,
    collect_api_keys,
    collect_apify_key,
    collect_openai_key,
    prompt_embedding_provider,
    update_config_yaml,
    validate_openai_key,
    write_secrets_yaml,
)


class TestPromptEmbeddingProvider:
    @patch('builtins.input', return_value='1')
    def test_returns_openai_for_choice_1(self, mock_input):
        assert prompt_embedding_provider() == 'openai'

    @patch('builtins.input', return_value='')
    def test_returns_openai_for_empty_default(self, mock_input):
        assert prompt_embedding_provider() == 'openai'

    @patch('builtins.input', return_value='2')
    def test_returns_local_for_choice_2(self, mock_input):
        assert prompt_embedding_provider() == 'local'

    @patch('builtins.input', side_effect=['invalid', '3', '1'])
    def test_retries_on_invalid_input(self, mock_input):
        result = prompt_embedding_provider()
        assert result == 'openai'
        assert mock_input.call_count == 3


class TestValidateOpenaiKey:
    def test_returns_true_for_valid_key(self):
        mock_provider = MagicMock()
        mock_provider.embed_single.return_value = [0.1, 0.2, 0.3]
        mock_cls = MagicMock(return_value=mock_provider)

        with patch.dict('sys.modules', {
            'utilities.llm_manager.openai_embedding_provider': MagicMock(
                OpenAIEmbeddingProvider=mock_cls
            ),
        }):
            result = validate_openai_key('sk-test-valid-key')

        assert result is True

    def test_returns_false_on_api_error(self):
        with patch.dict('sys.modules', {
            'utilities.llm_manager.openai_embedding_provider': MagicMock(
                OpenAIEmbeddingProvider=MagicMock(side_effect=Exception("401 Unauthorized")),
            ),
        }):
            result = validate_openai_key('sk-test-invalid-key')

        assert result is False

    def test_restores_env_after_validation(self):
        import os
        original = os.environ.get('OPENAI_API_KEY')

        with patch.dict('sys.modules', {
            'utilities.llm_manager.openai_embedding_provider': MagicMock(
                OpenAIEmbeddingProvider=MagicMock(side_effect=Exception("test")),
            ),
        }):
            validate_openai_key('sk-temporary-key')

        # Env should be restored
        assert os.environ.get('OPENAI_API_KEY') == original


class TestCollectOpenaiKey:
    @patch('linkedout.setup.api_keys.validate_openai_key', return_value=True)
    @patch('getpass.getpass', return_value='sk-valid')
    def test_returns_key_on_valid(self, mock_getpass, mock_validate):
        result = collect_openai_key()
        assert result == 'sk-valid'

    @patch('getpass.getpass', return_value='')
    def test_returns_none_on_empty_input(self, mock_getpass):
        result = collect_openai_key()
        assert result is None

    @patch('builtins.input', return_value='2')
    @patch('linkedout.setup.api_keys.validate_openai_key', return_value=False)
    @patch('getpass.getpass', return_value='sk-bad')
    def test_returns_none_when_user_switches_to_local(self, mock_getpass, mock_validate, mock_input):
        result = collect_openai_key()
        assert result is None


class TestCollectApifyKey:
    @patch('getpass.getpass', return_value='apify_api_test123')
    def test_returns_key_when_provided(self, mock_getpass):
        result = collect_apify_key()
        assert result == 'apify_api_test123'

    @patch('getpass.getpass', return_value='')
    def test_returns_none_when_skipped(self, mock_getpass):
        result = collect_apify_key()
        assert result is None


class TestWriteSecretsYaml:
    def test_creates_file_with_correct_permissions(self, tmp_path):
        data_dir = tmp_path / 'linkedout-data'

        path = write_secrets_yaml({'openai_api_key': 'sk-test'}, data_dir)

        assert path.exists()
        mode = path.stat().st_mode
        assert mode & stat.S_IRUSR
        assert mode & stat.S_IWUSR
        assert not (mode & stat.S_IRGRP)
        assert not (mode & stat.S_IROTH)

    def test_writes_keys_as_yaml(self, tmp_path):
        data_dir = tmp_path / 'linkedout-data'

        write_secrets_yaml(
            {'openai_api_key': 'sk-test', 'apify_api_key': 'apify_123'},
            data_dir,
        )

        secrets_path = data_dir / 'config' / 'secrets.yaml'
        with open(secrets_path, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        assert data['openai_api_key'] == 'sk-test'
        assert data['apify_api_key'] == 'apify_123'

    def test_writes_none_values_as_comments(self, tmp_path):
        data_dir = tmp_path / 'linkedout-data'

        write_secrets_yaml({'apify_api_key': None}, data_dir)

        secrets_path = data_dir / 'config' / 'secrets.yaml'
        content = secrets_path.read_text(encoding='utf-8')
        assert '# apify_api_key:' in content
        # Should not have a non-comment apify_api_key line
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith('apify_api_key:'):
                raise AssertionError("None value should be written as comment")

    def test_creates_config_directory_if_missing(self, tmp_path):
        data_dir = tmp_path / 'nonexistent'
        assert not data_dir.exists()

        write_secrets_yaml({'openai_api_key': 'sk-x'}, data_dir)

        assert (data_dir / 'config').is_dir()

    def test_api_keys_never_appear_in_logs(self, tmp_path, caplog):
        data_dir = tmp_path / 'linkedout-data'
        test_key = 'sk-proj-SUPER-SECRET-KEY-12345'

        with caplog.at_level(logging.DEBUG):
            write_secrets_yaml({'openai_api_key': test_key}, data_dir)

        # The key value must never appear in log output
        for record in caplog.records:
            assert test_key not in record.getMessage()


class TestUpdateConfigYaml:
    def test_updates_existing_value(self, tmp_path):
        data_dir = tmp_path / 'linkedout-data'
        config_dir = data_dir / 'config'
        config_dir.mkdir(parents=True)
        config_path = config_dir / 'config.yaml'
        config_path.write_text('embedding_provider: openai\nlog_level: INFO\n')

        update_config_yaml({'embedding_provider': 'local'}, data_dir)

        with open(config_path, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        assert data['embedding_provider'] == 'local'

    def test_creates_file_if_missing(self, tmp_path):
        data_dir = tmp_path / 'linkedout-data'

        update_config_yaml({'embedding_provider': 'local'}, data_dir)

        config_path = data_dir / 'config' / 'config.yaml'
        assert config_path.exists()
        with open(config_path, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        assert data['embedding_provider'] == 'local'


class TestReadExistingSecrets:
    def test_returns_empty_dict_when_file_missing(self, tmp_path):
        result = _read_existing_secrets(tmp_path / 'nonexistent')
        assert result == {}

    def test_reads_existing_secrets(self, tmp_path):
        data_dir = tmp_path / 'linkedout-data'
        config_dir = data_dir / 'config'
        config_dir.mkdir(parents=True)
        secrets_path = config_dir / 'secrets.yaml'
        secrets_path.write_text('openai_api_key: sk-existing\n')

        result = _read_existing_secrets(data_dir)
        assert result['openai_api_key'] == 'sk-existing'


class TestCollectApiKeysIdempotency:
    @patch('linkedout.setup.api_keys.collect_apify_key', return_value=None)
    @patch('linkedout.setup.api_keys.collect_openai_key', return_value='sk-kept')
    @patch('linkedout.setup.api_keys.prompt_embedding_provider', return_value='local')
    @patch('builtins.input', return_value='n')
    def test_detects_existing_provider_on_rerun(
        self, _mock_input, _mock_prompt, _mock_openai, _mock_apify, tmp_path
    ):
        data_dir = tmp_path / 'linkedout-data'
        config_dir = data_dir / 'config'
        config_dir.mkdir(parents=True)
        config_path = config_dir / 'config.yaml'
        config_path.write_text('embedding_provider: openai\n')
        # Also create existing secrets so the openai key path is skipped
        secrets_path = config_dir / 'secrets.yaml'
        secrets_path.write_text('openai_api_key: sk-existing\n')

        report = collect_api_keys(data_dir)

        # Should have asked about changing existing provider and key
        assert report.counts.skipped >= 1
        # prompt_embedding_provider should NOT have been called since user said 'n'
        _mock_prompt.assert_not_called()
