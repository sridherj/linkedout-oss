# SPDX-License-Identifier: Apache-2.0
"""SSE streaming search endpoint for LinkedIn network intelligence."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from shared.utilities.langfuse_guard import get_client
from sqlalchemy import text

from linkedout.intelligence.contracts import (
    ConversationTurnResponse,
    IntroPath,
    IntroPathsResponse,
    ProfileDetailResponse,
    SearchRequest,
    SearchResultItem,
)
from linkedout.intelligence.controllers._sse_helpers import (
    create_or_resume_session,
    save_session_state,
    sse_line,
    stream_with_heartbeat,
)
from linkedout.intelligence.explainer.why_this_person import BATCH_SIZE, WhyThisPersonExplainer
from shared.infra.db.db_session_manager import DbSessionManager
from shared.utilities.logger import get_logger
from utilities.llm_manager.embedding_factory import get_embedding_column_name, get_embedding_provider

logger = get_logger(__name__, component="backend")

search_router = APIRouter(
    prefix="/tenants/{tenant_id}/bus/{bu_id}",
    tags=["search"],
)


def _strength_label(affinity_score: float | None) -> str:
    if affinity_score is None:
        return "weak"
    if affinity_score >= 70:
        return "strong"
    if affinity_score >= 40:
        return "moderate"
    return "weak"


# ---------------------------------------------------------------------------
# People Like X — pure vector similarity (no LLM)
# ---------------------------------------------------------------------------

def _get_similar_sql(embedding_column: str) -> str:
    """Build similar-profile SQL for the given embedding column.

    The column name is one of two known values (``embedding_openai`` or
    ``embedding_nomic``), determined from application config — NOT from user
    input — so string formatting is safe here.
    """
    return f"""
SELECT cp.id, cp.full_name, cp.headline, cp.current_position,
       cp.current_company_name, cp.location_city, cp.location_country,
       cp.linkedin_url, cp.public_identifier,
       c.id as connection_id, c.affinity_score, c.dunbar_tier, c.connected_at,
       cp.has_enriched_data,
       1 - (cp.{embedding_column} <=> CAST(:target_embedding AS vector)) AS similarity
FROM crawled_profile cp
JOIN connection c ON c.crawled_profile_id = cp.id
WHERE cp.id != :source_profile_id
  AND cp.{embedding_column} IS NOT NULL
ORDER BY cp.{embedding_column} <=> CAST(:target_embedding AS vector)
LIMIT :limit
"""


@search_router.post("/search/similar/{connection_id}")
async def find_similar(
    request: Request,
    tenant_id: str,
    bu_id: str,
    connection_id: str,
    limit: int = Query(default=10, le=50),
    app_user_id: str = Header(..., alias="X-App-User-Id"),
) -> list[SearchResultItem]:
    """Find people similar to a given connection."""
    db_manager = request.app.state.db_manager

    def _run() -> list[SearchResultItem]:
        provider = get_embedding_provider()
        col = get_embedding_column_name(provider)
        with db_manager.get_session(app_user_id=app_user_id) as session:
            # Look up the connection and its profile (RLS scopes to this user)
            # col is one of two known values from application config, not user input
            row = session.execute(
                text(
                    f"SELECT c.crawled_profile_id, cp.{col}, cp.has_enriched_data, cp.full_name "
                    "FROM connection c "
                    "JOIN crawled_profile cp ON cp.id = c.crawled_profile_id "
                    "WHERE c.id = :conn_id"
                ),
                {"conn_id": connection_id},
            ).fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Connection not found")

            profile_id, embedding, has_enriched, full_name = row

            if not has_enriched or not embedding:
                raise HTTPException(
                    status_code=400,
                    detail="Profile must be enriched for similarity search",
                )

            results = session.execute(
                text(_get_similar_sql(col)),
                {
                    "target_embedding": embedding,
                    "source_profile_id": profile_id,
                    "limit": limit,
                },
            ).fetchall()

            columns = [
                "crawled_profile_id", "full_name", "headline", "current_position",
                "current_company_name", "location_city", "location_country",
                "linkedin_url", "public_identifier",
                "connection_id", "affinity_score", "dunbar_tier", "connected_at",
                "has_enriched_data", "similarity_score",
            ]
            return [
                SearchResultItem(**dict(zip(columns, r)))
                for r in results
            ]

    return await asyncio.to_thread(_run)


# ---------------------------------------------------------------------------
# Warm Intro Paths — shared-company connections
# ---------------------------------------------------------------------------

_INTRO_SQL = """
SELECT DISTINCT c2.id AS connection_id, cp2.full_name, c2.affinity_score,
       e1.company_name AS shared_company
FROM experience e1
JOIN experience e2 ON e1.company_id = e2.company_id
     AND e1.crawled_profile_id != e2.crawled_profile_id
JOIN connection c2 ON c2.crawled_profile_id = e2.crawled_profile_id
JOIN crawled_profile cp2 ON cp2.id = c2.crawled_profile_id
WHERE e1.crawled_profile_id = :target_profile_id
  AND e1.company_id IS NOT NULL
ORDER BY c2.affinity_score DESC NULLS LAST
LIMIT 5
"""


@search_router.get("/search/intros/{connection_id}")
async def find_intro_paths(
    request: Request,
    tenant_id: str,
    bu_id: str,
    connection_id: str,
    app_user_id: str = Header(..., alias="X-App-User-Id"),
) -> IntroPathsResponse:
    """Find mutual connections who could introduce you to target."""
    db_manager = request.app.state.db_manager

    def _run() -> IntroPathsResponse:
        with db_manager.get_session(app_user_id=app_user_id) as session:
            # Look up target connection (RLS scopes to this user)
            target = session.execute(
                text(
                    "SELECT c.crawled_profile_id, cp.full_name "
                    "FROM connection c "
                    "JOIN crawled_profile cp ON cp.id = c.crawled_profile_id "
                    "WHERE c.id = :conn_id"
                ),
                {"conn_id": connection_id},
            ).fetchone()

            if not target:
                raise HTTPException(status_code=404, detail="Connection not found")

            target_profile_id, target_name = target

            rows = session.execute(
                text(_INTRO_SQL),
                {
                    "target_profile_id": target_profile_id,
                },
            ).fetchall()

            intro_paths = [
                IntroPath(
                    via={
                        "connection_id": r[0],
                        "name": r[1],
                        "affinity_score": r[2],
                    },
                    shared_context=f"Both worked at {r[3]}",
                    strength=_strength_label(r[2]),
                )
                for r in rows
            ]

            return IntroPathsResponse(
                target={"connection_id": connection_id, "name": target_name},
                intro_paths=intro_paths,
            )

    return await asyncio.to_thread(_run)


# ---------------------------------------------------------------------------
# Profile Detail — slide-over panel data
# ---------------------------------------------------------------------------

@search_router.get("/search/profile/{connection_id}")
async def get_profile(
    request: Request,
    tenant_id: str,
    bu_id: str,
    connection_id: str,
    app_user_id: str = Header(..., alias="X-App-User-Id"),
    query: str = Query(default="", description="Current search query for skill relevance highlighting"),
) -> ProfileDetailResponse:
    """Get full profile detail for the slide-over panel (all 4 tabs)."""
    from linkedout.intelligence.tools.profile_tool import get_profile_detail
    db_manager = request.app.state.db_manager

    def _run() -> ProfileDetailResponse:
        with db_manager.get_session(app_user_id=app_user_id) as session:
            data = get_profile_detail(
                connection_id=connection_id,
                session=session,
                query=query or None,
            )
            if "error" in data:
                raise HTTPException(status_code=404, detail=data["error"])
            return ProfileDetailResponse(**data)

    return await asyncio.to_thread(_run)


# ---------------------------------------------------------------------------
# SSE Streaming Search (existing) + Search History Integration
# ---------------------------------------------------------------------------

async def _stream_search(
    db_manager: DbSessionManager,
    tenant_id: str,
    bu_id: str,
    app_user_id: str,
    request: SearchRequest,
    explain: bool,
) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE events from SearchAgent."""
    yield sse_line({"type": "thinking", "message": "Starting search..."})

    try:
        from linkedout.intelligence.agents.search_agent import SearchAgent

        # Create or resume session
        search_session_id, turn_history = await asyncio.to_thread(
            create_or_resume_session,
            db_manager, tenant_id, bu_id, app_user_id, request.query, request.session_id,
        )

        yield sse_line({"type": "session", "payload": {"session_id": search_session_id}})

        def _run_agent() -> ConversationTurnResponse:
            """Run SearchAgent.run_turn() in a thread (sync DB + LLM calls)."""
            langfuse = get_client()
            with langfuse.start_as_current_observation(
                name="search_request",
                metadata={"session_id": search_session_id, "query": request.query},
            ):
                with db_manager.get_session(app_user_id=app_user_id) as session:
                    agent = SearchAgent(
                        session=session,
                        app_user_id=app_user_id,
                        session_id=search_session_id,
                        tenant_id=tenant_id,
                        bu_id=bu_id,
                    )
                    return agent.run_turn(
                        query=request.query,
                        turn_history=turn_history,
                    )

        turn_response = await asyncio.to_thread(_run_agent)
        results = turn_response.results
        all_explanations: dict[str, dict] = {}
        logger.info(f"Agent returned {len(results)} results")

        # Stream individual results
        for item in results:
            yield sse_line({
                "type": "result",
                "payload": item.model_dump(mode="json"),
            })

        # Run explainer if enabled and there are results
        if explain and results:
            yield sse_line({"type": "thinking", "message": "Generating explanations..."})

            explainer = WhyThisPersonExplainer()

            # Phase 1: Enrichment fetch (needs DB session, one call)
            def _prep():
                with db_manager.get_session(app_user_id=app_user_id) as session:
                    return explainer.prepare_enrichment(results, session)

            enrichment_map = await asyncio.to_thread(_prep)
            if not enrichment_map:
                logger.warning("Enrichment fetch failed — skipping explanations")
            else:
                # Phase 2: Stream each batch (LLM only, no DB needed)
                for i in range(0, len(results), BATCH_SIZE):
                    batch = results[i:i + BATCH_SIZE]
                    batch_result = await asyncio.to_thread(
                        explainer.explain_batch, request.query, batch, enrichment_map
                    )
                    if batch_result:
                        payload = {cid: exp.model_dump() for cid, exp in batch_result.items()}
                        all_explanations.update(payload)
                        logger.info(f"Streaming {len(payload)} explanations (batch {i // BATCH_SIZE + 1})")
                        yield sse_line({"type": "explanations", "payload": payload})

        # Conversation state event — structured metadata for frontend
        yield sse_line({
            "type": "conversation_state",
            "payload": {
                "result_summary_chips": [c.model_dump() for c in turn_response.result_summary_chips],
                "suggested_actions": [a.model_dump() for a in turn_response.suggested_actions],
                "result_metadata": turn_response.result_metadata.model_dump(),
                "facets": [fg.model_dump() for fg in turn_response.facets],
            },
        })

        # Done event
        yield sse_line({
            "type": "done",
            "payload": {
                "total": len(results),
                "query_type": turn_response.query_type,
                "answer": turn_response.message,
                "session_id": search_session_id,
            },
        })

        # Persist session state (fire-and-forget)
        try:
            await asyncio.to_thread(
                save_session_state,
                db_manager,
                search_session_id,
                request.query,
                turn_response,
                all_explanations,
            )
        except Exception:
            logger.warning("Failed to persist session state", exc_info=True)


    except Exception as e:
        logger.exception(f"Search stream error: {e}")
        yield sse_line({"type": "error", "message": str(e)})



@search_router.post("/search")
async def search(
    http_request: Request,
    tenant_id: str,
    bu_id: str,
    request: SearchRequest,
    app_user_id: str = Header(..., alias="X-App-User-Id"),
    explain: bool = Query(default=True, description="Include 'Why This Person' explanations"),
):
    """SSE streaming search endpoint."""
    db_manager = http_request.app.state.db_manager
    return StreamingResponse(
        stream_with_heartbeat(_stream_search(db_manager, tenant_id, bu_id, app_user_id, request, explain)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
