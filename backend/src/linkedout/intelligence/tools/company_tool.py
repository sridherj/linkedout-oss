# SPDX-License-Identifier: Apache-2.0
"""Company resolution and classification tools for SearchAgent."""
from shared.utilities.langfuse_guard import observe
from sqlalchemy import text
from sqlalchemy.orm import Session

from dev_tools.company_utils import normalize_company_name, resolve_subsidiary
from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="backend")


@observe(name="resolve_company_aliases")
def resolve_company_aliases(company_name: str, session: Session) -> dict:
    """Resolve a company name to its canonical form, aliases, and DB record.

    Checks the subsidiary map, normalizes the name, and looks up the company
    and company_alias tables.

    Returns:
        {canonical_name, aliases, subsidiary_of, company_id, normalized_name}
    """
    if not company_name or not company_name.strip():
        return {"error": "company_name is required", "suggestion": "Provide a non-empty company name"}

    name = company_name.strip()
    parent = resolve_subsidiary(name)
    normalized = normalize_company_name(name)

    # Look up in company table (try canonical_name ILIKE match)
    search_names = [name]
    if parent:
        search_names.append(parent)
    if normalized and normalized != name.lower():
        search_names.append(normalized)

    company_row = None
    for search_name in search_names:
        result = session.execute(
            text(
                "SELECT id, canonical_name, industry, size_tier, estimated_employee_count, "
                "hq_city, hq_country "
                "FROM company WHERE canonical_name ILIKE :pattern LIMIT 1"
            ),
            {"pattern": f"%{search_name}%"},
        )
        row = result.fetchone()
        if row:
            company_row = row
            break

    # Look up aliases from company_alias table
    aliases = []
    company_id = None
    if company_row:
        company_id = company_row[0]
        alias_result = session.execute(
            text("SELECT alias_name FROM company_alias WHERE company_id = :cid"),
            {"cid": company_id},
        )
        aliases = [r[0] for r in alias_result.fetchall()]

    response = {
        "canonical_name": company_row[1] if company_row else (parent or name),
        "normalized_name": normalized,
        "subsidiary_of": parent,
        "company_id": company_id,
        "aliases": aliases,
    }

    if company_row:
        response["industry"] = company_row[2]
        response["size_tier"] = company_row[3]
        response["estimated_employee_count"] = company_row[4]
        response["hq_city"] = company_row[5]
        response["hq_country"] = company_row[6]

    return response


@observe(name="classify_company")
def classify_company(company_names: list[str], session: Session) -> dict:
    """Classify one or more companies by type, industry, and size.

    Returns:
        {companies: [{name, canonical_name, type, industry, size_tier}]}
    """
    if not company_names:
        return {"error": "company_names list is required", "suggestion": "Provide at least one company name"}

    results = []
    for name in company_names[:10]:  # Cap at 10 to prevent abuse
        if not name or not name.strip():
            continue

        row = None
        result = session.execute(
            text(
                "SELECT canonical_name, industry, size_tier, estimated_employee_count "
                "FROM company WHERE canonical_name ILIKE :pattern LIMIT 1"
            ),
            {"pattern": f"%{name.strip()}%"},
        )
        row = result.fetchone()

        company_type = _infer_company_type(
            name=name.strip(),
            industry=row[1] if row else None,
            size_tier=row[2] if row else None,
            employee_count=row[3] if row else None,
        )

        results.append({
            "name": name.strip(),
            "canonical_name": row[0] if row else name.strip(),
            "type": company_type,
            "industry": row[1] if row else None,
            "size_tier": row[2] if row else None,
        })

    return {"companies": results}


def _infer_company_type(
    name: str,
    industry: str | None,
    size_tier: str | None,
    employee_count: int | None,
) -> str:
    """Infer company type from available data."""
    name_lower = name.lower()
    industry_lower = (industry or "").lower()

    # Check if it's a known IT services/outsourcing company
    _IT_SERVICES = {
        "tcs", "tata consultancy", "infosys", "wipro", "cognizant", "hcl",
        "tech mahindra", "capgemini", "accenture", "mindtree", "ltimindtree",
        "mphasis", "hexaware", "persistent", "zensar",
    }
    if any(s in name_lower for s in _IT_SERVICES):
        return "services"
    if "outsourcing" in industry_lower or "staffing" in industry_lower:
        return "services"

    # Consulting
    _CONSULTING = {"mckinsey", "bain", "bcg", "deloitte", "kpmg", "pwc", "ey", "ernst"}
    if any(s in name_lower for s in _CONSULTING):
        return "consulting"
    if "consulting" in industry_lower:
        return "consulting"

    # Startup detection
    if size_tier in ("tiny", "small") or (employee_count and employee_count < 200):
        return "startup"

    # Enterprise/big tech
    if size_tier == "enterprise" or (employee_count and employee_count > 5000):
        return "enterprise"

    # Default to "product" for software/internet companies
    if any(kw in industry_lower for kw in ("software", "internet", "saas", "technology")):
        return "product"

    return "unknown"
