# SPDX-License-Identifier: Apache-2.0
"""ProfileSkill entity -- shared (no tenant/BU scoping)."""
from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from common.entities.base_entity import BaseEntity


class ProfileSkillEntity(BaseEntity):
    __tablename__ = 'profile_skill'
    id_prefix = 'psk'

    crawled_profile_id: Mapped[str] = mapped_column(
        String, ForeignKey('crawled_profile.id', ondelete='CASCADE'), nullable=False, comment='Profile this skill belongs to'
    )
    skill_name: Mapped[str] = mapped_column(String(255), nullable=False, comment='Name of the skill')
    endorsement_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment='Number of endorsements for this skill')

    __table_args__ = (
        UniqueConstraint('crawled_profile_id', 'skill_name', name='uq_psk_profile_skill'),
        Index('ix_psk_profile', 'crawled_profile_id'),
        Index('ix_psk_skill', 'skill_name'),
    )
