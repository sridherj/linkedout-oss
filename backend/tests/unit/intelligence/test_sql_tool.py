# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the SQL query execution tool."""
import pytest

from linkedout.intelligence.tools.sql_tool import _inject_limit, _is_select_only


class TestIsSelectOnly:
    def test_simple_select(self):
        assert _is_select_only("SELECT * FROM crawled_profile") is True

    def test_select_with_whitespace(self):
        assert _is_select_only("  select id from connection  ") is True

    def test_select_with_cte(self):
        query = "WITH cte AS (SELECT id FROM connection) SELECT * FROM cte"
        assert _is_select_only(query) is True

    def test_insert_rejected(self):
        assert _is_select_only("INSERT INTO connection (id) VALUES ('x')") is False

    def test_update_rejected(self):
        assert _is_select_only("UPDATE connection SET notes = 'x'") is False

    def test_delete_rejected(self):
        assert _is_select_only("DELETE FROM connection WHERE id = 'x'") is False

    def test_drop_rejected(self):
        assert _is_select_only("DROP TABLE connection") is False

    def test_truncate_rejected(self):
        assert _is_select_only("TRUNCATE connection") is False

    def test_select_case_insensitive(self):
        assert _is_select_only("Select id From crawled_profile") is True

    def test_semicolon_stripped(self):
        assert _is_select_only("SELECT 1;") is True


class TestInjectLimit:
    def test_adds_limit_when_missing(self):
        result = _inject_limit("SELECT * FROM crawled_profile")
        assert "LIMIT 100" in result

    def test_preserves_existing_limit(self):
        query = "SELECT * FROM crawled_profile LIMIT 10"
        result = _inject_limit(query)
        assert "LIMIT 10" in result
        assert "LIMIT 100" not in result

    def test_custom_max_rows(self):
        result = _inject_limit("SELECT * FROM crawled_profile", max_rows=50)
        assert "LIMIT 50" in result

    def test_case_insensitive_limit_detection(self):
        query = "SELECT * FROM crawled_profile limit 25"
        result = _inject_limit(query)
        assert "limit 25" in result
        assert "LIMIT 100" not in result

    def test_strips_trailing_semicolon(self):
        result = _inject_limit("SELECT * FROM crawled_profile;")
        assert result.endswith("LIMIT 100")


class TestExecuteSql:
    def test_rejects_non_select(self):
        from linkedout.intelligence.tools.sql_tool import execute_sql
        from unittest.mock import MagicMock

        session = MagicMock()
        result = execute_sql("INSERT INTO foo VALUES (1)", session)
        assert "error" in result
        assert result["row_count"] == 0
        session.execute.assert_not_called()
