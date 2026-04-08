# SPDX-License-Identifier: Apache-2.0
"""SearchSession entity -- scoped to tenant/BU via TenantBuMixin."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from common.entities.base_entity import BaseEntity
from common.entities.tenant_bu_mixin import TenantBuMixin


class SearchSessionEntity(TenantBuMixin, BaseEntity):
    __tablename__ = 'search_session'
    id_prefix = 'ss'

    app_user_id: Mapped[str] = mapped_column(
        String, ForeignKey('app_user.id'), nullable=False,
        comment='User who owns the session',
    )
    initial_query: Mapped[str] = mapped_column(
        Text, nullable=False, comment='First search query that started the session',
    )
    turn_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment='Number of conversation turns',
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment='Last activity timestamp',
    )
    is_saved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment='Whether this session was explicitly saved/bookmarked by the user',
    )
    saved_name: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment='User-provided name for the saved session',
    )

    __table_args__ = (
        Index('ix_ss_app_user_latest', 'app_user_id', 'last_active_at'),
        Index('ix_ss_app_user_saved', 'app_user_id', 'is_saved'),
    )
