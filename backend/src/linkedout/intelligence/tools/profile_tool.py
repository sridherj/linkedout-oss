# SPDX-License-Identifier: Apache-2.0
"""Profile detail and enrichment tools for SearchAgent."""
from __future__ import annotations

from datetime import date

from shared.utilities.langfuse_guard import observe
from sqlalchemy import text
from sqlalchemy.orm import Session

from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="backend")

# Dunbar tier descriptions for the Affinity tab
_TIER_DESCRIPTIONS = {
    "inner_circle": "Top 15 — your closest professional contacts",
    "active": "Top 50 — people you actively engage with",
    "familiar": "Top 150 — people you'd recognize and greet",
    "acquaintance": "Beyond 150 — wider network connections",
}


@observe(name="get_profile_detail")
def get_profile_detail(connection_id: str, session: Session, query: str | None = None) -> dict:
    """Get comprehensive profile detail for the slide-over panel.

    Returns all data needed by the 4 panel tabs:
    Overview, Experience, Affinity, and Ask.

    Args:
        connection_id: The connection ID to look up.
        session: RLS-scoped SQLAlchemy session.
        query: The current search query (used for skill relevance highlighting).

    Returns:
        Dict with profile identity, experiences, education, skills,
        affinity breakdown, connection metadata, and suggested questions.
    """
    if not connection_id or not connection_id.strip():
        return {"error": "connection_id is required"}

    # 1. Core profile + connection data
    row = session.execute(
        text("""
            SELECT c.id AS connection_id, cp.id AS crawled_profile_id,
                   cp.full_name, cp.headline, cp.current_position, cp.current_company_name,
                   cp.location_city, cp.location_country, cp.linkedin_url,
                   cp.profile_image_url, cp.has_enriched_data, cp.about,
                   c.connected_at, c.tags, c.sources,
                   c.affinity_score, c.dunbar_tier,
                   c.affinity_recency, c.affinity_career_overlap,
                   c.affinity_mutual_connections, c.affinity_external_contact,
                   c.affinity_embedding_similarity
            FROM connection c
            JOIN crawled_profile cp ON cp.id = c.crawled_profile_id
            WHERE c.id = :conn_id
        """),
        {"conn_id": connection_id},
    ).fetchone()

    if not row:
        return {"error": f"Connection {connection_id} not found"}

    profile_id = row.crawled_profile_id

    # Build location string
    location_parts = [p for p in [row.location_city, row.location_country] if p]
    location = ", ".join(location_parts) if location_parts else None

    result = {
        "connection_id": row.connection_id,
        "crawled_profile_id": profile_id,
        "full_name": row.full_name,
        "headline": row.headline,
        "current_position": row.current_position,
        "current_company_name": row.current_company_name,
        "location": location,
        "linkedin_url": row.linkedin_url,
        "profile_image_url": row.profile_image_url,
        "has_enriched_data": row.has_enriched_data,
        "about": row.about,
        "connected_at": str(row.connected_at) if row.connected_at else None,
        "connection_source": row.sources[0] if row.sources else None,
        "tags": [t.strip() for t in row.tags.split(",")] if row.tags else [],
    }

    # 2. Affinity breakdown
    result["affinity"] = {
        "score": row.affinity_score,
        "tier": row.dunbar_tier,
        "tier_description": _TIER_DESCRIPTIONS.get(row.dunbar_tier, ""),
        "sub_scores": [
            {"name": "recency", "value": row.affinity_recency or 0, "max_value": 100},
            {"name": "career_overlap", "value": row.affinity_career_overlap or 0, "max_value": 100},
            {"name": "mutual_connections", "value": row.affinity_mutual_connections or 0, "max_value": 100},
            {"name": "external_contact", "value": row.affinity_external_contact or 0, "max_value": 100},
            {"name": "embedding_similarity", "value": row.affinity_embedding_similarity or 0, "max_value": 100},
        ],
    }

    # 3. Full experience timeline (no truncation)
    exp_rows = session.execute(
        text("""
            SELECT e.position, e.company_name, e.start_date, e.end_date, e.is_current,
                   co.industry, co.size_tier
            FROM experience e
            LEFT JOIN company co ON co.id = e.company_id
            WHERE e.crawled_profile_id = :profile_id
            ORDER BY e.start_date DESC NULLS FIRST
        """),
        {"profile_id": profile_id},
    ).fetchall()

    today = date.today()
    experiences = []
    for exp in exp_rows:
        duration_months = None
        if exp.start_date:
            end = exp.end_date if exp.end_date else (today if exp.is_current else None)
            if end:
                duration_months = (end.year - exp.start_date.year) * 12 + (end.month - exp.start_date.month)

        experiences.append({
            "role": exp.position or "Unknown Role",
            "company": exp.company_name or "Unknown Company",
            "start_date": str(exp.start_date) if exp.start_date else None,
            "end_date": str(exp.end_date) if exp.end_date else None,
            "duration_months": duration_months,
            "is_current": bool(exp.is_current),
            "company_industry": exp.industry,
            "company_size_tier": exp.size_tier,
        })
    result["experiences"] = experiences

    # 4. Education
    edu_rows = session.execute(
        text("""
            SELECT school_name, degree, field_of_study, start_year, end_year
            FROM education
            WHERE crawled_profile_id = :profile_id
            ORDER BY end_year DESC NULLS FIRST
        """),
        {"profile_id": profile_id},
    ).fetchall()

    result["education"] = [
        {
            "school": edu.school_name or "Unknown School",
            "degree": edu.degree,
            "field_of_study": edu.field_of_study,
            "start_year": edu.start_year,
            "end_year": edu.end_year,
        }
        for edu in edu_rows
    ]

    # 5. Skills with query-relevance highlighting
    skill_rows = session.execute(
        text("""
            SELECT skill_name
            FROM profile_skill
            WHERE crawled_profile_id = :profile_id
            ORDER BY skill_name
        """),
        {"profile_id": profile_id},
    ).fetchall()

    query_lower = (query or "").lower()
    query_terms = query_lower.split() if query_lower else []
    result["skills"] = [
        {
            "name": s.skill_name,
            "is_featured": any(term in s.skill_name.lower() for term in query_terms) if query_terms else False,
        }
        for s in skill_rows
    ]

    return result


@observe(name="request_enrichment")
def request_enrichment(connection_id: str, session: Session) -> dict:
    """Request external enrichment for a profile.

    This tool does NOT auto-trigger enrichment. It checks the profile state
    and returns a confirmation prompt that the LLM must relay to the user.
    Actual enrichment only proceeds after explicit user confirmation.

    Args:
        connection_id: The connection ID to enrich.
        session: RLS-scoped SQLAlchemy session.

    Returns:
        Dict with profile status and confirmation message for the user.
    """
    if not connection_id or not connection_id.strip():
        return {"error": "connection_id is required"}

    row = session.execute(
        text("""
            SELECT c.id, cp.full_name, cp.has_enriched_data, cp.linkedin_url,
                   cp.last_crawled_at
            FROM connection c
            JOIN crawled_profile cp ON cp.id = c.crawled_profile_id
            WHERE c.id = :conn_id
        """),
        {"conn_id": connection_id},
    ).fetchone()

    if not row:
        return {"error": f"Connection {connection_id} not found"}

    if row.has_enriched_data:
        last_crawled = str(row.last_crawled_at) if row.last_crawled_at else "unknown"
        return {
            "status": "already_enriched",
            "full_name": row.full_name,
            "last_crawled_at": last_crawled,
            "message": (
                f"{row.full_name}'s profile is already enriched (last updated: {last_crawled}). "
                "Would you like to re-crawl for the latest data? This will make an external API call."
            ),
            "requires_user_confirmation": True,
        }

    return {
        "status": "not_enriched",
        "full_name": row.full_name,
        "linkedin_url": row.linkedin_url,
        "message": (
            f"{row.full_name}'s profile has only basic data (name, title, company). "
            "Enriching will fetch their full experience history, education, skills, and about section "
            "via an external API call. Shall I proceed?"
        ),
        "requires_user_confirmation": True,
    }
