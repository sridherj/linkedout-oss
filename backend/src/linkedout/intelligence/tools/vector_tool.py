# SPDX-License-Identifier: Apache-2.0
"""Vector semantic search tool for SearchAgent — user-scoped pgvector queries."""
from shared.utilities.langfuse_guard import observe
from sqlalchemy import text
from sqlalchemy.orm import Session

from shared.utilities.logger import get_logger
from utilities.llm_manager.embedding_factory import get_embedding_provider
from utilities.llm_manager.embedding_provider import EmbeddingProvider

logger = get_logger(__name__, component="backend")


def _get_embedding_column() -> str:
    """Determine which embedding column to query based on configured provider."""
    from shared.config.config import backend_config

    provider = backend_config.embedding.provider
    if provider == 'local':
        return 'embedding_nomic'
    return 'embedding_openai'


def _get_search_sql(embedding_column: str) -> str:
    """Build the semantic search SQL for the given embedding column.

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
           1 - (cp.{embedding_column} <=> CAST(:query_embedding AS vector)) AS similarity
    FROM crawled_profile cp
    JOIN connection c ON c.crawled_profile_id = cp.id
    WHERE cp.{embedding_column} IS NOT NULL
      AND 1 - (cp.{embedding_column} <=> CAST(:query_embedding AS vector)) > 0.25
    ORDER BY cp.{embedding_column} <=> CAST(:query_embedding AS vector)
    LIMIT :limit
    """

_RESULT_COLUMNS = [
    'id', 'full_name', 'headline', 'current_position',
    'current_company_name', 'location_city', 'location_country',
    'linkedin_url', 'public_identifier',
    'connection_id', 'affinity_score', 'dunbar_tier', 'connected_at',
    'has_enriched_data', 'similarity',
]


@observe(name="vector_search")
def search_profiles(
    query: str,
    session: Session,
    limit: int = 20,
    embedding_provider: EmbeddingProvider | None = None,
) -> list[dict]:
    """Semantic search over user's network. Returns ranked results with similarity scores.

    The session must already have app.current_user_id set (via
    ``get_session(app_user_id=...)``). RLS policies enforce tenant
    isolation at the database level.

    Args:
        query: Natural language search query.
        session: RLS-scoped SQLAlchemy session.
        limit: Maximum number of results to return.
        embedding_provider: Optional pre-configured provider; creates one from config if not provided.

    Returns:
        List of dicts with profile data and similarity score, ordered by relevance.
    """
    provider = embedding_provider or get_embedding_provider()
    query_embedding = provider.embed_single(query)

    # Format as pgvector literal
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    embedding_column = _get_embedding_column()
    search_sql = _get_search_sql(embedding_column)

    result = session.execute(
        text(search_sql),
        {
            "query_embedding": embedding_str,
            "limit": limit,
        },
    )

    rows = result.fetchall()
    return [dict(zip(_RESULT_COLUMNS, row)) for row in rows]
