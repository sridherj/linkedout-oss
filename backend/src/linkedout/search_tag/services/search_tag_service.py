# SPDX-License-Identifier: Apache-2.0
"""Service for SearchTag entity."""
from typing import Any

from common.services.base_service import BaseService
from linkedout.search_tag.entities.search_tag_entity import SearchTagEntity
from linkedout.search_tag.repositories.search_tag_repository import SearchTagRepository
from linkedout.search_tag.schemas.search_tag_schema import SearchTagSchema


class SearchTagService(BaseService[SearchTagEntity, SearchTagSchema, SearchTagRepository]):
    _repository_class = SearchTagRepository
    _schema_class = SearchTagSchema
    _entity_class = SearchTagEntity
    _entity_name = 'search_tag'
    _entity_id_field = 'search_tag_id'

    def _extract_filter_kwargs(self, list_request: Any) -> dict:
        return {
            'app_user_id': list_request.app_user_id,
            'session_id': list_request.session_id,
            'crawled_profile_id': list_request.crawled_profile_id,
            'tag_name': list_request.tag_name,
        }

    def _create_entity_from_request(self, create_request: Any) -> SearchTagEntity:
        return SearchTagEntity(
            tenant_id=create_request.tenant_id,
            bu_id=create_request.bu_id,
            app_user_id=create_request.app_user_id,
            session_id=create_request.session_id,
            crawled_profile_id=create_request.crawled_profile_id,
            tag_name=create_request.tag_name,
        )

    def _update_entity_from_request(self, entity: SearchTagEntity, update_request: Any) -> None:
        if update_request.tag_name is not None:
            entity.tag_name = update_request.tag_name
