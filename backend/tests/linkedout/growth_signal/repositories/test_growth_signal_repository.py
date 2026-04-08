# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for GrowthSignalRepository."""
import pytest
from unittest.mock import Mock

from sqlalchemy.orm import Session

from linkedout.funding.entities.growth_signal_entity import GrowthSignalEntity
from linkedout.funding.repositories.growth_signal_repository import GrowthSignalRepository


class TestGrowthSignalRepositoryWiring:
    def test_can_instantiate(self):
        repo = GrowthSignalRepository(Mock(spec=Session))
        assert repo is not None

    def test_has_crud_methods(self):
        repo = GrowthSignalRepository(Mock(spec=Session))
        assert callable(getattr(repo, 'list_with_filters', None))
        assert callable(getattr(repo, 'count_with_filters', None))
        assert callable(getattr(repo, 'create', None))
        assert callable(getattr(repo, 'get_by_id', None))
        assert callable(getattr(repo, 'update', None))
        assert callable(getattr(repo, 'delete', None))
