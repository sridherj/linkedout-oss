# SPDX-License-Identifier: Apache-2.0
"""StartupTracking entity — shared (no tenant/BU scoping)."""
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, Index, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from common.entities.base_entity import BaseEntity


class StartupTrackingEntity(BaseEntity):
    __tablename__ = 'startup_tracking'
    id_prefix = 'st'

    company_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, comment='1:1 FK to company.id')
    watching: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment='Pipeline filter flag')
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Startup description')
    vertical: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment='AI Agents, Voice AI, Dev Tools, etc.')
    sub_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment='Finer classification')
    funding_stage: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment='Denormalized from funding_rounds')
    total_raised_usd: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment='Denormalized sum')
    last_funding_date: Mapped[Optional[str]] = mapped_column(Date, nullable=True, comment='Denormalized latest')
    round_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment='Denormalized count')
    estimated_arr_usd: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment='Revenue estimate')
    arr_signal_date: Mapped[Optional[str]] = mapped_column(Date, nullable=True, comment='When ARR was estimated')
    arr_confidence: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True, comment='Confidence 1-10')

    __table_args__ = (
        Index('ix_st_company', 'company_id', unique=True),
        Index('ix_st_watching', 'watching', postgresql_where='watching = true'),
        Index('ix_st_vertical', 'vertical'),
    )
