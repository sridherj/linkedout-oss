# SPDX-License-Identifier: Apache-2.0
"""Experience entity -- shared (no tenant/BU scoping)."""
from datetime import date
from typing import Optional

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from common.entities.base_entity import BaseEntity


class ExperienceEntity(BaseEntity):
    __tablename__ = 'experience'
    id_prefix = 'exp'

    crawled_profile_id: Mapped[str] = mapped_column(
        String, ForeignKey('crawled_profile.id', ondelete='CASCADE'), nullable=False, comment='Profile this experience belongs to'
    )
    position: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Job title or position')
    position_normalized: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Normalized job title')
    company_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment='Name of the company')
    company_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey('company.id'), nullable=True, comment='Resolved company entity ID if matched'
    )
    company_linkedin_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment='LinkedIn URL of the company')
    employment_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment='Type of employment (full-time, part-time, etc)')
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment='Start date of role')
    start_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment='Start year')
    start_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment='Start month')
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment='End date of role')
    end_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment='End year')
    end_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment='End month')
    end_date_text: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment='Textual end date like "Present"')
    # Regular nullable Boolean for SQLite compat. In PostgreSQL would be Computed('end_date IS NULL').
    is_current: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=None, comment='Whether this is the current role')
    seniority_level: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment='Estimated seniority level')
    function_area: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment='Function area or department')
    location: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment='Location of the role')
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Description of the role/experience')
    # Text placeholder for JSONB (SQLite compat)
    raw_experience: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Raw JSON payload of experience data')

    __table_args__ = (
        Index('ix_exp_profile', 'crawled_profile_id'),
        Index('ix_exp_company', 'company_id'),
        Index('ix_exp_current', 'is_current'),
        Index('ix_exp_dates', 'start_date', 'end_date'),
    )
