# SPDX-License-Identifier: Apache-2.0
"""Career pattern analysis and role alias lookup tools for SearchAgent."""
from datetime import date

from shared.utilities.langfuse_guard import observe
from sqlalchemy import text
from sqlalchemy.orm import Session

from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="backend")

# Seniority levels ordered by progression
_SENIORITY_ORDER = {
    "intern": 0, "junior": 1, "mid": 2, "senior": 3, "lead": 4,
    "manager": 5, "director": 6, "vp": 7, "c_suite": 8, "founder": 9,
}


@observe(name="analyze_career_pattern")
def analyze_career_pattern(profile_ids: list[str], session: Session) -> dict:
    """Analyze career patterns for a list of profile IDs.

    Computes tenure, seniority progression, company type transitions,
    and career velocity for each profile.

    Args:
        profile_ids: List of crawled_profile IDs (max 20).
        session: RLS-scoped SQLAlchemy session.

    Returns:
        {profiles: [{id, name, avg_tenure_years, current_role_duration_years,
                     seniority_progression, company_transitions, career_velocity}]}
    """
    if not profile_ids:
        return {"error": "profile_ids list is required", "suggestion": "Provide crawled_profile IDs from a prior SQL query"}

    ids = profile_ids[:20]  # Cap at 20
    placeholders = ", ".join(f":id{i}" for i in range(len(ids)))
    params = {f"id{i}": pid for i, pid in enumerate(ids)}

    # Fetch experiences with company info
    result = session.execute(
        text(f"""
            SELECT e.crawled_profile_id, cp.full_name,
                   e.position, e.company_name, e.seniority_level,
                   e.start_date, e.end_date, e.is_current,
                   co.industry, co.size_tier, co.estimated_employee_count
            FROM experience e
            JOIN crawled_profile cp ON cp.id = e.crawled_profile_id
            LEFT JOIN company co ON co.id = e.company_id
            WHERE e.crawled_profile_id IN ({placeholders})
            ORDER BY e.crawled_profile_id, e.start_date ASC NULLS FIRST
        """),
        params,
    )
    rows = result.fetchall()

    # Group by profile
    profiles_data: dict[str, dict] = {}
    for row in rows:
        pid = row[0]
        if pid not in profiles_data:
            profiles_data[pid] = {"name": row[1], "experiences": []}
        profiles_data[pid]["experiences"].append({
            "position": row[2],
            "company_name": row[3],
            "seniority_level": row[4],
            "start_date": row[5],
            "end_date": row[6],
            "is_current": row[7],
            "industry": row[8],
            "size_tier": row[9],
            "employee_count": row[10],
        })

    results = []
    for pid in ids:
        if pid not in profiles_data:
            results.append({"id": pid, "error": "no experience data found"})
            continue

        data = profiles_data[pid]
        exps = data["experiences"]
        analysis = _analyze_experiences(exps)
        analysis["id"] = pid
        analysis["name"] = data["name"]
        results.append(analysis)

    return {"profiles": results}


def _analyze_experiences(experiences: list[dict]) -> dict:
    """Compute career metrics from a list of experience records."""
    today = date.today()

    tenures = []
    seniority_levels = []
    company_types = []
    current_role_duration = None

    for exp in experiences:
        start = exp["start_date"]
        end = exp["end_date"]

        if start:
            end_dt = end if end else (today if exp["is_current"] else None)
            if end_dt:
                years = (end_dt - start).days / 365.25
                tenures.append(years)
                if exp["is_current"]:
                    current_role_duration = round(years, 1)

        if exp["seniority_level"] and exp["seniority_level"] in _SENIORITY_ORDER:
            seniority_levels.append(exp["seniority_level"])

        ctype = _infer_company_type_simple(exp)
        if ctype:
            company_types.append(ctype)

    # Seniority progression (deduplicated, in order seen)
    seen = set()
    progression = []
    for level in seniority_levels:
        if level not in seen:
            seen.add(level)
            progression.append(level)

    # Career velocity: how many seniority jumps per year of experience
    total_years = sum(tenures) if tenures else 0
    unique_levels = len(set(seniority_levels))
    velocity = round(unique_levels / max(total_years, 1), 2) if unique_levels > 1 else 0

    return {
        "avg_tenure_years": round(sum(tenures) / len(tenures), 1) if tenures else None,
        "current_role_duration_years": current_role_duration,
        "total_experience_years": round(total_years, 1) if tenures else None,
        "seniority_progression": progression,
        "company_transitions": _dedupe_list(company_types),
        "career_velocity": velocity,
        "role_count": len(experiences),
    }


def _infer_company_type_simple(exp: dict) -> str | None:
    """Quick company type inference from experience record."""
    industry = (exp.get("industry") or "").lower()
    name = (exp.get("company_name") or "").lower()
    size_tier = exp.get("size_tier")
    employee_count = exp.get("employee_count")

    _IT_SERVICES = {"tcs", "infosys", "wipro", "cognizant", "hcl", "accenture", "capgemini", "tech mahindra"}
    if any(s in name for s in _IT_SERVICES):
        return "services"
    if "outsourcing" in industry or "staffing" in industry:
        return "services"
    if size_tier in ("tiny", "small") or (employee_count and employee_count < 200):
        return "startup"
    if any(kw in industry for kw in ("software", "internet", "saas")):
        return "product"
    return None


def _dedupe_list(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


@observe(name="lookup_role_aliases")
def lookup_role_aliases(role_query: str, session: Session) -> dict:
    """Look up canonical role titles and their aliases from the role_alias table.

    Useful for finding all title variants that map to a concept (e.g., "senior engineer"
    matches "Sr. Software Engineer", "Senior SDE", etc.)

    Args:
        role_query: A role title or keyword to search for.
        session: SQLAlchemy session.

    Returns:
        {matches: [{alias_title, canonical_title, seniority_level, function_area}]}
    """
    if not role_query or not role_query.strip():
        return {"error": "role_query is required", "suggestion": "Provide a role title or keyword"}

    query = role_query.strip()
    result = session.execute(
        text("""
            SELECT alias_title, canonical_title, seniority_level, function_area
            FROM role_alias
            WHERE alias_title ILIKE :pattern
               OR canonical_title ILIKE :pattern
            ORDER BY canonical_title
            LIMIT 20
        """),
        {"pattern": f"%{query}%"},
    )
    rows = result.fetchall()

    return {
        "query": query,
        "matches": [
            {
                "alias_title": row[0],
                "canonical_title": row[1],
                "seniority_level": row[2],
                "function_area": row[3],
            }
            for row in rows
        ],
        "match_count": len(rows),
    }
