# SPDX-License-Identifier: Apache-2.0
"""Tests for AuthConfig."""
from shared.auth.config import AuthConfig


class TestAuthConfig:
    def test_default_values(self):
        config = AuthConfig(AUTH_ENABLED=True, FIREBASE_ENABLED=True)
        assert config.AUTH_ENABLED is True
        assert config.FIREBASE_ENABLED is True
        assert config.API_KEY_AUTH_ENABLED is False
        assert config.API_KEY_HEADER == "X-API-Key"
        assert config.DEV_BYPASS_USER_ID == "dev-user-001"

    def test_get_service_account_map_empty(self):
        config = AuthConfig(SERVICE_ACCOUNT_TOKENS="")
        assert config.get_service_account_map() == {}

    def test_get_service_account_map_single(self):
        config = AuthConfig(SERVICE_ACCOUNT_TOKENS="svc_abc:agent_service")
        result = config.get_service_account_map()
        assert result == {"svc_abc": "agent_service"}

    def test_get_service_account_map_multiple(self):
        config = AuthConfig(
            SERVICE_ACCOUNT_TOKENS="svc_abc:agent_service, svc_def:worker_service"
        )
        result = config.get_service_account_map()
        assert result == {"svc_abc": "agent_service", "svc_def": "worker_service"}

    def test_get_service_account_map_ignores_malformed(self):
        config = AuthConfig(SERVICE_ACCOUNT_TOKENS="valid_token:name,no_colon")
        result = config.get_service_account_map()
        assert result == {"valid_token": "name"}
