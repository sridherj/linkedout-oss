# SPDX-License-Identifier: Apache-2.0
"""AppUser entity - sits above tenant/BU scoping."""
from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from common.entities.base_entity import BaseEntity


class AppUserEntity(BaseEntity):
    __tablename__ = 'app_user'
    id_prefix = 'usr'

    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    auth_provider_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True)
    api_key_prefix: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    api_key_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    own_crawled_profile_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey('crawled_profile.id', ondelete='SET NULL'), nullable=True,
        comment="The user's own LinkedIn profile in the crawled_profile table",
    )
    network_preferences: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment='Free-text user preferences about their network, injected into search agent context',
    )
