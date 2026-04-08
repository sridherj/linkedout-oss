# SPDX-License-Identifier: Apache-2.0
"""Service for EnrichmentEvent entity."""
from typing import Any

from common.services.base_service import BaseService
from linkedout.enrichment_event.entities.enrichment_event_entity import EnrichmentEventEntity
from linkedout.enrichment_event.repositories.enrichment_event_repository import EnrichmentEventRepository
from linkedout.enrichment_event.schemas.enrichment_event_schema import EnrichmentEventSchema


class EnrichmentEventService(BaseService[EnrichmentEventEntity, EnrichmentEventSchema, EnrichmentEventRepository]):
    _repository_class = EnrichmentEventRepository
    _schema_class = EnrichmentEventSchema
    _entity_class = EnrichmentEventEntity
    _entity_name = 'enrichment_event'
    _entity_id_field = 'enrichment_event_id'

    def _extract_filter_kwargs(self, list_request: Any) -> dict:
        return {
            'app_user_id': list_request.app_user_id,
            'crawled_profile_id': list_request.crawled_profile_id,
            'event_type': list_request.event_type,
            'enrichment_mode': list_request.enrichment_mode,
        }

    def _create_entity_from_request(self, create_request: Any) -> EnrichmentEventEntity:
        return EnrichmentEventEntity(
            tenant_id=create_request.tenant_id,
            bu_id=create_request.bu_id,
            app_user_id=create_request.app_user_id,
            crawled_profile_id=create_request.crawled_profile_id,
            event_type=create_request.event_type,
            enrichment_mode=create_request.enrichment_mode,
            crawler_name=create_request.crawler_name,
            cost_estimate_usd=create_request.cost_estimate_usd,
            crawler_run_id=create_request.crawler_run_id,
        )

    def _update_entity_from_request(self, entity: EnrichmentEventEntity, update_request: Any) -> None:
        if update_request.event_type is not None:
            entity.event_type = update_request.event_type
        if update_request.enrichment_mode is not None:
            entity.enrichment_mode = update_request.enrichment_mode
        if update_request.crawler_name is not None:
            entity.crawler_name = update_request.crawler_name
        if update_request.cost_estimate_usd is not None:
            entity.cost_estimate_usd = update_request.cost_estimate_usd
        if update_request.crawler_run_id is not None:
            entity.crawler_run_id = update_request.crawler_run_id
