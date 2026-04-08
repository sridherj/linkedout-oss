# SPDX-License-Identifier: Apache-2.0
"""Company entity -- shared (no tenant/BU scoping)."""
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from common.entities.base_entity import BaseEntity


class CompanyEntity(BaseEntity):
    __tablename__ = 'company'
    id_prefix = 'co'

    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, comment='The globally recognized unique name for this company')
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, comment='Lowercase alphanumeric string for consistent fuzzy matching')
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment='Public LinkedIn company page URL')
    universal_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment='LinkedIn universal name representation')
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment='Primary corporate website URL')
    domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment='Primary email domain for employees')
    industry: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment='High-level industry categorization')
    founded_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment='Year the company was founded')
    hq_city: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment='City where headquarters is located')
    hq_country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment='Country where headquarters is located')
    employee_count_range: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment='Bracket representation of employee size')
    estimated_employee_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment='Estimated precise employee count')
    size_tier: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment='Internal categorization of company size (e.g. SMB, Enterprise)')
    network_connection_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment='Aggregated cache of known contacts connected to this company')
    parent_company_id: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, comment='Reference ID to an overarching corporate parent entity'
    )
    enrichment_sources: Mapped[Optional[list]] = mapped_column(
        ARRAY(Text), nullable=True, comment='List of third-party sources that contributed to this entity data'
    )
    enriched_at: Mapped[Optional[str]] = mapped_column(DateTime(timezone=True), nullable=True, comment='Timestamp of last external data enrichment')
    pdl_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment='People Data Labs company identifier')
    wikidata_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment='Wikidata Q-number identifier')

    __table_args__ = (
        Index('ix_co_canonical', 'canonical_name', unique=True),
        Index('ix_co_domain', 'domain'),
        Index('ix_co_industry', 'industry'),
        Index('ix_co_size_tier', 'size_tier'),
    )
