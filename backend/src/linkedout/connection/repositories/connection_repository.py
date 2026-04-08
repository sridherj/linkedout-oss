# SPDX-License-Identifier: Apache-2.0
"""Repository for Connection entity."""
from typing import List

from common.repositories.base_repository import BaseRepository, FilterSpec
from linkedout.connection.entities.connection_entity import ConnectionEntity
from linkedout.connection.schemas.connection_api_schema import ConnectionSortByFields


class ConnectionRepository(BaseRepository[ConnectionEntity, ConnectionSortByFields]):
    _entity_class = ConnectionEntity
    _default_sort_field = 'created_at'
    _entity_name = 'connection'

    def _get_filter_specs(self) -> List[FilterSpec]:
        return [
            FilterSpec('app_user_id', 'eq'),
            FilterSpec('crawled_profile_id', 'eq'),
            FilterSpec('dunbar_tier', 'eq'),
            FilterSpec('affinity_score_min', 'gte', entity_field='affinity_score'),
            FilterSpec('affinity_score_max', 'lte', entity_field='affinity_score'),
        ]
