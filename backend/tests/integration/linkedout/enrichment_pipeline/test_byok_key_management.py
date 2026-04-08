# SPDX-License-Identifier: Apache-2.0
"""Integration tests for BYOK key management endpoints."""
import uuid
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


class TestByokKeyManagement:
    """Tests for PUT/DELETE/GET apify-key on enrichment pipeline."""

    @pytest.fixture
    def app_user(self, seeded_data: dict):
        return seeded_data['app_user'][0]

    @pytest.fixture
    def base_url(self, test_tenant_id: str, test_bu_id: str):
        return f'/tenants/{test_tenant_id}/bus/{test_bu_id}/enrichment'

    def test_byok_key_lifecycle(self, test_client: TestClient, base_url: str, app_user):
        """Store key → validate → encrypt → hint visible → delete."""
        fake_key = f'apify_api_test_{uuid.uuid4().hex[:20]}'
        uid = app_user.id

        # Mock Apify validation to return 200
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'username': 'test_user'}

        with patch('linkedout.enrichment_pipeline.controller.http_requests.get', return_value=mock_resp):
            res = test_client.put(
                f'{base_url}/apify-key?app_user_id={uid}',
                json={'api_key': fake_key},
            )
            assert res.status_code == 200
            data = res.json()
            assert data['status'] == 'validated'
            assert data['key_hint'] == f'...{fake_key[-4:]}'

        # GET config — should show byok mode + hint
        res = test_client.get(f'{base_url}/config?app_user_id={uid}')
        assert res.status_code == 200
        config = res.json()
        assert config['enrichment_mode'] == 'byok'
        assert config['key_hint'] == f'...{fake_key[-4:]}'

        # DELETE key
        res = test_client.delete(f'{base_url}/apify-key?app_user_id={uid}')
        assert res.status_code == 204

        # GET config — should be back to platform, no hint
        res = test_client.get(f'{base_url}/config?app_user_id={uid}')
        assert res.status_code == 200
        config = res.json()
        assert config['enrichment_mode'] == 'platform'
        assert config['key_hint'] is None

    def test_byok_invalid_key(self, test_client: TestClient, base_url: str, app_user):
        """Invalid key (mock Apify 401) → rejected."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = 'Unauthorized'

        with patch('linkedout.enrichment_pipeline.controller.http_requests.get', return_value=mock_resp):
            res = test_client.put(
                f'{base_url}/apify-key?app_user_id={app_user.id}',
                json={'api_key': 'bad_key_value'},
            )
            assert res.status_code == 400
            assert 'Invalid Apify API key' in res.json()['detail']

    def test_get_config_no_config_exists(self, test_client: TestClient, base_url: str, app_user):
        """GET config for user with no config returns platform defaults."""
        # Use a different user ID that exists but has no config
        users = ['usr-test-002']  # second seeded user, likely no config
        res = test_client.get(f'{base_url}/config?app_user_id={users[0]}')
        assert res.status_code == 200
        config = res.json()
        assert config['enrichment_mode'] == 'platform'
        assert config['key_hint'] is None

    def test_delete_key_no_config(self, test_client: TestClient, base_url: str):
        """DELETE key with no config returns 404."""
        res = test_client.delete(f'{base_url}/apify-key?app_user_id=usr-nonexistent-999')
        assert res.status_code == 404
