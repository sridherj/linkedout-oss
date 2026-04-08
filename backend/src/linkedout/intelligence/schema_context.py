# SPDX-License-Identifier: Apache-2.0
"""Dynamic schema context builder for SearchAgent LLM system prompt."""
from sqlalchemy.orm import Session

from linkedout.company.entities.company_entity import CompanyEntity
from linkedout.company_alias.entities.company_alias_entity import CompanyAliasEntity
from linkedout.connection.entities.connection_entity import ConnectionEntity
from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
from linkedout.education.entities.education_entity import EducationEntity
from linkedout.experience.entities.experience_entity import ExperienceEntity
from linkedout.profile_skill.entities.profile_skill_entity import ProfileSkillEntity
from linkedout.funding.entities.funding_round_entity import FundingRoundEntity
from linkedout.funding.entities.startup_tracking_entity import StartupTrackingEntity
from linkedout.role_alias.entities.role_alias_entity import RoleAliasEntity
from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="backend")

_ENTITIES = [
    CrawledProfileEntity,
    ConnectionEntity,
    ExperienceEntity,
    EducationEntity,
    CompanyEntity,
    CompanyAliasEntity,
    ProfileSkillEntity,
    RoleAliasEntity,
    FundingRoundEntity,
    StartupTrackingEntity,
]

_BUSINESS_RULES = """
## Business Rules

- The database is automatically scoped to the current user's network via Row-Level Security (RLS). No user ID filtering is needed in SQL queries.
- Always JOIN through `connection` to access profiles: `FROM crawled_profile cp JOIN connection c ON c.crawled_profile_id = cp.id`.
- All connections have a `crawled_profile` (stub or enriched). Check `cp.has_enriched_data` to distinguish.
- Stub profiles (`has_enriched_data = FALSE`) have basic CSV data (name, company, title) but no embedding, no about, no experience/education.
- `experience` and `education` link to `crawled_profile` via `crawled_profile_id`.
- `company` links via `company_id` on both `crawled_profile` and `experience`.
- `role_alias` maps title variants to canonical titles with seniority_level and function_area.
- `funding_round` links to `company` via `company_id`. Contains round_type, amount_usd, lead_investors (text array), all_investors (text). NOT user-scoped (no RLS) — public company data.
- `startup_tracking` links to `company` via `company_id` (1:1). Contains funding_stage, total_raised_usd, vertical, watching flag. NOT user-scoped.

## Required SELECT Columns

Every SQL query returning people MUST include these columns:

```sql
SELECT cp.id AS crawled_profile_id, c.id AS connection_id,
       cp.full_name, cp.headline, cp.current_position, cp.current_company_name,
       cp.location_city, cp.location_country, cp.linkedin_url, cp.public_identifier,
       cp.has_enriched_data,
       c.affinity_score, c.dunbar_tier, c.connected_at
```

Always alias `cp.id` as `crawled_profile_id` and `c.id` as `connection_id`.
Always include `cp.has_enriched_data` — the UI uses this to show enriched cards vs. the "Enrich" button.

## Data Availability

- Some `company` metadata columns (industry, size_tier, estimated_employee_count) may be NULL. Use `resolve_company_aliases` tool for company lookups.
- ~79% of experience records have `seniority_level`; ~63% have `function_area`. Add ILIKE fallback on `cp.current_position` when filtering by these.
- `experience.start_date` is populated for ~98% of records. `experience.is_current` is TRUE for ~18% of records.
- Past roles have `is_current IS NULL` (not FALSE). Use `e.is_current IS NULL AND e.end_year IS NOT NULL` for "previously at" queries.
""".strip()


def _describe_table(entity_cls) -> str:
    """Build a table description from SQLAlchemy entity metadata."""
    table = entity_cls.__table__
    lines = [f"### {table.name}"]
    for col in table.columns:
        col_type = str(col.type)
        nullable = "nullable" if col.nullable else "not null"
        comment = col.comment or ""
        parts = [f"  - `{col.name}` ({col_type}, {nullable})"]
        if comment:
            parts.append(f" — {comment}")
        lines.append("".join(parts))
    return "\n".join(lines)


def build_schema_context(session: Session | None = None) -> str:
    """Build schema reference string from entity metadata for LLM system prompt.

    Args:
        session: Optional SQLAlchemy session (reserved for future introspection).

    Returns:
        A formatted string describing tables, columns, types, and business rules.
    """
    sections = ["# Database Schema Reference\n"]

    sections.append("## Tables\n")
    for entity_cls in _ENTITIES:
        sections.append(_describe_table(entity_cls))
        sections.append("")

    sections.append(_BUSINESS_RULES)

    return "\n".join(sections)
