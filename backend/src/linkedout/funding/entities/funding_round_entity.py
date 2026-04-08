# SPDX-License-Identifier: Apache-2.0
"""FundingRound entity — shared (no tenant/BU scoping)."""
from typing import Optional

from sqlalchemy import BigInteger, Date, Index, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from common.entities.base_entity import BaseEntity


class FundingRoundEntity(BaseEntity):
    __tablename__ = 'funding_round'
    id_prefix = 'fr'

    company_id: Mapped[str] = mapped_column(String, nullable=False, comment='FK to company.id')
    round_type: Mapped[str] = mapped_column(String(50), nullable=False, comment='Seed, Series A, Series B, etc.')
    announced_on: Mapped[Optional[str]] = mapped_column(Date, nullable=True, comment='Date the round was announced')
    amount_usd: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment='Round amount in whole USD')
    lead_investors: Mapped[Optional[list]] = mapped_column(ARRAY(Text), nullable=True, comment='Lead investor names')
    all_investors: Mapped[Optional[list]] = mapped_column(ARRAY(Text), nullable=True, comment='All investor names')
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment='URL of source article')
    confidence: Mapped[int] = mapped_column(SmallInteger, default=5, nullable=False, comment='Confidence score 1-10')

    __table_args__ = (
        Index('ix_fr_company', 'company_id'),
        Index('ix_fr_announced', 'announced_on'),
        Index('ix_fr_round_type', 'round_type'),
        UniqueConstraint('company_id', 'round_type', 'amount_usd', name='ix_fr_dedup'),
    )
