# SPDX-License-Identifier: Apache-2.0
"""Request/response schemas for ContactSource API."""
from datetime import date
from enum import StrEnum
from datetime import date
from enum import StrEnum
from typing import Annotated, Any, List, Optional

from pydantic import Field

from common.schemas.base_enums_schemas import SortOrder
from common.schemas.base_request_schema import BaseRequestSchema, PaginateRequestSchema
from common.schemas.base_response_schema import BaseResponseSchema, PaginateResponseSchema
from linkedout.contact_source.schemas.contact_source_schema import ContactSourceSchema


class ContactSourceSortByFields(StrEnum):
    CREATED_AT = 'created_at'
    UPDATED_AT = 'updated_at'
    SOURCE_TYPE = 'source_type'
    DEDUP_STATUS = 'dedup_status'


class ListContactSourcesRequestSchema(PaginateRequestSchema):
    tenant_id: Annotated[Optional[str], Field(default=None, description='Tenant ID')]
    bu_id: Annotated[Optional[str], Field(default=None, description='Business Unit ID')]
    sort_by: Annotated[ContactSourceSortByFields, Field(default=ContactSourceSortByFields.CREATED_AT, description='Field to sort by')]
    sort_order: Annotated[SortOrder, Field(default=SortOrder.DESC, description='Sort direction')]
    app_user_id: Annotated[Optional[str], Field(default=None, description='Filter by system app_user_id')]
    import_job_id: Annotated[Optional[str], Field(default=None, description='Filter by parent import_job_id')]
    source_type: Annotated[Optional[str], Field(default=None, description='Filter by source_type')]
    dedup_status: Annotated[Optional[str], Field(default=None, description='Filter by dedup_status')]
    connection_id: Annotated[Optional[str], Field(default=None, description='Filter by resolved connection_id')]


class CreateContactSourceRequestSchema(BaseRequestSchema):
    tenant_id: Annotated[Optional[str], Field(default=None, description='Tenant ID')]
    bu_id: Annotated[Optional[str], Field(default=None, description='Business Unit ID')]
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
    raw_record: Annotated[Optional[Any], Field(default=None, description='Raw JSON data')]
    connection_id: Annotated[Optional[str], Field(default=None, description='Resolved Connection ID')]
    dedup_status: Annotated[str, Field(default='pending', description='Deduplication status')]
    dedup_method: Annotated[Optional[str], Field(default=None, description='Deduplication match method')]
    dedup_confidence: Annotated[Optional[float], Field(default=None, description='Match confidence score')]


class CreateContactSourcesRequestSchema(BaseRequestSchema):
    tenant_id: Annotated[Optional[str], Field(default=None, description='Tenant ID')]
    bu_id: Annotated[Optional[str], Field(default=None, description='Business Unit ID')]
    contact_sources: Annotated[List[CreateContactSourceRequestSchema], Field(description='List of sources to insert in bulk')]


class UpdateContactSourceRequestSchema(BaseRequestSchema):
    tenant_id: Annotated[Optional[str], Field(default=None, description='Tenant ID')]
    bu_id: Annotated[Optional[str], Field(default=None, description='Business Unit ID')]
    contact_source_id: Annotated[Optional[str], Field(default=None, description='ID of the source to update')]
    source_type: Annotated[Optional[str], Field(default=None, description='Updated source type')]
    source_file_name: Annotated[Optional[str], Field(default=None, description='Updated filename')]
    first_name: Annotated[Optional[str], Field(default=None, description='Updated first name')]
    last_name: Annotated[Optional[str], Field(default=None, description='Updated last name')]
    full_name: Annotated[Optional[str], Field(default=None, description='Updated full name')]
    email: Annotated[Optional[str], Field(default=None, description='Updated email')]
    phone: Annotated[Optional[str], Field(default=None, description='Updated phone')]
    company: Annotated[Optional[str], Field(default=None, description='Updated company')]
    title: Annotated[Optional[str], Field(default=None, description='Updated title')]
    linkedin_url: Annotated[Optional[str], Field(default=None, description='Updated LinkedIn URL')]
    connected_at: Annotated[Optional[date], Field(default=None, description='Updated connected_at date')]
    raw_record: Annotated[Optional[Any], Field(default=None, description='Updated raw record')]
    connection_id: Annotated[Optional[str], Field(default=None, description='Updated connection_id match')]
    dedup_status: Annotated[Optional[str], Field(default=None, description='Updated dedup status')]
    dedup_method: Annotated[Optional[str], Field(default=None, description='Updated dedup method')]
    dedup_confidence: Annotated[Optional[float], Field(default=None, description='Updated dedup confidence')]


class GetContactSourceByIdRequestSchema(BaseRequestSchema):
    tenant_id: Annotated[Optional[str], Field(default=None, description='Tenant ID')]
    bu_id: Annotated[Optional[str], Field(default=None, description='Business Unit ID')]
    contact_source_id: Annotated[Optional[str], Field(default=None, description='ID of the source to retrieve')]


class DeleteContactSourceByIdRequestSchema(BaseRequestSchema):
    tenant_id: Annotated[Optional[str], Field(default=None, description='Tenant ID')]
    bu_id: Annotated[Optional[str], Field(default=None, description='Business Unit ID')]
    contact_source_id: Annotated[Optional[str], Field(default=None, description='ID of the source to delete')]


class ListContactSourcesResponseSchema(PaginateResponseSchema):
    contact_sources: Annotated[List[ContactSourceSchema], Field(description='List of matching sources')]


class CreateContactSourceResponseSchema(BaseResponseSchema):
    contact_source: Annotated[ContactSourceSchema, Field(description='Created source')]


class CreateContactSourcesResponseSchema(BaseResponseSchema):
    contact_sources: Annotated[List[ContactSourceSchema], Field(description='Created sources')]


class UpdateContactSourceResponseSchema(BaseResponseSchema):
    contact_source: Annotated[ContactSourceSchema, Field(description='Updated source')]


class GetContactSourceByIdResponseSchema(BaseResponseSchema):
    contact_source: Annotated[ContactSourceSchema, Field(description='Retrieved source')]
