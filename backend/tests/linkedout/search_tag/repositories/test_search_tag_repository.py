# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for SearchTagRepository."""
from unittest.mock import Mock

from sqlalchemy.orm import Session

from linkedout.search_tag.repositories.search_tag_repository import SearchTagRepository


class TestSearchTagRepositoryWiring:
    def test_can_instantiate_with_session(self):
        repo = SearchTagRepository(Mock(spec=Session))
        assert repo is not None

    def test_has_crud_methods(self):
        repo = SearchTagRepository(Mock(spec=Session))
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
        repo = SearchTagRepository(Mock(spec=Session))
        specs = repo._get_filter_specs()
        field_names = [s.field_name for s in specs]
        assert 'app_user_id' in field_names
        assert 'session_id' in field_names
        assert 'crawled_profile_id' in field_names
        assert 'tag_name' in field_names

    def test_tag_name_filter_is_ilike(self):
        repo = SearchTagRepository(Mock(spec=Session))
        specs = repo._get_filter_specs()
        tag_spec = next(s for s in specs if s.field_name == 'tag_name')
        assert tag_spec.filter_type == 'ilike'

    def test_entity_class_configured(self):
        from linkedout.search_tag.entities.search_tag_entity import SearchTagEntity
        repo = SearchTagRepository(Mock(spec=Session))
        assert repo._entity_class is SearchTagEntity

    def test_default_sort_field(self):
        repo = SearchTagRepository(Mock(spec=Session))
        assert repo._default_sort_field == 'created_at'

    def test_entity_name(self):
        repo = SearchTagRepository(Mock(spec=Session))
        assert repo._entity_name == 'search_tag'
