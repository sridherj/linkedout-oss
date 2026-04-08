# SPDX-License-Identifier: Apache-2.0
"""Connection entity -- scoped to tenant/BU via TenantBuMixin."""
from typing import Optional

from sqlalchemy import (
    Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from common.entities.base_entity import BaseEntity
from common.entities.tenant_bu_mixin import TenantBuMixin


class ConnectionEntity(TenantBuMixin, BaseEntity):
    __tablename__ = 'connection'
    id_prefix = 'conn'

    app_user_id: Mapped[str] = mapped_column(
        String, ForeignKey('app_user.id'), nullable=False, comment='User who owns this connection'
    )
    crawled_profile_id: Mapped[str] = mapped_column(
        String, ForeignKey('crawled_profile.id'), nullable=False, comment='Profile representing the connected person'
    )
    connected_at: Mapped[Optional[str]] = mapped_column(Date, nullable=True, comment='When the connection was established')
    emails: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Comma-separated email addresses')
    phones: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Comma-separated phone numbers')
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Personal notes about this connection')
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Comma-separated structural tags')
    sources: Mapped[Optional[list]] = mapped_column(ARRAY(Text), nullable=True, comment='Where this connection was imported from (e.g. LinkedIn)')
    # JSONB column uses Text placeholder for SQLite
    source_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Raw JSON data from the import source')
    affinity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment='Calculated affinity score (0-100)')
    dunbar_tier: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment='Assigned Dunbar number tier')
    affinity_source_count: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment='Number of interaction sources factored into affinity')
    affinity_recency: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment='Recency dimension of affinity score')
    affinity_career_overlap: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment='Career overlap dimension of affinity score')
    affinity_mutual_connections: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment='Mutual connections dimension of affinity score')
    affinity_external_contact: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment='External contact warmth signal')
    affinity_embedding_similarity: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment='Embedding similarity signal')
    affinity_computed_at: Mapped[Optional[str]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment='When affinity was last calculated'
    )
    affinity_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment='Version of affinity algorithm used')

    __table_args__ = (
        UniqueConstraint('app_user_id', 'crawled_profile_id', name='uq_conn_app_user_profile'),
        Index('ix_conn_app_user', 'app_user_id'),
        Index('ix_conn_tenant', 'tenant_id'),
        Index('ix_conn_bu', 'bu_id'),
        Index('ix_conn_app_user_profile', 'app_user_id', 'crawled_profile_id'),
        # Affinity indexes use plain columns for SQLite compatibility.
        # Add DESC NULLS LAST in the Alembic migration for PostgreSQL.
        Index('ix_conn_app_user_affinity', 'app_user_id', 'affinity_score'),
        Index('ix_conn_tenant_affinity', 'tenant_id', 'affinity_score'),
        Index('ix_conn_dunbar', 'app_user_id', 'dunbar_tier'),
    )
