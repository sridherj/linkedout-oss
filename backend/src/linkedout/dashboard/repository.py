# SPDX-License-Identifier: Apache-2.0
"""Dashboard repository — aggregation queries over connection + crawled_profile."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from linkedout.connection.entities.connection_entity import ConnectionEntity
from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity


class DashboardRepository:
    def __init__(self, session: Session):
        self._session = session

    def _base_connection_filter(self, stmt, tenant_id: str, bu_id: str, app_user_id: str):
        return stmt.where(
            ConnectionEntity.app_user_id == app_user_id,
            ConnectionEntity.tenant_id == tenant_id,
            ConnectionEntity.bu_id == bu_id,
            ConnectionEntity.is_active == True,  # noqa: E712
        )

    def get_total_connections(self, tenant_id: str, bu_id: str, app_user_id: str) -> int:
        stmt = select(func.count()).select_from(ConnectionEntity)
        stmt = self._base_connection_filter(stmt, tenant_id, bu_id, app_user_id)
        return self._session.execute(stmt).scalar() or 0

    def get_enrichment_status(self, tenant_id: str, bu_id: str, app_user_id: str) -> list[tuple]:
        stmt = (
            select(
                CrawledProfileEntity.has_enriched_data,
                func.count().label("cnt"),
            )
            .select_from(ConnectionEntity)
            .join(CrawledProfileEntity, ConnectionEntity.crawled_profile_id == CrawledProfileEntity.id)
            .group_by(CrawledProfileEntity.has_enriched_data)
        )
        stmt = self._base_connection_filter(stmt, tenant_id, bu_id, app_user_id)
        return self._session.execute(stmt).all()

    def get_industry_breakdown(self, tenant_id: str, bu_id: str, app_user_id: str) -> list[tuple]:
        stmt = (
            select(CrawledProfileEntity.function_area.label("label"), func.count().label("cnt"))
            .select_from(ConnectionEntity)
            .join(CrawledProfileEntity, ConnectionEntity.crawled_profile_id == CrawledProfileEntity.id)
            .where(CrawledProfileEntity.function_area.isnot(None))
            .group_by(CrawledProfileEntity.function_area)
            .order_by(func.count().desc())
            .limit(10)
        )
        stmt = self._base_connection_filter(stmt, tenant_id, bu_id, app_user_id)
        return self._session.execute(stmt).all()

    def get_seniority_distribution(self, tenant_id: str, bu_id: str, app_user_id: str) -> list[tuple]:
        stmt = (
            select(CrawledProfileEntity.seniority_level.label("label"), func.count().label("cnt"))
            .select_from(ConnectionEntity)
            .join(CrawledProfileEntity, ConnectionEntity.crawled_profile_id == CrawledProfileEntity.id)
            .group_by(CrawledProfileEntity.seniority_level)
            .order_by(func.count().desc())
        )
        stmt = self._base_connection_filter(stmt, tenant_id, bu_id, app_user_id)
        return self._session.execute(stmt).all()

    def get_location_top(self, tenant_id: str, bu_id: str, app_user_id: str) -> list[tuple]:
        stmt = (
            select(
                CrawledProfileEntity.location_city.label("label"),
                func.count().label("cnt"),
            )
            .select_from(ConnectionEntity)
            .join(CrawledProfileEntity, ConnectionEntity.crawled_profile_id == CrawledProfileEntity.id)
            .where(CrawledProfileEntity.location_city.isnot(None))
            .group_by(CrawledProfileEntity.location_city)
            .order_by(func.count().desc())
            .limit(10)
        )
        stmt = self._base_connection_filter(stmt, tenant_id, bu_id, app_user_id)
        return self._session.execute(stmt).all()

    def get_top_companies(self, tenant_id: str, bu_id: str, app_user_id: str) -> list[tuple]:
        stmt = (
            select(
                CrawledProfileEntity.current_company_name.label("label"),
                func.count().label("cnt"),
            )
            .select_from(ConnectionEntity)
            .join(CrawledProfileEntity, ConnectionEntity.crawled_profile_id == CrawledProfileEntity.id)
            .where(CrawledProfileEntity.current_company_name.isnot(None))
            .group_by(CrawledProfileEntity.current_company_name)
            .order_by(func.count().desc())
            .limit(10)
        )
        stmt = self._base_connection_filter(stmt, tenant_id, bu_id, app_user_id)
        return self._session.execute(stmt).all()

    def get_affinity_tier_distribution(self, tenant_id: str, bu_id: str, app_user_id: str) -> list[tuple]:
        label = func.coalesce(ConnectionEntity.dunbar_tier, "Unassigned")
        stmt = (
            select(label.label("label"), func.count().label("cnt"))
            .group_by(label)
            .order_by(func.count().desc())
        )
        stmt = self._base_connection_filter(stmt, tenant_id, bu_id, app_user_id)
        return self._session.execute(stmt).all()

    def get_network_sources(self, tenant_id: str, bu_id: str, app_user_id: str) -> list[tuple]:
        source_unnest = func.unnest(ConnectionEntity.sources).label("source")
        subq = (
            select(ConnectionEntity.id, source_unnest)
            .where(
                ConnectionEntity.app_user_id == app_user_id,
                ConnectionEntity.tenant_id == tenant_id,
                ConnectionEntity.bu_id == bu_id,
                ConnectionEntity.is_active == True,  # noqa: E712
                ConnectionEntity.sources.isnot(None),
            )
            .subquery()
        )
        stmt = (
            select(subq.c.source.label("label"), func.count().label("cnt"))
            .group_by(subq.c.source)
            .order_by(func.count().desc())
        )
        return self._session.execute(stmt).all()
