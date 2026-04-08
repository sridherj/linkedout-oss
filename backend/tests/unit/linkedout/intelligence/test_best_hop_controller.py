# SPDX-License-Identifier: Apache-2.0
"""Unit tests for best_hop_controller -- SSE stream, event sequence, errors."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from linkedout.intelligence.contracts import BestHopRequest, BestHopResultItem
from linkedout.intelligence.services.best_hop_service import BestHopDone


# ── Helpers ──────────────────────────────────────────────────────────────


def _parse_sse_events(raw_lines: list[str]) -> list[dict]:
    """Parse SSE lines into event dicts."""
    events = []
    for line in raw_lines:
        line = line.strip()
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def _make_result_item(rank: int, profile_id: str) -> BestHopResultItem:
    return BestHopResultItem(
        rank=rank,
        connection_id=f"conn_{profile_id}",
        crawled_profile_id=profile_id,
        full_name=f"Person {rank}",
        current_position="Engineer",
        current_company_name="Acme",
        affinity_score=80.0 - rank * 10,
        dunbar_tier="active",
        linkedin_url=f"https://linkedin.com/in/{profile_id}",
        why_this_person=f"Reason for rank {rank}",
    )


def _make_done(total: int = 3, matched: int = 3, unmatched: int = 2) -> BestHopDone:
    return BestHopDone(
        total=total,
        matched=matched,
        unmatched=unmatched,
        unmatched_urls=["https://linkedin.com/in/unk1", "https://linkedin.com/in/unk2"][:unmatched],
    )


def _make_request() -> BestHopRequest:
    return BestHopRequest(
        target_name="Jane Target",
        target_url="https://linkedin.com/in/janetarget",
        mutual_urls=["https://linkedin.com/in/m1", "https://linkedin.com/in/m2"],
    )


# ── Tests ────────────────────────────────────────────────────────────────


class TestBestHopController:
    @pytest.mark.asyncio
    @patch("linkedout.intelligence.controllers.best_hop_controller.save_session_state")
    @patch("linkedout.intelligence.controllers.best_hop_controller.create_or_resume_session")
    @patch("linkedout.intelligence.controllers.best_hop_controller.db_session_manager")
    @patch("linkedout.intelligence.controllers.best_hop_controller.BestHopService")
    async def test_returns_sse_stream(
        self, mock_service_cls, mock_db, mock_create_session, mock_save,
    ):
        """Verify response is text/event-stream with correct SSE format."""
        from linkedout.intelligence.controllers.best_hop_controller import _stream_best_hop

        mock_create_session.return_value = ("sess_001", None)

        items = [_make_result_item(1, "cp_1"), _make_done(1, 1, 0)]
        mock_service = MagicMock()
        mock_service.rank.return_value = items
        mock_service_cls.return_value = mock_service

        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)

        request = _make_request()
        sse_lines = []
        async for line in _stream_best_hop("t1", "bu1", "usr_001", request):
            sse_lines.append(line)

        events = _parse_sse_events(sse_lines)
        # Every line should be valid SSE format
        for line in sse_lines:
            assert line.startswith("data: "), f"Not valid SSE: {line}"
            assert line.endswith("\n\n"), f"Missing double newline: {line}"

    @pytest.mark.asyncio
    @patch("linkedout.intelligence.controllers.best_hop_controller.save_session_state")
    @patch("linkedout.intelligence.controllers.best_hop_controller.create_or_resume_session")
    @patch("linkedout.intelligence.controllers.best_hop_controller.db_session_manager")
    @patch("linkedout.intelligence.controllers.best_hop_controller.BestHopService")
    async def test_event_sequence(
        self, mock_service_cls, mock_db, mock_create_session, mock_save,
    ):
        """Mock service yielding 3 results. Verify SSE events: thinking, session, thinking, result x3, done."""
        from linkedout.intelligence.controllers.best_hop_controller import _stream_best_hop

        mock_create_session.return_value = ("sess_001", None)

        items = [
            _make_result_item(1, "cp_1"),
            _make_result_item(2, "cp_2"),
            _make_result_item(3, "cp_3"),
            _make_done(3, 3, 2),
        ]
        mock_service = MagicMock()
        mock_service.rank.return_value = items
        mock_service_cls.return_value = mock_service

        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)

        request = _make_request()
        sse_lines = []
        async for line in _stream_best_hop("t1", "bu1", "usr_001", request):
            sse_lines.append(line)

        events = _parse_sse_events(sse_lines)
        event_types = [e["type"] for e in events]

        # Expected order: thinking, session, thinking (found N of M), result x3, done
        assert event_types[0] == "thinking"
        assert event_types[1] == "session"
        assert events[1]["payload"]["session_id"] == "sess_001"
        assert event_types[2] == "thinking"
        assert "3 of 5" in events[2]["message"]
        assert event_types[3:6] == ["result", "result", "result"]
        assert event_types[6] == "done"

        # Done payload should have matched/unmatched counts
        done_payload = events[6]["payload"]
        assert done_payload["matched"] == 3
        assert done_payload["unmatched"] == 2
        assert done_payload["session_id"] == "sess_001"

    @pytest.mark.asyncio
    @patch("linkedout.intelligence.controllers.best_hop_controller.save_session_state")
    @patch("linkedout.intelligence.controllers.best_hop_controller.create_or_resume_session")
    @patch("linkedout.intelligence.controllers.best_hop_controller.db_session_manager")
    @patch("linkedout.intelligence.controllers.best_hop_controller.BestHopService")
    async def test_error_yields_error_event(
        self, mock_service_cls, mock_db, mock_create_session, mock_save,
    ):
        """Service raises exception → SSE error event emitted."""
        from linkedout.intelligence.controllers.best_hop_controller import _stream_best_hop

        mock_create_session.return_value = ("sess_001", None)

        # Service.rank raises
        mock_service = MagicMock()
        mock_service.rank.side_effect = ValueError("Target not found in DB")
        mock_service_cls.return_value = mock_service

        mock_session = MagicMock()
        mock_db.get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.get_session.return_value.__exit__ = MagicMock(return_value=False)

        request = _make_request()
        sse_lines = []
        async for line in _stream_best_hop("t1", "bu1", "usr_001", request):
            sse_lines.append(line)

        events = _parse_sse_events(sse_lines)
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) >= 1
        assert "Target not found" in error_events[0]["message"]


class TestBestHopEndpoint:
    def test_requires_app_user_id_header(self):
        """Missing X-App-User-Id header → 422."""
        from fastapi.testclient import TestClient
        from linkedout.intelligence.controllers.best_hop_controller import best_hop_router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(best_hop_router)

        with TestClient(app) as client:
            response = client.post(
                "/tenants/t1/bus/bu1/best-hop",
                json={
                    "target_name": "Jane",
                    "target_url": "https://linkedin.com/in/jane",
                    "mutual_urls": [],
                },
                # No X-App-User-Id header
            )
            assert response.status_code == 422
