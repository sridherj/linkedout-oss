# SPDX-License-Identifier: Apache-2.0
"""Repository for CrawledProfile entity (shared, no tenant/BU scoping)."""
from typing import List, Optional

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from common.schemas.base_enums_schemas import SortOrder
from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
from linkedout.crawled_profile.schemas.crawled_profile_api_schema import CrawledProfileSortByFields
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class CrawledProfileRepository:
    """
    Repository for CrawledProfile entity.

    CrawledProfile is a shared entity with no tenant/BU scoping.
    """

    def __init__(self, session: Session):
        self._session = session
        logger.debug('Initialized CrawledProfileRepository with database session')

    def list_with_filters(
        self,
        limit: int = 20,
        offset: int = 0,
        sort_by: CrawledProfileSortByFields = CrawledProfileSortByFields.CREATED_AT,
        sort_order: SortOrder = SortOrder.DESC,
        full_name: Optional[str] = None,
        current_company_name: Optional[str] = None,
        company_id: Optional[str] = None,
        seniority_level: Optional[str] = None,
        function_area: Optional[str] = None,
        data_source: Optional[str] = None,
        has_enriched_data: Optional[bool] = None,
        location_country_code: Optional[str] = None,
        crawled_profile_ids: Optional[List[str]] = None,
        linkedin_url: Optional[str] = None,
    ) -> List[CrawledProfileEntity]:
        """List crawled profiles with filters, sorting, and pagination."""
        logger.debug(f'Fetching crawled profiles - sort_by: {sort_by}, sort_order: {sort_order}')

        query = self._session.query(CrawledProfileEntity)

        # Apply filters
        if full_name:
            query = query.filter(CrawledProfileEntity.full_name.ilike(f'%{full_name}%'))
        if current_company_name:
            query = query.filter(CrawledProfileEntity.current_company_name.ilike(f'%{current_company_name}%'))
        if company_id:
            query = query.filter(CrawledProfileEntity.company_id == company_id)
        if seniority_level:
            query = query.filter(CrawledProfileEntity.seniority_level == seniority_level)
        if function_area:
            query = query.filter(CrawledProfileEntity.function_area == function_area)
        if data_source:
            query = query.filter(CrawledProfileEntity.data_source == data_source)
        if has_enriched_data is not None:
            query = query.filter(CrawledProfileEntity.has_enriched_data == has_enriched_data)
        if location_country_code:
            query = query.filter(CrawledProfileEntity.location_country_code == location_country_code)
        if crawled_profile_ids:
            query = query.filter(CrawledProfileEntity.id.in_(crawled_profile_ids))
        if linkedin_url:
            query = query.filter(CrawledProfileEntity.linkedin_url == linkedin_url)

        # Apply sorting
        sort_column = getattr(CrawledProfileEntity, sort_by, CrawledProfileEntity.created_at)
        if sort_order == SortOrder.DESC:
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        results = query.limit(limit).offset(offset).all()
        logger.debug(f'Fetched {len(results)} crawled profiles (limit: {limit}, offset: {offset})')
        return results

    def count_with_filters(
        self,
        full_name: Optional[str] = None,
        current_company_name: Optional[str] = None,
        company_id: Optional[str] = None,
        seniority_level: Optional[str] = None,
        function_area: Optional[str] = None,
        data_source: Optional[str] = None,
        has_enriched_data: Optional[bool] = None,
        location_country_code: Optional[str] = None,
        crawled_profile_ids: Optional[List[str]] = None,
        linkedin_url: Optional[str] = None,
    ) -> int:
        """Count crawled profiles matching filters."""
        logger.debug('Counting crawled profiles')

        query = self._session.query(CrawledProfileEntity)

        if full_name:
            query = query.filter(CrawledProfileEntity.full_name.ilike(f'%{full_name}%'))
        if current_company_name:
            query = query.filter(CrawledProfileEntity.current_company_name.ilike(f'%{current_company_name}%'))
        if company_id:
            query = query.filter(CrawledProfileEntity.company_id == company_id)
        if seniority_level:
            query = query.filter(CrawledProfileEntity.seniority_level == seniority_level)
        if function_area:
            query = query.filter(CrawledProfileEntity.function_area == function_area)
        if data_source:
            query = query.filter(CrawledProfileEntity.data_source == data_source)
        if has_enriched_data is not None:
            query = query.filter(CrawledProfileEntity.has_enriched_data == has_enriched_data)
        if location_country_code:
            query = query.filter(CrawledProfileEntity.location_country_code == location_country_code)
        if crawled_profile_ids:
            query = query.filter(CrawledProfileEntity.id.in_(crawled_profile_ids))
        if linkedin_url:
            query = query.filter(CrawledProfileEntity.linkedin_url == linkedin_url)

        count = query.count()
        logger.debug(f'Total crawled profile count with filters: {count}')
        return count

    def create(self, crawled_profile: CrawledProfileEntity) -> CrawledProfileEntity:
        """Create a new crawled profile."""
        assert crawled_profile.linkedin_url is not None, 'LinkedIn URL is required'

        logger.debug(f'Creating crawled profile: {crawled_profile.linkedin_url}')
        try:
            self._session.add(crawled_profile)
            self._session.flush()
            self._session.refresh(crawled_profile)
            logger.info(f'Successfully created crawled profile with ID: {crawled_profile.id}')
            return crawled_profile
        except Exception as e:
            logger.error(f'Failed to create crawled profile: {str(e)}')
            raise

    def get_by_id(self, crawled_profile_id: str) -> Optional[CrawledProfileEntity]:
        """Get a crawled profile by ID."""
        assert crawled_profile_id is not None, 'CrawledProfile ID is required'

        logger.debug(f'Fetching crawled profile by ID: {crawled_profile_id}')
        try:
            crawled_profile = (
                self._session.query(CrawledProfileEntity)
                .filter(CrawledProfileEntity.id == crawled_profile_id)
                .one_or_none()
            )
            if crawled_profile is None:
                logger.debug(f'CrawledProfile not found: {crawled_profile_id}')
            else:
                logger.info(f'Successfully fetched crawled profile: {crawled_profile_id}')
            return crawled_profile
        except Exception as e:
            logger.error(f'Failed to fetch crawled profile {crawled_profile_id}: {str(e)}')
            raise

    def update(self, crawled_profile: CrawledProfileEntity) -> CrawledProfileEntity:
        """Update a crawled profile."""
        assert crawled_profile.id is not None, 'CrawledProfile ID is required'

        logger.debug(f'Updating crawled profile: {crawled_profile.id}')
        try:
            self._session.merge(crawled_profile)
            self._session.flush()
            self._session.refresh(crawled_profile)
            logger.info(f'Successfully updated crawled profile: {crawled_profile.id}')
            return crawled_profile
        except Exception as e:
            logger.error(f'Failed to update crawled profile: {str(e)}')
            raise

    def delete(self, crawled_profile: CrawledProfileEntity) -> None:
        """Delete a crawled profile."""
        assert crawled_profile.id is not None, 'CrawledProfile ID is required'

        logger.debug(f'Deleting crawled profile: {crawled_profile.id}')
        try:
            self._session.delete(crawled_profile)
            logger.info(f'Successfully deleted crawled profile: {crawled_profile.id}')
        except Exception as e:
            logger.error(f'Failed to delete crawled profile: {str(e)}')
            raise
