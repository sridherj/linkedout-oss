# SPDX-License-Identifier: Apache-2.0
"""Service for Connection entity."""
from typing import Any

from common.services.base_service import BaseService
from linkedout.connection.entities.connection_entity import ConnectionEntity
from linkedout.connection.repositories.connection_repository import ConnectionRepository
from linkedout.connection.schemas.connection_schema import ConnectionSchema


class ConnectionService(BaseService[ConnectionEntity, ConnectionSchema, ConnectionRepository]):
    _repository_class = ConnectionRepository
    _schema_class = ConnectionSchema
    _entity_class = ConnectionEntity
    _entity_name = 'connection'
    _entity_id_field = 'connection_id'

    def _extract_filter_kwargs(self, list_request: Any) -> dict:
        return {
            'app_user_id': list_request.app_user_id,
            'crawled_profile_id': list_request.crawled_profile_id,
            'dunbar_tier': list_request.dunbar_tier,
            'affinity_score_min': list_request.affinity_score_min,
            'affinity_score_max': list_request.affinity_score_max,
        }

    def _create_entity_from_request(self, create_request: Any) -> ConnectionEntity:
        return ConnectionEntity(
            tenant_id=create_request.tenant_id,
            bu_id=create_request.bu_id,
            app_user_id=create_request.app_user_id,
            crawled_profile_id=create_request.crawled_profile_id,
            connected_at=create_request.connected_at,
            emails=create_request.emails,
            phones=create_request.phones,
            notes=create_request.notes,
            tags=create_request.tags,
            sources=create_request.sources,
            source_details=create_request.source_details,
            affinity_score=create_request.affinity_score,
            dunbar_tier=create_request.dunbar_tier,
            affinity_source_count=create_request.affinity_source_count,
            affinity_recency=create_request.affinity_recency,
            affinity_career_overlap=create_request.affinity_career_overlap,
            affinity_mutual_connections=create_request.affinity_mutual_connections,
            affinity_computed_at=create_request.affinity_computed_at,
            affinity_version=create_request.affinity_version,
        )

    def _update_entity_from_request(self, entity: ConnectionEntity, update_request: Any) -> None:
        if update_request.connected_at is not None:
            entity.connected_at = update_request.connected_at
        if update_request.emails is not None:
            entity.emails = update_request.emails
        if update_request.phones is not None:
            entity.phones = update_request.phones
        if update_request.notes is not None:
            entity.notes = update_request.notes
        if update_request.tags is not None:
            entity.tags = update_request.tags
        if update_request.sources is not None:
            entity.sources = update_request.sources
        if update_request.source_details is not None:
            entity.source_details = update_request.source_details
        if update_request.affinity_score is not None:
            entity.affinity_score = update_request.affinity_score
        if update_request.dunbar_tier is not None:
            entity.dunbar_tier = update_request.dunbar_tier
        if update_request.affinity_source_count is not None:
            entity.affinity_source_count = update_request.affinity_source_count
        if update_request.affinity_recency is not None:
            entity.affinity_recency = update_request.affinity_recency
        if update_request.affinity_career_overlap is not None:
            entity.affinity_career_overlap = update_request.affinity_career_overlap
        if update_request.affinity_mutual_connections is not None:
            entity.affinity_mutual_connections = update_request.affinity_mutual_connections
        if update_request.affinity_computed_at is not None:
            entity.affinity_computed_at = update_request.affinity_computed_at
        if update_request.affinity_version is not None:
            entity.affinity_version = update_request.affinity_version
