# SPDX-License-Identifier: Apache-2.0
"""Tests for ApiKeyAuthProvider."""
import pytest
from unittest.mock import MagicMock, patch

import bcrypt

from shared.auth.providers.api_key_auth_provider import ApiKeyAuthProvider


class TestApiKeyAuthProvider:
    def test_singleton_pattern(self):
        # Reset singleton for clean test
        ApiKeyAuthProvider._instance = None
        a = ApiKeyAuthProvider.get_instance()
        b = ApiKeyAuthProvider.get_instance()
        assert a is b

    def test_verify_short_key_returns_none(self):
        ApiKeyAuthProvider._instance = None
        provider = ApiKeyAuthProvider.get_instance()
        session = MagicMock()
        result = provider.verify_api_key("short", session)
        assert result is None

    def test_verify_unknown_prefix_returns_none(self):
        ApiKeyAuthProvider._instance = None
        provider = ApiKeyAuthProvider.get_instance()
        session = MagicMock()

        # No user found for this prefix
        session.query.return_value.filter.return_value.first.return_value = None

        with patch("organization.entities.app_user_entity.AppUserEntity") as MockEntity:
            MockEntity.api_key_prefix = "api_key_prefix"
            result = provider.verify_api_key("unknown_prefix_key_value", session)

        assert result is None

    def test_verify_valid_key(self):
        ApiKeyAuthProvider._instance = None
        provider = ApiKeyAuthProvider.get_instance()

        api_key = "testpfx1_the_rest_of_the_key"
        hashed = bcrypt.hashpw(api_key.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        mock_user = MagicMock()
        mock_user.id = "usr_001"
        mock_user.api_key_hash = hashed
        mock_user.tenant_id = "t-001"

        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = mock_user

        with patch("organization.entities.app_user_entity.AppUserEntity"):
            result = provider.verify_api_key(api_key, session)

        assert result is not None
        assert result["app_user_id"] == "usr_001"

    def test_verify_invalid_key_bcrypt_fails(self):
        ApiKeyAuthProvider._instance = None
        provider = ApiKeyAuthProvider.get_instance()

        correct_key = "testpfx1_correct_key"
        wrong_key = "testpfx1_wrong_key_value"
        hashed = bcrypt.hashpw(correct_key.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        mock_user = MagicMock()
        mock_user.id = "usr_001"
        mock_user.api_key_hash = hashed
        mock_user.tenant_id = "t-001"

        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = mock_user

        with patch("organization.entities.app_user_entity.AppUserEntity"):
            result = provider.verify_api_key(wrong_key, session)

        assert result is None

    def test_verify_token_raises_not_implemented(self):
        ApiKeyAuthProvider._instance = None
        provider = ApiKeyAuthProvider.get_instance()
        with pytest.raises(NotImplementedError):
            provider.verify_token("some-token")

    def test_create_user_raises_not_implemented(self):
        ApiKeyAuthProvider._instance = None
        provider = ApiKeyAuthProvider.get_instance()
        with pytest.raises(NotImplementedError):
            provider.create_user("test@example.com")
