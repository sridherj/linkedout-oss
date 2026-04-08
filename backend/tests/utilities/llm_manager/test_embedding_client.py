# SPDX-License-Identifier: Apache-2.0
"""Tests for EmbeddingClient — unit tests with mocked OpenAI."""
from unittest.mock import MagicMock, patch

from utilities.llm_manager.embedding_client import EmbeddingClient


class TestBuildEmbeddingText:
    def test_full_profile(self):
        profile = {
            'full_name': 'John Doe',
            'headline': 'Senior Engineer',
            'about': 'Building cool things',
            'experiences': [
                {'company_name': 'Acme', 'title': 'Engineer'},
                {'company_name': 'Beta Corp', 'title': 'Lead'},
            ],
        }
        result = EmbeddingClient.build_embedding_text(profile)
        assert result == 'John Doe | Senior Engineer | Building cool things | Experience: Acme - Engineer, Beta Corp - Lead'

    def test_minimal_profile(self):
        profile = {'full_name': 'Jane'}
        result = EmbeddingClient.build_embedding_text(profile)
        assert result == 'Jane'

    def test_empty_profile(self):
        assert EmbeddingClient.build_embedding_text({}) == ''

    def test_experience_with_company_only(self):
        profile = {'experiences': [{'company_name': 'Acme'}]}
        result = EmbeddingClient.build_embedding_text(profile)
        assert result == 'Experience: Acme'

    def test_experience_with_title_only(self):
        profile = {'experiences': [{'title': 'Engineer'}]}
        result = EmbeddingClient.build_embedding_text(profile)
        assert result == 'Experience: Engineer'


class TestEmbedText:
    @patch('utilities.llm_manager.embedding_client.OpenAI')
    def test_returns_embedding(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1, 0.2, 0.3]
        mock_response = MagicMock()
        mock_response.data = [mock_embedding]
        mock_client.embeddings.create.return_value = mock_response

        client = EmbeddingClient(api_key='test-key')
        result = client.embed_text('hello world')

        assert result == [0.1, 0.2, 0.3]
        mock_client.embeddings.create.assert_called_once()

    @patch('utilities.llm_manager.embedding_client.OpenAI')
    def test_empty_text_raises(self, mock_openai_cls):
        client = EmbeddingClient(api_key='test-key')
        try:
            client.embed_text('')
            assert False, 'Should have raised ValueError'
        except ValueError:
            pass


class TestEmbedBatch:
    @patch('utilities.llm_manager.embedding_client.OpenAI')
    def test_filters_empty_texts(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_emb = MagicMock()
        mock_emb.embedding = [1.0, 2.0]
        mock_response = MagicMock()
        mock_response.data = [mock_emb]
        mock_client.embeddings.create.return_value = mock_response

        client = EmbeddingClient(api_key='test-key', dimensions=2)
        results = client.embed_batch(['', 'hello', ''])

        assert len(results) == 3
        assert results[0] == [0.0, 0.0]  # empty -> zero vector
        assert results[1] == [1.0, 2.0]  # real embedding
        assert results[2] == [0.0, 0.0]  # empty -> zero vector

    @patch('utilities.llm_manager.embedding_client.OpenAI')
    def test_empty_list(self, mock_openai_cls):
        client = EmbeddingClient(api_key='test-key')
        assert client.embed_batch([]) == []
