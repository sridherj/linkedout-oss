# SPDX-License-Identifier: Apache-2.0
"""Result set tools for conversational search.

Tag operations persist to the SearchTag entity via CRUD.
compute_facets operates on in-memory result sets for UI faceting.
"""
from collections import Counter

from shared.utilities.langfuse_guard import observe
from sqlalchemy import text
from sqlalchemy.orm import Session

from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="backend")

# ── Facet dimensions computed from result set ────────────────────────────

_FACET_DIMENSIONS = {
    "dunbar_tier": "Dunbar Tier",
    "location_city": "Location",
    "current_company_name": "Company",
}

# Seniority keywords mapped to buckets for faceting
_SENIORITY_KEYWORDS = {
    "intern": "Intern", "junior": "Junior", "mid": "Mid",
    "senior": "Senior", "lead": "Lead", "staff": "Staff",
    "principal": "Principal", "manager": "Manager",
    "director": "Director", "vp": "VP", "head": "VP",
    "c-level": "C-Suite", "cto": "C-Suite", "ceo": "C-Suite",
    "cfo": "C-Suite", "coo": "C-Suite", "founder": "Founder",
}


def compute_facets(result_set: list[dict]) -> list[dict]:
    """Compute facet groups from an in-memory result set.

    Returns:
        [{group: str, items: [{label: str, count: int}]}]
    """
    facets = []

    for field, group_name in _FACET_DIMENSIONS.items():
        counter: Counter = Counter()
        for profile in result_set:
            val = profile.get(field)
            if val:
                counter[str(val)] += 1
        if counter:
            items = [{"label": k, "count": v} for k, v in counter.most_common(10)]
            facets.append({"group": group_name, "items": items})

    # Seniority facet: infer from current_position text
    seniority_counter: Counter = Counter()
    for profile in result_set:
        pos = (profile.get("current_position") or "").lower()
        for keyword, bucket in _SENIORITY_KEYWORDS.items():
            if keyword in pos:
                seniority_counter[bucket] += 1
                break
    if seniority_counter:
        items = [{"label": k, "count": v} for k, v in seniority_counter.most_common()]
        facets.append({"group": "Seniority", "items": items})

    return facets


# ── Tool implementations ─────────────────────────────────────────────────

@observe(name="tag_profiles")
def tag_profiles(
    session: Session,
    app_user_id: str,
    session_id: str,
    tenant_id: str,
    bu_id: str,
    profile_ids: list[str],
    tag_name: str,
    action: str = "add",
) -> dict:
    """Add or remove tags on profiles, persisting to SearchTag entity.

    Args:
        session: DB session for tag persistence.
        app_user_id: Current user ID.
        session_id: Current search session ID.
        tenant_id: Tenant ID.
        bu_id: Business unit ID.
        profile_ids: Profiles to tag.
        tag_name: Tag label.
        action: "add" or "remove".

    Returns:
        {action, tag_name, profile_ids, count}
    """
    from linkedout.search_tag.entities.search_tag_entity import SearchTagEntity

    if action == "add":
        for pid in profile_ids:
            # Check for existing tag to avoid duplicates
            existing = session.execute(
                text(
                    "SELECT id FROM search_tag "
                    "WHERE app_user_id = :uid AND session_id = :sid "
                    "AND crawled_profile_id = :pid AND tag_name = :tag"
                ),
                {"uid": app_user_id, "sid": session_id, "pid": pid, "tag": tag_name},
            ).first()
            if not existing:
                entity = SearchTagEntity(
                    tenant_id=tenant_id,
                    bu_id=bu_id,
                    app_user_id=app_user_id,
                    session_id=session_id,
                    crawled_profile_id=pid,
                    tag_name=tag_name,
                )
                session.add(entity)
        session.flush()
    elif action == "remove":
        session.execute(
            text(
                "DELETE FROM search_tag "
                "WHERE app_user_id = :uid AND session_id = :sid "
                "AND crawled_profile_id = ANY(:pids) AND tag_name = :tag"
            ),
            {"uid": app_user_id, "sid": session_id, "pids": profile_ids, "tag": tag_name},
        )
        session.flush()

    return {
        "action": action,
        "tag_name": tag_name,
        "profile_ids": profile_ids,
        "count": len(profile_ids),
    }


@observe(name="get_tagged_profiles")
def get_tagged_profiles(
    session: Session,
    app_user_id: str,
    tag_name: str,
    session_id: str | None = None,
) -> dict:
    """Retrieve profiles with a specific tag.

    Args:
        session: DB session.
        app_user_id: Current user ID.
        tag_name: Tag to look up.
        session_id: Optional session scope; if None, returns all sessions.

    Returns:
        {tag_name, profiles: [{crawled_profile_id, full_name, ...}], count}
    """
    params: dict = {"uid": app_user_id, "tag": tag_name}
    where_clause = "st.app_user_id = :uid AND st.tag_name = :tag"
    if session_id:
        where_clause += " AND st.session_id = :sid"
        params["sid"] = session_id

    result = session.execute(
        text(f"""
            SELECT DISTINCT st.crawled_profile_id, cp.full_name,
                   cp.current_position, cp.current_company_name
            FROM search_tag st
            JOIN crawled_profile cp ON cp.id = st.crawled_profile_id
            WHERE {where_clause}
            ORDER BY cp.full_name
        """),
        params,
    )
    rows = result.fetchall()

    return {
        "tag_name": tag_name,
        "profiles": [
            {
                "crawled_profile_id": row[0],
                "full_name": row[1],
                "current_position": row[2],
                "current_company_name": row[3],
            }
            for row in rows
        ],
        "count": len(rows),
    }


