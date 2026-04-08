# SPDX-License-Identifier: Apache-2.0
"""ContactSource entity -- scoped to tenant/BU via TenantBuMixin."""
from typing import Optional

from sqlalchemy import (
    Date, Float, ForeignKey, Index, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from common.entities.base_entity import BaseEntity
from common.entities.tenant_bu_mixin import TenantBuMixin


class ContactSourceEntity(TenantBuMixin, BaseEntity):
    __tablename__ = 'contact_source'
    id_prefix = 'cs'

    app_user_id: Mapped[str] = mapped_column(
        String, ForeignKey('app_user.id'), nullable=False, comment='Owner of this contact source'
    )
    import_job_id: Mapped[str] = mapped_column(
        String, ForeignKey('import_job.id'), nullable=False, comment='Import job that created this source'
    )

    # Source identification
    source_type: Mapped[str] = mapped_column(String, nullable=False, comment='Type of source: linkedin_csv, google, etc.')
    source_file_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Original filename if imported from file')

    # Parsed contact data
    first_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Parsed first name')
    last_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Parsed last name')
    full_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Full name from source')
    email: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Primary email')
    phone: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Primary phone')
    company: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Company name from source')
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Job title from source')
    linkedin_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='LinkedIn URL if available')
    connected_at: Mapped[Optional[str]] = mapped_column(Date, nullable=True, comment='Date they connected (if applicable)')

    # Raw original record
    raw_record: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, comment='Raw JSON data from the source file/API')

    # Dedup outcome
    connection_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey('connection.id'), nullable=True, comment='Resolved Connection ID after dedup'
    )
    dedup_status: Mapped[str] = mapped_column(
        String, nullable=False, default='pending', comment='Status of dedup: pending, matched, ambiguous, new'
    )
    dedup_method: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment='Method used for dedup match')
    dedup_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment='Confidence score of the match')

    # Import origin label for external contact signal
    source_label: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment='Import origin: google_personal, google_work, icloud, office365')

    __table_args__ = (
        Index('ix_cs_app_user', 'app_user_id'),
        Index('ix_cs_import_job', 'import_job_id'),
        Index('ix_cs_linkedin_url', 'linkedin_url', postgresql_where='linkedin_url IS NOT NULL'),
        Index('ix_cs_email', 'email', postgresql_where='email IS NOT NULL'),
        Index('ix_cs_dedup_status', 'dedup_status', postgresql_where="dedup_status = 'pending'"),
    )
