# SPDX-License-Identifier: Apache-2.0
"""Unit tests for Warm Intro Paths (find_intro_paths) endpoint."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from linkedout.intelligence.controllers.search_controller import find_intro_paths


@pytest.fixture()
def _mock_db():
    """Create a mock request with app.state.db_manager for all tests."""
    mock_session = MagicMock()
    mock_db = MagicMock()
    mock_db.get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)

    mock_request = MagicMock()
    mock_request.app.state.db_manager = mock_db
    yield mock_request, mock_session


@pytest.mark.asyncio
async def test_returns_404_when_connection_not_found(_mock_db):
    mock_request, mock_session = _mock_db
    mock_session.execute.return_value.fetchone.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await find_intro_paths(
            request=mock_request,
            tenant_id="t1", bu_id="b1", connection_id="conn_xxx",
            app_user_id="usr_1",
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_finds_shared_company_connections(_mock_db):
    mock_request, mock_session = _mock_db
    calls = [
        # Target lookup
        MagicMock(fetchone=MagicMock(return_value=("cp_target", "Target Person"))),
        # Intro paths
        MagicMock(fetchall=MagicMock(return_value=[
            ("conn_mutual", "Mutual Person", 85.0, "Stripe"),
        ])),
    ]
    mock_session.execute.side_effect = calls

    result = await find_intro_paths(
        request=mock_request,
        tenant_id="t1", bu_id="b1", connection_id="conn_target",
        app_user_id="usr_1",
    )

    assert result.target["name"] == "Target Person"
    assert len(result.intro_paths) == 1
    assert result.intro_paths[0].via["name"] == "Mutual Person"
    assert result.intro_paths[0].shared_context == "Both worked at Stripe"


@pytest.mark.asyncio
async def test_ranks_by_affinity_score(_mock_db):
    mock_request, mock_session = _mock_db
    calls = [
        MagicMock(fetchone=MagicMock(return_value=("cp_target", "Target"))),
        MagicMock(fetchall=MagicMock(return_value=[
            ("conn_1", "High Affinity", 90.0, "Google"),
            ("conn_2", "Low Affinity", 30.0, "Google"),
        ])),
    ]
    mock_session.execute.side_effect = calls

    result = await find_intro_paths(
        request=mock_request,
        tenant_id="t1", bu_id="b1", connection_id="conn_target",
        app_user_id="usr_1",
    )

    assert len(result.intro_paths) == 2
    # First result should have higher affinity (ordering done in SQL)
    assert result.intro_paths[0].via["affinity_score"] == 90.0
    assert result.intro_paths[1].via["affinity_score"] == 30.0


@pytest.mark.asyncio
async def test_correct_strength_labels(_mock_db):
    mock_request, mock_session = _mock_db
    calls = [
        MagicMock(fetchone=MagicMock(return_value=("cp_target", "Target"))),
        MagicMock(fetchall=MagicMock(return_value=[
            ("conn_1", "Strong", 75.0, "Co1"),
            ("conn_2", "Moderate", 50.0, "Co2"),
            ("conn_3", "Weak", 20.0, "Co3"),
        ])),
    ]
    mock_session.execute.side_effect = calls

    result = await find_intro_paths(
        request=mock_request,
        tenant_id="t1", bu_id="b1", connection_id="conn_target",
        app_user_id="usr_1",
    )

    assert result.intro_paths[0].strength == "strong"
    assert result.intro_paths[1].strength == "moderate"
    assert result.intro_paths[2].strength == "weak"


@pytest.mark.asyncio
async def test_empty_intro_paths_when_no_experience(_mock_db):
    mock_request, mock_session = _mock_db
    calls = [
        MagicMock(fetchone=MagicMock(return_value=("cp_target", "Target"))),
        MagicMock(fetchall=MagicMock(return_value=[])),
    ]
    mock_session.execute.side_effect = calls

    result = await find_intro_paths(
        request=mock_request,
        tenant_id="t1", bu_id="b1", connection_id="conn_target",
        app_user_id="usr_1",
    )

    assert result.target["connection_id"] == "conn_target"
    assert result.intro_paths == []


@pytest.mark.asyncio
async def test_null_affinity_score_maps_to_weak(_mock_db):
    mock_request, mock_session = _mock_db
    calls = [
        MagicMock(fetchone=MagicMock(return_value=("cp_target", "Target"))),
        MagicMock(fetchall=MagicMock(return_value=[
            ("conn_1", "No Score", None, "SomeCorp"),
        ])),
    ]
    mock_session.execute.side_effect = calls

    result = await find_intro_paths(
        request=mock_request,
        tenant_id="t1", bu_id="b1", connection_id="conn_target",
        app_user_id="usr_1",
    )

    assert result.intro_paths[0].strength == "weak"
