# SPDX-License-Identifier: Apache-2.0
"""Shared SSE utilities for streaming endpoints (search, best-hop, etc.)."""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from linkedout.intelligence.contracts import ConversationTurnResponse, SearchResultItem
from linkedout.search_session.entities.search_session_entity import SearchSessionEntity
from linkedout.search_session.services.search_session_service import SearchSessionService
from shared.infra.db.db_session_manager import DbSessionType, db_session_manager
from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="backend")

HEARTBEAT_INTERVAL = 15  # seconds


def sse_line(event: dict) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


async def stream_with_heartbeat(
    stream: AsyncGenerator[str, None],
    interval: int = HEARTBEAT_INTERVAL,
) -> AsyncGenerator[str, None]:
    """Wrap any SSE generator with periodic heartbeats to prevent idle timeout.

    Uses asyncio.wait() instead of wait_for() to avoid cancelling the
    underlying generator when the heartbeat timeout fires.
    """
    next_event: asyncio.Task | None = None

    try:
        while True:
            if next_event is None:
                next_event = asyncio.create_task(stream.__anext__())

            done_set, _ = await asyncio.wait({next_event}, timeout=interval)

            if done_set:
                try:
                    event = next_event.result()
                    yield event
                    next_event = None
                except StopAsyncIteration:
                    break
            else:
                yield sse_line({"type": "heartbeat"})
    finally:
        if next_event and not next_event.done():
            next_event.cancel()
        try:
            await stream.aclose()
        except RuntimeError:
            pass  # generator already running/closed during cancellation


def create_or_resume_session(
    tenant_id: str,
    bu_id: str,
    app_user_id: str,
    query: str,
    session_id: str | None,
) -> tuple[str, list[dict] | None]:
    """Create a new SearchSession or resume an existing one.

    Returns (session_id, turn_history).
    Turn history is rebuilt from search_turn rows via ConversationManager.
    """
    from linkedout.search_session.entities.search_turn_entity import SearchTurnEntity

    with db_session_manager.get_session(DbSessionType.WRITE) as db:
        service = SearchSessionService(db)

        if session_id:
            existing = service.get_by_id(session_id)
            if existing:
                turns = (
                    db.query(SearchTurnEntity)
                    .filter(SearchTurnEntity.session_id == session_id)
                    .order_by(SearchTurnEntity.turn_number)
                    .all()
                )
                turn_history = [
                    {
                        "user_query": t.user_query,
                        "transcript": t.transcript.get("messages", []) if t.transcript else [],
                        "summary": t.summary,
                    }
                    for t in turns
                ]
                return existing.id, turn_history if turn_history else None

        entity = SearchSessionEntity(
            tenant_id=tenant_id,
            bu_id=bu_id,
            app_user_id=app_user_id,
            initial_query=query,
            turn_count=0,
            last_active_at=datetime.now(timezone.utc),
        )
        db.add(entity)
        db.flush()
        return entity.id, None


def merge_results_with_explanations(
    results: list[SearchResultItem],
    explanations: dict[str, dict] | None,
) -> list[dict]:
    """Serialize results, merging in explanation data for DB persistence."""
    merged = []
    for r in results:
        d = r.model_dump(mode="json")
        if explanations:
            exp = explanations.get(r.connection_id) or explanations.get(r.crawled_profile_id)
            if exp:
                d["why_this_person"] = exp.get("explanation")
                d["highlighted_attributes"] = exp.get("highlighted_attributes", [])
                d["match_strength"] = exp.get("match_strength")
        merged.append(d)
    return merged


def save_session_state(
    session_id: str,
    user_query: str,
    turn_response: ConversationTurnResponse,
    explanations: dict[str, dict] | None = None,
) -> None:
    """Persist turn data to search_turn and update session turn_count."""
    from linkedout.search_session.entities.search_turn_entity import SearchTurnEntity
    from linkedout.search_session.schemas.search_session_api_schema import UpdateSearchSessionRequestSchema

    with db_session_manager.get_session(DbSessionType.WRITE) as db:
        service = SearchSessionService(db)
        existing = service.get_by_id(session_id)
        if not existing:
            return

        turn_number = (existing.turn_count or 0) + 1

        turn_entity = SearchTurnEntity(
            tenant_id=existing.tenant_id,
            bu_id=existing.bu_id,
            session_id=session_id,
            turn_number=turn_number,
            user_query=user_query,
            transcript={"messages": turn_response.turn_transcript} if turn_response.turn_transcript else None,
            summary=turn_response.message or None,
            results=merge_results_with_explanations(turn_response.results, explanations) if turn_response.results else None,
        )
        db.add(turn_entity)

        req = UpdateSearchSessionRequestSchema(
            tenant_id=existing.tenant_id,
            bu_id=existing.bu_id,
            search_session_id=session_id,
            turn_count=turn_number,
            last_active_at=datetime.now(timezone.utc),
        )
        service.update_entity(req)
