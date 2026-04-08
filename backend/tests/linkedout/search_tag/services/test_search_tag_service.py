# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for SearchTagService."""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec

from sqlalchemy.orm import Session

from linkedout.search_tag.entities.search_tag_entity import SearchTagEntity
from linkedout.search_tag.repositories.search_tag_repository import SearchTagRepository
from linkedout.search_tag.services.search_tag_service import SearchTagService
from linkedout.search_tag.schemas.search_tag_schema import SearchTagSchema
from linkedout.search_tag.schemas.search_tag_api_schema import (
    CreateSearchTagRequestSchema,
    ListSearchTagsRequestSchema,
    UpdateSearchTagRequestSchema,
)


@pytest.fixture
def mock_session():
    return create_autospec(Session, instance=True, spec_set=True)


@pytest.fixture
def mock_repository():
    return create_autospec(SearchTagRepository, instance=True, spec_set=True)


@pytest.fixture
def service(mock_session, mock_repository):
    svc = SearchTagService(mock_session)
    svc._repository = mock_repository
    return svc


@pytest.fixture
def mock_entity():
    entity = SearchTagEntity(
        tenant_id='t_1',
        bu_id='bu_1',
        app_user_id='au_1',
        session_id='ss_1',
        crawled_profile_id='cp_1',
        tag_name='engineering',
    )
    entity.id = 'stag_test123'
    entity.created_at = datetime.now(timezone.utc)
    entity.updated_at = datetime.now(timezone.utc)
    return entity


class TestSearchTagServiceWiring:
    def test_can_instantiate(self, mock_session):
        svc = SearchTagService(mock_session)
        assert svc is not None

    def test_repository_created(self, mock_session):
        svc = SearchTagService(mock_session)
        assert isinstance(svc._repository, SearchTagRepository)

    def test_has_crud_methods(self, mock_session):
        svc = SearchTagService(mock_session)
        assert hasattr(svc, 'list_entities')
        assert hasattr(svc, 'create_entity')
        assert hasattr(svc, 'create_entities_bulk')
        assert hasattr(svc, 'update_entity')
        assert hasattr(svc, 'get_entity_by_id')
        assert hasattr(svc, 'delete_entity_by_id')

    def test_entity_name(self, mock_session):
        svc = SearchTagService(mock_session)
        assert svc._entity_name == 'search_tag'

    def test_entity_id_field(self, mock_session):
        svc = SearchTagService(mock_session)
        assert svc._entity_id_field == 'search_tag_id'


class TestSearchTagServiceList:
    def test_list_calls_repository(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        req = ListSearchTagsRequestSchema(tenant_id='t_1', bu_id='bu_1')
        items, count = service.list_entities(req)
        assert items == []
        assert count == 0
        mock_repository.list_with_filters.assert_called_once()
        mock_repository.count_with_filters.assert_called_once()

    def test_list_passes_filters(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        req = ListSearchTagsRequestSchema(
            tenant_id='t_1', bu_id='bu_1',
            app_user_id='au_1',
            session_id='ss_1',
            crawled_profile_id='cp_1',
            tag_name='eng',
        )
        service.list_entities(req)

        call_kwargs = mock_repository.list_with_filters.call_args
        assert call_kwargs.kwargs['app_user_id'] == 'au_1'
        assert call_kwargs.kwargs['session_id'] == 'ss_1'
        assert call_kwargs.kwargs['crawled_profile_id'] == 'cp_1'
        assert call_kwargs.kwargs['tag_name'] == 'eng'

    def test_list_returns_schemas(self, service, mock_repository, mock_entity):
        mock_repository.list_with_filters.return_value = [mock_entity]
        mock_repository.count_with_filters.return_value = 1

        req = ListSearchTagsRequestSchema(tenant_id='t_1', bu_id='bu_1')
        items, count = service.list_entities(req)
        assert count == 1
        assert len(items) == 1
        assert isinstance(items[0], SearchTagSchema)
        assert items[0].id == 'stag_test123'


class TestSearchTagServiceCreate:
    def test_creates_entity(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateSearchTagRequestSchema(
            tenant_id='t_1', bu_id='bu_1',
            app_user_id='au_1',
            session_id='ss_1',
            crawled_profile_id='cp_1',
            tag_name='engineering',
        )
        result = service.create_entity(req)
        assert isinstance(result, SearchTagSchema)
        assert result.tag_name == 'engineering'
        mock_repository.create.assert_called_once()

    def test_create_maps_all_fields(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateSearchTagRequestSchema(
            tenant_id='t_1', bu_id='bu_1',
            app_user_id='au_1',
            session_id='ss_1',
            crawled_profile_id='cp_1',
            tag_name='engineering',
        )
        service.create_entity(req)

        created_entity = mock_repository.create.call_args[0][0]
        assert created_entity.app_user_id == 'au_1'
        assert created_entity.session_id == 'ss_1'
        assert created_entity.crawled_profile_id == 'cp_1'
        assert created_entity.tag_name == 'engineering'


class TestSearchTagServiceUpdate:
    def test_update_provided_fields(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        req = UpdateSearchTagRequestSchema(
            tenant_id='t_1', bu_id='bu_1', search_tag_id='stag_test123',
            tag_name='design',
        )
        service.update_entity(req)
        assert mock_entity.tag_name == 'design'

    def test_update_none_does_not_change(self, service, mock_repository, mock_entity):
        mock_entity.tag_name = 'engineering'
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        req = UpdateSearchTagRequestSchema(
            tenant_id='t_1', bu_id='bu_1', search_tag_id='stag_test123',
        )
        service.update_entity(req)
        assert mock_entity.tag_name == 'engineering'

    def test_update_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        req = UpdateSearchTagRequestSchema(
            tenant_id='t_1', bu_id='bu_1', search_tag_id='stag_nonexistent',
            tag_name='design',
        )
        with pytest.raises(ValueError, match='not found'):
            service.update_entity(req)


class TestSearchTagServiceDelete:
    def test_delete_calls_repository(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity

        from linkedout.search_tag.schemas.search_tag_api_schema import DeleteSearchTagByIdRequestSchema
        req = DeleteSearchTagByIdRequestSchema(
            tenant_id='t_1', bu_id='bu_1', search_tag_id='stag_test123',
        )
        service.delete_entity_by_id(req)
        mock_repository.delete.assert_called_once_with(mock_entity)

    def test_delete_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        from linkedout.search_tag.schemas.search_tag_api_schema import DeleteSearchTagByIdRequestSchema
        req = DeleteSearchTagByIdRequestSchema(
            tenant_id='t_1', bu_id='bu_1', search_tag_id='stag_nonexistent',
        )
        with pytest.raises(ValueError, match='not found'):
            service.delete_entity_by_id(req)
