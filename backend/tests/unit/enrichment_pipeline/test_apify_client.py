# SPDX-License-Identifier: Apache-2.0
"""Unit tests for Apify client abstraction."""
from unittest.mock import MagicMock, patch

import pytest

from linkedout.enrichment_pipeline.apify_client import (
    LinkedOutApifyClient,
    get_byok_apify_key,
    get_platform_apify_key,
    reset_key_cycle,
)


class TestGetPlatformApifyKey:
    """Tests for platform key retrieval from config with round-robin rotation."""

    def setup_method(self):
        reset_key_cycle()

    def test_returns_single_key_from_config(self):
        mock_config = MagicMock()
        mock_config.get_apify_api_keys.return_value = []
        mock_config.apify_api_key = 'test_key'

        with patch('linkedout.enrichment_pipeline.apify_client.get_config', return_value=mock_config):
            assert get_platform_apify_key() == 'test_key'

    def test_no_key_raises(self):
        mock_config = MagicMock()
        mock_config.get_apify_api_keys.return_value = []
        mock_config.apify_api_key = None

        with patch('linkedout.enrichment_pipeline.apify_client.get_config', return_value=mock_config):
            with pytest.raises(ValueError, match='APIFY_API_KEY is not configured'):
                get_platform_apify_key()

    def test_round_robin_multiple_keys(self):
        mock_config = MagicMock()
        mock_config.get_apify_api_keys.return_value = ['key_a', 'key_b']
        mock_config.apify_api_key = None

        with patch('linkedout.enrichment_pipeline.apify_client.get_config', return_value=mock_config):
            keys = [get_platform_apify_key() for _ in range(4)]
        assert keys == ['key_a', 'key_b', 'key_a', 'key_b']

    def test_keys_list_takes_precedence_over_single(self):
        mock_config = MagicMock()
        mock_config.get_apify_api_keys.return_value = ['list_key']
        mock_config.apify_api_key = 'single_key'

        with patch('linkedout.enrichment_pipeline.apify_client.get_config', return_value=mock_config):
            assert get_platform_apify_key() == 'list_key'


class TestGetByokApifyKey:
    """Tests for BYOK key decryption."""

    def test_decrypts_key(self, monkeypatch):
        from cryptography.fernet import Fernet
        encryption_key = Fernet.generate_key()
        monkeypatch.setenv('TENANT_SECRET_ENCRYPTION_KEY', encryption_key.decode())

        fernet = Fernet(encryption_key)
        encrypted = fernet.encrypt(b'my_apify_key').decode()

        mock_config = MagicMock()
        mock_config.apify_key_encrypted = encrypted

        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_config

        result = get_byok_apify_key('usr_123', mock_session)
        assert result == 'my_apify_key'

    def test_no_config_raises(self):
        mock_session = MagicMock()
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        with pytest.raises(ValueError, match='No BYOK key'):
            get_byok_apify_key('usr_123', mock_session)


class TestLinkedOutApifyClient:
    """Tests for the Apify client with mocked HTTP calls."""

    def test_enrich_profile_sync_success(self):
        client = LinkedOutApifyClient(api_key='test_key')
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{'linkedinUrl': 'https://linkedin.com/in/test', 'firstName': 'Test'}]

        with patch('linkedout.enrichment_pipeline.apify_client.requests.post', return_value=mock_response):
            result = client.enrich_profile_sync('https://linkedin.com/in/test')

        assert result is not None
        assert result['firstName'] == 'Test'

    def test_enrich_profile_sync_failure(self):
        client = LinkedOutApifyClient(api_key='test_key')
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = 'Rate limited'

        with patch('linkedout.enrichment_pipeline.apify_client.requests.post', return_value=mock_response):
            result = client.enrich_profile_sync('https://linkedin.com/in/test')

        assert result is None

    def test_enrich_profile_sync_empty_response(self):
        client = LinkedOutApifyClient(api_key='test_key')
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch('linkedout.enrichment_pipeline.apify_client.requests.post', return_value=mock_response):
            result = client.enrich_profile_sync('https://linkedin.com/in/test')

        assert result is None

    def test_enrich_profiles_async(self):
        client = LinkedOutApifyClient(api_key='test_key')
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': {'id': 'run_abc123'}}
        mock_response.raise_for_status = MagicMock()

        with patch('linkedout.enrichment_pipeline.apify_client.requests.post', return_value=mock_response):
            run_id = client.enrich_profiles_async(['https://linkedin.com/in/a', 'https://linkedin.com/in/b'])

        assert run_id == 'run_abc123'

    def test_poll_run_success(self):
        client = LinkedOutApifyClient(api_key='test_key')
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'data': {'status': 'SUCCEEDED', 'defaultDatasetId': 'ds_abc'}
        }
        mock_response.raise_for_status = MagicMock()

        with patch('linkedout.enrichment_pipeline.apify_client.requests.get', return_value=mock_response):
            dataset_id = client.poll_run('run_abc', timeout=10)

        assert dataset_id == 'ds_abc'

    def test_poll_run_failed(self):
        client = LinkedOutApifyClient(api_key='test_key')
        mock_response = MagicMock()
        mock_response.json.return_value = {'data': {'status': 'FAILED'}}
        mock_response.raise_for_status = MagicMock()

        with patch('linkedout.enrichment_pipeline.apify_client.requests.get', return_value=mock_response):
            with pytest.raises(RuntimeError, match='FAILED'):
                client.poll_run('run_abc', timeout=10)

    def test_fetch_results(self):
        client = LinkedOutApifyClient(api_key='test_key')
        mock_response = MagicMock()
        mock_response.json.return_value = [{'linkedinUrl': 'https://linkedin.com/in/x'}]
        mock_response.raise_for_status = MagicMock()

        with patch('linkedout.enrichment_pipeline.apify_client.requests.get', return_value=mock_response):
            results = client.fetch_results('ds_abc')

        assert len(results) == 1
