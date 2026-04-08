# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for RoleAliasService.

These tests verify that RoleAliasService is correctly wired.

Wiring tests verify:
- Correct instantiation with session
- Filter extraction maps request fields correctly
- Entity creation maps request fields correctly
- Entity update maps request fields correctly
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec

from sqlalchemy.orm import Session

from linkedout.role_alias.entities.role_alias_entity import RoleAliasEntity
from linkedout.role_alias.repositories.role_alias_repository import RoleAliasRepository
from linkedout.role_alias.services.role_alias_service import RoleAliasService
from linkedout.role_alias.schemas.role_alias_schema import RoleAliasSchema
from linkedout.role_alias.schemas.role_alias_api_schema import (
    CreateRoleAliasRequestSchema,
    ListRoleAliasesRequestSchema,
    UpdateRoleAliasRequestSchema,
)


@pytest.fixture
def mock_session():
    return create_autospec(Session, instance=True, spec_set=True)


@pytest.fixture
def mock_repository():
    return create_autospec(RoleAliasRepository, instance=True, spec_set=True)


@pytest.fixture
def service(mock_session, mock_repository):
    svc = RoleAliasService(mock_session)
    svc._repository = mock_repository
    return svc


@pytest.fixture
def mock_entity():
    entity = RoleAliasEntity(
        alias_title='Software Engineer',
        canonical_title='Software Engineer',
        seniority_level='Mid',
        function_area='Engineering',
    )
    entity.id = 'ra_test123'
    entity.created_at = datetime.now(timezone.utc)
    entity.updated_at = datetime.now(timezone.utc)
    return entity


class TestRoleAliasServiceWiring:
    def test_can_instantiate(self, mock_session):
        svc = RoleAliasService(mock_session)
        assert svc is not None

    def test_repository_created(self, mock_session):
        svc = RoleAliasService(mock_session)
        assert isinstance(svc._repository, RoleAliasRepository)

    def test_has_crud_methods(self, mock_session):
        svc = RoleAliasService(mock_session)
        assert hasattr(svc, 'list_role_aliases')
        assert hasattr(svc, 'create_role_alias')
        assert hasattr(svc, 'create_role_aliases_bulk')
        assert hasattr(svc, 'update_role_alias')
        assert hasattr(svc, 'get_role_alias_by_id')
        assert hasattr(svc, 'delete_role_alias_by_id')


class TestRoleAliasServiceList:
    def test_list_calls_repository(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        req = ListRoleAliasesRequestSchema()
        items, count = service.list_role_aliases(req)
        assert items == []
        assert count == 0
        mock_repository.list_with_filters.assert_called_once()
        mock_repository.count_with_filters.assert_called_once()

    def test_list_passes_filters(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        req = ListRoleAliasesRequestSchema(
            alias_title='Engineer',
            seniority_level='Senior',
        )
        service.list_role_aliases(req)

        call_kwargs = mock_repository.list_with_filters.call_args
        assert call_kwargs.kwargs['alias_title'] == 'Engineer'
        assert call_kwargs.kwargs['seniority_level'] == 'Senior'

    def test_list_returns_schemas(self, service, mock_repository, mock_entity):
        mock_repository.list_with_filters.return_value = [mock_entity]
        mock_repository.count_with_filters.return_value = 1

        req = ListRoleAliasesRequestSchema()
        items, count = service.list_role_aliases(req)
        assert count == 1
        assert len(items) == 1
        assert isinstance(items[0], RoleAliasSchema)
        assert items[0].id == 'ra_test123'


class TestRoleAliasServiceCreate:
    def test_creates_entity(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateRoleAliasRequestSchema(
            alias_title='Software Engineer',
            canonical_title='Software Engineer',
            seniority_level='Mid',
            function_area='Engineering',
        )
        result = service.create_role_alias(req)
        assert isinstance(result, RoleAliasSchema)
        assert result.alias_title == 'Software Engineer'
        mock_repository.create.assert_called_once()

    def test_create_maps_all_fields(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateRoleAliasRequestSchema(
            alias_title='SWE',
            canonical_title='Software Engineer',
            seniority_level='Senior',
            function_area='Engineering',
        )
        service.create_role_alias(req)

        created_entity = mock_repository.create.call_args[0][0]
        assert created_entity.alias_title == 'SWE'
        assert created_entity.canonical_title == 'Software Engineer'
        assert created_entity.seniority_level == 'Senior'
        assert created_entity.function_area == 'Engineering'


class TestRoleAliasServiceUpdate:
    def test_update_provided_fields(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        req = UpdateRoleAliasRequestSchema(canonical_title='Senior Software Engineer')
        service.update_role_alias('ra_test123', req)

        assert mock_entity.canonical_title == 'Senior Software Engineer'

    def test_update_none_does_not_change(self, service, mock_repository, mock_entity):
        original_title = mock_entity.alias_title
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        req = UpdateRoleAliasRequestSchema()
        service.update_role_alias('ra_test123', req)

        assert mock_entity.alias_title == original_title

    def test_update_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        req = UpdateRoleAliasRequestSchema(canonical_title='x')
        with pytest.raises(ValueError, match='not found'):
            service.update_role_alias('ra_nonexistent', req)


class TestRoleAliasServiceDelete:
    def test_delete_calls_repository(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity

        service.delete_role_alias_by_id('ra_test123')
        mock_repository.delete.assert_called_once_with(mock_entity)

    def test_delete_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        with pytest.raises(ValueError, match='not found'):
            service.delete_role_alias_by_id('ra_nonexistent')
