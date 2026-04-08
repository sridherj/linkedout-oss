# SPDX-License-Identifier: Apache-2.0
"""Service for ContactSource entity."""
from typing import Any

from common.services.base_service import BaseService
from linkedout.contact_source.entities.contact_source_entity import ContactSourceEntity
from linkedout.contact_source.repositories.contact_source_repository import ContactSourceRepository
from linkedout.contact_source.schemas.contact_source_schema import ContactSourceSchema


class ContactSourceService(BaseService[ContactSourceEntity, ContactSourceSchema, ContactSourceRepository]):
    _repository_class = ContactSourceRepository
    _schema_class = ContactSourceSchema
    _entity_class = ContactSourceEntity
    _entity_name = 'contact_source'
    _entity_id_field = 'contact_source_id'

    def _extract_filter_kwargs(self, list_request: Any) -> dict:
        return {
            'app_user_id': list_request.app_user_id,
            'import_job_id': list_request.import_job_id,
            'source_type': list_request.source_type,
            'dedup_status': list_request.dedup_status,
            'connection_id': list_request.connection_id,
        }

    def _create_entity_from_request(self, create_request: Any) -> ContactSourceEntity:
        return ContactSourceEntity(
            tenant_id=create_request.tenant_id,
            bu_id=create_request.bu_id,
            app_user_id=create_request.app_user_id,
            import_job_id=create_request.import_job_id,
            source_type=create_request.source_type,
            source_file_name=create_request.source_file_name,
            first_name=create_request.first_name,
            last_name=create_request.last_name,
            full_name=create_request.full_name,
            email=create_request.email,
            phone=create_request.phone,
            company=create_request.company,
            title=create_request.title,
            linkedin_url=create_request.linkedin_url,
            connected_at=create_request.connected_at,
            raw_record=create_request.raw_record,
            connection_id=create_request.connection_id,
            dedup_status=create_request.dedup_status,
            dedup_method=create_request.dedup_method,
            dedup_confidence=create_request.dedup_confidence,
        )

    def _update_entity_from_request(self, entity: ContactSourceEntity, update_request: Any) -> None:
        if update_request.source_type is not None:
            entity.source_type = update_request.source_type
        if update_request.source_file_name is not None:
            entity.source_file_name = update_request.source_file_name
        if update_request.first_name is not None:
            entity.first_name = update_request.first_name
        if update_request.last_name is not None:
            entity.last_name = update_request.last_name
        if update_request.full_name is not None:
            entity.full_name = update_request.full_name
        if update_request.email is not None:
            entity.email = update_request.email
        if update_request.phone is not None:
            entity.phone = update_request.phone
        if update_request.company is not None:
            entity.company = update_request.company
        if update_request.title is not None:
            entity.title = update_request.title
        if update_request.linkedin_url is not None:
            entity.linkedin_url = update_request.linkedin_url
        if update_request.connected_at is not None:
            entity.connected_at = update_request.connected_at
        if update_request.raw_record is not None:
            entity.raw_record = update_request.raw_record
        if update_request.connection_id is not None:
            entity.connection_id = update_request.connection_id
        if update_request.dedup_status is not None:
            entity.dedup_status = update_request.dedup_status
        if update_request.dedup_method is not None:
            entity.dedup_method = update_request.dedup_method
        if update_request.dedup_confidence is not None:
            entity.dedup_confidence = update_request.dedup_confidence
