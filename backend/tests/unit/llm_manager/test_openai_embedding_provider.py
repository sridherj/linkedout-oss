# SPDX-License-Identifier: Apache-2.0
"""Tests for OpenAIEmbeddingProvider."""

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


def _make_embedding_response(vectors: list[list[float]]):
    """Build a mock OpenAI embeddings response."""
    mock_resp = MagicMock()
    mock_resp.data = [MagicMock(embedding=v) for v in vectors]
    return mock_resp


class TestOpenAIEmbeddingProviderInit:
    """Verify provider initialization and config resolution."""

    def test_raises_without_api_key(self, monkeypatch, tmp_path):
        """Provider raises RuntimeError with actionable message when API key is missing."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("LINKEDOUT_DATA_DIR", str(tmp_path))
        # Reset cached config so it re-reads without .env keys
        import shared.config.settings as _cfg_mod
        monkeypatch.setattr(_cfg_mod, "_settings_instance", None)
        monkeypatch.chdir(tmp_path)

        from utilities.llm_manager.openai_embedding_provider import (
            OpenAIEmbeddingProvider,
        )

        with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not configured"):
            OpenAIEmbeddingProvider()

    @patch("utilities.llm_manager.embedding_client.OpenAI")
    def test_uses_config_defaults(self, mock_openai_cls, _openai_env):
        """Provider reads model/dimensions from config when not specified."""
        from utilities.llm_manager.openai_embedding_provider import (
            OpenAIEmbeddingProvider,
        )

        provider = OpenAIEmbeddingProvider()
        assert provider.model_name() == "text-embedding-3-small"
        assert provider.dimension() == 1536

    @patch("utilities.llm_manager.embedding_client.OpenAI")
    def test_override_model_and_dimensions(self, mock_openai_cls, _openai_env):
        """Explicit model/dimensions override config values."""
        from utilities.llm_manager.openai_embedding_provider import (
            OpenAIEmbeddingProvider,
        )

        provider = OpenAIEmbeddingProvider(
            model="text-embedding-3-large", dimensions=3072
        )
        assert provider.model_name() == "text-embedding-3-large"
        assert provider.dimension() == 3072


class TestEmbed:
    """Verify embed() and embed_single() delegation to EmbeddingClient."""

    @patch("utilities.llm_manager.embedding_client.OpenAI")
    def test_embed_returns_vectors(self, mock_openai_cls, _openai_env):
        """embed() returns a list of vectors with correct dimension."""
        from utilities.llm_manager.openai_embedding_provider import (
            OpenAIEmbeddingProvider,
        )

        expected_vectors = [[0.1] * 1536, [0.2] * 1536]
        mock_client_instance = mock_openai_cls.return_value
        mock_client_instance.embeddings.create.return_value = _make_embedding_response(
            expected_vectors
        )

        provider = OpenAIEmbeddingProvider()
        actual_result = provider.embed(["hello", "world"])

        assert len(actual_result) == 2
        assert len(actual_result[0]) == 1536
        assert len(actual_result[1]) == 1536
        assert actual_result[0] == expected_vectors[0]

    @patch("utilities.llm_manager.embedding_client.OpenAI")
    def test_embed_single_returns_vector(self, mock_openai_cls, _openai_env):
        """embed_single() returns a single vector."""
        from utilities.llm_manager.openai_embedding_provider import (
            OpenAIEmbeddingProvider,
        )

        expected_vector = [0.5] * 1536
        mock_client_instance = mock_openai_cls.return_value
        mock_client_instance.embeddings.create.return_value = _make_embedding_response(
            [expected_vector]
        )

        provider = OpenAIEmbeddingProvider()
        actual_result = provider.embed_single("hello world")

        assert len(actual_result) == 1536
        assert actual_result == expected_vector

    @patch("utilities.llm_manager.embedding_client.OpenAI")
    def test_embed_empty_list_returns_empty(self, mock_openai_cls, _openai_env):
        """embed([]) returns an empty list without calling the API."""
        from utilities.llm_manager.openai_embedding_provider import (
            OpenAIEmbeddingProvider,
        )

        provider = OpenAIEmbeddingProvider()
        actual_result = provider.embed([])

        assert actual_result == []
        mock_openai_cls.return_value.embeddings.create.assert_not_called()

    @patch("utilities.llm_manager.embedding_client.OpenAI")
    def test_embed_empty_string_returns_zero_vector(self, mock_openai_cls, _openai_env):
        """embed(['']) returns a zero vector (EmbeddingClient behavior)."""
        from utilities.llm_manager.openai_embedding_provider import (
            OpenAIEmbeddingProvider,
        )

        provider = OpenAIEmbeddingProvider()
        actual_result = provider.embed([""])

        # EmbeddingClient.embed_batch filters empty texts and returns zero vectors
        assert len(actual_result) == 1
        assert actual_result[0] == [0.0] * 1536


class TestDiagnostics:
    """Verify dimension(), model_name(), estimate_time(), estimate_cost()."""

    @patch("utilities.llm_manager.embedding_client.OpenAI")
    def test_dimension(self, mock_openai_cls, _openai_env):
        from utilities.llm_manager.openai_embedding_provider import (
            OpenAIEmbeddingProvider,
        )

        provider = OpenAIEmbeddingProvider()
        assert provider.dimension() == 1536

    @patch("utilities.llm_manager.embedding_client.OpenAI")
    def test_model_name(self, mock_openai_cls, _openai_env):
        from utilities.llm_manager.openai_embedding_provider import (
            OpenAIEmbeddingProvider,
        )

        provider = OpenAIEmbeddingProvider()
        assert provider.model_name() == "text-embedding-3-small"

    @patch("utilities.llm_manager.embedding_client.OpenAI")
    def test_estimate_time_4000(self, mock_openai_cls, _openai_env):
        """4000 texts ≈ 40 minutes at 100/min."""
        from utilities.llm_manager.openai_embedding_provider import (
            OpenAIEmbeddingProvider,
        )

        provider = OpenAIEmbeddingProvider()
        actual_result = provider.estimate_time(4000)
        assert "40" in actual_result
        assert "minute" in actual_result

    @patch("utilities.llm_manager.embedding_client.OpenAI")
    def test_estimate_time_zero(self, mock_openai_cls, _openai_env):
        from utilities.llm_manager.openai_embedding_provider import (
            OpenAIEmbeddingProvider,
        )

        provider = OpenAIEmbeddingProvider()
        assert provider.estimate_time(0) == "< 1 second"

    @patch("utilities.llm_manager.embedding_client.OpenAI")
    def test_estimate_time_small_count(self, mock_openai_cls, _openai_env):
        """Small counts should return ~1 minute (not zero)."""
        from utilities.llm_manager.openai_embedding_provider import (
            OpenAIEmbeddingProvider,
        )

        provider = OpenAIEmbeddingProvider()
        assert provider.estimate_time(50) == "~1 minute"

    @patch("utilities.llm_manager.embedding_client.OpenAI")
    def test_estimate_cost_4000(self, mock_openai_cls, _openai_env):
        """4000 profiles ≈ 2M tokens ≈ $0.04."""
        from utilities.llm_manager.openai_embedding_provider import (
            OpenAIEmbeddingProvider,
        )

        provider = OpenAIEmbeddingProvider()
        actual_result = provider.estimate_cost(4000)
        assert actual_result is not None
        assert "$" in actual_result
        assert "4000" in actual_result

    @patch("utilities.llm_manager.embedding_client.OpenAI")
    def test_estimate_cost_zero(self, mock_openai_cls, _openai_env):
        from utilities.llm_manager.openai_embedding_provider import (
            OpenAIEmbeddingProvider,
        )

        provider = OpenAIEmbeddingProvider()
        assert provider.estimate_cost(0) is None


class TestIsEmbeddingProvider:
    """Verify that OpenAIEmbeddingProvider is a proper subclass of EmbeddingProvider."""

    @patch("utilities.llm_manager.embedding_client.OpenAI")
    def test_isinstance(self, mock_openai_cls, _openai_env):
        from utilities.llm_manager.embedding_provider import EmbeddingProvider
        from utilities.llm_manager.openai_embedding_provider import (
            OpenAIEmbeddingProvider,
        )

        provider = OpenAIEmbeddingProvider()
        assert isinstance(provider, EmbeddingProvider)
