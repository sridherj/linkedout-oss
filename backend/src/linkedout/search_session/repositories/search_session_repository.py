# SPDX-License-Identifier: Apache-2.0
"""Repository for SearchSession entity."""
from typing import List

from common.repositories.base_repository import BaseRepository, FilterSpec
from linkedout.search_session.entities.search_session_entity import SearchSessionEntity
from linkedout.search_session.schemas.search_session_api_schema import SearchSessionSortByFields


class SearchSessionRepository(BaseRepository[SearchSessionEntity, SearchSessionSortByFields]):
    _entity_class = SearchSessionEntity
    _default_sort_field = 'last_active_at'
    _entity_name = 'search_session'

    def _get_filter_specs(self) -> List[FilterSpec]:
        return [
            FilterSpec('app_user_id', 'eq'),
            FilterSpec('is_saved', 'eq'),
        ]
