# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for FundingRoundService."""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec

from sqlalchemy.orm import Session

from linkedout.funding.entities.funding_round_entity import FundingRoundEntity
from linkedout.funding.repositories.funding_round_repository import FundingRoundRepository
from linkedout.funding.services.funding_round_service import FundingRoundService
from linkedout.funding.schemas.funding_round_schema import FundingRoundSchema
from linkedout.funding.schemas.funding_round_api_schema import (
    ListFundingRoundsRequestSchema,
    CreateFundingRoundRequestSchema,
    UpdateFundingRoundRequestSchema,
)


@pytest.fixture
def mock_session():
    return create_autospec(Session, instance=True, spec_set=True)


@pytest.fixture
def mock_repository():
    return create_autospec(FundingRoundRepository, instance=True, spec_set=True)


@pytest.fixture
def service(mock_session, mock_repository):
    svc = FundingRoundService(mock_session)
    svc._repository = mock_repository
    return svc


@pytest.fixture
def mock_entity():
    entity = FundingRoundEntity(
        company_id='co_test123',
        round_type='Seed',
        confidence=8,
    )
    entity.id = 'fr_test123'
    entity.created_at = datetime.now(timezone.utc)
    entity.updated_at = datetime.now(timezone.utc)
    return entity


class TestFundingRoundServiceWiring:
    def test_can_instantiate(self, mock_session):
        svc = FundingRoundService(mock_session)
        assert svc is not None

    def test_has_repository(self, service):
        assert service._repository is not None

    def test_has_crud_methods(self):
        svc = FundingRoundService(create_autospec(Session, instance=True))
        assert callable(getattr(svc, 'list_funding_rounds', None))
        assert callable(getattr(svc, 'create_funding_round', None))
        assert callable(getattr(svc, 'update_funding_round', None))
        assert callable(getattr(svc, 'get_funding_round_by_id', None))
        assert callable(getattr(svc, 'delete_funding_round_by_id', None))


class TestFundingRoundServiceList:
    def test_calls_repository(self, service, mock_repository, mock_entity):
        mock_repository.list_with_filters.return_value = [mock_entity]
        mock_repository.count_with_filters.return_value = 1

        req = ListFundingRoundsRequestSchema()
        results, total = service.list_funding_rounds(req)

        assert total == 1
        assert len(results) == 1
        assert isinstance(results[0], FundingRoundSchema)

    def test_handles_empty(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        req = ListFundingRoundsRequestSchema()
        results, total = service.list_funding_rounds(req)

        assert total == 0
        assert results == []


class TestFundingRoundServiceCreate:
    def test_creates_entity(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateFundingRoundRequestSchema(
            company_id='co_test123',
            round_type='Seed',
        )
        result = service.create_funding_round(req)

        assert isinstance(result, FundingRoundSchema)
        assert result.round_type == 'Seed'
        mock_repository.create.assert_called_once()


class TestFundingRoundServiceUpdate:
    def test_updates_provided_fields(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        req = UpdateFundingRoundRequestSchema(
            funding_round_id='fr_test123',
            confidence=9,
        )
        result = service.update_funding_round(req)

        assert isinstance(result, FundingRoundSchema)
        mock_repository.get_by_id.assert_called_once_with('fr_test123')

    def test_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        req = UpdateFundingRoundRequestSchema(
            funding_round_id='fr_nonexistent',
            confidence=9,
        )
        with pytest.raises(ValueError, match='FundingRound not found'):
            service.update_funding_round(req)
