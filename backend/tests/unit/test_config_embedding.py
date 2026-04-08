# SPDX-License-Identifier: Apache-2.0
"""Tests for embedding-related config wiring in LinkedOutSettings."""

import pytest

from shared.config.settings import EmbeddingConfig, LinkedOutSettings


class TestEmbeddingProviderValidation:
    """Verify embedding_provider field validation."""

    def test_openai_is_valid(self):
        cfg = EmbeddingConfig(provider="openai")
        assert cfg.provider == "openai"

    def test_local_is_valid(self):
        cfg = EmbeddingConfig(provider="local")
        assert cfg.provider == "local"

    def test_invalid_provider_raises(self):
        with pytest.raises(ValueError, match="must be 'openai' or 'local'"):
            EmbeddingConfig(provider="bogus")

    def test_auto_provider_rejected(self):
        with pytest.raises(ValueError, match="must be 'openai' or 'local'"):
            EmbeddingConfig(provider="auto")


class TestEmbeddingConfigEnvOverride:
    """Verify env var overrides for embedding config."""

    def test_env_sets_provider_to_local(self, monkeypatch):
        monkeypatch.setenv("LINKEDOUT_EMBEDDING__PROVIDER", "local")
        monkeypatch.setenv("LINKEDOUT_EMBEDDING__DIMENSIONS", "768")
        # Provide an API key so the openai warning path isn't hit
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        settings = LinkedOutSettings()
        assert settings.embedding.provider == "local"

    def test_env_sets_model(self, monkeypatch):
        monkeypatch.setenv("LINKEDOUT_EMBEDDING__MODEL", "custom-model")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        settings = LinkedOutSettings()
        assert settings.embedding.model == "custom-model"

    def test_openai_without_api_key_warns(self, monkeypatch, caplog, tmp_path):
        """OpenAI provider without API key should warn, not error."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        # Ensure no secrets.yaml, config.yaml, or .env interferes
        monkeypatch.setenv("LINKEDOUT_DATA_DIR", str(tmp_path))
        # Point env_file to a nonexistent path so .env keys don't leak in
        monkeypatch.chdir(tmp_path)
        import logging

        with caplog.at_level(logging.WARNING, logger="linkedout.config"):
            settings = LinkedOutSettings(_env_file=None)
        assert settings.embedding.provider == "openai"
        assert "OPENAI_API_KEY is not set" in caplog.text
