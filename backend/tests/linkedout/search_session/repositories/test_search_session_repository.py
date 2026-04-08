# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for SearchSessionRepository."""
from unittest.mock import Mock

from sqlalchemy.orm import Session

from linkedout.search_session.repositories.search_session_repository import SearchSessionRepository


class TestSearchSessionRepositoryWiring:
    def test_can_instantiate_with_session(self):
        repo = SearchSessionRepository(Mock(spec=Session))
        assert repo is not None

    def test_has_crud_methods(self):
        repo = SearchSessionRepository(Mock(spec=Session))
        assert hasattr(repo, 'list_with_filters')
        assert hasattr(repo, 'count_with_filters')
        assert hasattr(repo, 'create')
        assert hasattr(repo, 'get_by_id')
        assert hasattr(repo, 'update')
        assert hasattr(repo, 'delete')
        assert callable(repo.list_with_filters)
        assert callable(repo.count_with_filters)
        assert callable(repo.create)
        assert callable(repo.get_by_id)
        assert callable(repo.update)
        assert callable(repo.delete)

    def test_filter_specs_defined(self):
        repo = SearchSessionRepository(Mock(spec=Session))
        specs = repo._get_filter_specs()
        field_names = [s.field_name for s in specs]
        assert 'app_user_id' in field_names
        assert 'is_saved' in field_names

    def test_entity_class_configured(self):
        from linkedout.search_session.entities.search_session_entity import SearchSessionEntity
        repo = SearchSessionRepository(Mock(spec=Session))
        assert repo._entity_class is SearchSessionEntity

    def test_default_sort_field(self):
        repo = SearchSessionRepository(Mock(spec=Session))
        assert repo._default_sort_field == 'last_active_at'

    def test_entity_name_configured(self):
        repo = SearchSessionRepository(Mock(spec=Session))
        assert repo._entity_name == 'search_session'
