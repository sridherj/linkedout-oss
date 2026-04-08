# SPDX-License-Identifier: Apache-2.0
"""Request/response schemas for ImportJob API."""
from datetime import datetime
from enum import StrEnum
from typing import Annotated, List, Optional

from pydantic import Field

from common.schemas.base_enums_schemas import SortOrder
from common.schemas.base_request_schema import BaseRequestSchema, PaginateRequestSchema
from common.schemas.base_response_schema import BaseResponseSchema, PaginateResponseSchema
from linkedout.import_job.schemas.import_job_schema import ImportJobSchema


class ImportJobSortByFields(StrEnum):
    CREATED_AT = 'created_at'
    UPDATED_AT = 'updated_at'
    STATUS = 'status'
    SOURCE_TYPE = 'source_type'


class ListImportJobsRequestSchema(PaginateRequestSchema):
    tenant_id: Annotated[Optional[str], Field(description='Tenant ID filter', default=None)] = None
    bu_id: Annotated[Optional[str], Field(description='Business Unit ID filter', default=None)] = None
    sort_by: Annotated[ImportJobSortByFields, Field(description='Sort field', default=ImportJobSortByFields.CREATED_AT)] = ImportJobSortByFields.CREATED_AT
    sort_order: Annotated[SortOrder, Field(description='Sort order', default=SortOrder.DESC)] = SortOrder.DESC
    app_user_id: Annotated[Optional[str], Field(description='Filter by user ID', default=None)] = None
    source_type: Annotated[Optional[str], Field(description='Filter by source type', default=None)] = None
    status: Annotated[Optional[str], Field(description='Filter by status', default=None)] = None


class CreateImportJobRequestSchema(BaseRequestSchema):
    tenant_id: Annotated[Optional[str], Field(description='Tenant ID', default=None)] = None
    bu_id: Annotated[Optional[str], Field(description='Business Unit ID', default=None)] = None
    app_user_id: Annotated[str, Field(description='User who initiated the import')]
    source_type: Annotated[str, Field(description='Source of the import (e.g. linkedin_csv)')]
    file_name: Annotated[Optional[str], Field(description='Name of the uploaded file', default=None)] = None
    file_size_bytes: Annotated[Optional[int], Field(description='Size of the file in bytes', default=None)] = None
    status: Annotated[str, Field(description='Current status of the import job', default='pending')] = 'pending'
    total_records: Annotated[int, Field(description='Total records found in the source', default=0)] = 0
    parsed_count: Annotated[int, Field(description='Number of records successfully parsed', default=0)] = 0
    matched_count: Annotated[int, Field(description='Number of records matched to existing profiles', default=0)] = 0
    new_count: Annotated[int, Field(description='Number of new profiles created', default=0)] = 0
    failed_count: Annotated[int, Field(description='Number of records that failed processing', default=0)] = 0
    enrichment_queued: Annotated[int, Field(description='Number of profiles queued for enrichment', default=0)] = 0
    error_message: Annotated[Optional[str], Field(description='Overall error message if job failed', default=None)] = None
    started_at: Annotated[Optional[datetime], Field(description='Timestamp when processing started', default=None)] = None
    completed_at: Annotated[Optional[datetime], Field(description='Timestamp when processing completed', default=None)] = None


class CreateImportJobsRequestSchema(BaseRequestSchema):
    tenant_id: Optional[str] = None
    bu_id: Optional[str] = None
    import_jobs: List[CreateImportJobRequestSchema]


class UpdateImportJobRequestSchema(BaseRequestSchema):
    tenant_id: Annotated[Optional[str], Field(description='Tenant ID', default=None)] = None
    bu_id: Annotated[Optional[str], Field(description='Business Unit ID', default=None)] = None
    import_job_id: Annotated[Optional[str], Field(description='Import Job ID to update', default=None)] = None
    source_type: Annotated[Optional[str], Field(description='Source of the import', default=None)] = None
    file_name: Annotated[Optional[str], Field(description='Name of the uploaded file', default=None)] = None
    file_size_bytes: Annotated[Optional[int], Field(description='Size of the file in bytes', default=None)] = None
    status: Annotated[Optional[str], Field(description='Current status of the import job', default=None)] = None
    total_records: Annotated[Optional[int], Field(description='Total records found in the source', default=None)] = None
    parsed_count: Annotated[Optional[int], Field(description='Number of records successfully parsed', default=None)] = None
    matched_count: Annotated[Optional[int], Field(description='Number of records matched to existing profiles', default=None)] = None
    new_count: Annotated[Optional[int], Field(description='Number of new profiles created', default=None)] = None
    failed_count: Annotated[Optional[int], Field(description='Number of records that failed processing', default=None)] = None
    enrichment_queued: Annotated[Optional[int], Field(description='Number of profiles queued for enrichment', default=None)] = None
    error_message: Annotated[Optional[str], Field(description='Overall error message if job failed', default=None)] = None
    started_at: Annotated[Optional[datetime], Field(description='Timestamp when processing started', default=None)] = None
    completed_at: Annotated[Optional[datetime], Field(description='Timestamp when processing completed', default=None)] = None


class GetImportJobByIdRequestSchema(BaseRequestSchema):
    tenant_id: Optional[str] = None
    bu_id: Optional[str] = None
    import_job_id: Optional[str] = None


class DeleteImportJobByIdRequestSchema(BaseRequestSchema):
    tenant_id: Optional[str] = None
    bu_id: Optional[str] = None
    import_job_id: Optional[str] = None


class ListImportJobsResponseSchema(PaginateResponseSchema):
    import_jobs: List[ImportJobSchema]


class CreateImportJobResponseSchema(BaseResponseSchema):
    import_job: ImportJobSchema


class CreateImportJobsResponseSchema(BaseResponseSchema):
    import_jobs: List[ImportJobSchema]


class UpdateImportJobResponseSchema(BaseResponseSchema):
    import_job: ImportJobSchema


class GetImportJobByIdResponseSchema(BaseResponseSchema):
    import_job: ImportJobSchema
