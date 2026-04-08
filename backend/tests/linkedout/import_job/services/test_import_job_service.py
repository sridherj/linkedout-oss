# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for ImportJobService."""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec

from sqlalchemy.orm import Session

from linkedout.import_job.entities.import_job_entity import ImportJobEntity
from linkedout.import_job.repositories.import_job_repository import ImportJobRepository
from linkedout.import_job.services.import_job_service import ImportJobService
from linkedout.import_job.schemas.import_job_schema import ImportJobSchema
from linkedout.import_job.schemas.import_job_api_schema import (
    CreateImportJobRequestSchema,
    DeleteImportJobByIdRequestSchema,
    ListImportJobsRequestSchema,
    UpdateImportJobRequestSchema,
)


@pytest.fixture
def mock_session():
    return create_autospec(Session, instance=True, spec_set=True)


@pytest.fixture
def mock_repository():
    return create_autospec(ImportJobRepository, instance=True, spec_set=True)


@pytest.fixture
def service(mock_session, mock_repository):
    svc = ImportJobService(mock_session)
    svc._repository = mock_repository
    return svc


@pytest.fixture
def mock_entity():
    entity = ImportJobEntity(
        tenant_id='t_1',
        bu_id='bu_1',
        app_user_id='au_1',
        source_type='linkedin_csv',
        status='pending',
    )
    entity.id = 'ij_test123'
    entity.file_name = None
    entity.file_size_bytes = None
    entity.total_records = 0
    entity.parsed_count = 0
    entity.matched_count = 0
    entity.new_count = 0
    entity.failed_count = 0
    entity.enrichment_queued = 0
    entity.error_message = None
    entity.started_at = None
    entity.completed_at = None
    entity.created_at = datetime.now(timezone.utc)
    entity.updated_at = datetime.now(timezone.utc)
    return entity


class TestImportJobServiceWiring:
    def test_can_instantiate(self, mock_session):
        svc = ImportJobService(mock_session)
        assert svc is not None

    def test_repository_created(self, mock_session):
        svc = ImportJobService(mock_session)
        assert isinstance(svc._repository, ImportJobRepository)

    def test_has_crud_methods(self, mock_session):
        svc = ImportJobService(mock_session)
        assert hasattr(svc, 'list_entities')
        assert hasattr(svc, 'create_entity')
        assert hasattr(svc, 'create_entities_bulk')
        assert hasattr(svc, 'update_entity')
        assert hasattr(svc, 'get_entity_by_id')
        assert hasattr(svc, 'delete_entity_by_id')


class TestImportJobServiceList:
    def test_list_calls_repository(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        req = ListImportJobsRequestSchema(tenant_id='t_1', bu_id='bu_1')
        items, count = service.list_entities(req)
        assert items == []
        assert count == 0
        mock_repository.list_with_filters.assert_called_once()
        mock_repository.count_with_filters.assert_called_once()

    def test_list_passes_filters(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        req = ListImportJobsRequestSchema(
            tenant_id='t_1', bu_id='bu_1',
            app_user_id='au_1',
            source_type='linkedin_csv',
            status='pending',
        )
        service.list_entities(req)

        call_kwargs = mock_repository.list_with_filters.call_args
        assert call_kwargs.kwargs['app_user_id'] == 'au_1'
        assert call_kwargs.kwargs['source_type'] == 'linkedin_csv'
        assert call_kwargs.kwargs['status'] == 'pending'

    def test_list_returns_schemas(self, service, mock_repository, mock_entity):
        mock_repository.list_with_filters.return_value = [mock_entity]
        mock_repository.count_with_filters.return_value = 1

        req = ListImportJobsRequestSchema(tenant_id='t_1', bu_id='bu_1')
        items, count = service.list_entities(req)
        assert count == 1
        assert len(items) == 1
        assert isinstance(items[0], ImportJobSchema)
        assert items[0].id == 'ij_test123'


class TestImportJobServiceCreate:
    def test_creates_entity(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateImportJobRequestSchema(
            tenant_id='t_1', bu_id='bu_1',
            app_user_id='au_1',
            source_type='linkedin_csv',
        )
        result = service.create_entity(req)
        assert isinstance(result, ImportJobSchema)
        assert result.app_user_id == 'au_1'
        mock_repository.create.assert_called_once()

    def test_create_maps_all_fields(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateImportJobRequestSchema(
            tenant_id='t_1', bu_id='bu_1',
            app_user_id='au_1',
            source_type='google_contacts',
            file_name='contacts.csv',
            file_size_bytes=1024,
        )
        service.create_entity(req)

        created_entity = mock_repository.create.call_args[0][0]
        assert created_entity.app_user_id == 'au_1'
        assert created_entity.source_type == 'google_contacts'
        assert created_entity.file_name == 'contacts.csv'
        assert created_entity.file_size_bytes == 1024


class TestImportJobServiceUpdate:
    def test_update_provided_fields(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        req = UpdateImportJobRequestSchema(
            tenant_id='t_1', bu_id='bu_1', import_job_id='ij_test123',
            status='parsing',
        )
        service.update_entity(req)
        assert mock_entity.status == 'parsing'

    def test_update_none_does_not_change(self, service, mock_repository, mock_entity):
        mock_entity.status = 'pending'
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        req = UpdateImportJobRequestSchema(
            tenant_id='t_1', bu_id='bu_1', import_job_id='ij_test123',
        )
        service.update_entity(req)
        assert mock_entity.status == 'pending'

    def test_update_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        req = UpdateImportJobRequestSchema(
            tenant_id='t_1', bu_id='bu_1', import_job_id='ij_nonexistent',
            status='parsing',
        )
        with pytest.raises(ValueError, match='not found'):
            service.update_entity(req)


class TestImportJobServiceDelete:
    def test_delete_calls_repository(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity

        req = DeleteImportJobByIdRequestSchema(
            tenant_id='t_1', bu_id='bu_1', import_job_id='ij_test123',
        )
        service.delete_entity_by_id(req)
        mock_repository.delete.assert_called_once_with(mock_entity)

    def test_delete_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        req = DeleteImportJobByIdRequestSchema(
            tenant_id='t_1', bu_id='bu_1', import_job_id='ij_nonexistent',
        )
        with pytest.raises(ValueError, match='not found'):
            service.delete_entity_by_id(req)
