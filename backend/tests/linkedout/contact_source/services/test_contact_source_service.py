# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for ContactSourceService."""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec

from sqlalchemy.orm import Session

from linkedout.contact_source.entities.contact_source_entity import ContactSourceEntity
from linkedout.contact_source.repositories.contact_source_repository import ContactSourceRepository
from linkedout.contact_source.services.contact_source_service import ContactSourceService
from linkedout.contact_source.schemas.contact_source_schema import ContactSourceSchema
from linkedout.contact_source.schemas.contact_source_api_schema import (
    CreateContactSourceRequestSchema,
    DeleteContactSourceByIdRequestSchema,
    ListContactSourcesRequestSchema,
    UpdateContactSourceRequestSchema,
)


@pytest.fixture
def mock_session():
    return create_autospec(Session, instance=True, spec_set=True)


@pytest.fixture
def mock_repository():
    return create_autospec(ContactSourceRepository, instance=True, spec_set=True)


@pytest.fixture
def service(mock_session, mock_repository):
    svc = ContactSourceService(mock_session)
    svc._repository = mock_repository
    return svc


@pytest.fixture
def mock_entity():
    entity = ContactSourceEntity(
        tenant_id='t_1',
        bu_id='bu_1',
        app_user_id='au_1',
        import_job_id='ij_1',
        source_type='linkedin_csv',
        dedup_status='pending',
    )
    entity.id = 'cs_test123'
    entity.source_file_name = None
    entity.first_name = 'John'
    entity.last_name = 'Doe'
    entity.full_name = 'John Doe'
    entity.email = 'john@example.com'
    entity.phone = None
    entity.company = 'Acme Inc'
    entity.title = 'Engineer'
    entity.linkedin_url = None
    entity.connected_at = None
    entity.raw_record = None
    entity.connection_id = None
    entity.dedup_method = None
    entity.dedup_confidence = None
    entity.created_at = datetime.now(timezone.utc)
    entity.updated_at = datetime.now(timezone.utc)
    return entity


class TestContactSourceServiceWiring:
    def test_can_instantiate(self, mock_session):
        svc = ContactSourceService(mock_session)
        assert svc is not None

    def test_repository_created(self, mock_session):
        svc = ContactSourceService(mock_session)
        assert isinstance(svc._repository, ContactSourceRepository)

    def test_has_crud_methods(self, mock_session):
        svc = ContactSourceService(mock_session)
        assert hasattr(svc, 'list_entities')
        assert hasattr(svc, 'create_entity')
        assert hasattr(svc, 'create_entities_bulk')
        assert hasattr(svc, 'update_entity')
        assert hasattr(svc, 'get_entity_by_id')
        assert hasattr(svc, 'delete_entity_by_id')


class TestContactSourceServiceList:
    def test_list_calls_repository(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        req = ListContactSourcesRequestSchema(tenant_id='t_1', bu_id='bu_1')
        items, count = service.list_entities(req)
        assert items == []
        assert count == 0
        mock_repository.list_with_filters.assert_called_once()
        mock_repository.count_with_filters.assert_called_once()

    def test_list_passes_filters(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        req = ListContactSourcesRequestSchema(
            tenant_id='t_1', bu_id='bu_1',
            app_user_id='au_1',
            import_job_id='ij_1',
            source_type='linkedin_csv',
            dedup_status='pending',
            connection_id='conn_1',
        )
        service.list_entities(req)

        call_kwargs = mock_repository.list_with_filters.call_args
        assert call_kwargs.kwargs['app_user_id'] == 'au_1'
        assert call_kwargs.kwargs['import_job_id'] == 'ij_1'
        assert call_kwargs.kwargs['source_type'] == 'linkedin_csv'
        assert call_kwargs.kwargs['dedup_status'] == 'pending'
        assert call_kwargs.kwargs['connection_id'] == 'conn_1'

    def test_list_returns_schemas(self, service, mock_repository, mock_entity):
        mock_repository.list_with_filters.return_value = [mock_entity]
        mock_repository.count_with_filters.return_value = 1

        req = ListContactSourcesRequestSchema(tenant_id='t_1', bu_id='bu_1')
        items, count = service.list_entities(req)
        assert count == 1
        assert len(items) == 1
        assert isinstance(items[0], ContactSourceSchema)
        assert items[0].id == 'cs_test123'


class TestContactSourceServiceCreate:
    def test_creates_entity(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateContactSourceRequestSchema(
            tenant_id='t_1', bu_id='bu_1',
            app_user_id='au_1',
            import_job_id='ij_1',
            source_type='linkedin_csv',
        )
        result = service.create_entity(req)
        assert isinstance(result, ContactSourceSchema)
        assert result.app_user_id == 'au_1'
        mock_repository.create.assert_called_once()

    def test_create_maps_all_fields(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateContactSourceRequestSchema(
            tenant_id='t_1', bu_id='bu_1',
            app_user_id='au_1',
            import_job_id='ij_1',
            source_type='linkedin_csv',
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            company='Acme Inc',
        )
        service.create_entity(req)

        created_entity = mock_repository.create.call_args[0][0]
        assert created_entity.app_user_id == 'au_1'
        assert created_entity.import_job_id == 'ij_1'
        assert created_entity.source_type == 'linkedin_csv'
        assert created_entity.first_name == 'John'
        assert created_entity.last_name == 'Doe'
        assert created_entity.email == 'john@example.com'
        assert created_entity.company == 'Acme Inc'


class TestContactSourceServiceUpdate:
    def test_update_provided_fields(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        req = UpdateContactSourceRequestSchema(
            tenant_id='t_1', bu_id='bu_1', contact_source_id='cs_test123',
            dedup_status='matched',
        )
        service.update_entity(req)
        assert mock_entity.dedup_status == 'matched'

    def test_update_none_does_not_change(self, service, mock_repository, mock_entity):
        mock_entity.dedup_status = 'pending'
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        req = UpdateContactSourceRequestSchema(
            tenant_id='t_1', bu_id='bu_1', contact_source_id='cs_test123',
        )
        service.update_entity(req)
        assert mock_entity.dedup_status == 'pending'

    def test_update_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        req = UpdateContactSourceRequestSchema(
            tenant_id='t_1', bu_id='bu_1', contact_source_id='cs_nonexistent',
            dedup_status='matched',
        )
        with pytest.raises(ValueError, match='not found'):
            service.update_entity(req)


class TestContactSourceServiceDelete:
    def test_delete_calls_repository(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity

        req = DeleteContactSourceByIdRequestSchema(
            tenant_id='t_1', bu_id='bu_1', contact_source_id='cs_test123',
        )
        service.delete_entity_by_id(req)
        mock_repository.delete.assert_called_once_with(mock_entity)

    def test_delete_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        req = DeleteContactSourceByIdRequestSchema(
            tenant_id='t_1', bu_id='bu_1', contact_source_id='cs_nonexistent',
        )
        with pytest.raises(ValueError, match='not found'):
            service.delete_entity_by_id(req)
