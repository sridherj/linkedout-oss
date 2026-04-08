# SPDX-License-Identifier: Apache-2.0
"""Service for RoleAlias entity.

Shared entity (no tenant/BU scoping). Uses a standalone service
rather than BaseService which requires tenant_id/bu_id.
"""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from linkedout.role_alias.entities.role_alias_entity import RoleAliasEntity
from linkedout.role_alias.repositories.role_alias_repository import RoleAliasRepository
from linkedout.role_alias.schemas.role_alias_api_schema import (
    CreateRoleAliasRequestSchema,
    CreateRoleAliasesRequestSchema,
    ListRoleAliasesRequestSchema,
    UpdateRoleAliasRequestSchema,
)
from linkedout.role_alias.schemas.role_alias_schema import RoleAliasSchema
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class RoleAliasService:
    """Service for RoleAlias. Shared entity, no tenant/BU scoping."""

    def __init__(self, session: Session):
        self._session = session
        self._repository = RoleAliasRepository(self._session)

    def commit(self) -> None:
        self._session.commit()

    def list_role_aliases(
        self, list_request: ListRoleAliasesRequestSchema,
    ) -> Tuple[List[RoleAliasSchema], int]:
        entities = self._repository.list_with_filters(
            limit=list_request.limit,
            offset=list_request.offset,
            sort_by=list_request.sort_by,
            sort_order=list_request.sort_order,
            alias_title=list_request.alias_title,
            canonical_title=list_request.canonical_title,
            seniority_level=list_request.seniority_level,
            function_area=list_request.function_area,
        )
        total_count = self._repository.count_with_filters(
            alias_title=list_request.alias_title,
            canonical_title=list_request.canonical_title,
            seniority_level=list_request.seniority_level,
            function_area=list_request.function_area,
        )
        schemas = [RoleAliasSchema.model_validate(e) for e in entities]
        return schemas, total_count

    def create_role_alias(
        self, create_request: CreateRoleAliasRequestSchema,
    ) -> RoleAliasSchema:
        entity = RoleAliasEntity(
            alias_title=create_request.alias_title,
            canonical_title=create_request.canonical_title,
            seniority_level=create_request.seniority_level,
            function_area=create_request.function_area,
        )
        created = self._repository.create(entity)
        return RoleAliasSchema.model_validate(created)

    def create_role_aliases_bulk(
        self, create_request: CreateRoleAliasesRequestSchema,
    ) -> List[RoleAliasSchema]:
        created_entities = []
        for item in create_request.role_aliases:
            entity = RoleAliasEntity(
                alias_title=item.alias_title,
                canonical_title=item.canonical_title,
                seniority_level=item.seniority_level,
                function_area=item.function_area,
            )
            created = self._repository.create(entity)
            created_entities.append(created)
        return [RoleAliasSchema.model_validate(e) for e in created_entities]

    def update_role_alias(
        self, role_alias_id: str, update_request: UpdateRoleAliasRequestSchema,
    ) -> RoleAliasSchema:
        entity = self._repository.get_by_id(role_alias_id)
        if not entity:
            raise ValueError(f'RoleAlias not found with ID: {role_alias_id}')

        if update_request.alias_title is not None:
            entity.alias_title = update_request.alias_title
        if update_request.canonical_title is not None:
            entity.canonical_title = update_request.canonical_title
        if update_request.seniority_level is not None:
            entity.seniority_level = update_request.seniority_level
        if update_request.function_area is not None:
            entity.function_area = update_request.function_area

        updated = self._repository.update(entity)
        return RoleAliasSchema.model_validate(updated)

    def get_role_alias_by_id(self, entity_id: str) -> Optional[RoleAliasSchema]:
        entity = self._repository.get_by_id(entity_id)
        if not entity:
            return None
        return RoleAliasSchema.model_validate(entity)

    def delete_role_alias_by_id(self, entity_id: str) -> None:
        entity = self._repository.get_by_id(entity_id)
        if not entity:
            raise ValueError(f'RoleAlias not found with ID: {entity_id}')
        self._repository.delete(entity)
