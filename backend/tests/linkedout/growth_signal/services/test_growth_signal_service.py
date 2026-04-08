# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for GrowthSignalService."""
import pytest
from datetime import date, datetime, timezone
from unittest.mock import create_autospec

from sqlalchemy.orm import Session

from linkedout.funding.entities.growth_signal_entity import GrowthSignalEntity
from linkedout.funding.repositories.growth_signal_repository import GrowthSignalRepository
from linkedout.funding.services.growth_signal_service import GrowthSignalService
from linkedout.funding.schemas.growth_signal_schema import GrowthSignalSchema
from linkedout.funding.schemas.growth_signal_api_schema import (
    ListGrowthSignalsRequestSchema,
    CreateGrowthSignalRequestSchema,
    UpdateGrowthSignalRequestSchema,
)


@pytest.fixture
def mock_session():
    return create_autospec(Session, instance=True, spec_set=True)


@pytest.fixture
def mock_repository():
    return create_autospec(GrowthSignalRepository, instance=True, spec_set=True)


@pytest.fixture
def service(mock_session, mock_repository):
    svc = GrowthSignalService(mock_session)
    svc._repository = mock_repository
    return svc


@pytest.fixture
def mock_entity():
    entity = GrowthSignalEntity(
        company_id='co_test123',
        signal_type='arr',
        signal_date=date(2026, 1, 15),
        value_numeric=5000000,
        confidence=7,
    )
    entity.id = 'gs_test123'
    entity.created_at = datetime.now(timezone.utc)
    entity.updated_at = datetime.now(timezone.utc)
    return entity


class TestGrowthSignalServiceWiring:
    def test_can_instantiate(self, mock_session):
        svc = GrowthSignalService(mock_session)
        assert svc is not None

    def test_has_crud_methods(self):
        svc = GrowthSignalService(create_autospec(Session, instance=True))
        assert callable(getattr(svc, 'list_growth_signals', None))
        assert callable(getattr(svc, 'create_growth_signal', None))
        assert callable(getattr(svc, 'update_growth_signal', None))
        assert callable(getattr(svc, 'get_growth_signal_by_id', None))
        assert callable(getattr(svc, 'delete_growth_signal_by_id', None))


class TestGrowthSignalServiceList:
    def test_calls_repository(self, service, mock_repository, mock_entity):
        mock_repository.list_with_filters.return_value = [mock_entity]
        mock_repository.count_with_filters.return_value = 1

        req = ListGrowthSignalsRequestSchema()
        results, total = service.list_growth_signals(req)

        assert total == 1
        assert len(results) == 1
        assert isinstance(results[0], GrowthSignalSchema)


class TestGrowthSignalServiceCreate:
    def test_creates_entity(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateGrowthSignalRequestSchema(
            company_id='co_test123',
            signal_type='arr',
            signal_date=date(2026, 1, 15),
        )
        result = service.create_growth_signal(req)

        assert isinstance(result, GrowthSignalSchema)
        assert result.signal_type == 'arr'
        mock_repository.create.assert_called_once()


class TestGrowthSignalServiceUpdate:
    def test_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        req = UpdateGrowthSignalRequestSchema(
            growth_signal_id='gs_nonexistent',
            confidence=9,
        )
        with pytest.raises(ValueError, match='GrowthSignal not found'):
            service.update_growth_signal(req)
