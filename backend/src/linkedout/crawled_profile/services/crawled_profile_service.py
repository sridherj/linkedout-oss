# SPDX-License-Identifier: Apache-2.0
"""Service for CrawledProfile entity (shared, no tenant/BU scoping)."""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
from linkedout.crawled_profile.repositories.crawled_profile_repository import CrawledProfileRepository
from linkedout.crawled_profile.schemas.crawled_profile_api_schema import (
    CreateCrawledProfileRequestSchema,
    CreateCrawledProfilesRequestSchema,
    DeleteCrawledProfileByIdRequestSchema,
    GetCrawledProfileByIdRequestSchema,
    ListCrawledProfilesRequestSchema,
    UpdateCrawledProfileRequestSchema,
)
from linkedout.crawled_profile.schemas.crawled_profile_schema import CrawledProfileSchema
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class CrawledProfileService:
    """
    Service for CrawledProfile business logic.

    CrawledProfile is a shared entity with no tenant/BU scoping.
    """

    def __init__(self, session: Session):
        self._session = session
        self._repository = CrawledProfileRepository(session)
        logger.debug('Initialized CrawledProfileService')

    def list_crawled_profiles(
        self, list_request: ListCrawledProfilesRequestSchema
    ) -> Tuple[List[CrawledProfileSchema], int]:
        """List crawled profiles with filtering, sorting, and pagination."""
        logger.debug('Listing crawled profiles')

        crawled_profiles = self._repository.list_with_filters(
            limit=list_request.limit,
            offset=list_request.offset,
            sort_by=list_request.sort_by,
            sort_order=list_request.sort_order,
            full_name=list_request.full_name,
            current_company_name=list_request.current_company_name,
            company_id=list_request.company_id,
            seniority_level=list_request.seniority_level,
            function_area=list_request.function_area,
            data_source=list_request.data_source,
            has_enriched_data=list_request.has_enriched_data,
            location_country_code=list_request.location_country_code,
            crawled_profile_ids=list_request.crawled_profile_ids,
            linkedin_url=list_request.linkedin_url,
        )

        total_count = self._repository.count_with_filters(
            full_name=list_request.full_name,
            current_company_name=list_request.current_company_name,
            company_id=list_request.company_id,
            seniority_level=list_request.seniority_level,
            function_area=list_request.function_area,
            data_source=list_request.data_source,
            has_enriched_data=list_request.has_enriched_data,
            location_country_code=list_request.location_country_code,
            crawled_profile_ids=list_request.crawled_profile_ids,
            linkedin_url=list_request.linkedin_url,
        )

        logger.debug(f'Found {len(crawled_profiles)} crawled profiles out of {total_count} total')
        schemas = [CrawledProfileSchema.model_validate(c) for c in crawled_profiles]
        return schemas, total_count

    def create_crawled_profile(self, create_request: CreateCrawledProfileRequestSchema) -> CrawledProfileSchema:
        """Create a new crawled profile."""
        assert create_request.linkedin_url is not None, 'LinkedIn URL is required'

        logger.info(f'Creating crawled profile: {create_request.linkedin_url}')

        entity = CrawledProfileEntity(
            linkedin_url=create_request.linkedin_url,
            public_identifier=create_request.public_identifier,
            first_name=create_request.first_name,
            last_name=create_request.last_name,
            full_name=create_request.full_name,
            headline=create_request.headline,
            about=create_request.about,
            location_city=create_request.location_city,
            location_state=create_request.location_state,
            location_country=create_request.location_country,
            location_country_code=create_request.location_country_code,
            location_raw=create_request.location_raw,
            connections_count=create_request.connections_count,
            follower_count=create_request.follower_count,
            open_to_work=create_request.open_to_work,
            premium=create_request.premium,
            current_company_name=create_request.current_company_name,
            current_position=create_request.current_position,
            company_id=create_request.company_id,
            seniority_level=create_request.seniority_level,
            function_area=create_request.function_area,
            source_app_user_id=create_request.source_app_user_id,
            data_source=create_request.data_source,
            has_enriched_data=create_request.has_enriched_data,
            last_crawled_at=create_request.last_crawled_at,
            raw_profile=create_request.raw_profile,
        )

        created = self._repository.create(entity)
        logger.info(f'CrawledProfile created successfully with ID: {created.id}')
        return CrawledProfileSchema.model_validate(created)

    def create_crawled_profiles(self, create_request: CreateCrawledProfilesRequestSchema) -> List[CrawledProfileSchema]:
        """Create multiple crawled profiles."""
        logger.info(f'Creating {len(create_request.crawled_profiles)} crawled profiles')

        created_profiles = []
        for profile_data in create_request.crawled_profiles:
            entity = CrawledProfileEntity(
                linkedin_url=profile_data.linkedin_url,
                public_identifier=profile_data.public_identifier,
                first_name=profile_data.first_name,
                last_name=profile_data.last_name,
                full_name=profile_data.full_name,
                headline=profile_data.headline,
                about=profile_data.about,
                location_city=profile_data.location_city,
                location_state=profile_data.location_state,
                location_country=profile_data.location_country,
                location_country_code=profile_data.location_country_code,
                location_raw=profile_data.location_raw,
                connections_count=profile_data.connections_count,
                follower_count=profile_data.follower_count,
                open_to_work=profile_data.open_to_work,
                premium=profile_data.premium,
                current_company_name=profile_data.current_company_name,
                current_position=profile_data.current_position,
                company_id=profile_data.company_id,
                seniority_level=profile_data.seniority_level,
                function_area=profile_data.function_area,
                source_app_user_id=profile_data.source_app_user_id,
                data_source=profile_data.data_source,
                has_enriched_data=profile_data.has_enriched_data,
                last_crawled_at=profile_data.last_crawled_at,
                raw_profile=profile_data.raw_profile,
            )
            created = self._repository.create(entity)
            created_profiles.append(created)

        logger.info(f'Successfully created {len(created_profiles)} crawled profiles')
        return [CrawledProfileSchema.model_validate(c) for c in created_profiles]

    def update_crawled_profile(self, update_request: UpdateCrawledProfileRequestSchema) -> CrawledProfileSchema:
        """Update a crawled profile."""
        assert update_request.crawled_profile_id is not None, 'CrawledProfile ID is required'

        logger.info(f'Updating crawled profile {update_request.crawled_profile_id}')

        entity = self._repository.get_by_id(update_request.crawled_profile_id)
        if not entity:
            raise ValueError(f'CrawledProfile not found with ID: {update_request.crawled_profile_id}')

        # Update only provided fields
        if update_request.linkedin_url is not None:
            entity.linkedin_url = update_request.linkedin_url
        if update_request.public_identifier is not None:
            entity.public_identifier = update_request.public_identifier
        if update_request.first_name is not None:
            entity.first_name = update_request.first_name
        if update_request.last_name is not None:
            entity.last_name = update_request.last_name
        if update_request.full_name is not None:
            entity.full_name = update_request.full_name
        if update_request.headline is not None:
            entity.headline = update_request.headline
        if update_request.about is not None:
            entity.about = update_request.about
        if update_request.location_city is not None:
            entity.location_city = update_request.location_city
        if update_request.location_state is not None:
            entity.location_state = update_request.location_state
        if update_request.location_country is not None:
            entity.location_country = update_request.location_country
        if update_request.location_country_code is not None:
            entity.location_country_code = update_request.location_country_code
        if update_request.location_raw is not None:
            entity.location_raw = update_request.location_raw
        if update_request.connections_count is not None:
            entity.connections_count = update_request.connections_count
        if update_request.follower_count is not None:
            entity.follower_count = update_request.follower_count
        if update_request.open_to_work is not None:
            entity.open_to_work = update_request.open_to_work
        if update_request.premium is not None:
            entity.premium = update_request.premium
        if update_request.current_company_name is not None:
            entity.current_company_name = update_request.current_company_name
        if update_request.current_position is not None:
            entity.current_position = update_request.current_position
        if update_request.company_id is not None:
            entity.company_id = update_request.company_id
        if update_request.seniority_level is not None:
            entity.seniority_level = update_request.seniority_level
        if update_request.function_area is not None:
            entity.function_area = update_request.function_area
        if update_request.source_app_user_id is not None:
            entity.source_app_user_id = update_request.source_app_user_id
        if update_request.data_source is not None:
            entity.data_source = update_request.data_source
        if update_request.has_enriched_data is not None:
            entity.has_enriched_data = update_request.has_enriched_data
        if update_request.last_crawled_at is not None:
            entity.last_crawled_at = update_request.last_crawled_at
        if update_request.raw_profile is not None:
            entity.raw_profile = update_request.raw_profile

        updated = self._repository.update(entity)
        logger.info(f'CrawledProfile updated successfully: {updated.id}')
        return CrawledProfileSchema.model_validate(updated)

    def get_crawled_profile_by_id(self, get_request: GetCrawledProfileByIdRequestSchema) -> Optional[CrawledProfileSchema]:
        """Get a crawled profile by ID."""
        assert get_request.crawled_profile_id is not None, 'CrawledProfile ID is required'

        logger.info(f'Getting crawled profile {get_request.crawled_profile_id}')

        entity = self._repository.get_by_id(get_request.crawled_profile_id)
        if not entity:
            logger.info(f'CrawledProfile not found: {get_request.crawled_profile_id}')
            return None

        return CrawledProfileSchema.model_validate(entity)

    def delete_crawled_profile_by_id(self, delete_request: DeleteCrawledProfileByIdRequestSchema) -> None:
        """Delete a crawled profile by ID."""
        assert delete_request.crawled_profile_id is not None, 'CrawledProfile ID is required'

        logger.info(f'Deleting crawled profile {delete_request.crawled_profile_id}')

        entity = self._repository.get_by_id(delete_request.crawled_profile_id)
        if not entity:
            raise ValueError(f'CrawledProfile not found with ID: {delete_request.crawled_profile_id}')

        self._repository.delete(entity)
        logger.info(f'CrawledProfile deleted successfully: {delete_request.crawled_profile_id}')
