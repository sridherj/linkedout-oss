# SPDX-License-Identifier: Apache-2.0
"""SearchTag entity -- scoped to tenant/BU via TenantBuMixin."""
from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from common.entities.base_entity import BaseEntity
from common.entities.tenant_bu_mixin import TenantBuMixin


class SearchTagEntity(TenantBuMixin, BaseEntity):
    __tablename__ = 'search_tag'
    id_prefix = 'stag'

    app_user_id: Mapped[str] = mapped_column(
        String, ForeignKey('app_user.id'), nullable=False,
        comment='User who created the tag',
    )
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey('search_session.id'), nullable=False,
        comment='Search session where the tag was created',
    )
    crawled_profile_id: Mapped[str] = mapped_column(
        String, ForeignKey('crawled_profile.id'), nullable=False,
        comment='Tagged profile',
    )
    tag_name: Mapped[str] = mapped_column(
        Text, nullable=False, comment='Tag label',
    )

    __table_args__ = (
        Index('ix_stag_app_user_tag', 'app_user_id', 'tag_name'),
        Index('ix_stag_app_user_profile', 'app_user_id', 'crawled_profile_id'),
        Index('ix_stag_session', 'session_id'),
    )
