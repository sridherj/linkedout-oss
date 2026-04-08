# SPDX-License-Identifier: Apache-2.0
"""Repository for SearchTurn entity."""
from typing import List

from common.repositories.base_repository import BaseRepository, FilterSpec
from linkedout.search_session.entities.search_turn_entity import SearchTurnEntity
from linkedout.search_session.schemas.search_turn_api_schema import SearchTurnSortByFields


class SearchTurnRepository(BaseRepository[SearchTurnEntity, SearchTurnSortByFields]):
    _entity_class = SearchTurnEntity
    _default_sort_field = 'turn_number'
    _entity_name = 'search_turn'

    def _get_filter_specs(self) -> List[FilterSpec]:
        return [
            FilterSpec('session_id', 'eq'),
        ]
