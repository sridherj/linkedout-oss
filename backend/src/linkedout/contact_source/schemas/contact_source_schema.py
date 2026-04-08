# SPDX-License-Identifier: Apache-2.0
"""Core Pydantic schema for ContactSource."""
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ContactSourceType(StrEnum):
    LINKEDIN_CSV = 'linkedin_csv'
    GOOGLE_CONTACTS = 'google_contacts'
    ICLOUD = 'icloud'
    OFFICE = 'office'


class DedupStatus(StrEnum):
    PENDING = 'pending'
    MATCHED = 'matched'
    AMBIGUOUS = 'ambiguous'
    NEW = 'new'


class DedupMethod(StrEnum):
    EXACT_URL = 'exact_url'
    EXACT_EMAIL = 'exact_email'
    FUZZY_NAME = 'fuzzy_name'
    MANUAL = 'manual'


class ContactSourceSchema(BaseModel):
    id: Annotated[str, Field(description='Unique Contact Source ID')]
    tenant_id: Annotated[str, Field(description='Tenant ID')]
    bu_id: Annotated[str, Field(description='Business Unit ID')]
    app_user_id: Annotated[str, Field(description='User who owns this source')]
    import_job_id: Annotated[str, Field(description='Import job that created this source')]
    source_type: Annotated[str, Field(description='Type of the imported source')]
    source_file_name: Annotated[Optional[str], Field(default=None, description='Original filename')]
    first_name: Annotated[Optional[str], Field(default=None, description='Parsed first name')]
    last_name: Annotated[Optional[str], Field(default=None, description='Parsed last name')]
    full_name: Annotated[Optional[str], Field(default=None, description='Full name')]
    email: Annotated[Optional[str], Field(default=None, description='Primary email')]
    phone: Annotated[Optional[str], Field(default=None, description='Primary phone')]
    company: Annotated[Optional[str], Field(default=None, description='Company name')]
    title: Annotated[Optional[str], Field(default=None, description='Job title')]
    linkedin_url: Annotated[Optional[str], Field(default=None, description='LinkedIn profile URL')]
    connected_at: Annotated[Optional[date], Field(default=None, description='Date of connection')]
    raw_record: Annotated[Optional[Any], Field(default=None, description='Raw JSON parsing')]
    connection_id: Annotated[Optional[str], Field(default=None, description='Resolved Connection ID')]
    dedup_status: Annotated[str, Field(default='pending', description='Deduplication status')]
    dedup_method: Annotated[Optional[str], Field(default=None, description='Deduplication method matched')]
    dedup_confidence: Annotated[Optional[float], Field(default=None, description='Match confidence score')]
    created_at: Annotated[datetime, Field(description='Creation time')]
    updated_at: Annotated[datetime, Field(description='Update time')]

    model_config = ConfigDict(from_attributes=True)
