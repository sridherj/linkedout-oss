# SPDX-License-Identifier: Apache-2.0
"""Repository for Experience entity (shared, no tenant/BU scoping)."""
from typing import List, Optional

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from common.schemas.base_enums_schemas import SortOrder
from linkedout.experience.entities.experience_entity import ExperienceEntity
from linkedout.experience.schemas.experience_api_schema import ExperienceSortByFields
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class ExperienceRepository:
    """
    Repository for Experience entity.

    Experience is a shared entity with no tenant/BU scoping.
    Follows the same pattern as CompanyRepository.
    """

    def __init__(self, session: Session):
        self._session = session
        logger.debug('Initialized ExperienceRepository with database session')

    def list_with_filters(
        self,
        limit: int = 20,
        offset: int = 0,
        sort_by: ExperienceSortByFields = ExperienceSortByFields.CREATED_AT,
        sort_order: SortOrder = SortOrder.ASC,
        crawled_profile_id: Optional[str] = None,
        company_id: Optional[str] = None,
        is_current: Optional[bool] = None,
        employment_type: Optional[str] = None,
    ) -> List[ExperienceEntity]:
        """List experiences with filters, sorting, and pagination."""
        logger.debug(f'Fetching experiences - sort_by: {sort_by}, sort_order: {sort_order}')

        query = self._session.query(ExperienceEntity)

        if crawled_profile_id:
            query = query.filter(ExperienceEntity.crawled_profile_id == crawled_profile_id)
        if company_id:
            query = query.filter(ExperienceEntity.company_id == company_id)
        if is_current is not None:
            query = query.filter(ExperienceEntity.is_current == is_current)
        if employment_type:
            query = query.filter(ExperienceEntity.employment_type == employment_type)

        sort_column = getattr(ExperienceEntity, sort_by, ExperienceEntity.created_at)
        if sort_order == SortOrder.DESC:
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        results = query.limit(limit).offset(offset).all()
        logger.debug(f'Fetched {len(results)} experiences (limit: {limit}, offset: {offset})')
        return results

    def count_with_filters(
        self,
        crawled_profile_id: Optional[str] = None,
        company_id: Optional[str] = None,
        is_current: Optional[bool] = None,
        employment_type: Optional[str] = None,
    ) -> int:
        """Count experiences matching filters."""
        logger.debug('Counting experiences')

        query = self._session.query(ExperienceEntity)

        if crawled_profile_id:
            query = query.filter(ExperienceEntity.crawled_profile_id == crawled_profile_id)
        if company_id:
            query = query.filter(ExperienceEntity.company_id == company_id)
        if is_current is not None:
            query = query.filter(ExperienceEntity.is_current == is_current)
        if employment_type:
            query = query.filter(ExperienceEntity.employment_type == employment_type)

        count = query.count()
        logger.debug(f'Total experience count with filters: {count}')
        return count

    def create(self, experience: ExperienceEntity) -> ExperienceEntity:
        """Create a new experience."""
        assert experience.crawled_profile_id is not None, 'Crawled profile ID is required'

        logger.debug(f'Creating experience for profile: {experience.crawled_profile_id}')
        try:
            self._session.add(experience)
            self._session.flush()
            self._session.refresh(experience)
            logger.info(f'Successfully created experience with ID: {experience.id}')
            return experience
        except Exception as e:
            logger.error(f'Failed to create experience: {str(e)}')
            raise

    def get_by_id(self, experience_id: str) -> Optional[ExperienceEntity]:
        """Get an experience by ID."""
        assert experience_id is not None, 'Experience ID is required'

        logger.debug(f'Fetching experience by ID: {experience_id}')
        try:
            experience = (
                self._session.query(ExperienceEntity)
                .filter(ExperienceEntity.id == experience_id)
                .one_or_none()
            )
            if experience is None:
                logger.debug(f'Experience not found: {experience_id}')
            else:
                logger.info(f'Successfully fetched experience: {experience_id}')
            return experience
        except Exception as e:
            logger.error(f'Failed to fetch experience {experience_id}: {str(e)}')
            raise

    def update(self, experience: ExperienceEntity) -> ExperienceEntity:
        """Update an experience."""
        assert experience.id is not None, 'Experience ID is required'

        logger.debug(f'Updating experience: {experience.id}')
        try:
            self._session.merge(experience)
            self._session.flush()
            self._session.refresh(experience)
            logger.info(f'Successfully updated experience: {experience.id}')
            return experience
        except Exception as e:
            logger.error(f'Failed to update experience: {str(e)}')
            raise

    def delete(self, experience: ExperienceEntity) -> None:
        """Delete an experience."""
        assert experience.id is not None, 'Experience ID is required'

        logger.debug(f'Deleting experience: {experience.id}')
        try:
            self._session.delete(experience)
            logger.info(f'Successfully deleted experience: {experience.id}')
        except Exception as e:
            logger.error(f'Failed to delete experience: {str(e)}')
            raise
