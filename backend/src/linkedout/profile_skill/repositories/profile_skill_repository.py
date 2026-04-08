# SPDX-License-Identifier: Apache-2.0
"""Repository for ProfileSkill entity (shared, no tenant/BU scoping)."""
from typing import List, Optional

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from common.schemas.base_enums_schemas import SortOrder
from linkedout.profile_skill.entities.profile_skill_entity import ProfileSkillEntity
from linkedout.profile_skill.schemas.profile_skill_api_schema import ProfileSkillSortByFields
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class ProfileSkillRepository:
    """
    Repository for ProfileSkill entity.

    ProfileSkill is a shared entity with no tenant/BU scoping.
    Follows the same pattern as CompanyRepository.
    """

    def __init__(self, session: Session):
        self._session = session
        logger.debug('Initialized ProfileSkillRepository with database session')

    def list_with_filters(
        self,
        limit: int = 20,
        offset: int = 0,
        sort_by: ProfileSkillSortByFields = ProfileSkillSortByFields.CREATED_AT,
        sort_order: SortOrder = SortOrder.ASC,
        crawled_profile_id: Optional[str] = None,
        skill_name: Optional[str] = None,
    ) -> List[ProfileSkillEntity]:
        """List profile skills with filters, sorting, and pagination."""
        logger.debug(f'Fetching profile skills - sort_by: {sort_by}, sort_order: {sort_order}')

        query = self._session.query(ProfileSkillEntity)

        if crawled_profile_id:
            query = query.filter(ProfileSkillEntity.crawled_profile_id == crawled_profile_id)
        if skill_name:
            query = query.filter(ProfileSkillEntity.skill_name.ilike(f'%{skill_name}%'))

        sort_column = getattr(ProfileSkillEntity, sort_by, ProfileSkillEntity.created_at)
        if sort_order == SortOrder.DESC:
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        results = query.limit(limit).offset(offset).all()
        logger.debug(f'Fetched {len(results)} profile skills (limit: {limit}, offset: {offset})')
        return results

    def count_with_filters(
        self,
        crawled_profile_id: Optional[str] = None,
        skill_name: Optional[str] = None,
    ) -> int:
        """Count profile skills matching filters."""
        logger.debug('Counting profile skills')

        query = self._session.query(ProfileSkillEntity)

        if crawled_profile_id:
            query = query.filter(ProfileSkillEntity.crawled_profile_id == crawled_profile_id)
        if skill_name:
            query = query.filter(ProfileSkillEntity.skill_name.ilike(f'%{skill_name}%'))

        count = query.count()
        logger.debug(f'Total profile skill count with filters: {count}')
        return count

    def create(self, profile_skill: ProfileSkillEntity) -> ProfileSkillEntity:
        """Create a new profile skill."""
        assert profile_skill.crawled_profile_id is not None, 'Crawled profile ID is required'
        assert profile_skill.skill_name is not None, 'Skill name is required'

        logger.debug(f'Creating profile skill: {profile_skill.skill_name} for profile: {profile_skill.crawled_profile_id}')
        try:
            self._session.add(profile_skill)
            self._session.flush()
            self._session.refresh(profile_skill)
            logger.info(f'Successfully created profile skill with ID: {profile_skill.id}')
            return profile_skill
        except Exception as e:
            logger.error(f'Failed to create profile skill: {str(e)}')
            raise

    def get_by_id(self, profile_skill_id: str) -> Optional[ProfileSkillEntity]:
        """Get a profile skill by ID."""
        assert profile_skill_id is not None, 'ProfileSkill ID is required'

        logger.debug(f'Fetching profile skill by ID: {profile_skill_id}')
        try:
            profile_skill = (
                self._session.query(ProfileSkillEntity)
                .filter(ProfileSkillEntity.id == profile_skill_id)
                .one_or_none()
            )
            if profile_skill is None:
                logger.debug(f'ProfileSkill not found: {profile_skill_id}')
            else:
                logger.info(f'Successfully fetched profile skill: {profile_skill_id}')
            return profile_skill
        except Exception as e:
            logger.error(f'Failed to fetch profile skill {profile_skill_id}: {str(e)}')
            raise

    def update(self, profile_skill: ProfileSkillEntity) -> ProfileSkillEntity:
        """Update a profile skill."""
        assert profile_skill.id is not None, 'ProfileSkill ID is required'

        logger.debug(f'Updating profile skill: {profile_skill.id}')
        try:
            self._session.merge(profile_skill)
            self._session.flush()
            self._session.refresh(profile_skill)
            logger.info(f'Successfully updated profile skill: {profile_skill.id}')
            return profile_skill
        except Exception as e:
            logger.error(f'Failed to update profile skill: {str(e)}')
            raise

    def delete(self, profile_skill: ProfileSkillEntity) -> None:
        """Delete a profile skill."""
        assert profile_skill.id is not None, 'ProfileSkill ID is required'

        logger.debug(f'Deleting profile skill: {profile_skill.id}')
        try:
            self._session.delete(profile_skill)
            logger.info(f'Successfully deleted profile skill: {profile_skill.id}')
        except Exception as e:
            logger.error(f'Failed to delete profile skill: {str(e)}')
            raise
