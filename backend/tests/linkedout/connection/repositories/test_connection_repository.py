# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for ConnectionRepository."""
from unittest.mock import Mock

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Session

from linkedout.connection.repositories.connection_repository import ConnectionRepository


class TestConnectionRepositoryWiring:
    def test_can_instantiate_with_session(self):
        repo = ConnectionRepository(Mock(spec=Session))
        assert repo is not None

    def test_has_crud_methods(self):
        repo = ConnectionRepository(Mock(spec=Session))
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
        repo = ConnectionRepository(Mock(spec=Session))
        specs = repo._get_filter_specs()
        field_names = [s.field_name for s in specs]
        assert 'app_user_id' in field_names
        assert 'crawled_profile_id' in field_names
        assert 'dunbar_tier' in field_names
        assert 'affinity_score_min' in field_names
        assert 'affinity_score_max' in field_names

    def test_entity_class_configured(self):
        from linkedout.connection.entities.connection_entity import ConnectionEntity
        repo = ConnectionRepository(Mock(spec=Session))
        assert repo._entity_class is ConnectionEntity

    def test_default_sort_field(self):
        repo = ConnectionRepository(Mock(spec=Session))
        assert repo._default_sort_field == 'created_at'

    def test_unique_constraint_per_user_per_profile(self):
        from linkedout.connection.entities.connection_entity import ConnectionEntity
        constraints = [c for c in ConnectionEntity.__table_args__ if isinstance(c, UniqueConstraint)]
        uq = next((c for c in constraints if set(c.columns.keys()) == {'app_user_id', 'crawled_profile_id'}), None)
        assert uq is not None, "Missing unique constraint on (app_user_id, crawled_profile_id)"
        assert uq.name == 'uq_conn_app_user_profile'
