# SPDX-License-Identifier: Apache-2.0
"""Stateless company resolution — match or create via CompanyMatcher."""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from linkedout.company.entities.company_entity import CompanyEntity
from shared.utils.company_matcher import CompanyMatcher, normalize_company_linkedin_url, normalize_company_name


def resolve_company(
    session: Session,
    company_matcher: CompanyMatcher,
    company_by_canonical: dict[str, CompanyEntity],
    company_name: Optional[str],
    linkedin_url: Optional[str] = None,
    universal_name: Optional[str] = None,
) -> Optional[str]:
    """Resolve or create a company, returning its ID.

    Uses CompanyMatcher for in-memory dedup. Creates new CompanyEntity if no match.
    Handles concurrent insert races via SAVEPOINT + fallback SELECT.
    Caller manages the CompanyMatcher and company_by_canonical cache.
    """
    if not company_name:
        return None
    canonical = company_matcher.match_or_create(
        company_name=company_name, linkedin_url=linkedin_url, universal_name=universal_name)
    if not canonical:
        return None
    if canonical in company_by_canonical:
        return company_by_canonical[canonical].id
    # Create new company, handling concurrent insert race
    norm_url = normalize_company_linkedin_url(linkedin_url) if linkedin_url else None
    co = CompanyEntity(
        canonical_name=canonical,
        normalized_name=normalize_company_name(canonical),
        linkedin_url=norm_url,
        universal_name=universal_name,
    )
    try:
        with session.begin_nested():
            session.add(co)
            session.flush()
    except IntegrityError:
        # Another concurrent request committed this company — fetch it
        existing = session.execute(
            select(CompanyEntity).where(CompanyEntity.canonical_name == canonical)
        ).scalar_one()
        company_by_canonical[canonical] = existing
        return existing.id
    company_by_canonical[canonical] = co
    return co.id
