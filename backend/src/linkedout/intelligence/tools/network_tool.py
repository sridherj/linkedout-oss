# SPDX-License-Identifier: Apache-2.0
"""Network statistics tool for SearchAgent."""
from shared.utilities.langfuse_guard import observe
from sqlalchemy import text
from sqlalchemy.orm import Session

from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="backend")


@observe(name="get_network_stats")
def get_network_stats(session: Session) -> dict:
    """Get summary statistics about the current user's network.

    Helps the LLM calibrate queries by understanding network composition
    before writing complex SQL.

    Args:
        session: RLS-scoped SQLAlchemy session.

    Returns:
        {total_connections, top_industries, top_companies, seniority_distribution,
         top_locations, avg_affinity_score}
    """
    stats: dict = {}

    # Total connections
    result = session.execute(text("SELECT COUNT(*) FROM connection"))
    stats["total_connections"] = result.scalar() or 0

    # Top companies (by current_company_name)
    result = session.execute(text("""
        SELECT cp.current_company_name, COUNT(*) as cnt
        FROM crawled_profile cp
        JOIN connection c ON c.crawled_profile_id = cp.id
        WHERE cp.current_company_name IS NOT NULL
        GROUP BY cp.current_company_name
        ORDER BY cnt DESC
        LIMIT 10
    """))
    stats["top_companies"] = [
        {"name": row[0], "count": row[1]} for row in result.fetchall()
    ]

    # Top industries (from company table)
    result = session.execute(text("""
        SELECT co.industry, COUNT(DISTINCT cp.id) as cnt
        FROM crawled_profile cp
        JOIN connection c ON c.crawled_profile_id = cp.id
        JOIN company co ON co.id = cp.company_id
        WHERE co.industry IS NOT NULL
        GROUP BY co.industry
        ORDER BY cnt DESC
        LIMIT 10
    """))
    stats["top_industries"] = [
        {"industry": row[0], "count": row[1]} for row in result.fetchall()
    ]

    # Seniority distribution
    result = session.execute(text("""
        SELECT cp.seniority_level, COUNT(*) as cnt
        FROM crawled_profile cp
        JOIN connection c ON c.crawled_profile_id = cp.id
        WHERE cp.seniority_level IS NOT NULL
        GROUP BY cp.seniority_level
        ORDER BY cnt DESC
    """))
    stats["seniority_distribution"] = [
        {"level": row[0], "count": row[1]} for row in result.fetchall()
    ]

    # Top locations
    result = session.execute(text("""
        SELECT cp.location_city, cp.location_country, COUNT(*) as cnt
        FROM crawled_profile cp
        JOIN connection c ON c.crawled_profile_id = cp.id
        WHERE cp.location_city IS NOT NULL
        GROUP BY cp.location_city, cp.location_country
        ORDER BY cnt DESC
        LIMIT 10
    """))
    stats["top_locations"] = [
        {"city": row[0], "country": row[1], "count": row[2]} for row in result.fetchall()
    ]

    return stats
