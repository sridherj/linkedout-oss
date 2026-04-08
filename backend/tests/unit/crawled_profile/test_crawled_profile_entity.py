# SPDX-License-Identifier: Apache-2.0
"""Unit tests for CrawledProfileEntity embedding columns."""
from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity


class TestEmbeddingColumns:
    """Verify the entity has the expected multi-provider embedding attributes."""

    def test_has_embedding_openai(self):
        assert hasattr(CrawledProfileEntity, 'embedding_openai')

    def test_has_embedding_nomic(self):
        assert hasattr(CrawledProfileEntity, 'embedding_nomic')

    def test_has_embedding_model(self):
        assert hasattr(CrawledProfileEntity, 'embedding_model')

    def test_has_embedding_dim(self):
        assert hasattr(CrawledProfileEntity, 'embedding_dim')

    def test_has_embedding_updated_at(self):
        assert hasattr(CrawledProfileEntity, 'embedding_updated_at')

    def test_old_embedding_attribute_removed(self):
        assert not hasattr(CrawledProfileEntity, 'embedding')
