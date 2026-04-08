# SPDX-License-Identifier: Apache-2.0
"""Service for SearchTurn entity."""
from typing import Any

from common.services.base_service import BaseService
from linkedout.search_session.entities.search_turn_entity import SearchTurnEntity
from linkedout.search_session.repositories.search_turn_repository import SearchTurnRepository
from linkedout.search_session.schemas.search_turn_schema import SearchTurnSchema


class SearchTurnService(BaseService[SearchTurnEntity, SearchTurnSchema, SearchTurnRepository]):
    _repository_class = SearchTurnRepository
    _schema_class = SearchTurnSchema
    _entity_class = SearchTurnEntity
    _entity_name = 'search_turn'
    _entity_id_field = 'search_turn_id'

    def _extract_filter_kwargs(self, list_request: Any) -> dict:
        return {
            'session_id': list_request.session_id,
        }

    def _create_entity_from_request(self, create_request: Any) -> SearchTurnEntity:
        return SearchTurnEntity(
            tenant_id=create_request.tenant_id,
            bu_id=create_request.bu_id,
            session_id=create_request.session_id,
            turn_number=create_request.turn_number,
            user_query=create_request.user_query,
            transcript=create_request.transcript,
            results=create_request.results,
            summary=create_request.summary,
        )

    def _update_entity_from_request(self, entity: SearchTurnEntity, update_request: Any) -> None:
        if update_request.transcript is not None:
            entity.transcript = update_request.transcript
        if update_request.results is not None:
            entity.results = update_request.results
        if update_request.summary is not None:
            entity.summary = update_request.summary
