# SPDX-License-Identifier: Apache-2.0
"""Repository for EnrichmentEvent entity."""
from typing import List

from common.repositories.base_repository import BaseRepository, FilterSpec
from linkedout.enrichment_event.entities.enrichment_event_entity import EnrichmentEventEntity
from linkedout.enrichment_event.schemas.enrichment_event_api_schema import EnrichmentEventSortByFields


class EnrichmentEventRepository(BaseRepository[EnrichmentEventEntity, EnrichmentEventSortByFields]):
    _entity_class = EnrichmentEventEntity
    _default_sort_field = 'created_at'
    _entity_name = 'enrichment_event'

    def _get_filter_specs(self) -> List[FilterSpec]:
        return [
            FilterSpec('app_user_id', 'eq'),
            FilterSpec('crawled_profile_id', 'eq'),
            FilterSpec('event_type', 'eq'),
            FilterSpec('enrichment_mode', 'eq'),
        ]
