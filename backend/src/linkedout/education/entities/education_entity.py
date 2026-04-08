# SPDX-License-Identifier: Apache-2.0
"""Education entity -- shared (no tenant/BU scoping)."""
from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from common.entities.base_entity import BaseEntity


class EducationEntity(BaseEntity):
    __tablename__ = 'education'
    id_prefix = 'edu'

    crawled_profile_id: Mapped[str] = mapped_column(
        String, ForeignKey('crawled_profile.id', ondelete='CASCADE'), nullable=False, comment='Profile this education belongs to'
    )
    school_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Name of the school/university')
    school_linkedin_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment='LinkedIn URL of the school')
    degree: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment='Degree obtained')
    field_of_study: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment='Field of study / major')
    start_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment='Year started')
    end_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment='Year ended or expected to end')
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Additional description about the education')
    # Text placeholder for JSONB (SQLite compat)
    raw_education: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Raw JSON payload of education data')

    __table_args__ = (
        Index('ix_edu_profile', 'crawled_profile_id'),
        Index('ix_edu_school', 'school_name'),
    )
