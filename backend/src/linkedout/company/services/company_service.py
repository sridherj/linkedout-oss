# SPDX-License-Identifier: Apache-2.0
"""Service for Company entity (shared, no tenant/BU scoping)."""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from linkedout.company.entities.company_entity import CompanyEntity
from linkedout.company.repositories.company_repository import CompanyRepository
from linkedout.company.schemas.company_api_schema import (
    CreateCompanyRequestSchema,
    CreateCompaniesRequestSchema,
    DeleteCompanyByIdRequestSchema,
    GetCompanyByIdRequestSchema,
    ListCompaniesRequestSchema,
    UpdateCompanyRequestSchema,
)
from linkedout.company.schemas.company_schema import CompanySchema
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class CompanyService:
    """
    Service for Company business logic.

    Company is a shared entity with no tenant/BU scoping.
    Follows the same pattern as TenantService.
    """

    def __init__(self, session: Session):
        self._session = session
        self._repository = CompanyRepository(session)
        logger.debug('Initialized CompanyService')

    def list_companies(
        self, list_request: ListCompaniesRequestSchema
    ) -> Tuple[List[CompanySchema], int]:
        """List companies with filtering, sorting, and pagination."""
        logger.debug('Listing companies')

        companies = self._repository.list_with_filters(
            limit=list_request.limit,
            offset=list_request.offset,
            sort_by=list_request.sort_by,
            sort_order=list_request.sort_order,
            canonical_name=list_request.canonical_name,
            domain=list_request.domain,
            industry=list_request.industry,
            size_tier=list_request.size_tier,
            hq_country=list_request.hq_country,
            company_ids=list_request.company_ids,
        )

        total_count = self._repository.count_with_filters(
            canonical_name=list_request.canonical_name,
            domain=list_request.domain,
            industry=list_request.industry,
            size_tier=list_request.size_tier,
            hq_country=list_request.hq_country,
            company_ids=list_request.company_ids,
        )

        logger.debug(f'Found {len(companies)} companies out of {total_count} total')
        schemas = [CompanySchema.model_validate(c) for c in companies]
        return schemas, total_count

    def create_company(self, create_request: CreateCompanyRequestSchema) -> CompanySchema:
        """Create a new company."""
        assert create_request.canonical_name is not None, 'Canonical name is required'

        logger.info(f'Creating company: {create_request.canonical_name}')

        entity = CompanyEntity(
            canonical_name=create_request.canonical_name,
            normalized_name=create_request.normalized_name,
            linkedin_url=create_request.linkedin_url,
            universal_name=create_request.universal_name,
            website=create_request.website,
            domain=create_request.domain,
            industry=create_request.industry,
            founded_year=create_request.founded_year,
            hq_city=create_request.hq_city,
            hq_country=create_request.hq_country,
            employee_count_range=create_request.employee_count_range,
            estimated_employee_count=create_request.estimated_employee_count,
            size_tier=create_request.size_tier,
            network_connection_count=create_request.network_connection_count,
            parent_company_id=create_request.parent_company_id,
            enrichment_sources=create_request.enrichment_sources,
        )

        created = self._repository.create(entity)
        logger.info(f'Company created successfully with ID: {created.id}')
        return CompanySchema.model_validate(created)

    def create_companies(self, create_request: CreateCompaniesRequestSchema) -> List[CompanySchema]:
        """Create multiple companies."""
        logger.info(f'Creating {len(create_request.companies)} companies')

        created_companies = []
        for company_data in create_request.companies:
            entity = CompanyEntity(
                canonical_name=company_data.canonical_name,
                normalized_name=company_data.normalized_name,
                linkedin_url=company_data.linkedin_url,
                universal_name=company_data.universal_name,
                website=company_data.website,
                domain=company_data.domain,
                industry=company_data.industry,
                founded_year=company_data.founded_year,
                hq_city=company_data.hq_city,
                hq_country=company_data.hq_country,
                employee_count_range=company_data.employee_count_range,
                estimated_employee_count=company_data.estimated_employee_count,
                size_tier=company_data.size_tier,
                network_connection_count=company_data.network_connection_count,
                parent_company_id=company_data.parent_company_id,
                enrichment_sources=company_data.enrichment_sources,
            )
            created = self._repository.create(entity)
            created_companies.append(created)

        logger.info(f'Successfully created {len(created_companies)} companies')
        return [CompanySchema.model_validate(c) for c in created_companies]

    def update_company(self, update_request: UpdateCompanyRequestSchema) -> CompanySchema:
        """Update a company."""
        assert update_request.company_id is not None, 'Company ID is required'

        logger.info(f'Updating company {update_request.company_id}')

        entity = self._repository.get_by_id(update_request.company_id)
        if not entity:
            raise ValueError(f'Company not found with ID: {update_request.company_id}')

        # Update only provided fields
        if update_request.canonical_name is not None:
            entity.canonical_name = update_request.canonical_name
        if update_request.normalized_name is not None:
            entity.normalized_name = update_request.normalized_name
        if update_request.linkedin_url is not None:
            entity.linkedin_url = update_request.linkedin_url
        if update_request.universal_name is not None:
            entity.universal_name = update_request.universal_name
        if update_request.website is not None:
            entity.website = update_request.website
        if update_request.domain is not None:
            entity.domain = update_request.domain
        if update_request.industry is not None:
            entity.industry = update_request.industry
        if update_request.founded_year is not None:
            entity.founded_year = update_request.founded_year
        if update_request.hq_city is not None:
            entity.hq_city = update_request.hq_city
        if update_request.hq_country is not None:
            entity.hq_country = update_request.hq_country
        if update_request.employee_count_range is not None:
            entity.employee_count_range = update_request.employee_count_range
        if update_request.estimated_employee_count is not None:
            entity.estimated_employee_count = update_request.estimated_employee_count
        if update_request.size_tier is not None:
            entity.size_tier = update_request.size_tier
        if update_request.network_connection_count is not None:
            entity.network_connection_count = update_request.network_connection_count
        if update_request.parent_company_id is not None:
            entity.parent_company_id = update_request.parent_company_id
        if update_request.enrichment_sources is not None:
            entity.enrichment_sources = update_request.enrichment_sources

        updated = self._repository.update(entity)
        logger.info(f'Company updated successfully: {updated.id}')
        return CompanySchema.model_validate(updated)

    def get_company_by_id(self, get_request: GetCompanyByIdRequestSchema) -> Optional[CompanySchema]:
        """Get a company by ID."""
        assert get_request.company_id is not None, 'Company ID is required'

        logger.info(f'Getting company {get_request.company_id}')

        entity = self._repository.get_by_id(get_request.company_id)
        if not entity:
            logger.info(f'Company not found: {get_request.company_id}')
            return None

        return CompanySchema.model_validate(entity)

    def delete_company_by_id(self, delete_request: DeleteCompanyByIdRequestSchema) -> None:
        """Delete a company by ID."""
        assert delete_request.company_id is not None, 'Company ID is required'

        logger.info(f'Deleting company {delete_request.company_id}')

        entity = self._repository.get_by_id(delete_request.company_id)
        if not entity:
            raise ValueError(f'Company not found with ID: {delete_request.company_id}')

        self._repository.delete(entity)
        logger.info(f'Company deleted successfully: {delete_request.company_id}')
