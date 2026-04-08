# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for SearchTurnService."""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec

from sqlalchemy.orm import Session

from linkedout.search_session.entities.search_turn_entity import SearchTurnEntity
from linkedout.search_session.repositories.search_turn_repository import SearchTurnRepository
from linkedout.search_session.services.search_turn_service import SearchTurnService
from linkedout.search_session.schemas.search_turn_schema import SearchTurnSchema
from linkedout.search_session.schemas.search_turn_api_schema import (
    CreateSearchTurnRequestSchema,
    ListSearchTurnsRequestSchema,
    UpdateSearchTurnRequestSchema,
)


@pytest.fixture
def mock_session():
    return create_autospec(Session, instance=True, spec_set=True)


@pytest.fixture
def mock_repository():
    return create_autospec(SearchTurnRepository, instance=True, spec_set=True)


@pytest.fixture
def service(mock_session, mock_repository):
    svc = SearchTurnService(mock_session)
    svc._repository = mock_repository
    return svc


@pytest.fixture
def mock_entity():
    entity = SearchTurnEntity(
        tenant_id='t_1',
        bu_id='bu_1',
        session_id='ss_test123',
        turn_number=1,
        user_query='find senior engineers',
    )
    entity.id = 'sturn_test123'
    entity.transcript = None
    entity.results = None
    entity.summary = None
    entity.created_at = datetime.now(timezone.utc)
    entity.updated_at = datetime.now(timezone.utc)
    return entity


class TestSearchTurnServiceWiring:
    def test_can_instantiate(self, mock_session):
        svc = SearchTurnService(mock_session)
        assert svc is not None

    def test_repository_created(self, mock_session):
        svc = SearchTurnService(mock_session)
        assert isinstance(svc._repository, SearchTurnRepository)

    def test_has_crud_methods(self, mock_session):
        svc = SearchTurnService(mock_session)
        assert hasattr(svc, 'list_entities')
        assert hasattr(svc, 'create_entity')
        assert hasattr(svc, 'create_entities_bulk')
        assert hasattr(svc, 'update_entity')
        assert hasattr(svc, 'get_entity_by_id')
        assert hasattr(svc, 'delete_entity_by_id')

    def test_entity_class_configured(self, mock_session):
        svc = SearchTurnService(mock_session)
        assert svc._entity_class is SearchTurnEntity

    def test_entity_name_configured(self, mock_session):
        svc = SearchTurnService(mock_session)
        assert svc._entity_name == 'search_turn'


class TestSearchTurnServiceList:
    def test_list_calls_repository(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        req = ListSearchTurnsRequestSchema(tenant_id='t_1', bu_id='bu_1')
        items, count = service.list_entities(req)
        assert items == []
        assert count == 0
        mock_repository.list_with_filters.assert_called_once()
        mock_repository.count_with_filters.assert_called_once()

    def test_list_passes_filters(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        req = ListSearchTurnsRequestSchema(
            tenant_id='t_1', bu_id='bu_1',
            session_id='ss_test123',
        )
        service.list_entities(req)

        call_kwargs = mock_repository.list_with_filters.call_args
        assert call_kwargs.kwargs['session_id'] == 'ss_test123'

    def test_list_returns_schemas(self, service, mock_repository, mock_entity):
        mock_repository.list_with_filters.return_value = [mock_entity]
        mock_repository.count_with_filters.return_value = 1

        req = ListSearchTurnsRequestSchema(tenant_id='t_1', bu_id='bu_1')
        items, count = service.list_entities(req)
        assert count == 1
        assert len(items) == 1
        assert isinstance(items[0], SearchTurnSchema)
        assert items[0].id == 'sturn_test123'


class TestSearchTurnServiceCreate:
    def test_creates_entity(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateSearchTurnRequestSchema(
            tenant_id='t_1', bu_id='bu_1',
            session_id='ss_test123',
            turn_number=1,
            user_query='find senior engineers',
        )
        result = service.create_entity(req)
        assert isinstance(result, SearchTurnSchema)
        assert result.session_id == 'ss_test123'
        mock_repository.create.assert_called_once()

    def test_create_maps_all_fields(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateSearchTurnRequestSchema(
            tenant_id='t_1', bu_id='bu_1',
            session_id='ss_test123',
            turn_number=2,
            user_query='find senior engineers',
            transcript={'messages': []},
            results=[{'full_name': 'Jane Doe', 'headline': 'Senior Engineer'}],
            summary='Test summary',
        )
        service.create_entity(req)

        created_entity = mock_repository.create.call_args[0][0]
        assert created_entity.session_id == 'ss_test123'
        assert created_entity.turn_number == 2
        assert created_entity.user_query == 'find senior engineers'
        assert created_entity.transcript == {'messages': []}
        assert created_entity.results == [{'full_name': 'Jane Doe', 'headline': 'Senior Engineer'}]
        assert created_entity.summary == 'Test summary'


class TestSearchTurnServiceUpdate:
    def test_update_provided_fields(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        req = UpdateSearchTurnRequestSchema(
            tenant_id='t_1', bu_id='bu_1', search_turn_id='sturn_test123',
            summary='Updated summary',
        )
        service.update_entity(req)
        assert mock_entity.summary == 'Updated summary'

    def test_update_none_does_not_change(self, service, mock_repository, mock_entity):
        mock_entity.summary = 'Original'
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        req = UpdateSearchTurnRequestSchema(
            tenant_id='t_1', bu_id='bu_1', search_turn_id='sturn_test123',
        )
        service.update_entity(req)
        assert mock_entity.summary == 'Original'

    def test_update_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        req = UpdateSearchTurnRequestSchema(
            tenant_id='t_1', bu_id='bu_1', search_turn_id='sturn_nonexistent',
            summary='Updated',
        )
        with pytest.raises(ValueError, match='not found'):
            service.update_entity(req)


class TestSearchTurnServiceDelete:
    def test_delete_calls_repository(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity

        from linkedout.search_session.schemas.search_turn_api_schema import DeleteSearchTurnByIdRequestSchema
        req = DeleteSearchTurnByIdRequestSchema(
            tenant_id='t_1', bu_id='bu_1', search_turn_id='sturn_test123',
        )
        service.delete_entity_by_id(req)
        mock_repository.delete.assert_called_once_with(mock_entity)

    def test_delete_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        from linkedout.search_session.schemas.search_turn_api_schema import DeleteSearchTurnByIdRequestSchema
        req = DeleteSearchTurnByIdRequestSchema(
            tenant_id='t_1', bu_id='bu_1', search_turn_id='sturn_nonexistent',
        )
        with pytest.raises(ValueError, match='not found'):
            service.delete_entity_by_id(req)
