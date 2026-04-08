# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for StartupTrackingRepository."""
import pytest
from unittest.mock import Mock

from sqlalchemy.orm import Session

from linkedout.funding.entities.startup_tracking_entity import StartupTrackingEntity
from linkedout.funding.repositories.startup_tracking_repository import StartupTrackingRepository


class TestStartupTrackingRepositoryWiring:
    def test_can_instantiate(self):
        repo = StartupTrackingRepository(Mock(spec=Session))
        assert repo is not None

    def test_has_crud_methods(self):
        repo = StartupTrackingRepository(Mock(spec=Session))
        assert callable(getattr(repo, 'list_with_filters', None))
        assert callable(getattr(repo, 'count_with_filters', None))
        assert callable(getattr(repo, 'create', None))
        assert callable(getattr(repo, 'get_by_id', None))
        assert callable(getattr(repo, 'update', None))
        assert callable(getattr(repo, 'delete', None))
