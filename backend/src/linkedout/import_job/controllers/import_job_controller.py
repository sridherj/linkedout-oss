# SPDX-License-Identifier: Apache-2.0
"""Controller for ImportJob endpoints (scoped to tenant/BU)."""
import math
from typing import Annotated, Generator

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response

from common.controllers.base_controller_utils import build_pagination_links, create_service_dependency
from linkedout.import_job.schemas.import_job_api_schema import (
    CreateImportJobRequestSchema,
    CreateImportJobResponseSchema,
    CreateImportJobsRequestSchema,
    CreateImportJobsResponseSchema,
    DeleteImportJobByIdRequestSchema,
    GetImportJobByIdRequestSchema,
    GetImportJobByIdResponseSchema,
    ListImportJobsRequestSchema,
    ListImportJobsResponseSchema,
    UpdateImportJobRequestSchema,
    UpdateImportJobResponseSchema,
)
from linkedout.import_job.services.import_job_service import ImportJobService
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger

logger = get_logger(__name__)

import_jobs_router = APIRouter(
    prefix='/tenants/{tenant_id}/bus/{bu_id}/import-jobs',
    tags=['import-jobs'],
)

_META_FIELDS = [
    'sort_by', 'sort_order', 'app_user_id', 'source_type', 'status',
]


def _get_import_job_service() -> Generator[ImportJobService, None, None]:
    yield from create_service_dependency(ImportJobService, DbSessionType.READ)


def _get_write_import_job_service() -> Generator[ImportJobService, None, None]:
    yield from create_service_dependency(ImportJobService, DbSessionType.WRITE)


@import_jobs_router.get(
    '', response_model=ListImportJobsResponseSchema,
    summary='List import jobs with filtering and pagination',
)
def list_import_jobs(
    request: Request, tenant_id: str, bu_id: str,
    list_request: Annotated[ListImportJobsRequestSchema, Query()],
    service: ImportJobService = Depends(_get_import_job_service),
):
    list_request.tenant_id = tenant_id
    list_request.bu_id = bu_id

    try:
        import_jobs, total_count = service.list_entities(list_request)
        meta = {field: getattr(list_request, field, None) for field in _META_FIELDS}

        if total_count > 0:
            page_count = math.ceil(total_count / list_request.limit)
            links = build_pagination_links(
                request=request, entity_path='import-jobs',
                tenant_id=tenant_id, bu_id=bu_id,
                total=total_count, limit=list_request.limit, offset=list_request.offset,
                params=meta,
            )
            return ListImportJobsResponseSchema(
                import_jobs=import_jobs, total=total_count,
                limit=list_request.limit, offset=list_request.offset,
                page_count=page_count, links=links, meta=meta,
            )
        else:
            return ListImportJobsResponseSchema(
                import_jobs=[], total=0,
                limit=list_request.limit, offset=list_request.offset,
                page_count=1, links=None, meta=meta,
            )
    except Exception as e:
        logger.error(f'Error listing import jobs: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to list import jobs: {str(e)}')


@import_jobs_router.post(
    '', status_code=201,
    response_model=CreateImportJobResponseSchema,
    summary='Create a new import job',
)
def create_import_job(
    tenant_id: str, bu_id: str,
    create_request: Annotated[CreateImportJobRequestSchema, Body()],
    service: ImportJobService = Depends(_get_write_import_job_service),
):
    create_request.tenant_id = tenant_id
    create_request.bu_id = bu_id
    try:
        created = service.create_entity(create_request)
        return CreateImportJobResponseSchema(import_job=created)
    except Exception as e:
        logger.error(f'Error creating import job: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create import job: {str(e)}')


@import_jobs_router.post(
    '/bulk', status_code=201,
    response_model=CreateImportJobsResponseSchema,
    summary='Create multiple import jobs',
)
def create_import_jobs_bulk(
    tenant_id: str, bu_id: str,
    create_request: Annotated[CreateImportJobsRequestSchema, Body()],
    service: ImportJobService = Depends(_get_write_import_job_service),
):
    create_request.tenant_id = tenant_id
    create_request.bu_id = bu_id
    try:
        created = service.create_entities_bulk(create_request)
        return CreateImportJobsResponseSchema(import_jobs=created)
    except Exception as e:
        logger.error(f'Error creating import jobs: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to create import jobs: {str(e)}')


@import_jobs_router.patch(
    '/{import_job_id}',
    response_model=UpdateImportJobResponseSchema,
    summary='Update an import job',
)
def update_import_job(
    tenant_id: str, bu_id: str, import_job_id: str,
    update_request: Annotated[UpdateImportJobRequestSchema, Body()],
    service: ImportJobService = Depends(_get_write_import_job_service),
):
    update_request.tenant_id = tenant_id
    update_request.bu_id = bu_id
    update_request.import_job_id = import_job_id
    try:
        updated = service.update_entity(update_request)
        return UpdateImportJobResponseSchema(import_job=updated)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error updating import job: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to update import job: {str(e)}')


@import_jobs_router.get(
    '/{import_job_id}',
    response_model=GetImportJobByIdResponseSchema,
    summary='Get an import job by ID',
)
def get_import_job_by_id(
    tenant_id: str, bu_id: str, import_job_id: str,
    service: ImportJobService = Depends(_get_import_job_service),
):
    get_request = GetImportJobByIdRequestSchema(
        tenant_id=tenant_id, bu_id=bu_id, import_job_id=import_job_id
    )
    try:
        import_job = service.get_entity_by_id(get_request)
        if not import_job:
            raise HTTPException(status_code=404, detail=f'Import job with ID {import_job_id} not found')
        return GetImportJobByIdResponseSchema(import_job=import_job)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error getting import job {import_job_id}: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to get import job: {str(e)}')


@import_jobs_router.delete(
    '/{import_job_id}', status_code=204,
    summary='Delete an import job by ID',
)
def delete_import_job_by_id(
    tenant_id: str, bu_id: str, import_job_id: str,
    service: ImportJobService = Depends(_get_write_import_job_service),
):
    delete_request = DeleteImportJobByIdRequestSchema(
        tenant_id=tenant_id, bu_id=bu_id, import_job_id=import_job_id
    )
    try:
        service.delete_entity_by_id(delete_request)
        return Response(status_code=204)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f'Error deleting import job {import_job_id}: {str(e)}')
        raise HTTPException(status_code=500, detail=f'Failed to delete import job: {str(e)}')
