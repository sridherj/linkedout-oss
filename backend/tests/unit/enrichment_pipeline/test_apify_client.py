# SPDX-License-Identifier: Apache-2.0
"""Unit tests for Apify client abstraction."""
from unittest.mock import MagicMock, patch

import pytest

from linkedout.enrichment_pipeline.apify_client import (
    AllKeysExhaustedError,
    ApifyAuthError,
    ApifyCreditExhaustedError,
    ApifyError,
    ApifyRateLimitError,
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


# ---------------------------------------------------------------------------
# Client HTTP tests
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_config():
    cfg = MagicMock()
    cfg.enrichment.apify_base_url = 'https://api.apify.com/v2'
    cfg.enrichment.sync_timeout_seconds = 60
    cfg.enrichment.async_start_timeout_seconds = 30
    cfg.enrichment.run_poll_timeout_seconds = 300
    cfg.enrichment.run_poll_interval_seconds = 5
    cfg.enrichment.fetch_results_timeout_seconds = 30
    return cfg


@pytest.fixture
def client(mock_config):
    with patch('linkedout.enrichment_pipeline.apify_client.get_config', return_value=mock_config):
        return LinkedOutApifyClient(api_key='test_key')


def _mock_response(status_code: int, json_data=None, text: str = '') -> MagicMock:
    """Build a mock requests.Response with the given status."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 400
    resp.text = text or f'HTTP {status_code}'
    if json_data is not None:
        resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


class TestLinkedOutApifyClient:
    """Tests for the Apify client with mocked HTTP calls."""

    def test_enrich_profile_sync_success(self, client):
        mock_resp = _mock_response(200, json_data=[
            {'linkedinUrl': 'https://linkedin.com/in/test', 'firstName': 'Test'},
        ])

        with patch('linkedout.enrichment_pipeline.apify_client.requests.post', return_value=mock_resp):
            result = client.enrich_profile_sync('https://linkedin.com/in/test')

        assert result is not None
        assert result['firstName'] == 'Test'

    def test_enrich_profile_sync_empty_response(self, client):
        mock_resp = _mock_response(200, json_data=[])

        with patch('linkedout.enrichment_pipeline.apify_client.requests.post', return_value=mock_resp):
            result = client.enrich_profile_sync('https://linkedin.com/in/test')

        assert result is None

    def test_enrich_profiles_async(self, client):
        mock_resp = _mock_response(200, json_data={'data': {'id': 'run_abc123'}})

        with patch('linkedout.enrichment_pipeline.apify_client.requests.post', return_value=mock_resp):
            run_id = client.enrich_profiles_async(['https://linkedin.com/in/a', 'https://linkedin.com/in/b'])

        assert run_id == 'run_abc123'

    def test_poll_run_success(self, client):
        mock_resp = _mock_response(200, json_data={
            'data': {'status': 'SUCCEEDED', 'defaultDatasetId': 'ds_abc'},
        })

        with patch('linkedout.enrichment_pipeline.apify_client.requests.get', return_value=mock_resp):
            dataset_id = client.poll_run('run_abc', timeout=10)

        assert dataset_id == 'ds_abc'

    def test_poll_run_failed(self, client):
        mock_resp = _mock_response(200, json_data={'data': {'status': 'FAILED'}})

        with patch('linkedout.enrichment_pipeline.apify_client.requests.get', return_value=mock_resp):
            with pytest.raises(RuntimeError, match='FAILED'):
                client.poll_run('run_abc', timeout=10)

    def test_fetch_results(self, client):
        mock_resp = _mock_response(200, json_data=[{'linkedinUrl': 'https://linkedin.com/in/x'}])

        with patch('linkedout.enrichment_pipeline.apify_client.requests.get', return_value=mock_resp):
            results = client.fetch_results('ds_abc')

        assert len(results) == 1


# ---------------------------------------------------------------------------
# Error-mapping tests for enrich_profile_sync
# ---------------------------------------------------------------------------

class TestEnrichProfileSyncErrors:
    """HTTP status codes map to the correct Apify exception subclass."""

    def test_402_raises_credit_exhausted(self, client):
        mock_resp = _mock_response(402, text='Payment required')

        with patch('linkedout.enrichment_pipeline.apify_client.requests.post', return_value=mock_resp):
            with pytest.raises(ApifyCreditExhaustedError) as exc_info:
                client.enrich_profile_sync('https://linkedin.com/in/test')

        assert exc_info.value.status_code == 402

    def test_429_raises_rate_limit(self, client):
        mock_resp = _mock_response(429, text='Rate limited')

        with patch('linkedout.enrichment_pipeline.apify_client.requests.post', return_value=mock_resp):
            with pytest.raises(ApifyRateLimitError) as exc_info:
                client.enrich_profile_sync('https://linkedin.com/in/test')

        assert exc_info.value.status_code == 429

    def test_401_raises_auth_error(self, client):
        mock_resp = _mock_response(401, text='Unauthorized')

        with patch('linkedout.enrichment_pipeline.apify_client.requests.post', return_value=mock_resp):
            with pytest.raises(ApifyAuthError) as exc_info:
                client.enrich_profile_sync('https://linkedin.com/in/test')

        assert exc_info.value.status_code == 401

    def test_403_raises_auth_error(self, client):
        mock_resp = _mock_response(403, text='Forbidden')

        with patch('linkedout.enrichment_pipeline.apify_client.requests.post', return_value=mock_resp):
            with pytest.raises(ApifyAuthError) as exc_info:
                client.enrich_profile_sync('https://linkedin.com/in/test')

        assert exc_info.value.status_code == 403

    def test_500_raises_generic_apify_error(self, client):
        mock_resp = _mock_response(500, text='Internal server error')

        with patch('linkedout.enrichment_pipeline.apify_client.requests.post', return_value=mock_resp):
            with pytest.raises(ApifyError) as exc_info:
                client.enrich_profile_sync('https://linkedin.com/in/test')

        assert exc_info.value.status_code == 500

    def test_success_returns_data(self, client):
        mock_resp = _mock_response(200, json_data=[{'firstName': 'Alice'}])

        with patch('linkedout.enrichment_pipeline.apify_client.requests.post', return_value=mock_resp):
            result = client.enrich_profile_sync('https://linkedin.com/in/alice')

        assert result == {'firstName': 'Alice'}
