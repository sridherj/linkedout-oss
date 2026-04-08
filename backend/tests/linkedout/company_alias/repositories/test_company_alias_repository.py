# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for CompanyAliasRepository."""
from unittest.mock import Mock

from sqlalchemy.orm import Session

from linkedout.company_alias.repositories.company_alias_repository import CompanyAliasRepository


class TestCompanyAliasRepositoryWiring:
    def test_can_instantiate(self):
        repo = CompanyAliasRepository(Mock(spec=Session))
        assert repo is not None

    def test_has_crud_methods(self):
        repo = CompanyAliasRepository(Mock(spec=Session))
        assert callable(getattr(repo, 'list_with_filters', None))
        assert callable(getattr(repo, 'count_with_filters', None))
        assert callable(getattr(repo, 'create', None))
        assert callable(getattr(repo, 'get_by_id', None))
        assert callable(getattr(repo, 'update', None))
        assert callable(getattr(repo, 'delete', None))
