# SPDX-License-Identifier: Apache-2.0
"""Repository for Education entity (shared, no tenant/BU scoping)."""
from typing import List, Optional

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from common.schemas.base_enums_schemas import SortOrder
from linkedout.education.entities.education_entity import EducationEntity
from linkedout.education.schemas.education_api_schema import EducationSortByFields
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class EducationRepository:
    """
    Repository for Education entity.

    Education is a shared entity with no tenant/BU scoping.
    Follows the same pattern as CompanyRepository.
    """

    def __init__(self, session: Session):
        self._session = session
        logger.debug('Initialized EducationRepository with database session')

    def list_with_filters(
        self,
        limit: int = 20,
        offset: int = 0,
        sort_by: EducationSortByFields = EducationSortByFields.CREATED_AT,
        sort_order: SortOrder = SortOrder.ASC,
        crawled_profile_id: Optional[str] = None,
        school_name: Optional[str] = None,
        degree: Optional[str] = None,
    ) -> List[EducationEntity]:
        """List educations with filters, sorting, and pagination."""
        logger.debug(f'Fetching educations - sort_by: {sort_by}, sort_order: {sort_order}')

        query = self._session.query(EducationEntity)

        if crawled_profile_id:
            query = query.filter(EducationEntity.crawled_profile_id == crawled_profile_id)
        if school_name:
            query = query.filter(EducationEntity.school_name.ilike(f'%{school_name}%'))
        if degree:
            query = query.filter(EducationEntity.degree.ilike(f'%{degree}%'))

        sort_column = getattr(EducationEntity, sort_by, EducationEntity.created_at)
        if sort_order == SortOrder.DESC:
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        results = query.limit(limit).offset(offset).all()
        logger.debug(f'Fetched {len(results)} educations (limit: {limit}, offset: {offset})')
        return results

    def count_with_filters(
        self,
        crawled_profile_id: Optional[str] = None,
        school_name: Optional[str] = None,
        degree: Optional[str] = None,
    ) -> int:
        """Count educations matching filters."""
        logger.debug('Counting educations')

        query = self._session.query(EducationEntity)

        if crawled_profile_id:
            query = query.filter(EducationEntity.crawled_profile_id == crawled_profile_id)
        if school_name:
            query = query.filter(EducationEntity.school_name.ilike(f'%{school_name}%'))
        if degree:
            query = query.filter(EducationEntity.degree.ilike(f'%{degree}%'))

        count = query.count()
        logger.debug(f'Total education count with filters: {count}')
        return count

    def create(self, education: EducationEntity) -> EducationEntity:
        """Create a new education."""
        assert education.crawled_profile_id is not None, 'Crawled profile ID is required'

        logger.debug(f'Creating education for profile: {education.crawled_profile_id}')
        try:
            self._session.add(education)
            self._session.flush()
            self._session.refresh(education)
            logger.info(f'Successfully created education with ID: {education.id}')
            return education
        except Exception as e:
            logger.error(f'Failed to create education: {str(e)}')
            raise

    def get_by_id(self, education_id: str) -> Optional[EducationEntity]:
        """Get an education by ID."""
        assert education_id is not None, 'Education ID is required'

        logger.debug(f'Fetching education by ID: {education_id}')
        try:
            education = (
                self._session.query(EducationEntity)
                .filter(EducationEntity.id == education_id)
                .one_or_none()
            )
            if education is None:
                logger.debug(f'Education not found: {education_id}')
            else:
                logger.info(f'Successfully fetched education: {education_id}')
            return education
        except Exception as e:
            logger.error(f'Failed to fetch education {education_id}: {str(e)}')
            raise

    def update(self, education: EducationEntity) -> EducationEntity:
        """Update an education."""
        assert education.id is not None, 'Education ID is required'

        logger.debug(f'Updating education: {education.id}')
        try:
            self._session.merge(education)
            self._session.flush()
            self._session.refresh(education)
            logger.info(f'Successfully updated education: {education.id}')
            return education
        except Exception as e:
            logger.error(f'Failed to update education: {str(e)}')
            raise

    def delete(self, education: EducationEntity) -> None:
        """Delete an education."""
        assert education.id is not None, 'Education ID is required'

        logger.debug(f'Deleting education: {education.id}')
        try:
            self._session.delete(education)
            logger.info(f'Successfully deleted education: {education.id}')
        except Exception as e:
            logger.error(f'Failed to delete education: {str(e)}')
            raise
