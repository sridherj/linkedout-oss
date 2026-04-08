# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for EnrichmentConfigService."""
import pytest
from unittest.mock import create_autospec

from sqlalchemy.orm import Session

from organization.enrichment_config.entities.enrichment_config_entity import EnrichmentConfigEntity
from organization.enrichment_config.repositories.enrichment_config_repository import EnrichmentConfigRepository
from organization.enrichment_config.services.enrichment_config_service import EnrichmentConfigService
from organization.enrichment_config.schemas.enrichment_config_schema import EnrichmentConfigSchema
from organization.enrichment_config.schemas.enrichment_config_api_schema import (
    CreateEnrichmentConfigRequestSchema,
    ListEnrichmentConfigsRequestSchema,
    UpdateEnrichmentConfigRequestSchema,
)


@pytest.fixture
def mock_session():
    return create_autospec(Session, instance=True, spec_set=True)


@pytest.fixture
def mock_repository():
    return create_autospec(EnrichmentConfigRepository, instance=True, spec_set=True)


@pytest.fixture
def service(mock_session, mock_repository):
    svc = EnrichmentConfigService(mock_session)
    svc._repository = mock_repository
    return svc


@pytest.fixture
def mock_entity():
    entity = EnrichmentConfigEntity(
        app_user_id='usr_test123',
        enrichment_mode='platform',
    )
    entity.id = 'ec_test123'
    from datetime import datetime, timezone
    entity.created_at = datetime.now(timezone.utc)
    entity.updated_at = datetime.now(timezone.utc)
    return entity


class TestEnrichmentConfigServiceWiring:
    def test_has_list_method(self):
        assert hasattr(EnrichmentConfigService, 'list_enrichment_configs')

    def test_has_create_method(self):
        assert hasattr(EnrichmentConfigService, 'create_enrichment_config')

    def test_has_update_method(self):
        assert hasattr(EnrichmentConfigService, 'update_enrichment_config')

    def test_has_get_by_id_method(self):
        assert hasattr(EnrichmentConfigService, 'get_enrichment_config_by_id')

    def test_has_delete_method(self):
        assert hasattr(EnrichmentConfigService, 'delete_enrichment_config_by_id')


class TestEnrichmentConfigServiceList:
    def test_list_calls_repository(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0
        req = ListEnrichmentConfigsRequestSchema()
        items, count = service.list_enrichment_configs(req)
        assert items == []
        assert count == 0


class TestEnrichmentConfigServiceCreate:
    def test_create_returns_schema(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity
        req = CreateEnrichmentConfigRequestSchema(
            app_user_id='usr_test123',
            enrichment_mode='platform',
        )
        result = service.create_enrichment_config(req)
        assert isinstance(result, EnrichmentConfigSchema)
        assert result.app_user_id == 'usr_test123'


class TestEnrichmentConfigServiceUpdate:
    def test_update_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None
        req = UpdateEnrichmentConfigRequestSchema(enrichment_mode='byok')
        with pytest.raises(ValueError):
            service.update_enrichment_config('nonexistent', req)

    def test_update_changes_fields(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity
        req = UpdateEnrichmentConfigRequestSchema(enrichment_mode='byok')
        service.update_enrichment_config('ec_test123', req)
        assert mock_entity.enrichment_mode == 'byok'


class TestEnrichmentConfigServiceDelete:
    def test_delete_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None
        with pytest.raises(ValueError):
            service.delete_enrichment_config_by_id('nonexistent')
