# SPDX-License-Identifier: Apache-2.0
"""GrowthSignal entity — shared (no tenant/BU scoping)."""
from typing import Optional

from sqlalchemy import BigInteger, Date, Index, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from common.entities.base_entity import BaseEntity


class GrowthSignalEntity(BaseEntity):
    __tablename__ = 'growth_signal'
    id_prefix = 'gs'

    company_id: Mapped[str] = mapped_column(String, nullable=False, comment='FK to company.id')
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False, comment='arr, mrr, revenue, headcount, etc.')
    signal_date: Mapped[str] = mapped_column(Date, nullable=False, comment='Date signal was observed')
    value_numeric: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment='Numeric value (USD, count)')
    value_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Human-readable description')
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment='URL where signal was found')
    confidence: Mapped[int] = mapped_column(SmallInteger, default=5, nullable=False, comment='Confidence score 1-10')

    __table_args__ = (
        Index('ix_gs_company_date', 'company_id', 'signal_date'),
        Index('ix_gs_signal_type', 'signal_type'),
        UniqueConstraint('company_id', 'signal_type', 'signal_date', 'source', name='ix_gs_dedup'),
    )
