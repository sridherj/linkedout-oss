# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for ConnectionService."""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec

from sqlalchemy.orm import Session

from linkedout.connection.entities.connection_entity import ConnectionEntity
from linkedout.connection.repositories.connection_repository import ConnectionRepository
from linkedout.connection.services.connection_service import ConnectionService
from linkedout.connection.schemas.connection_schema import ConnectionSchema
from linkedout.connection.schemas.connection_api_schema import (
    CreateConnectionRequestSchema,
    ListConnectionsRequestSchema,
    UpdateConnectionRequestSchema,
)


@pytest.fixture
def mock_session():
    return create_autospec(Session, instance=True, spec_set=True)


@pytest.fixture
def mock_repository():
    return create_autospec(ConnectionRepository, instance=True, spec_set=True)


@pytest.fixture
def service(mock_session, mock_repository):
    svc = ConnectionService(mock_session)
    svc._repository = mock_repository
    return svc


@pytest.fixture
def mock_entity():
    entity = ConnectionEntity(
        tenant_id='t_1',
        bu_id='bu_1',
        app_user_id='au_1',
        crawled_profile_id='cp_1',
    )
    entity.id = 'conn_test123'
    entity.affinity_score = None
    entity.dunbar_tier = None
    entity.affinity_source_count = 0
    entity.affinity_recency = 0
    entity.affinity_career_overlap = 0
    entity.affinity_mutual_connections = 0
    entity.affinity_version = 0
    entity.created_at = datetime.now(timezone.utc)
    entity.updated_at = datetime.now(timezone.utc)
    return entity


class TestConnectionServiceWiring:
    def test_can_instantiate(self, mock_session):
        svc = ConnectionService(mock_session)
        assert svc is not None

    def test_repository_created(self, mock_session):
        svc = ConnectionService(mock_session)
        assert isinstance(svc._repository, ConnectionRepository)

    def test_has_crud_methods(self, mock_session):
        svc = ConnectionService(mock_session)
        assert hasattr(svc, 'list_entities')
        assert hasattr(svc, 'create_entity')
        assert hasattr(svc, 'create_entities_bulk')
        assert hasattr(svc, 'update_entity')
        assert hasattr(svc, 'get_entity_by_id')
        assert hasattr(svc, 'delete_entity_by_id')


class TestConnectionServiceList:
    def test_list_calls_repository(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        req = ListConnectionsRequestSchema(tenant_id='t_1', bu_id='bu_1')
        items, count = service.list_entities(req)
        assert items == []
        assert count == 0
        mock_repository.list_with_filters.assert_called_once()
        mock_repository.count_with_filters.assert_called_once()

    def test_list_passes_filters(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        req = ListConnectionsRequestSchema(
            tenant_id='t_1', bu_id='bu_1',
            app_user_id='au_1',
            dunbar_tier='active',
        )
        service.list_entities(req)

        call_kwargs = mock_repository.list_with_filters.call_args
        assert call_kwargs.kwargs['app_user_id'] == 'au_1'
        assert call_kwargs.kwargs['dunbar_tier'] == 'active'

    def test_list_returns_schemas(self, service, mock_repository, mock_entity):
        mock_repository.list_with_filters.return_value = [mock_entity]
        mock_repository.count_with_filters.return_value = 1

        req = ListConnectionsRequestSchema(tenant_id='t_1', bu_id='bu_1')
        items, count = service.list_entities(req)
        assert count == 1
        assert len(items) == 1
        assert isinstance(items[0], ConnectionSchema)
        assert items[0].id == 'conn_test123'


class TestConnectionServiceCreate:
    def test_creates_entity(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateConnectionRequestSchema(
            tenant_id='t_1', bu_id='bu_1',
            app_user_id='au_1',
            crawled_profile_id='cp_1',
        )
        result = service.create_entity(req)
        assert isinstance(result, ConnectionSchema)
        assert result.app_user_id == 'au_1'
        mock_repository.create.assert_called_once()

    def test_create_maps_all_fields(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateConnectionRequestSchema(
            tenant_id='t_1', bu_id='bu_1',
            app_user_id='au_1',
            crawled_profile_id='cp_1',
            dunbar_tier='active',
            affinity_score=0.85,
        )
        service.create_entity(req)

        created_entity = mock_repository.create.call_args[0][0]
        assert created_entity.app_user_id == 'au_1'
        assert created_entity.crawled_profile_id == 'cp_1'
        assert created_entity.dunbar_tier == 'active'
        assert created_entity.affinity_score == 0.85


class TestConnectionServiceUpdate:
    def test_update_provided_fields(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        req = UpdateConnectionRequestSchema(
            tenant_id='t_1', bu_id='bu_1', connection_id='conn_test123',
            dunbar_tier='inner_circle',
        )
        service.update_entity(req)
        assert mock_entity.dunbar_tier == 'inner_circle'

    def test_update_none_does_not_change(self, service, mock_repository, mock_entity):
        mock_entity.dunbar_tier = 'active'
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        req = UpdateConnectionRequestSchema(
            tenant_id='t_1', bu_id='bu_1', connection_id='conn_test123',
        )
        service.update_entity(req)
        assert mock_entity.dunbar_tier == 'active'

    def test_update_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        req = UpdateConnectionRequestSchema(
            tenant_id='t_1', bu_id='bu_1', connection_id='conn_nonexistent',
            dunbar_tier='active',
        )
        with pytest.raises(ValueError, match='not found'):
            service.update_entity(req)


class TestConnectionServiceDelete:
    def test_delete_calls_repository(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity

        from linkedout.connection.schemas.connection_api_schema import DeleteConnectionByIdRequestSchema
        req = DeleteConnectionByIdRequestSchema(
            tenant_id='t_1', bu_id='bu_1', connection_id='conn_test123',
        )
        service.delete_entity_by_id(req)
        mock_repository.delete.assert_called_once_with(mock_entity)

    def test_delete_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        from linkedout.connection.schemas.connection_api_schema import DeleteConnectionByIdRequestSchema
        req = DeleteConnectionByIdRequestSchema(
            tenant_id='t_1', bu_id='bu_1', connection_id='conn_nonexistent',
        )
        with pytest.raises(ValueError, match='not found'):
            service.delete_entity_by_id(req)
