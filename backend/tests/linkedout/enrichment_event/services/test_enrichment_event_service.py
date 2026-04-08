# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for EnrichmentEventService."""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec

from sqlalchemy.orm import Session

from linkedout.enrichment_event.entities.enrichment_event_entity import EnrichmentEventEntity
from linkedout.enrichment_event.repositories.enrichment_event_repository import EnrichmentEventRepository
from linkedout.enrichment_event.services.enrichment_event_service import EnrichmentEventService
from linkedout.enrichment_event.schemas.enrichment_event_schema import EnrichmentEventSchema
from linkedout.enrichment_event.schemas.enrichment_event_api_schema import (
    CreateEnrichmentEventRequestSchema,
    ListEnrichmentEventsRequestSchema,
    UpdateEnrichmentEventRequestSchema,
)


@pytest.fixture
def mock_session():
    return create_autospec(Session, instance=True, spec_set=True)


@pytest.fixture
def mock_repository():
    return create_autospec(EnrichmentEventRepository, instance=True, spec_set=True)


@pytest.fixture
def service(mock_session, mock_repository):
    svc = EnrichmentEventService(mock_session)
    svc._repository = mock_repository
    return svc


@pytest.fixture
def mock_entity():
    entity = EnrichmentEventEntity(
        tenant_id='t_1',
        bu_id='bu_1',
        app_user_id='au_1',
        crawled_profile_id='cp_1',
        event_type='crawled',
        enrichment_mode='platform',
    )
    entity.id = 'ee_test123'
    entity.crawler_name = None
    entity.cost_estimate_usd = 0
    entity.crawler_run_id = None
    entity.created_at = datetime.now(timezone.utc)
    entity.updated_at = datetime.now(timezone.utc)
    return entity


class TestEnrichmentEventServiceWiring:
    def test_can_instantiate(self, mock_session):
        svc = EnrichmentEventService(mock_session)
        assert svc is not None

    def test_repository_created(self, mock_session):
        svc = EnrichmentEventService(mock_session)
        assert isinstance(svc._repository, EnrichmentEventRepository)

    def test_has_crud_methods(self, mock_session):
        svc = EnrichmentEventService(mock_session)
        assert hasattr(svc, 'list_entities')
        assert hasattr(svc, 'create_entity')
        assert hasattr(svc, 'create_entities_bulk')
        assert hasattr(svc, 'update_entity')
        assert hasattr(svc, 'get_entity_by_id')
        assert hasattr(svc, 'delete_entity_by_id')


class TestEnrichmentEventServiceList:
    def test_list_calls_repository(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        req = ListEnrichmentEventsRequestSchema(tenant_id='t_1', bu_id='bu_1')
        items, count = service.list_entities(req)
        assert items == []
        assert count == 0
        mock_repository.list_with_filters.assert_called_once()
        mock_repository.count_with_filters.assert_called_once()

    def test_list_passes_filters(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        req = ListEnrichmentEventsRequestSchema(
            tenant_id='t_1', bu_id='bu_1',
            app_user_id='au_1',
            event_type='crawled',
        )
        service.list_entities(req)

        call_kwargs = mock_repository.list_with_filters.call_args
        assert call_kwargs.kwargs['app_user_id'] == 'au_1'
        assert call_kwargs.kwargs['event_type'] == 'crawled'

    def test_list_returns_schemas(self, service, mock_repository, mock_entity):
        mock_repository.list_with_filters.return_value = [mock_entity]
        mock_repository.count_with_filters.return_value = 1

        req = ListEnrichmentEventsRequestSchema(tenant_id='t_1', bu_id='bu_1')
        items, count = service.list_entities(req)
        assert count == 1
        assert len(items) == 1
        assert isinstance(items[0], EnrichmentEventSchema)
        assert items[0].id == 'ee_test123'


class TestEnrichmentEventServiceCreate:
    def test_creates_entity(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateEnrichmentEventRequestSchema(
            tenant_id='t_1', bu_id='bu_1',
            app_user_id='au_1',
            crawled_profile_id='cp_1',
            event_type='crawled',
            enrichment_mode='platform',
        )
        result = service.create_entity(req)
        assert isinstance(result, EnrichmentEventSchema)
        assert result.app_user_id == 'au_1'
        mock_repository.create.assert_called_once()

    def test_create_maps_all_fields(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateEnrichmentEventRequestSchema(
            tenant_id='t_1', bu_id='bu_1',
            app_user_id='au_1',
            crawled_profile_id='cp_1',
            event_type='crawled',
            enrichment_mode='platform',
            crawler_name='bright_data',
            cost_estimate_usd=0.05,
        )
        service.create_entity(req)

        created_entity = mock_repository.create.call_args[0][0]
        assert created_entity.app_user_id == 'au_1'
        assert created_entity.crawled_profile_id == 'cp_1'
        assert created_entity.event_type == 'crawled'
        assert created_entity.enrichment_mode == 'platform'
        assert created_entity.crawler_name == 'bright_data'
        assert created_entity.cost_estimate_usd == 0.05


class TestEnrichmentEventServiceUpdate:
    def test_update_provided_fields(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        req = UpdateEnrichmentEventRequestSchema(
            tenant_id='t_1', bu_id='bu_1', enrichment_event_id='ee_test123',
            event_type='failed',
        )
        service.update_entity(req)
        assert mock_entity.event_type == 'failed'

    def test_update_none_does_not_change(self, service, mock_repository, mock_entity):
        mock_entity.event_type = 'crawled'
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        req = UpdateEnrichmentEventRequestSchema(
            tenant_id='t_1', bu_id='bu_1', enrichment_event_id='ee_test123',
        )
        service.update_entity(req)
        assert mock_entity.event_type == 'crawled'

    def test_update_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        req = UpdateEnrichmentEventRequestSchema(
            tenant_id='t_1', bu_id='bu_1', enrichment_event_id='ee_nonexistent',
            event_type='failed',
        )
        with pytest.raises(ValueError, match='not found'):
            service.update_entity(req)


class TestEnrichmentEventServiceDelete:
    def test_delete_calls_repository(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity

        from linkedout.enrichment_event.schemas.enrichment_event_api_schema import DeleteEnrichmentEventByIdRequestSchema
        req = DeleteEnrichmentEventByIdRequestSchema(
            tenant_id='t_1', bu_id='bu_1', enrichment_event_id='ee_test123',
        )
        service.delete_entity_by_id(req)
        mock_repository.delete.assert_called_once_with(mock_entity)

    def test_delete_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        from linkedout.enrichment_event.schemas.enrichment_event_api_schema import DeleteEnrichmentEventByIdRequestSchema
        req = DeleteEnrichmentEventByIdRequestSchema(
            tenant_id='t_1', bu_id='bu_1', enrichment_event_id='ee_nonexistent',
        )
        with pytest.raises(ValueError, match='not found'):
            service.delete_entity_by_id(req)
