# SPDX-License-Identifier: Apache-2.0
"""Core Pydantic schema for ImportJob."""
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field


class ImportSourceType(StrEnum):
    LINKEDIN_CSV = 'linkedin_csv'
    GOOGLE_CONTACTS = 'google_contacts'
    ICLOUD = 'icloud'
    OFFICE = 'office'


class ImportJobStatus(StrEnum):
    PENDING = 'pending'
    PARSING = 'parsing'
    DEDUPING = 'deduping'
    ENRICHING = 'enriching'
    COMPLETED = 'completed'
    FAILED = 'failed'


class ImportJobSchema(BaseModel):
    id: Annotated[str, Field(description='Primary key')]
    tenant_id: Annotated[str, Field(description='Tenant ID')]
    bu_id: Annotated[str, Field(description='Business Unit ID')]
    app_user_id: Annotated[str, Field(description='User who initiated the import')]
    source_type: Annotated[str, Field(description='Source of the import (e.g. linkedin_csv)')]
    file_name: Annotated[Optional[str], Field(description='Name of the uploaded file', default=None)]
    file_size_bytes: Annotated[Optional[int], Field(description='Size of the file in bytes', default=None)]
    status: Annotated[str, Field(description='Current status of the import job')]
    total_records: Annotated[int, Field(description='Total records found in the source', default=0)]
    parsed_count: Annotated[int, Field(description='Number of records successfully parsed', default=0)]
    matched_count: Annotated[int, Field(description='Number of records matched to existing profiles', default=0)]
    new_count: Annotated[int, Field(description='Number of new profiles created', default=0)]
    failed_count: Annotated[int, Field(description='Number of records that failed processing', default=0)]
    enrichment_queued: Annotated[int, Field(description='Number of profiles queued for enrichment', default=0)]
    error_message: Annotated[Optional[str], Field(description='Overall error message if job failed', default=None)]
    started_at: Annotated[Optional[datetime], Field(description='Timestamp when processing started', default=None)]
    completed_at: Annotated[Optional[datetime], Field(description='Timestamp when processing completed', default=None)]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
