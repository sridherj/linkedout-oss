# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for SearchSessionService."""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec

from sqlalchemy.orm import Session

from linkedout.search_session.entities.search_session_entity import SearchSessionEntity
from linkedout.search_session.repositories.search_session_repository import SearchSessionRepository
from linkedout.search_session.services.search_session_service import SearchSessionService
from linkedout.search_session.schemas.search_session_schema import SearchSessionSchema
from linkedout.search_session.schemas.search_session_api_schema import (
    CreateSearchSessionRequestSchema,
    ListSearchSessionsRequestSchema,
    UpdateSearchSessionRequestSchema,
)


@pytest.fixture
def mock_session():
    return create_autospec(Session, instance=True, spec_set=True)


@pytest.fixture
def mock_repository():
    return create_autospec(SearchSessionRepository, instance=True, spec_set=True)


@pytest.fixture
def service(mock_session, mock_repository):
    svc = SearchSessionService(mock_session)
    svc._repository = mock_repository
    return svc


@pytest.fixture
def mock_entity():
    entity = SearchSessionEntity(
        tenant_id='t_1',
        bu_id='bu_1',
        app_user_id='au_1',
        initial_query='find senior engineers',
    )
    entity.id = 'ss_test123'
    entity.turn_count = 1
    entity.last_active_at = datetime.now(timezone.utc)
    entity.is_saved = False
    entity.saved_name = None
    entity.created_at = datetime.now(timezone.utc)
    entity.updated_at = datetime.now(timezone.utc)
    return entity


class TestSearchSessionServiceWiring:
    def test_can_instantiate(self, mock_session):
        svc = SearchSessionService(mock_session)
        assert svc is not None

    def test_repository_created(self, mock_session):
        svc = SearchSessionService(mock_session)
        assert isinstance(svc._repository, SearchSessionRepository)

    def test_has_crud_methods(self, mock_session):
        svc = SearchSessionService(mock_session)
        assert hasattr(svc, 'list_entities')
        assert hasattr(svc, 'create_entity')
        assert hasattr(svc, 'create_entities_bulk')
        assert hasattr(svc, 'update_entity')
        assert hasattr(svc, 'get_entity_by_id')
        assert hasattr(svc, 'delete_entity_by_id')

    def test_entity_class_configured(self, mock_session):
        svc = SearchSessionService(mock_session)
        assert svc._entity_class is SearchSessionEntity

    def test_entity_name_configured(self, mock_session):
        svc = SearchSessionService(mock_session)
        assert svc._entity_name == 'search_session'


class TestSearchSessionServiceList:
    def test_list_calls_repository(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        req = ListSearchSessionsRequestSchema(tenant_id='t_1', bu_id='bu_1')
        items, count = service.list_entities(req)
        assert items == []
        assert count == 0
        mock_repository.list_with_filters.assert_called_once()
        mock_repository.count_with_filters.assert_called_once()

    def test_list_passes_filters(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        req = ListSearchSessionsRequestSchema(
            tenant_id='t_1', bu_id='bu_1',
            app_user_id='au_1',
        )
        service.list_entities(req)

        call_kwargs = mock_repository.list_with_filters.call_args
        assert call_kwargs.kwargs['app_user_id'] == 'au_1'

    def test_list_returns_schemas(self, service, mock_repository, mock_entity):
        mock_repository.list_with_filters.return_value = [mock_entity]
        mock_repository.count_with_filters.return_value = 1

        req = ListSearchSessionsRequestSchema(tenant_id='t_1', bu_id='bu_1')
        items, count = service.list_entities(req)
        assert count == 1
        assert len(items) == 1
        assert isinstance(items[0], SearchSessionSchema)
        assert items[0].id == 'ss_test123'


class TestSearchSessionServiceCreate:
    def test_creates_entity(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateSearchSessionRequestSchema(
            tenant_id='t_1', bu_id='bu_1',
            app_user_id='au_1',
            initial_query='find senior engineers',
        )
        result = service.create_entity(req)
        assert isinstance(result, SearchSessionSchema)
        assert result.app_user_id == 'au_1'
        mock_repository.create.assert_called_once()

    def test_create_maps_all_fields(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateSearchSessionRequestSchema(
            tenant_id='t_1', bu_id='bu_1',
            app_user_id='au_1',
            initial_query='find senior engineers',
            turn_count=3,
        )
        service.create_entity(req)

        created_entity = mock_repository.create.call_args[0][0]
        assert created_entity.app_user_id == 'au_1'
        assert created_entity.initial_query == 'find senior engineers'
        assert created_entity.turn_count == 3


class TestSearchSessionServiceUpdate:
    def test_update_provided_fields(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        req = UpdateSearchSessionRequestSchema(
            tenant_id='t_1', bu_id='bu_1', search_session_id='ss_test123',
            turn_count=5,
        )
        service.update_entity(req)
        assert mock_entity.turn_count == 5

    def test_update_none_does_not_change(self, service, mock_repository, mock_entity):
        mock_entity.turn_count = 1
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        req = UpdateSearchSessionRequestSchema(
            tenant_id='t_1', bu_id='bu_1', search_session_id='ss_test123',
        )
        service.update_entity(req)
        assert mock_entity.turn_count == 1

    def test_update_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        req = UpdateSearchSessionRequestSchema(
            tenant_id='t_1', bu_id='bu_1', search_session_id='ss_nonexistent',
            turn_count=5,
        )
        with pytest.raises(ValueError, match='not found'):
            service.update_entity(req)


class TestSearchSessionServiceDelete:
    def test_delete_calls_repository(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity

        from linkedout.search_session.schemas.search_session_api_schema import DeleteSearchSessionByIdRequestSchema
        req = DeleteSearchSessionByIdRequestSchema(
            tenant_id='t_1', bu_id='bu_1', search_session_id='ss_test123',
        )
        service.delete_entity_by_id(req)
        mock_repository.delete.assert_called_once_with(mock_entity)

    def test_delete_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        from linkedout.search_session.schemas.search_session_api_schema import DeleteSearchSessionByIdRequestSchema
        req = DeleteSearchSessionByIdRequestSchema(
            tenant_id='t_1', bu_id='bu_1', search_session_id='ss_nonexistent',
        )
        with pytest.raises(ValueError, match='not found'):
            service.delete_entity_by_id(req)
