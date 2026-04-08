# SPDX-License-Identifier: Apache-2.0
"""Service for ImportJob entity."""
from typing import Any

from common.services.base_service import BaseService
from linkedout.import_job.entities.import_job_entity import ImportJobEntity
from linkedout.import_job.repositories.import_job_repository import ImportJobRepository
from linkedout.import_job.schemas.import_job_schema import ImportJobSchema


class ImportJobService(BaseService[ImportJobEntity, ImportJobSchema, ImportJobRepository]):
    _repository_class = ImportJobRepository
    _schema_class = ImportJobSchema
    _entity_class = ImportJobEntity
    _entity_name = 'import_job'
    _entity_id_field = 'import_job_id'

    def _extract_filter_kwargs(self, list_request: Any) -> dict:
        return {
            'app_user_id': list_request.app_user_id,
            'source_type': list_request.source_type,
            'status': list_request.status,
        }

    def _create_entity_from_request(self, create_request: Any) -> ImportJobEntity:
        return ImportJobEntity(
            tenant_id=create_request.tenant_id,
            bu_id=create_request.bu_id,
            app_user_id=create_request.app_user_id,
            source_type=create_request.source_type,
            file_name=create_request.file_name,
            file_size_bytes=create_request.file_size_bytes,
            status=create_request.status,
            total_records=create_request.total_records,
            parsed_count=create_request.parsed_count,
            matched_count=create_request.matched_count,
            new_count=create_request.new_count,
            failed_count=create_request.failed_count,
            enrichment_queued=create_request.enrichment_queued,
            error_message=create_request.error_message,
            started_at=create_request.started_at,
            completed_at=create_request.completed_at,
        )

    def _update_entity_from_request(self, entity: ImportJobEntity, update_request: Any) -> None:
        if update_request.source_type is not None:
            entity.source_type = update_request.source_type
        if update_request.file_name is not None:
            entity.file_name = update_request.file_name
        if update_request.file_size_bytes is not None:
            entity.file_size_bytes = update_request.file_size_bytes
        if update_request.status is not None:
            entity.status = update_request.status
        if update_request.total_records is not None:
            entity.total_records = update_request.total_records
        if update_request.parsed_count is not None:
            entity.parsed_count = update_request.parsed_count
        if update_request.matched_count is not None:
            entity.matched_count = update_request.matched_count
        if update_request.new_count is not None:
            entity.new_count = update_request.new_count
        if update_request.failed_count is not None:
            entity.failed_count = update_request.failed_count
        if update_request.enrichment_queued is not None:
            entity.enrichment_queued = update_request.enrichment_queued
        if update_request.error_message is not None:
            entity.error_message = update_request.error_message
        if update_request.started_at is not None:
            entity.started_at = update_request.started_at
        if update_request.completed_at is not None:
            entity.completed_at = update_request.completed_at
