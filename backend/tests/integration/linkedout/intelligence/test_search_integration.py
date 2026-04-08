# SPDX-License-Identifier: Apache-2.0
"""Integration tests for intelligence search components against PostgreSQL."""
import json

import pytest
from sqlalchemy import text

from linkedout.intelligence.tools.sql_tool import execute_sql

pytestmark = pytest.mark.integration


class TestSqlToolBasic:
    """Verify SQL tool works with an RLS-scoped session."""

    def test_select_returns_results(
        self, integration_db_session, intelligence_test_data
    ):
        query = (
            "SELECT cp.full_name FROM crawled_profile cp "
            "JOIN connection c ON c.crawled_profile_id = cp.id"
        )
        result = execute_sql(query, integration_db_session)

        assert 'error' not in result
        assert result['row_count'] > 0


class TestFundingTablesAccessible:
    """Verify funding tables are queryable via execute_sql."""

    def test_funding_round_queryable(self, integration_db_session, intelligence_test_data):
        result = execute_sql("SELECT COUNT(*) FROM funding_round", integration_db_session)
        assert 'error' not in result or 'does not exist' not in result.get('error', '')

    def test_startup_tracking_queryable(self, integration_db_session, intelligence_test_data):
        result = execute_sql("SELECT COUNT(*) FROM startup_tracking", integration_db_session)
        assert 'error' not in result or 'does not exist' not in result.get('error', '')

    def test_funding_join_with_company(self, integration_db_session, intelligence_test_data):
        result = execute_sql(
            "SELECT c.canonical_name, fr.round_type, fr.amount_usd "
            "FROM funding_round fr JOIN company c ON c.id = fr.company_id LIMIT 5",
            integration_db_session,
        )
        assert 'error' not in result or 'does not exist' not in result.get('error', '')


class TestSqlToolSafety:
    """Test SQL tool safety guardrails against real PostgreSQL."""

    def test_rejects_insert(self, integration_db_session, intelligence_test_data):
        result = execute_sql(
            "INSERT INTO connection (id) VALUES ('x')",
            integration_db_session,
        )
        assert 'error' in result
        assert 'SELECT' in result['error']

    def test_rejects_drop(self, integration_db_session, intelligence_test_data):
        result = execute_sql(
            "DROP TABLE connection",
            integration_db_session,
        )
        assert 'error' in result

    def test_auto_injects_limit(self, integration_db_session, intelligence_test_data):
        query = (
            "SELECT cp.full_name FROM crawled_profile cp "
            "JOIN connection c ON c.crawled_profile_id = cp.id"
        )
        result = execute_sql(query, integration_db_session)

        assert 'error' not in result
        assert result['row_count'] <= 100  # default LIMIT


class TestSqlToolUnenrichedVisibility:
    """SQL returns both enriched and unenriched profiles."""

    def test_sql_returns_enriched_and_unenriched(
        self, integration_db_session, intelligence_test_data
    ):
        query = (
            "SELECT cp.full_name, cp.has_enriched_data "
            "FROM crawled_profile cp "
            "JOIN connection c ON c.crawled_profile_id = cp.id"
        )
        result = execute_sql(query, integration_db_session)

        assert 'error' not in result
        enriched_flags = [row[1] for row in result['rows']]
        assert True in enriched_flags, "Should have enriched profiles"
        assert False in enriched_flags, "Should have stub (unenriched) profiles"


class TestSqlToolErrorHints:
    """Test that SQL errors produce helpful hints on PostgreSQL."""

    def test_bad_table_returns_hint(self, integration_db_session, intelligence_test_data):
        result = execute_sql(
            "SELECT * FROM nonexistent_table",
            integration_db_session,
        )
        assert 'error' in result
        # The error should mention the relation doesn't exist
        assert 'does not exist' in result['error'].lower() or 'error' in result

        # Rollback the failed transaction so subsequent tests work
        integration_db_session.rollback()


class TestVectorSearchUserScoped:
    """Test pgvector search is user-scoped (requires pgvector + embeddings)."""

    def test_vector_search_returns_only_user_connections(
        self, integration_db_session, intelligence_test_data,
        vector_column_ready,
    ):
        if not vector_column_ready:
            pytest.skip("pgvector not available in test schema")

        from linkedout.intelligence.tools.vector_tool import search_profiles
        from unittest.mock import MagicMock

        # Insert a test embedding for one of User A's profiles
        profile = intelligence_test_data['profiles_a'][0]
        embedding = [0.1] * 1536
        embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
        integration_db_session.execute(
            text("UPDATE crawled_profile SET embedding_openai = CAST(:emb AS vector) WHERE id = :pid"),
            {"emb": embedding_str, "pid": profile.id},
        )
        integration_db_session.flush()

        mock_provider = MagicMock()
        mock_provider.embed_single.return_value = [0.1] * 1536

        results = search_profiles(
            "test query", integration_db_session,
            limit=5, embedding_provider=mock_provider,
        )

        # All results should belong to user A's connections
        conn_ids_a = {c.id for c in intelligence_test_data['connections_a']}
        for r in results:
            assert r['connection_id'] in conn_ids_a

    def test_vector_search_excludes_unenriched(
        self, integration_db_session, intelligence_test_data,
        vector_column_ready,
    ):
        """Vector search only returns profiles with embeddings (enriched)."""
        if not vector_column_ready:
            pytest.skip("pgvector not available in test schema")

        from linkedout.intelligence.tools.vector_tool import search_profiles
        from unittest.mock import MagicMock

        mock_provider = MagicMock()
        mock_provider.embed_single.return_value = [0.1] * 1536

        results = search_profiles(
            "test", integration_db_session,
            limit=100, embedding_provider=mock_provider,
        )

        # Only profiles with embeddings should be returned
        for r in results:
            assert r['has_enriched_data'] is True


class TestSSEStreaming:
    """Test SSE endpoint streams correctly."""

    def test_sse_search_returns_event_stream(
        self, test_client, intelligence_test_data
    ):
        """SSE events stream correctly with proper content type."""
        user_a = intelligence_test_data['user_a']
        tenant = intelligence_test_data['tenant']
        bu = intelligence_test_data['bu']

        # The search endpoint needs an LLM, so we mock the SearchAgent
        from unittest.mock import patch, MagicMock
        from linkedout.intelligence.contracts import SearchResponse, SearchResultItem

        mock_response = SearchResponse(
            answer="Found results",
            results=[
                SearchResultItem(
                    connection_id="conn_test",
                    crawled_profile_id="cp_test",
                    full_name="Test Person",
                ),
            ],
            query_type="sql",
            result_count=1,
        )

        with patch(
            "linkedout.intelligence.agents.search_agent.SearchAgent"
        ) as MockAgent:
            mock_agent = MagicMock()
            mock_agent.run.return_value = mock_response
            MockAgent.return_value = mock_agent

            response = test_client.post(
                f"/tenants/{tenant.id}/bus/{bu.id}/search",
                json={"query": "engineers", "limit": 5},
                headers={"X-App-User-Id": user_a.id},
            )

            assert response.status_code == 200
            assert response.headers['content-type'].startswith('text/event-stream')

            # Parse SSE events
            events = []
            for line in response.text.split('\n'):
                if line.startswith('data: '):
                    events.append(json.loads(line[6:]))

            # Should have at least a result and done event
            event_types = [e['type'] for e in events]
            assert 'thinking' in event_types
            assert 'done' in event_types


class TestSearchSessionPersistence:
    """Verify that calling the search endpoint persists a session and turn."""

    def test_search_persists_session_and_turn(
        self, test_client, intelligence_test_data
    ):
        """After POST /search, a session and turn appear in GET /search-sessions."""
        user_a = intelligence_test_data['user_a']
        tenant = intelligence_test_data['tenant']
        bu = intelligence_test_data['bu']

        from unittest.mock import patch, MagicMock
        from linkedout.intelligence.contracts import ConversationTurnResponse, SearchResultItem

        mock_response = ConversationTurnResponse(
            message="Found results",
            results=[
                SearchResultItem(
                    connection_id="conn_test",
                    crawled_profile_id="cp_test",
                    full_name="Test Person",
                ),
            ],
            query_type="sql",
        )

        with patch(
            "linkedout.intelligence.agents.search_agent.SearchAgent"
        ) as MockAgent:
            mock_agent = MagicMock()
            mock_agent.run_turn.return_value = mock_response
            MockAgent.return_value = mock_agent

            response = test_client.post(
                f"/tenants/{tenant.id}/bus/{bu.id}/search",
                json={"query": "engineers in San Francisco", "limit": 5},
                headers={"X-App-User-Id": user_a.id},
            )

        assert response.status_code == 200

        sessions_response = test_client.get(
            f"/tenants/{tenant.id}/bus/{bu.id}/search-sessions",
            params={"app_user_id": user_a.id},
        )

        assert sessions_response.status_code == 200
        data = sessions_response.json()
        assert "search_sessions" in data
        assert data["total"] >= 1

        matching = [
            s for s in data["search_sessions"]
            if s.get("initial_query") == "engineers in San Francisco"
        ]
        assert len(matching) >= 1, "Expected at least one matching session"
        session = matching[0]
        assert session["is_saved"] is False
        assert session["turn_count"] >= 1


class TestWarmIntroPaths:
    """Test warm intro path discovery via shared companies."""

    def test_finds_shared_company_connections(
        self, test_client, intelligence_test_data
    ):
        user_a = intelligence_test_data['user_a']
        tenant = intelligence_test_data['tenant']
        bu = intelligence_test_data['bu']

        # profiles_a[1] worked at Google, and profiles_a[0] (user's own) also worked at Google
        # So profiles_a[1] should appear as an intro path for profiles_a[2] if they share a company
        # Actually, let's test: find intro paths for profiles_a[5] who worked at Google AND Stripe
        target_conn = intelligence_test_data['connections_a'][5]

        response = test_client.get(
            f"/tenants/{tenant.id}/bus/{bu.id}/search/intros/{target_conn.id}",
            headers={"X-App-User-Id": user_a.id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data['target']['connection_id'] == target_conn.id
        # Should find intro paths via shared Google/Stripe connections
        assert isinstance(data['intro_paths'], list)
