# SPDX-License-Identifier: Apache-2.0
"""Import pipeline controller — thin, delegates to ImportService."""
from __future__ import annotations

from typing import Generator

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from common.controllers.base_controller_utils import create_service_dependency
from linkedout.import_pipeline.service import ImportService
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger

logger = get_logger(__name__)

import_pipeline_router = APIRouter(
    prefix='/tenants/{tenant_id}/bus/{bu_id}/import',
    tags=['import-pipeline'],
)


def _get_import_service() -> Generator[ImportService, None, None]:
    yield from create_service_dependency(ImportService, DbSessionType.WRITE)


@import_pipeline_router.post(
    '',
    summary='Upload a CSV file for import',
    status_code=200,
)
def upload_import(
    tenant_id: str,
    bu_id: str,
    file: UploadFile = File(...),
    source_type: str | None = Form(None),
    app_user_id: str = Form(...),
    service: ImportService = Depends(_get_import_service),
):
    """Upload a CSV and run the import pipeline (parse → dedup → merge)."""
    try:
        result = service.process_import(
            file=file.file,
            file_name=file.filename or 'unknown.csv',
            tenant_id=tenant_id,
            bu_id=bu_id,
            app_user_id=app_user_id,
            source_type=source_type,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f'Import failed: {e}')
        raise HTTPException(status_code=500, detail=f'Import failed: {str(e)[:200]}')

    if result.get('error') == 'conflict':
        raise HTTPException(status_code=409, detail=result['message'])

    return result


def _get_read_import_service() -> Generator[ImportService, None, None]:
    yield from create_service_dependency(ImportService, DbSessionType.READ)


@import_pipeline_router.get(
    '-jobs/{job_id}',
    summary='Get import job status and counters',
)
def get_import_job_status(
    tenant_id: str,
    bu_id: str,
    job_id: str,
    service: ImportService = Depends(_get_read_import_service),
):
    """Get current ImportJob status + counters."""
    job = service.get_import_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f'Import job {job_id} not found')
    return {
        'import_job_id': job.id,
        'status': job.status,
        'total_records': job.total_records,
        'parsed_count': job.parsed_count,
        'matched_count': job.matched_count,
        'new_count': job.new_count,
        'failed_count': job.failed_count,
    }
