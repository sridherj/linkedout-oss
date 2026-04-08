# SPDX-License-Identifier: Apache-2.0
"""EnrichmentEvent entity -- scoped to tenant/BU via TenantBuMixin."""
from typing import Optional

from sqlalchemy import Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from common.entities.base_entity import BaseEntity
from common.entities.tenant_bu_mixin import TenantBuMixin


class EnrichmentEventEntity(TenantBuMixin, BaseEntity):
    __tablename__ = 'enrichment_event'
    id_prefix = 'ee'

    app_user_id: Mapped[str] = mapped_column(
        String, ForeignKey('app_user.id'), nullable=False, comment='User who initiated the enrichment'
    )
    crawled_profile_id: Mapped[str] = mapped_column(
        String, ForeignKey('crawled_profile.id'), nullable=False, comment='Profile this enrichment targets'
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False, comment='Type of enrichment event (e.g. crawled, failed)')
    enrichment_mode: Mapped[str] = mapped_column(String, nullable=False, comment='Mode of enrichment (e.g. platform, byok)')
    crawler_name: Mapped[Optional[str]] = mapped_column(String, nullable=True, comment='Name of the crawler used')
    cost_estimate_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment='Estimated cost in USD')
    crawler_run_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, comment='ID of the crawler run')

    __table_args__ = (
        Index('ix_ee_app_user', 'app_user_id'),
        Index('ix_ee_tenant', 'tenant_id'),
        Index('ix_ee_profile', 'crawled_profile_id'),
        Index('ix_ee_type', 'event_type'),
    )
