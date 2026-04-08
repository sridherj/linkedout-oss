# SPDX-License-Identifier: Apache-2.0
"""Repository for SearchTag entity."""
from typing import List

from common.repositories.base_repository import BaseRepository, FilterSpec
from linkedout.search_tag.entities.search_tag_entity import SearchTagEntity
from linkedout.search_tag.schemas.search_tag_api_schema import SearchTagSortByFields


class SearchTagRepository(BaseRepository[SearchTagEntity, SearchTagSortByFields]):
    _entity_class = SearchTagEntity
    _default_sort_field = 'created_at'
    _entity_name = 'search_tag'

    def _get_filter_specs(self) -> List[FilterSpec]:
        return [
            FilterSpec('app_user_id', 'eq'),
            FilterSpec('session_id', 'eq'),
            FilterSpec('crawled_profile_id', 'eq'),
            FilterSpec('tag_name', 'ilike'),
        ]
