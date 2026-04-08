# SPDX-License-Identifier: Apache-2.0
"""Service for Education entity (shared, no tenant/BU scoping)."""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from linkedout.education.entities.education_entity import EducationEntity
from linkedout.education.repositories.education_repository import EducationRepository
from linkedout.education.schemas.education_api_schema import (
    CreateEducationRequestSchema,
    CreateEducationsRequestSchema,
    DeleteEducationByIdRequestSchema,
    GetEducationByIdRequestSchema,
    ListEducationsRequestSchema,
    UpdateEducationRequestSchema,
)
from linkedout.education.schemas.education_schema import EducationSchema
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class EducationService:
    """
    Service for Education business logic.

    Education is a shared entity with no tenant/BU scoping.
    Follows the same pattern as CompanyService.
    """

    def __init__(self, session: Session):
        self._session = session
        self._repository = EducationRepository(session)
        logger.debug('Initialized EducationService')

    def list_educations(
        self, list_request: ListEducationsRequestSchema
    ) -> Tuple[List[EducationSchema], int]:
        """List educations with filtering, sorting, and pagination."""
        logger.debug('Listing educations')

        educations = self._repository.list_with_filters(
            limit=list_request.limit,
            offset=list_request.offset,
            sort_by=list_request.sort_by,
            sort_order=list_request.sort_order,
            crawled_profile_id=list_request.crawled_profile_id,
            school_name=list_request.school_name,
            degree=list_request.degree,
        )

        total_count = self._repository.count_with_filters(
            crawled_profile_id=list_request.crawled_profile_id,
            school_name=list_request.school_name,
            degree=list_request.degree,
        )

        logger.debug(f'Found {len(educations)} educations out of {total_count} total')
        schemas = [EducationSchema.model_validate(e) for e in educations]
        return schemas, total_count

    def create_education(self, create_request: CreateEducationRequestSchema) -> EducationSchema:
        """Create a new education."""
        assert create_request.crawled_profile_id is not None, 'Crawled profile ID is required'

        logger.info(f'Creating education for profile: {create_request.crawled_profile_id}')

        entity = EducationEntity(
            crawled_profile_id=create_request.crawled_profile_id,
            school_name=create_request.school_name,
            school_linkedin_url=create_request.school_linkedin_url,
            degree=create_request.degree,
            field_of_study=create_request.field_of_study,
            start_year=create_request.start_year,
            end_year=create_request.end_year,
            description=create_request.description,
            raw_education=create_request.raw_education,
        )

        created = self._repository.create(entity)
        logger.info(f'Education created successfully with ID: {created.id}')
        return EducationSchema.model_validate(created)

    def create_educations(self, create_request: CreateEducationsRequestSchema) -> List[EducationSchema]:
        """Create multiple educations."""
        logger.info(f'Creating {len(create_request.educations)} educations')

        created_educations = []
        for edu_data in create_request.educations:
            entity = EducationEntity(
                crawled_profile_id=edu_data.crawled_profile_id,
                school_name=edu_data.school_name,
                school_linkedin_url=edu_data.school_linkedin_url,
                degree=edu_data.degree,
                field_of_study=edu_data.field_of_study,
                start_year=edu_data.start_year,
                end_year=edu_data.end_year,
                description=edu_data.description,
                raw_education=edu_data.raw_education,
            )
            created = self._repository.create(entity)
            created_educations.append(created)

        logger.info(f'Successfully created {len(created_educations)} educations')
        return [EducationSchema.model_validate(e) for e in created_educations]

    def update_education(self, update_request: UpdateEducationRequestSchema) -> EducationSchema:
        """Update an education."""
        assert update_request.education_id is not None, 'Education ID is required'

        logger.info(f'Updating education {update_request.education_id}')

        entity = self._repository.get_by_id(update_request.education_id)
        if not entity:
            raise ValueError(f'Education not found with ID: {update_request.education_id}')

        if update_request.school_name is not None:
            entity.school_name = update_request.school_name
        if update_request.school_linkedin_url is not None:
            entity.school_linkedin_url = update_request.school_linkedin_url
        if update_request.degree is not None:
            entity.degree = update_request.degree
        if update_request.field_of_study is not None:
            entity.field_of_study = update_request.field_of_study
        if update_request.start_year is not None:
            entity.start_year = update_request.start_year
        if update_request.end_year is not None:
            entity.end_year = update_request.end_year
        if update_request.description is not None:
            entity.description = update_request.description
        if update_request.raw_education is not None:
            entity.raw_education = update_request.raw_education

        updated = self._repository.update(entity)
        logger.info(f'Education updated successfully: {updated.id}')
        return EducationSchema.model_validate(updated)

    def get_education_by_id(self, get_request: GetEducationByIdRequestSchema) -> Optional[EducationSchema]:
        """Get an education by ID."""
        assert get_request.education_id is not None, 'Education ID is required'

        logger.info(f'Getting education {get_request.education_id}')

        entity = self._repository.get_by_id(get_request.education_id)
        if not entity:
            logger.info(f'Education not found: {get_request.education_id}')
            return None

        return EducationSchema.model_validate(entity)

    def delete_education_by_id(self, delete_request: DeleteEducationByIdRequestSchema) -> None:
        """Delete an education by ID."""
        assert delete_request.education_id is not None, 'Education ID is required'

        logger.info(f'Deleting education {delete_request.education_id}')

        entity = self._repository.get_by_id(delete_request.education_id)
        if not entity:
            raise ValueError(f'Education not found with ID: {delete_request.education_id}')

        self._repository.delete(entity)
        logger.info(f'Education deleted successfully: {delete_request.education_id}')
