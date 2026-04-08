# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for ContactSourceRepository."""
from unittest.mock import Mock

from sqlalchemy.orm import Session

from linkedout.contact_source.repositories.contact_source_repository import ContactSourceRepository


class TestContactSourceRepositoryWiring:
    def test_can_instantiate_with_session(self):
        repo = ContactSourceRepository(Mock(spec=Session))
        assert repo is not None

    def test_has_crud_methods(self):
        repo = ContactSourceRepository(Mock(spec=Session))
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
        repo = ContactSourceRepository(Mock(spec=Session))
        specs = repo._get_filter_specs()
        field_names = [s.field_name for s in specs]
        assert 'app_user_id' in field_names
        assert 'import_job_id' in field_names
        assert 'source_type' in field_names
        assert 'dedup_status' in field_names
        assert 'connection_id' in field_names

    def test_entity_class_configured(self):
        from linkedout.contact_source.entities.contact_source_entity import ContactSourceEntity
        repo = ContactSourceRepository(Mock(spec=Session))
        assert repo._entity_class is ContactSourceEntity

    def test_default_sort_field(self):
        repo = ContactSourceRepository(Mock(spec=Session))
        assert repo._default_sort_field == 'created_at'
