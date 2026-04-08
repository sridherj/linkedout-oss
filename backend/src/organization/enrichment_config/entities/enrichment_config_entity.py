# SPDX-License-Identifier: Apache-2.0
"""EnrichmentConfig entity - per-user enrichment settings."""
from typing import Optional

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from common.entities.base_entity import BaseEntity


class EnrichmentConfigEntity(BaseEntity):
    __tablename__ = 'enrichment_config'
    id_prefix = 'ec'

    __table_args__ = (
        UniqueConstraint('app_user_id', name='uq_enrichment_config_app_user_id'),
    )

    app_user_id: Mapped[str] = mapped_column(
        String, ForeignKey('app_user.id'), nullable=False
    )
    enrichment_mode: Mapped[str] = mapped_column(
        String, nullable=False, default='platform'
    )
    apify_key_encrypted: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    apify_key_hint: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
