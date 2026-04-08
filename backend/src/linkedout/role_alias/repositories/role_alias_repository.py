# SPDX-License-Identifier: Apache-2.0
"""Repository for RoleAlias entity.

Shared entity (no tenant/BU scoping). Uses a standalone repository
rather than BaseRepository which requires tenant_id/bu_id.
"""
from typing import List, Optional

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from common.schemas.base_enums_schemas import SortOrder
from linkedout.role_alias.entities.role_alias_entity import RoleAliasEntity
from linkedout.role_alias.schemas.role_alias_api_schema import RoleAliasSortByFields
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class RoleAliasRepository:
    """Repository for RoleAlias. Shared entity, no tenant/BU scoping."""

    def __init__(self, session: Session):
        self._session = session

    def list_with_filters(
        self,
        limit: int = 20,
        offset: int = 0,
        sort_by: RoleAliasSortByFields = RoleAliasSortByFields.ALIAS_TITLE,
        sort_order: SortOrder = SortOrder.ASC,
        alias_title: Optional[str] = None,
        canonical_title: Optional[str] = None,
        seniority_level: Optional[str] = None,
        function_area: Optional[str] = None,
    ) -> List[RoleAliasEntity]:
        query = self._session.query(RoleAliasEntity)

        if alias_title:
            query = query.filter(RoleAliasEntity.alias_title.ilike(f'%{alias_title}%'))
        if canonical_title:
            query = query.filter(RoleAliasEntity.canonical_title.ilike(f'%{canonical_title}%'))
        if seniority_level:
            query = query.filter(RoleAliasEntity.seniority_level == seniority_level)
        if function_area:
            query = query.filter(RoleAliasEntity.function_area == function_area)

        sort_column = getattr(RoleAliasEntity, sort_by.value, RoleAliasEntity.alias_title)
        if sort_order == SortOrder.DESC:
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        return query.limit(limit).offset(offset).all()

    def count_with_filters(
        self,
        alias_title: Optional[str] = None,
        canonical_title: Optional[str] = None,
        seniority_level: Optional[str] = None,
        function_area: Optional[str] = None,
    ) -> int:
        query = self._session.query(RoleAliasEntity)

        if alias_title:
            query = query.filter(RoleAliasEntity.alias_title.ilike(f'%{alias_title}%'))
        if canonical_title:
            query = query.filter(RoleAliasEntity.canonical_title.ilike(f'%{canonical_title}%'))
        if seniority_level:
            query = query.filter(RoleAliasEntity.seniority_level == seniority_level)
        if function_area:
            query = query.filter(RoleAliasEntity.function_area == function_area)

        return query.count()

    def create(self, entity: RoleAliasEntity) -> RoleAliasEntity:
        self._session.add(entity)
        self._session.flush()
        self._session.refresh(entity)
        return entity

    def get_by_alias_title(self, title: str) -> Optional[RoleAliasEntity]:
        return (
            self._session.query(RoleAliasEntity)
            .filter(RoleAliasEntity.alias_title == title)
            .one_or_none()
        )

    def get_by_id(self, entity_id: str) -> Optional[RoleAliasEntity]:
        return (
            self._session.query(RoleAliasEntity)
            .filter(RoleAliasEntity.id == entity_id)
            .one_or_none()
        )

    def update(self, entity: RoleAliasEntity) -> RoleAliasEntity:
        self._session.merge(entity)
        self._session.flush()
        self._session.refresh(entity)
        return entity

    def delete(self, entity: RoleAliasEntity) -> None:
        self._session.delete(entity)
