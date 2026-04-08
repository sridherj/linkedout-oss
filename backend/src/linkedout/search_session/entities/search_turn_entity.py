# SPDX-License-Identifier: Apache-2.0
"""SearchTurn entity -- stores individual conversation turns within a search session."""
from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

try:
    from sqlalchemy.dialects.postgresql import JSONB
except ImportError:
    from sqlalchemy import JSON as JSONB  # Fallback for SQLite testing

from common.entities.base_entity import BaseEntity
from common.entities.tenant_bu_mixin import TenantBuMixin


class SearchTurnEntity(TenantBuMixin, BaseEntity):
    __tablename__ = 'search_turn'
    id_prefix = 'sturn'

    session_id: Mapped[str] = mapped_column(
        String, ForeignKey('search_session.id'), nullable=False,
        comment='Parent search session',
    )
    turn_number: Mapped[int] = mapped_column(
        Integer, nullable=False, comment='1-indexed turn number within session',
    )
    user_query: Mapped[str] = mapped_column(
        Text, nullable=False, comment='User query for this turn',
    )
    transcript: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment='Full LLM messages array including tool calls/results',
    )
    results: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment='Structured result set (profiles, scores, etc.)',
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment='LLM-generated summary, lazily populated',
    )

    __table_args__ = (
        Index('ix_sturn_session_turn', 'session_id', 'turn_number'),
    )
