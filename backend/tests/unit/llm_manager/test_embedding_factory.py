# SPDX-License-Identifier: Apache-2.0
"""Tests for the embedding provider factory and column name helper."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _reset_config_singleton():
    """Reset the config singleton before each test so monkeypatch env vars take effect."""
    import shared.config.settings as settings_mod

    settings_mod._settings_instance = None
    yield
    settings_mod._settings_instance = None


@pytest.fixture()
def _openai_env(monkeypatch):
    """Set minimal env for OpenAI provider instantiation."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("LINKEDOUT_EMBEDDING__PROVIDER", "openai")
    monkeypatch.setenv("LINKEDOUT_EMBEDDING__MODEL", "text-embedding-3-small")
    monkeypatch.setenv("LINKEDOUT_EMBEDDING__DIMENSIONS", "1536")
    monkeypatch.setenv("LINKEDOUT_DATA_DIR", "/tmp/linkedout-test")


@pytest.fixture()
def _local_env(monkeypatch):
    """Set minimal env for local provider instantiation."""
    monkeypatch.setenv("LINKEDOUT_EMBEDDING__PROVIDER", "local")
    monkeypatch.setenv("LINKEDOUT_DATA_DIR", "/tmp/linkedout-test")
    # No OPENAI_API_KEY needed for local
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


class TestGetEmbeddingProvider:
    """Verify factory returns the correct provider type."""

    @patch("utilities.llm_manager.embedding_client.OpenAI")
    def test_returns_openai_provider_from_config(self, mock_openai_cls, _openai_env):
        """Factory returns OpenAIEmbeddingProvider when config says 'openai'."""
        from utilities.llm_manager.embedding_factory import get_embedding_provider
        from utilities.llm_manager.openai_embedding_provider import OpenAIEmbeddingProvider

        provider = get_embedding_provider()

        assert isinstance(provider, OpenAIEmbeddingProvider)
        assert provider.model_name() == "text-embedding-3-small"
        assert provider.dimension() == 1536

    def test_returns_local_provider_from_config(self, _local_env):
        """Factory returns LocalEmbeddingProvider when config says 'local'."""
        from utilities.llm_manager.embedding_factory import get_embedding_provider
        from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider

        provider = get_embedding_provider()

        assert isinstance(provider, LocalEmbeddingProvider)
        assert provider.model_name() == "nomic-embed-text-v1.5"
        assert provider.dimension() == 768

    @patch("utilities.llm_manager.embedding_client.OpenAI")
    def test_explicit_provider_overrides_config(self, mock_openai_cls, _local_env):
        """Explicit provider='openai' overrides config that says 'local'."""
        # Config says local, but we force openai
        from utilities.llm_manager.embedding_factory import get_embedding_provider
        from utilities.llm_manager.openai_embedding_provider import OpenAIEmbeddingProvider

        # Need API key for OpenAI
        import os
        os.environ["OPENAI_API_KEY"] = "sk-test-key"
        try:
            provider = get_embedding_provider(provider="openai")
            assert isinstance(provider, OpenAIEmbeddingProvider)
        finally:
            os.environ.pop("OPENAI_API_KEY", None)

    def test_explicit_local_overrides_config(self, _openai_env):
        """Explicit provider='local' overrides config that says 'openai'."""
        from utilities.llm_manager.embedding_factory import get_embedding_provider
        from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider

        provider = get_embedding_provider(provider="local")

        assert isinstance(provider, LocalEmbeddingProvider)

    def test_unknown_provider_raises_value_error(self):
        """Unknown provider name raises ValueError with helpful message."""
        from utilities.llm_manager.embedding_factory import get_embedding_provider

        with pytest.raises(ValueError, match="Unknown embedding provider.*'invalid'"):
            get_embedding_provider(provider="invalid")

    @patch("utilities.llm_manager.embedding_client.OpenAI")
    def test_model_parameter_passed_through(self, mock_openai_cls, _openai_env):
        """Model override is passed to the provider."""
        from utilities.llm_manager.embedding_factory import get_embedding_provider

        provider = get_embedding_provider(provider="openai", model="text-embedding-3-large")

        assert provider.model_name() == "text-embedding-3-large"

    def test_model_parameter_passed_through_local(self, _local_env):
        """Model override is passed to the local provider."""
        from utilities.llm_manager.embedding_factory import get_embedding_provider

        provider = get_embedding_provider(provider="local", model="custom-model")

        # LocalEmbeddingProvider always returns the constant model name
        # but stores the custom model internally
        assert provider._model_name == "custom-model"


class TestGetEmbeddingColumnName:
    """Verify column name mapping from provider model names."""

    def test_openai_model_returns_embedding_openai(self):
        """OpenAI model names map to embedding_openai column."""
        from utilities.llm_manager.embedding_factory import get_embedding_column_name

        provider = MagicMock()
        provider.model_name.return_value = "text-embedding-3-small"

        assert get_embedding_column_name(provider) == "embedding_openai"

    def test_nomic_model_returns_embedding_nomic(self):
        """Nomic model names map to embedding_nomic column."""
        from utilities.llm_manager.embedding_factory import get_embedding_column_name

        provider = MagicMock()
        provider.model_name.return_value = "nomic-embed-text-v1.5"

        assert get_embedding_column_name(provider) == "embedding_nomic"

    def test_nomic_case_insensitive(self):
        """Nomic detection is case-insensitive."""
        from utilities.llm_manager.embedding_factory import get_embedding_column_name

        provider = MagicMock()
        provider.model_name.return_value = "Nomic-Embed-Text-V1.5"

        assert get_embedding_column_name(provider) == "embedding_nomic"

    def test_unknown_model_defaults_to_openai(self):
        """Unknown models default to embedding_openai column."""
        from utilities.llm_manager.embedding_factory import get_embedding_column_name

        provider = MagicMock()
        provider.model_name.return_value = "some-other-model"

        assert get_embedding_column_name(provider) == "embedding_openai"


class TestIsEmbeddingProvider:
    """Verify factory returns proper EmbeddingProvider subclasses."""

    @patch("utilities.llm_manager.embedding_client.OpenAI")
    def test_openai_is_embedding_provider(self, mock_openai_cls, _openai_env):
        from utilities.llm_manager.embedding_factory import get_embedding_provider
        from utilities.llm_manager.embedding_provider import EmbeddingProvider

        provider = get_embedding_provider()
        assert isinstance(provider, EmbeddingProvider)

    def test_local_is_embedding_provider(self, _local_env):
        from utilities.llm_manager.embedding_factory import get_embedding_provider
        from utilities.llm_manager.embedding_provider import EmbeddingProvider

        provider = get_embedding_provider()
        assert isinstance(provider, EmbeddingProvider)
