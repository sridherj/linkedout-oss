# SPDX-License-Identifier: Apache-2.0
"""Tests for EnrichmentConfig settings."""
from shared.config.settings import EnrichmentConfig


class TestEnrichmentConfig:
    """Tests for enrichment pipeline configuration defaults and overrides."""

    def test_default_values(self):
        config = EnrichmentConfig()
        assert config.max_batch_size == 100
        assert config.skip_embeddings is False

    def test_custom_values(self):
        config = EnrichmentConfig(max_batch_size=50, skip_embeddings=True)
        assert config.max_batch_size == 50
        assert config.skip_embeddings is True
