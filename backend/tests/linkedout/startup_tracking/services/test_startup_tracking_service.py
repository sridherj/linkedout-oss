# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for StartupTrackingService."""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec

from sqlalchemy.orm import Session

from linkedout.funding.entities.startup_tracking_entity import StartupTrackingEntity
from linkedout.funding.repositories.startup_tracking_repository import StartupTrackingRepository
from linkedout.funding.services.startup_tracking_service import StartupTrackingService
from linkedout.funding.schemas.startup_tracking_schema import StartupTrackingSchema
from linkedout.funding.schemas.startup_tracking_api_schema import (
    ListStartupTrackingsRequestSchema,
    CreateStartupTrackingRequestSchema,
    UpdateStartupTrackingRequestSchema,
)


@pytest.fixture
def mock_session():
    return create_autospec(Session, instance=True, spec_set=True)


@pytest.fixture
def mock_repository():
    return create_autospec(StartupTrackingRepository, instance=True, spec_set=True)


@pytest.fixture
def service(mock_session, mock_repository):
    svc = StartupTrackingService(mock_session)
    svc._repository = mock_repository
    return svc


@pytest.fixture
def mock_entity():
    entity = StartupTrackingEntity(
        company_id='co_test123',
        watching=True,
        vertical='AI Agents',
    )
    entity.id = 'st_test123'
    entity.round_count = 0
    entity.created_at = datetime.now(timezone.utc)
    entity.updated_at = datetime.now(timezone.utc)
    return entity


class TestStartupTrackingServiceWiring:
    def test_can_instantiate(self, mock_session):
        svc = StartupTrackingService(mock_session)
        assert svc is not None

    def test_has_crud_methods(self):
        svc = StartupTrackingService(create_autospec(Session, instance=True))
        assert callable(getattr(svc, 'list_startup_trackings', None))
        assert callable(getattr(svc, 'create_startup_tracking', None))
        assert callable(getattr(svc, 'update_startup_tracking', None))
        assert callable(getattr(svc, 'get_startup_tracking_by_id', None))
        assert callable(getattr(svc, 'delete_startup_tracking_by_id', None))


class TestStartupTrackingServiceList:
    def test_calls_repository(self, service, mock_repository, mock_entity):
        mock_repository.list_with_filters.return_value = [mock_entity]
        mock_repository.count_with_filters.return_value = 1

        req = ListStartupTrackingsRequestSchema()
        results, total = service.list_startup_trackings(req)

        assert total == 1
        assert len(results) == 1
        assert isinstance(results[0], StartupTrackingSchema)


class TestStartupTrackingServiceCreate:
    def test_creates_entity(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateStartupTrackingRequestSchema(
            company_id='co_test123',
            watching=True,
        )
        result = service.create_startup_tracking(req)

        assert isinstance(result, StartupTrackingSchema)
        assert result.watching is True
        mock_repository.create.assert_called_once()


class TestStartupTrackingServiceUpdate:
    def test_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        req = UpdateStartupTrackingRequestSchema(
            startup_tracking_id='st_nonexistent',
            watching=False,
        )
        with pytest.raises(ValueError, match='StartupTracking not found'):
            service.update_startup_tracking(req)
