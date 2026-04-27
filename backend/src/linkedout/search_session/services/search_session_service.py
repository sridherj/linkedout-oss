# SPDX-License-Identifier: Apache-2.0
"""Service for SearchSession entity."""
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import desc

from common.services.base_service import BaseService
from linkedout.search_session.entities.search_session_entity import SearchSessionEntity
from linkedout.search_session.repositories.search_session_repository import SearchSessionRepository
from linkedout.search_session.schemas.search_session_schema import SearchSessionSchema


class SearchSessionService(BaseService[SearchSessionEntity, SearchSessionSchema, SearchSessionRepository]):
    _repository_class = SearchSessionRepository
    _schema_class = SearchSessionSchema
    _entity_class = SearchSessionEntity
    _entity_name = 'search_session'
    _entity_id_field = 'search_session_id'

    def _extract_filter_kwargs(self, list_request: Any) -> dict:
        return {
            'app_user_id': list_request.app_user_id,
        }

    def _create_entity_from_request(self, create_request: Any) -> SearchSessionEntity:
        return SearchSessionEntity(
            tenant_id=create_request.tenant_id,
            bu_id=create_request.bu_id,
            app_user_id=create_request.app_user_id,
            initial_query=create_request.initial_query,
            turn_count=create_request.turn_count,
            last_active_at=create_request.last_active_at or datetime.now(timezone.utc),
        )

    def _update_entity_from_request(self, entity: SearchSessionEntity, update_request: Any) -> None:
        if update_request.initial_query is not None:
            entity.initial_query = update_request.initial_query
        if update_request.turn_count is not None:
            entity.turn_count = update_request.turn_count
        if update_request.last_active_at is not None:
            entity.last_active_at = update_request.last_active_at
        if update_request.is_saved is not None:
            entity.is_saved = update_request.is_saved
        if update_request.saved_name is not None:
            entity.saved_name = update_request.saved_name

    # -- Custom methods for session management --

    def get_latest_active(self, app_user_id: str) -> Optional[SearchSessionSchema]:
        """Load the most recent active session for a user."""
        entity = (
            self._session.query(SearchSessionEntity)
            .filter(
                SearchSessionEntity.app_user_id == app_user_id,
                SearchSessionEntity.deleted_at.is_(None),
            )
            .order_by(desc(SearchSessionEntity.last_active_at))
            .first()
        )
        if entity is None:
            return None
        return SearchSessionSchema.model_validate(entity)

    def get_by_id(self, session_id: str) -> Optional[SearchSessionSchema]:
        """Look up a session by primary key (no tenant/bu context needed)."""
        entity = self._session.query(SearchSessionEntity).get(session_id)
        if entity is None or entity.deleted_at is not None:
            return None
        return SearchSessionSchema.model_validate(entity)
