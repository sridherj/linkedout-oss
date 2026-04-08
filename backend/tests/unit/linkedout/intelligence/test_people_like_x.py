# SPDX-License-Identifier: Apache-2.0
"""Unit tests for People Like X (find_similar) endpoint."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from linkedout.intelligence.controllers.search_controller import find_similar


@pytest.fixture()
def _mock_db():
    """Patch db_session_manager and embedding provider for all tests."""
    mock_provider = MagicMock()
    mock_provider.model_name.return_value = 'text-embedding-3-small'
    mock_provider.dimension.return_value = 1536
    with patch(
        "linkedout.intelligence.controllers.search_controller.get_embedding_provider",
        return_value=mock_provider,
    ), patch(
        "linkedout.intelligence.controllers.search_controller.get_embedding_column_name",
        return_value="embedding_openai",
    ), patch(
        "linkedout.intelligence.controllers.search_controller.db_session_manager"
    ) as mock_db:
        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)
        yield mock_session


@pytest.mark.asyncio
async def test_returns_404_when_connection_not_found(_mock_db):
    _mock_db.execute.return_value.fetchone.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await find_similar(
            tenant_id="t1", bu_id="b1", connection_id="conn_xxx",
            limit=10, app_user_id="usr_1",
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_rejects_unenriched_profiles(_mock_db):
    # has_enriched_data=False, embedding=None
    _mock_db.execute.return_value.fetchone.return_value = ("cp_1", None, False, "John Doe")

    with pytest.raises(HTTPException) as exc_info:
        await find_similar(
            tenant_id="t1", bu_id="b1", connection_id="conn_xxx",
            limit=10, app_user_id="usr_1",
        )
    assert exc_info.value.status_code == 400
    assert "enriched" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_rejects_enriched_but_no_embedding(_mock_db):
    # has_enriched_data=True but embedding is None
    _mock_db.execute.return_value.fetchone.return_value = ("cp_1", None, True, "John Doe")

    with pytest.raises(HTTPException) as exc_info:
        await find_similar(
            tenant_id="t1", bu_id="b1", connection_id="conn_xxx",
            limit=10, app_user_id="usr_1",
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_returns_similar_profiles_excluding_source(_mock_db):
    embedding = "[0.1,0.2,0.3]"
    # First call: lookup connection
    # Second call: similarity search results
    calls = [
        MagicMock(fetchone=MagicMock(return_value=("cp_1", embedding, True, "Source Person"))),
        MagicMock(fetchall=MagicMock(return_value=[
            ("cp_2", "Alice", "Engineer", "SWE", "Acme", "SF", "US",
             "https://linkedin.com/in/alice", "alice",
             "conn_2", 85.0, "inner_circle", "2024-01-01", True, 0.95),
        ])),
    ]
    _mock_db.execute.side_effect = calls

    results = await find_similar(
        tenant_id="t1", bu_id="b1", connection_id="conn_1",
        limit=10, app_user_id="usr_1",
    )

    assert len(results) == 1
    assert results[0].connection_id == "conn_2"
    assert results[0].similarity_score == 0.95
    assert results[0].full_name == "Alice"


@pytest.mark.asyncio
async def test_similarity_search_uses_rls_session(_mock_db):
    """Verify that search uses get_session with app_user_id (RLS handles scoping)."""
    embedding = "[0.1,0.2]"
    calls = [
        MagicMock(fetchone=MagicMock(return_value=("cp_1", embedding, True, "Source"))),
        MagicMock(fetchall=MagicMock(return_value=[])),
    ]
    _mock_db.execute.side_effect = calls

    results = await find_similar(
        tenant_id="t1", bu_id="b1", connection_id="conn_1",
        limit=10, app_user_id="usr_specific",
    )

    assert results == []
    # The second execute call should NOT include app_user_id (RLS handles scoping)
    second_call_params = _mock_db.execute.call_args_list[1][0][1]
    assert "app_user_id" not in second_call_params
