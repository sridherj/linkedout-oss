# SPDX-License-Identifier: Apache-2.0
"""Introduction path finder tool for SearchAgent."""
from shared.utilities.langfuse_guard import observe
from sqlalchemy import text
from sqlalchemy.orm import Session

from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="backend")


@observe(name="find_intro_paths")
def find_intro_paths(target: str, session: Session) -> dict:
    """Find introduction paths to a target company or person.

    Returns ranked paths:
    - Tier 1: Direct connections currently at the target company
    - Tier 2: Alumni (people who previously worked at target)
    - Tier 3: Headline mentions (people mentioning target in headline but not employed there)
    - Tier 4: Shared-company warm paths (connections who worked at same prior companies as target employees)
    - Tier 5: Investor connections (connections at firms that invested in target company)

    Args:
        target: Company name or person name to find paths to.
        session: RLS-scoped SQLAlchemy session.

    Returns:
        {target, paths: [{tier, path_type, intermediary, current_role, affinity_score}]}
    """
    if not target or not target.strip():
        return {"error": "target is required", "suggestion": "Provide a company or person name"}

    target_name = target.strip()
    paths = []

    # Tier 1: Direct connections currently at the target company
    tier1 = session.execute(
        text("""
            SELECT cp.id, cp.full_name, cp.current_position, cp.current_company_name,
                   c.affinity_score, c.dunbar_tier
            FROM crawled_profile cp
            JOIN connection c ON c.crawled_profile_id = cp.id
            WHERE (cp.current_company_name ILIKE :pattern
                   OR cp.company_id IN (
                       SELECT id FROM company WHERE canonical_name ILIKE :pattern
                   ))
              AND c.affinity_score IS NOT NULL
            ORDER BY c.affinity_score DESC NULLS LAST
            LIMIT 10
        """),
        {"pattern": f"%{target_name}%"},
    )
    for row in tier1.fetchall():
        paths.append({
            "tier": 1,
            "path_type": "direct",
            "profile_id": row[0],
            "intermediary": row[1],
            "current_role": row[2],
            "company": row[3],
            "affinity_score": row[4],
            "dunbar_tier": row[5],
        })

    # Tier 2: Alumni — people who previously worked at the target
    tier2 = session.execute(
        text("""
            SELECT cp.id, cp.full_name, cp.current_position, cp.current_company_name,
                   e.position AS past_role, e.company_name AS past_company,
                   c.affinity_score, c.dunbar_tier
            FROM experience e
            JOIN crawled_profile cp ON cp.id = e.crawled_profile_id
            JOIN connection c ON c.crawled_profile_id = cp.id
            WHERE (e.company_name ILIKE :pattern
                   OR e.company_id IN (
                       SELECT id FROM company WHERE canonical_name ILIKE :pattern
                   ))
              AND (e.is_current IS NULL OR e.is_current = FALSE)
              AND cp.current_company_name NOT ILIKE :pattern
            ORDER BY c.affinity_score DESC NULLS LAST
            LIMIT 10
        """),
        {"pattern": f"%{target_name}%"},
    )
    for row in tier2.fetchall():
        paths.append({
            "tier": 2,
            "path_type": "alumni",
            "profile_id": row[0],
            "intermediary": row[1],
            "current_role": row[2],
            "current_company": row[3],
            "past_role": row[4],
            "past_company": row[5],
            "affinity_score": row[6],
            "dunbar_tier": row[7],
        })

    # Tier 3: Headline mentions — people mentioning target in headline but not employed there
    tier3 = session.execute(
        text("""
            SELECT cp.id, cp.full_name, cp.headline, cp.current_position, cp.current_company_name,
                   c.affinity_score, c.dunbar_tier
            FROM crawled_profile cp
            JOIN connection c ON c.crawled_profile_id = cp.id
            WHERE cp.headline ILIKE :pattern
              AND (cp.current_company_name NOT ILIKE :pattern OR cp.current_company_name IS NULL)
            ORDER BY c.affinity_score DESC NULLS LAST
            LIMIT 10
        """),
        {"pattern": f"%{target_name}%"},
    )
    for row in tier3.fetchall():
        paths.append({
            "tier": 3,
            "path_type": "headline_mention",
            "profile_id": row[0],
            "intermediary": row[1],
            "headline": row[2],
            "current_role": row[3],
            "company": row[4],
            "affinity_score": row[5],
            "dunbar_tier": row[6],
        })

    # Tier 4: Shared-company warm paths — connections who worked at same prior companies as target employees
    tier4 = session.execute(
        text("""
            SELECT DISTINCT cp2.id, cp2.full_name, cp2.current_position, cp2.current_company_name,
                   c2.affinity_score, c2.dunbar_tier,
                   e1.company_name AS shared_company, cp1.full_name AS target_person
            FROM crawled_profile cp1
            JOIN connection c1 ON c1.crawled_profile_id = cp1.id
            JOIN experience e1 ON e1.crawled_profile_id = cp1.id AND e1.company_id IS NOT NULL
            JOIN experience e2 ON e2.company_id = e1.company_id AND e2.crawled_profile_id != cp1.id
            JOIN crawled_profile cp2 ON cp2.id = e2.crawled_profile_id
            JOIN connection c2 ON c2.crawled_profile_id = cp2.id
            WHERE cp1.current_company_name ILIKE :pattern
              AND cp2.current_company_name NOT ILIKE :pattern
            ORDER BY c2.affinity_score DESC NULLS LAST
            LIMIT 10
        """),
        {"pattern": f"%{target_name}%"},
    )
    for row in tier4.fetchall():
        paths.append({
            "tier": 4,
            "path_type": "shared_company",
            "profile_id": row[0],
            "intermediary": row[1],
            "current_role": row[2],
            "current_company": row[3],
            "affinity_score": row[4],
            "dunbar_tier": row[5],
            "shared_company": row[6],
            "target_person": row[7],
        })

    # Tier 5: Investor connections — connections at firms that invested in target company
    tier5 = session.execute(
        text("""
            SELECT cp.id, cp.full_name, cp.current_position, cp.current_company_name,
                   c.affinity_score, c.dunbar_tier
            FROM funding_round fr
            JOIN company co_target ON co_target.id = fr.company_id
            CROSS JOIN LATERAL unnest(fr.lead_investors) AS inv(investor_name)
            JOIN crawled_profile cp ON cp.current_company_name ILIKE '%' || inv.investor_name || '%'
            JOIN connection c ON c.crawled_profile_id = cp.id
            WHERE co_target.canonical_name ILIKE :pattern
            ORDER BY c.affinity_score DESC NULLS LAST
            LIMIT 10
        """),
        {"pattern": f"%{target_name}%"},
    )
    for row in tier5.fetchall():
        paths.append({
            "tier": 5,
            "path_type": "investor",
            "profile_id": row[0],
            "intermediary": row[1],
            "current_role": row[2],
            "company": row[3],
            "affinity_score": row[4],
            "dunbar_tier": row[5],
        })

    return {
        "target": target_name,
        "paths": paths,
        "tier1_count": sum(1 for p in paths if p["tier"] == 1),
        "tier2_count": sum(1 for p in paths if p["tier"] == 2),
        "tier3_count": sum(1 for p in paths if p["tier"] == 3),
        "tier4_count": sum(1 for p in paths if p["tier"] == 4),
        "tier5_count": sum(1 for p in paths if p["tier"] == 5),
    }
