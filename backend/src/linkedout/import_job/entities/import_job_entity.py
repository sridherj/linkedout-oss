# SPDX-License-Identifier: Apache-2.0
"""ImportJob entity -- scoped to tenant/BU via TenantBuMixin."""
from typing import Optional

from sqlalchemy import (
    DateTime, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from common.entities.base_entity import BaseEntity
from common.entities.tenant_bu_mixin import TenantBuMixin


class ImportJobEntity(TenantBuMixin, BaseEntity):
    __tablename__ = 'import_job'
    id_prefix = 'ij'

    app_user_id: Mapped[str] = mapped_column(
        String, ForeignKey('app_user.id'), nullable=False, comment='User who initiated the import'
    )
    source_type: Mapped[str] = mapped_column(String, nullable=False, comment='Source of the import (e.g. linkedin_csv)')
    file_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Name of the uploaded file')
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment='Size of the file in bytes')
    status: Mapped[str] = mapped_column(String, nullable=False, default='pending', comment='Current status of the import job')
    total_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment='Total records found in the source')
    parsed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment='Number of records successfully parsed')
    matched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment='Number of records matched to existing profiles')
    new_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment='Number of new profiles created')
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment='Number of records that failed processing')
    enrichment_queued: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment='Number of profiles queued for enrichment')
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Overall error message if job failed')
    started_at: Mapped[Optional[str]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment='Timestamp when processing started'
    )
    completed_at: Mapped[Optional[str]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment='Timestamp when processing completed'
    )

    __table_args__ = (
        Index('ix_ij_app_user', 'app_user_id'),
        Index('ix_ij_status', 'status'),
    )
