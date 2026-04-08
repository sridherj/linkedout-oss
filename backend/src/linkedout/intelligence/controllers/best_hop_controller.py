# SPDX-License-Identifier: Apache-2.0
"""POST /best-hop SSE streaming endpoint for ranked mutual connection introductions."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from shared.utilities.langfuse_guard import get_client, propagate_attributes

from linkedout.intelligence.contracts import (
    BestHopRequest,
    BestHopResultItem,
    ConversationTurnResponse,
    SearchResultItem,
)
from linkedout.intelligence.controllers._sse_helpers import (
    create_or_resume_session,
    save_session_state,
    sse_line,
    stream_with_heartbeat,
)
from linkedout.intelligence.services.best_hop_service import BestHopDone, BestHopService
from shared.infra.db.db_session_manager import db_session_manager
from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="backend")

best_hop_router = APIRouter(
    prefix="/tenants/{tenant_id}/bus/{bu_id}",
    tags=["best-hop"],
)


@best_hop_router.post("/best-hop")
async def best_hop(
    tenant_id: str,
    bu_id: str,
    request: BestHopRequest,
    app_user_id: str = Header(..., alias="X-App-User-Id"),
):
    """SSE streaming best-hop ranking endpoint."""
    logger.info(
        "best-hop request: target=%s target_url=%s mutual_urls_count=%d app_user=%s mutual_urls=%s",
        request.target_name,
        request.target_url,
        len(request.mutual_urls),
        app_user_id,
        request.mutual_urls[:5],  # first 5 for debugging
    )
    return StreamingResponse(
        stream_with_heartbeat(_stream_best_hop(tenant_id, bu_id, app_user_id, request)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_best_hop(
    tenant_id: str,
    bu_id: str,
    app_user_id: str,
    request: BestHopRequest,
) -> AsyncGenerator[str, None]:
    """Generate SSE events for best-hop ranking."""
    try:
        yield sse_line({"type": "thinking", "message": "Assembling context..."})

        # Create or resume session
        session_id, _ = await asyncio.to_thread(
            create_or_resume_session,
            tenant_id,
            bu_id,
            app_user_id,
            f"Best hop → {request.target_name}",
            request.session_id,
        )
        yield sse_line({"type": "session", "payload": {"session_id": session_id}})

        # Run ranking in a thread (BestHopService is synchronous)
        def _run_ranking():
            langfuse = get_client()
            with langfuse.start_as_current_observation(
                name="best_hop_request",
                metadata={
                    "target_name": request.target_name,
                    "target_url": request.target_url,
                    "mutual_count": len(request.mutual_urls),
                },
            ):
                with propagate_attributes(session_id=session_id):
                    with db_session_manager.get_session(app_user_id=app_user_id) as db:
                        service = BestHopService(db, app_user_id)
                        return list(service.rank(request))

        items = await asyncio.to_thread(_run_ranking)

        # Separate results from the done sentinel
        results: list[BestHopResultItem] = []
        done_info: BestHopDone | None = None
        for item in items:
            if isinstance(item, BestHopDone):
                done_info = item
            else:
                results.append(item)

        yield sse_line({
            "type": "thinking",
            "message": f"Found {done_info.matched if done_info else len(results)} of "
                       f"{(done_info.matched + done_info.unmatched) if done_info else len(results)} "
                       f"mutual connections...",
        })

        # Emit each result
        for result in results:
            yield sse_line({"type": "result", "payload": result.model_dump(mode="json")})

        # Done event
        yield sse_line({
            "type": "done",
            "payload": {
                "total": done_info.total if done_info else len(results),
                "matched": done_info.matched if done_info else len(results),
                "unmatched": done_info.unmatched if done_info else 0,
                "unmatched_urls": done_info.unmatched_urls if done_info else [],
                "session_id": session_id,
            },
        })

        # Persist session state (fire-and-forget)
        asyncio.get_event_loop().run_in_executor(
            None,
            _save_best_hop_session,
            session_id,
            request.target_name,
            results,
        )

    except Exception as e:
        logger.exception("best-hop streaming error")
        yield sse_line({"type": "error", "message": str(e)})


def _save_best_hop_session(
    session_id: str,
    target_name: str,
    results: list[BestHopResultItem],
) -> None:
    """Persist best-hop results as a search turn."""
    search_results = [
        SearchResultItem(
            connection_id=r.connection_id,
            crawled_profile_id=r.crawled_profile_id,
            full_name=r.full_name,
            current_position=r.current_position,
            current_company_name=r.current_company_name,
            affinity_score=r.affinity_score,
            dunbar_tier=r.dunbar_tier,
            linkedin_url=r.linkedin_url,
        )
        for r in results
    ]
    turn_response = ConversationTurnResponse(
        message=f"Ranked {len(results)} mutual connections for intro to {target_name}",
        results=search_results,
    )
    save_session_state(
        session_id=session_id,
        user_query=f"Best hop → {target_name}",
        turn_response=turn_response,
    )
