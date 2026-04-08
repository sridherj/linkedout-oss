# SPDX-License-Identifier: Apache-2.0
"""Service for Experience entity (shared, no tenant/BU scoping)."""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from linkedout.experience.entities.experience_entity import ExperienceEntity
from linkedout.experience.repositories.experience_repository import ExperienceRepository
from linkedout.experience.schemas.experience_api_schema import (
    CreateExperienceRequestSchema,
    CreateExperiencesRequestSchema,
    DeleteExperienceByIdRequestSchema,
    GetExperienceByIdRequestSchema,
    ListExperiencesRequestSchema,
    UpdateExperienceRequestSchema,
)
from linkedout.experience.schemas.experience_schema import ExperienceSchema
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class ExperienceService:
    """
    Service for Experience business logic.

    Experience is a shared entity with no tenant/BU scoping.
    Follows the same pattern as CompanyService.
    """

    def __init__(self, session: Session):
        self._session = session
        self._repository = ExperienceRepository(session)
        logger.debug('Initialized ExperienceService')

    def list_experiences(
        self, list_request: ListExperiencesRequestSchema
    ) -> Tuple[List[ExperienceSchema], int]:
        """List experiences with filtering, sorting, and pagination."""
        logger.debug('Listing experiences')

        experiences = self._repository.list_with_filters(
            limit=list_request.limit,
            offset=list_request.offset,
            sort_by=list_request.sort_by,
            sort_order=list_request.sort_order,
            crawled_profile_id=list_request.crawled_profile_id,
            company_id=list_request.company_id,
            is_current=list_request.is_current,
            employment_type=list_request.employment_type,
        )

        total_count = self._repository.count_with_filters(
            crawled_profile_id=list_request.crawled_profile_id,
            company_id=list_request.company_id,
            is_current=list_request.is_current,
            employment_type=list_request.employment_type,
        )

        logger.debug(f'Found {len(experiences)} experiences out of {total_count} total')
        schemas = [ExperienceSchema.model_validate(e) for e in experiences]
        return schemas, total_count

    def create_experience(self, create_request: CreateExperienceRequestSchema) -> ExperienceSchema:
        """Create a new experience."""
        assert create_request.crawled_profile_id is not None, 'Crawled profile ID is required'

        logger.info(f'Creating experience for profile: {create_request.crawled_profile_id}')

        entity = ExperienceEntity(
            crawled_profile_id=create_request.crawled_profile_id,
            position=create_request.position,
            position_normalized=create_request.position_normalized,
            company_name=create_request.company_name,
            company_id=create_request.company_id,
            company_linkedin_url=create_request.company_linkedin_url,
            employment_type=create_request.employment_type,
            start_date=create_request.start_date,
            start_year=create_request.start_year,
            start_month=create_request.start_month,
            end_date=create_request.end_date,
            end_year=create_request.end_year,
            end_month=create_request.end_month,
            end_date_text=create_request.end_date_text,
            seniority_level=create_request.seniority_level,
            function_area=create_request.function_area,
            location=create_request.location,
            description=create_request.description,
            raw_experience=create_request.raw_experience,
        )

        created = self._repository.create(entity)
        logger.info(f'Experience created successfully with ID: {created.id}')
        return ExperienceSchema.model_validate(created)

    def create_experiences(self, create_request: CreateExperiencesRequestSchema) -> List[ExperienceSchema]:
        """Create multiple experiences."""
        logger.info(f'Creating {len(create_request.experiences)} experiences')

        created_experiences = []
        for exp_data in create_request.experiences:
            entity = ExperienceEntity(
                crawled_profile_id=exp_data.crawled_profile_id,
                position=exp_data.position,
                position_normalized=exp_data.position_normalized,
                company_name=exp_data.company_name,
                company_id=exp_data.company_id,
                company_linkedin_url=exp_data.company_linkedin_url,
                employment_type=exp_data.employment_type,
                start_date=exp_data.start_date,
                start_year=exp_data.start_year,
                start_month=exp_data.start_month,
                end_date=exp_data.end_date,
                end_year=exp_data.end_year,
                end_month=exp_data.end_month,
                end_date_text=exp_data.end_date_text,
                seniority_level=exp_data.seniority_level,
                function_area=exp_data.function_area,
                location=exp_data.location,
                description=exp_data.description,
                raw_experience=exp_data.raw_experience,
            )
            created = self._repository.create(entity)
            created_experiences.append(created)

        logger.info(f'Successfully created {len(created_experiences)} experiences')
        return [ExperienceSchema.model_validate(e) for e in created_experiences]

    def update_experience(self, update_request: UpdateExperienceRequestSchema) -> ExperienceSchema:
        """Update an experience."""
        assert update_request.experience_id is not None, 'Experience ID is required'

        logger.info(f'Updating experience {update_request.experience_id}')

        entity = self._repository.get_by_id(update_request.experience_id)
        if not entity:
            raise ValueError(f'Experience not found with ID: {update_request.experience_id}')

        if update_request.position is not None:
            entity.position = update_request.position
        if update_request.position_normalized is not None:
            entity.position_normalized = update_request.position_normalized
        if update_request.company_name is not None:
            entity.company_name = update_request.company_name
        if update_request.company_id is not None:
            entity.company_id = update_request.company_id
        if update_request.company_linkedin_url is not None:
            entity.company_linkedin_url = update_request.company_linkedin_url
        if update_request.employment_type is not None:
            entity.employment_type = update_request.employment_type
        if update_request.start_date is not None:
            entity.start_date = update_request.start_date
        if update_request.start_year is not None:
            entity.start_year = update_request.start_year
        if update_request.start_month is not None:
            entity.start_month = update_request.start_month
        if update_request.end_date is not None:
            entity.end_date = update_request.end_date
        if update_request.end_year is not None:
            entity.end_year = update_request.end_year
        if update_request.end_month is not None:
            entity.end_month = update_request.end_month
        if update_request.end_date_text is not None:
            entity.end_date_text = update_request.end_date_text
        if update_request.seniority_level is not None:
            entity.seniority_level = update_request.seniority_level
        if update_request.function_area is not None:
            entity.function_area = update_request.function_area
        if update_request.location is not None:
            entity.location = update_request.location
        if update_request.description is not None:
            entity.description = update_request.description
        if update_request.raw_experience is not None:
            entity.raw_experience = update_request.raw_experience

        updated = self._repository.update(entity)
        logger.info(f'Experience updated successfully: {updated.id}')
        return ExperienceSchema.model_validate(updated)

    def get_experience_by_id(self, get_request: GetExperienceByIdRequestSchema) -> Optional[ExperienceSchema]:
        """Get an experience by ID."""
        assert get_request.experience_id is not None, 'Experience ID is required'

        logger.info(f'Getting experience {get_request.experience_id}')

        entity = self._repository.get_by_id(get_request.experience_id)
        if not entity:
            logger.info(f'Experience not found: {get_request.experience_id}')
            return None

        return ExperienceSchema.model_validate(entity)

    def delete_experience_by_id(self, delete_request: DeleteExperienceByIdRequestSchema) -> None:
        """Delete an experience by ID."""
        assert delete_request.experience_id is not None, 'Experience ID is required'

        logger.info(f'Deleting experience {delete_request.experience_id}')

        entity = self._repository.get_by_id(delete_request.experience_id)
        if not entity:
            raise ValueError(f'Experience not found with ID: {delete_request.experience_id}')

        self._repository.delete(entity)
        logger.info(f'Experience deleted successfully: {delete_request.experience_id}')
