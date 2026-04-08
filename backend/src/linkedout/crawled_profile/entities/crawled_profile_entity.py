# SPDX-License-Identifier: Apache-2.0
"""CrawledProfile entity -- shared (no tenant/BU scoping)."""
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from common.entities.base_entity import BaseEntity


class CrawledProfileEntity(BaseEntity):
    __tablename__ = 'crawled_profile'
    id_prefix = 'cp'

    linkedin_url: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, comment='Full LinkedIn URL')
    public_identifier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment='LinkedIn public identifier token')
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment='First name')
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment='Last name')
    full_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment='Full name')
    headline: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Profile headline')
    about: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Profile about section')
    location_city: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment='City location')
    location_state: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment='State/province location')
    location_country: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment='Country location')
    location_country_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, comment='ISO country code')
    location_raw: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment='Raw location string')
    connections_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment='Total number of connections')
    follower_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment='Total number of followers')
    open_to_work: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, comment='Is the profile open to work')
    premium: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, comment='Is it a premium account')
    current_company_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment='Name of the current company')
    current_position: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment='Current job title/position')
    company_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey('company.id'), nullable=True, comment='Resolved internal company ID'
    )
    seniority_level: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment='Deduced seniority level')
    function_area: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment='Deduced function/department area')
    embedding_openai: Mapped[Optional[list]] = mapped_column(
        Vector(1536), nullable=True, comment='OpenAI text-embedding-3-small vector'
    )
    embedding_nomic: Mapped[Optional[list]] = mapped_column(
        Vector(768), nullable=True, comment='nomic-embed-text-v1.5 vector'
    )
    embedding_model: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment='Model that generated the active embedding'
    )
    embedding_dim: Mapped[Optional[int]] = mapped_column(
        SmallInteger, nullable=True, comment='Dimension of the active embedding'
    )
    embedding_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment='When embedding was last generated'
    )
    search_vector: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Text search vector')
    source_app_user_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey('app_user.id'), nullable=True, comment='User who initiated the crawl, if any'
    )
    data_source: Mapped[str] = mapped_column(String(50), nullable=False, comment='Source of data collection (e.g. extension, api)')
    has_enriched_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment='Whether extended enrichment has been applied')
    last_crawled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment='When this profile was last crawled/synced')
    profile_image_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True, comment='URL to profile image')
    raw_profile: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Raw JSON payload of the profile data')

    __table_args__ = (
        Index('ix_cp_linkedin_url', 'linkedin_url', unique=True),
        Index('ix_cp_company_id', 'company_id'),
        Index('ix_cp_current_company', 'current_company_name'),
        Index('ix_cp_location', 'location_city', 'location_country_code'),
        Index('ix_cp_seniority', 'seniority_level'),
        Index('ix_cp_function', 'function_area'),
        Index('ix_cp_has_enriched', 'has_enriched_data'),
    )
