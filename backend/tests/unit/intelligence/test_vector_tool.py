# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the vector semantic search tool."""
from unittest.mock import MagicMock, patch

class TestGetEmbeddingColumn:
    """Tests for _get_embedding_column() config-based column selection."""

    def test_returns_embedding_openai_for_openai_provider(self):
        mock_config = MagicMock()
        mock_config.embedding.provider = 'openai'
        with patch("linkedout.intelligence.tools.vector_tool.backend_config", mock_config, create=True):
            # Re-import to pick up the patched module-level import
            from linkedout.intelligence.tools import vector_tool
            with patch.object(vector_tool, '_get_embedding_column', wraps=vector_tool._get_embedding_column):
                # Patch the lazy import inside the function
                with patch("shared.config.config.backend_config", mock_config):
                    result = vector_tool._get_embedding_column()
        assert result == 'embedding_openai'

    def test_returns_embedding_nomic_for_local_provider(self):
        mock_config = MagicMock()
        mock_config.embedding.provider = 'local'
        with patch("shared.config.config.backend_config", mock_config):
            from linkedout.intelligence.tools.vector_tool import _get_embedding_column
            result = _get_embedding_column()
        assert result == 'embedding_nomic'


class TestGetSearchSql:
    """Tests for _get_search_sql() SQL template generation."""

    def test_openai_column_in_sql(self):
        from linkedout.intelligence.tools.vector_tool import _get_search_sql

        sql = _get_search_sql('embedding_openai')
        assert 'cp.embedding_openai' in sql
        assert 'cp.embedding_nomic' not in sql

    def test_nomic_column_in_sql(self):
        from linkedout.intelligence.tools.vector_tool import _get_search_sql

        sql = _get_search_sql('embedding_nomic')
        assert 'cp.embedding_nomic' in sql
        assert 'cp.embedding_openai' not in sql

    def test_sql_has_null_filter(self):
        from linkedout.intelligence.tools.vector_tool import _get_search_sql

        sql = _get_search_sql('embedding_openai')
        assert 'embedding_openai IS NOT NULL' in sql

    def test_sql_has_similarity_threshold(self):
        from linkedout.intelligence.tools.vector_tool import _get_search_sql

        sql = _get_search_sql('embedding_openai')
        assert '> 0.25' in sql


class TestSearchProfiles:
    def _patch_embedding_column(self):
        """Helper to patch _get_embedding_column for search_profiles tests."""
        return patch(
            "linkedout.intelligence.tools.vector_tool._get_embedding_column",
            return_value="embedding_openai",
        )

    def test_calls_embedding_provider(self):
        from linkedout.intelligence.tools.vector_tool import search_profiles

        mock_provider = MagicMock()
        mock_provider.embed_single.return_value = [0.1, 0.2, 0.3]

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        with self._patch_embedding_column():
            search_profiles("AI engineer", mock_session, embedding_provider=mock_provider)

        mock_provider.embed_single.assert_called_once_with("AI engineer")

    def test_result_format(self):
        from linkedout.intelligence.tools.vector_tool import search_profiles, _RESULT_COLUMNS

        mock_provider = MagicMock()
        mock_provider.embed_single.return_value = [0.1, 0.2, 0.3]

        mock_session = MagicMock()
        mock_result = MagicMock()
        # Build a fake row with the right number of columns
        fake_row = tuple(f"val_{i}" for i in range(len(_RESULT_COLUMNS)))
        mock_result.fetchall.return_value = [fake_row]
        mock_session.execute.return_value = mock_result

        with self._patch_embedding_column():
            results = search_profiles("test", mock_session, embedding_provider=mock_provider)

        assert len(results) == 1
        assert isinstance(results[0], dict)
        for col in _RESULT_COLUMNS:
            assert col in results[0]

    def test_limit_passed_to_query(self):
        from linkedout.intelligence.tools.vector_tool import search_profiles

        mock_provider = MagicMock()
        mock_provider.embed_single.return_value = [0.1]

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        with self._patch_embedding_column():
            search_profiles("test", mock_session, limit=5, embedding_provider=mock_provider)

        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 5

    def test_creates_default_provider_when_none_provided(self):
        with patch("linkedout.intelligence.tools.vector_tool.get_embedding_provider") as MockFactory:
            mock_instance = MagicMock()
            mock_instance.embed_single.return_value = [0.1]
            MockFactory.return_value = mock_instance

            mock_session = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = []
            mock_session.execute.return_value = mock_result

            from linkedout.intelligence.tools.vector_tool import search_profiles

            with self._patch_embedding_column():
                search_profiles("test", mock_session)

            MockFactory.assert_called_once()
