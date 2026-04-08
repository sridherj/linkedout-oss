# SPDX-License-Identifier: Apache-2.0
"""Tests for LocalEmbeddingProvider."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest


@pytest.fixture(autouse=True)
def _reset_config_singleton():
    """Reset the config singleton before each test so monkeypatch env vars take effect."""
    import shared.config.settings as settings_mod

    settings_mod._settings_instance = None
    yield
    settings_mod._settings_instance = None


@pytest.fixture()
def _local_env(monkeypatch):
    """Set minimal env for local provider tests."""
    monkeypatch.setenv("LINKEDOUT_EMBEDDING__PROVIDER", "local")
    monkeypatch.setenv("LINKEDOUT_EMBEDDING__DIMENSIONS", "768")
    monkeypatch.setenv("LINKEDOUT_DATA_DIR", "/tmp/linkedout-test")


def _make_mock_model(dim: int = 768):
    """Build a mock SentenceTransformer that returns numpy arrays of the given dimension."""
    mock_model = MagicMock()

    def _encode(texts, batch_size=32, show_progress_bar=False, normalize_embeddings=True):
        return np.random.default_rng(42).random((len(texts), dim)).astype(np.float32)

    mock_model.encode = _encode
    return mock_model


class TestInit:
    """Verify provider initialization and lazy loading."""

    def test_model_not_loaded_on_init(self):
        """Model is None after __init__ — no eager loading."""
        from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        assert provider._model is None

    def test_default_model_name(self):
        """Default model is nomic-ai/nomic-embed-text-v1.5."""
        from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        assert provider._model_name == "nomic-ai/nomic-embed-text-v1.5"

    def test_custom_model_name(self):
        """Custom model name is accepted."""
        from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider(model="custom/model")
        assert provider._model_name == "custom/model"


class TestLazyLoading:
    """Verify lazy model loading behavior."""

    @patch("utilities.llm_manager.local_embedding_provider.get_config")
    def test_model_loaded_on_first_embed(self, mock_get_config, _local_env):
        """Model is loaded on first embed() call, not before."""
        from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider

        mock_cfg = MagicMock()
        mock_cfg.data_dir = "/tmp/linkedout-test"
        mock_get_config.return_value = mock_cfg

        provider = LocalEmbeddingProvider()
        assert provider._model is None

        mock_model = _make_mock_model()
        with patch(
            "utilities.llm_manager.local_embedding_provider.LocalEmbeddingProvider._ensure_model_loaded"
        ) as mock_ensure:
            # Manually set model to simulate loading
            def _side_effect():
                provider._model = mock_model

            mock_ensure.side_effect = _side_effect
            provider.embed(["test"])
            mock_ensure.assert_called_once()

    def test_import_error_when_sentence_transformers_missing(self, _local_env):
        """Calling embed() without sentence-transformers raises ImportError with clear message."""
        from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()

        with patch.dict("sys.modules", {"sentence_transformers": None}):
            with patch(
                "builtins.__import__",
                side_effect=_make_import_error("sentence_transformers"),
            ):
                with pytest.raises(ImportError, match="sentence-transformers"):
                    provider._ensure_model_loaded()

    def test_import_module_succeeds_without_deps(self):
        """Importing local_embedding_provider works even without sentence-transformers."""
        # This test verifies the lazy import pattern — the module itself imports fine.
        from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider

        assert LocalEmbeddingProvider is not None


class TestEmbed:
    """Verify embed() and embed_single() behavior."""

    @patch("utilities.llm_manager.local_embedding_provider.get_config")
    def test_embed_returns_vectors(self, mock_get_config, _local_env):
        """embed() returns a list of vectors with correct dimension."""
        from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider

        mock_cfg = MagicMock()
        mock_cfg.data_dir = "/tmp/linkedout-test"
        mock_get_config.return_value = mock_cfg

        provider = LocalEmbeddingProvider()
        provider._model = _make_mock_model()

        result = provider.embed(["hello", "world"])
        assert len(result) == 2
        assert len(result[0]) == 768
        assert len(result[1]) == 768
        assert all(isinstance(v, float) for v in result[0])

    @patch("utilities.llm_manager.local_embedding_provider.get_config")
    def test_embed_single_returns_vector(self, mock_get_config, _local_env):
        """embed_single() returns a single 768-dim vector."""
        from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider

        mock_cfg = MagicMock()
        mock_cfg.data_dir = "/tmp/linkedout-test"
        mock_get_config.return_value = mock_cfg

        provider = LocalEmbeddingProvider()
        provider._model = _make_mock_model()

        result = provider.embed_single("hello world")
        assert len(result) == 768
        assert all(isinstance(v, float) for v in result)

    def test_embed_empty_list_returns_empty(self):
        """embed([]) returns an empty list without loading the model."""
        from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        result = provider.embed([])

        assert result == []
        assert provider._model is None  # model never loaded

    @patch("utilities.llm_manager.local_embedding_provider.get_config")
    def test_embed_empty_string(self, mock_get_config, _local_env):
        """embed(['']) returns a vector (model handles empty strings)."""
        from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider

        mock_cfg = MagicMock()
        mock_cfg.data_dir = "/tmp/linkedout-test"
        mock_get_config.return_value = mock_cfg

        provider = LocalEmbeddingProvider()
        provider._model = _make_mock_model()

        result = provider.embed([""])
        assert len(result) == 1
        assert len(result[0]) == 768


class TestDiagnostics:
    """Verify dimension(), model_name(), estimate_time(), estimate_cost()."""

    def test_dimension(self):
        from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        assert provider.dimension() == 768

    def test_model_name(self):
        from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        assert provider.model_name() == "nomic-embed-text-v1.5"

    def test_estimate_time_4000(self):
        """4000 profiles at ~7/sec ≈ ~10 minutes."""
        from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        result = provider.estimate_time(4000)
        assert "minute" in result
        assert "4,000" in result

    def test_estimate_time_zero(self):
        from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        assert provider.estimate_time(0) == "< 1 second"

    def test_estimate_time_small_count(self):
        """Small count returns ~1 minute."""
        from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        result = provider.estimate_time(5)
        assert "1 minute" in result

    def test_estimate_cost_returns_none(self):
        """Local inference is free — always returns None."""
        from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        assert provider.estimate_cost(4000) is None

    def test_estimate_cost_zero_returns_none(self):
        from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        assert provider.estimate_cost(0) is None


class TestIsEmbeddingProvider:
    """Verify that LocalEmbeddingProvider is a proper subclass of EmbeddingProvider."""

    def test_isinstance(self):
        from utilities.llm_manager.embedding_provider import EmbeddingProvider
        from utilities.llm_manager.local_embedding_provider import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        assert isinstance(provider, EmbeddingProvider)


def _make_import_error(module_name: str):
    """Create an __import__ side effect that fails for a specific module."""
    _real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

    def _fake_import(name, *args, **kwargs):
        if name == module_name:
            raise ImportError(f"No module named '{module_name}'")
        return _real_import(name, *args, **kwargs)

    return _fake_import
