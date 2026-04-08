# SPDX-License-Identifier: Apache-2.0
"""Service for EnrichmentConfig entity."""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from organization.enrichment_config.entities.enrichment_config_entity import EnrichmentConfigEntity
from organization.enrichment_config.repositories.enrichment_config_repository import EnrichmentConfigRepository
from organization.enrichment_config.schemas.enrichment_config_api_schema import (
    CreateEnrichmentConfigRequestSchema,
    ListEnrichmentConfigsRequestSchema,
    UpdateEnrichmentConfigRequestSchema,
)
from organization.enrichment_config.schemas.enrichment_config_schema import EnrichmentConfigSchema
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class EnrichmentConfigService:
    """Service for EnrichmentConfig. Organization-level, no tenant/bu scoping."""

    def __init__(self, session: Session = None):
        self._session = session
        self._repository = EnrichmentConfigRepository(self._session)

    def list_enrichment_configs(
        self, list_request: ListEnrichmentConfigsRequestSchema
    ) -> Tuple[List[EnrichmentConfigSchema], int]:
        entities = self._repository.list_with_filters(
            limit=list_request.limit,
            offset=list_request.offset,
            sort_by=list_request.sort_by,
            sort_order=list_request.sort_order,
            app_user_id=list_request.app_user_id,
            enrichment_mode=list_request.enrichment_mode,
        )
        total_count = self._repository.count_with_filters(
            app_user_id=list_request.app_user_id,
            enrichment_mode=list_request.enrichment_mode,
        )
        schemas = [EnrichmentConfigSchema.model_validate(e) for e in entities]
        return schemas, total_count

    def create_enrichment_config(
        self, create_request: CreateEnrichmentConfigRequestSchema
    ) -> EnrichmentConfigSchema:
        entity = EnrichmentConfigEntity(
            app_user_id=create_request.app_user_id,
            enrichment_mode=create_request.enrichment_mode,
            apify_key_encrypted=create_request.apify_key_encrypted,
            apify_key_hint=create_request.apify_key_hint,
        )
        created = self._repository.create(entity)
        return EnrichmentConfigSchema.model_validate(created)

    def update_enrichment_config(
        self, enrichment_config_id: str, update_request: UpdateEnrichmentConfigRequestSchema
    ) -> EnrichmentConfigSchema:
        entity = self._repository.get_by_id(enrichment_config_id)
        if not entity:
            raise ValueError(f'EnrichmentConfig not found with ID: {enrichment_config_id}')

        if update_request.enrichment_mode is not None:
            entity.enrichment_mode = update_request.enrichment_mode
        if update_request.apify_key_encrypted is not None:
            entity.apify_key_encrypted = update_request.apify_key_encrypted
        if update_request.apify_key_hint is not None:
            entity.apify_key_hint = update_request.apify_key_hint

        updated = self._repository.update(entity)
        return EnrichmentConfigSchema.model_validate(updated)

    def get_enrichment_config_by_id(self, entity_id: str) -> Optional[EnrichmentConfigSchema]:
        entity = self._repository.get_by_id(entity_id)
        if not entity:
            return None
        return EnrichmentConfigSchema.model_validate(entity)

    def delete_enrichment_config_by_id(self, entity_id: str) -> None:
        entity = self._repository.get_by_id(entity_id)
        if not entity:
            raise ValueError(f'EnrichmentConfig not found with ID: {entity_id}')
        self._repository.delete(entity)
