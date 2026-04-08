# SPDX-License-Identifier: Apache-2.0
"""Service for CompanyAlias entity (shared, no tenant/BU scoping)."""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from linkedout.company_alias.entities.company_alias_entity import CompanyAliasEntity
from linkedout.company_alias.repositories.company_alias_repository import CompanyAliasRepository
from linkedout.company_alias.schemas.company_alias_api_schema import (
    CreateCompanyAliasRequestSchema,
    CreateCompanyAliasesRequestSchema,
    DeleteCompanyAliasByIdRequestSchema,
    GetCompanyAliasByIdRequestSchema,
    ListCompanyAliasesRequestSchema,
    UpdateCompanyAliasRequestSchema,
)
from linkedout.company_alias.schemas.company_alias_schema import CompanyAliasSchema
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class CompanyAliasService:
    """
    Service for CompanyAlias business logic.

    CompanyAlias is a shared entity with no tenant/BU scoping.
    Follows the same pattern as CompanyService.
    """

    def __init__(self, session: Session):
        self._session = session
        self._repository = CompanyAliasRepository(session)
        logger.debug('Initialized CompanyAliasService')

    def list_company_aliases(
        self, list_request: ListCompanyAliasesRequestSchema
    ) -> Tuple[List[CompanyAliasSchema], int]:
        """List company aliases with filtering, sorting, and pagination."""
        logger.debug('Listing company aliases')

        company_aliases = self._repository.list_with_filters(
            limit=list_request.limit,
            offset=list_request.offset,
            sort_by=list_request.sort_by,
            sort_order=list_request.sort_order,
            alias_name=list_request.alias_name,
            company_id=list_request.company_id,
            source=list_request.source,
        )

        total_count = self._repository.count_with_filters(
            alias_name=list_request.alias_name,
            company_id=list_request.company_id,
            source=list_request.source,
        )

        logger.debug(f'Found {len(company_aliases)} company aliases out of {total_count} total')
        schemas = [CompanyAliasSchema.model_validate(ca) for ca in company_aliases]
        return schemas, total_count

    def create_company_alias(self, create_request: CreateCompanyAliasRequestSchema) -> CompanyAliasSchema:
        """Create a new company alias."""
        assert create_request.alias_name is not None, 'Alias name is required'

        logger.info(f'Creating company alias: {create_request.alias_name}')

        entity = CompanyAliasEntity(
            alias_name=create_request.alias_name,
            company_id=create_request.company_id,
            source=create_request.source,
        )

        created = self._repository.create(entity)
        logger.info(f'Company alias created successfully with ID: {created.id}')
        return CompanyAliasSchema.model_validate(created)

    def create_company_aliases(self, create_request: CreateCompanyAliasesRequestSchema) -> List[CompanyAliasSchema]:
        """Create multiple company aliases."""
        logger.info(f'Creating {len(create_request.company_aliases)} company aliases')

        created_aliases = []
        for alias_data in create_request.company_aliases:
            entity = CompanyAliasEntity(
                alias_name=alias_data.alias_name,
                company_id=alias_data.company_id,
                source=alias_data.source,
            )
            created = self._repository.create(entity)
            created_aliases.append(created)

        logger.info(f'Successfully created {len(created_aliases)} company aliases')
        return [CompanyAliasSchema.model_validate(ca) for ca in created_aliases]

    def update_company_alias(self, update_request: UpdateCompanyAliasRequestSchema) -> CompanyAliasSchema:
        """Update a company alias."""
        assert update_request.company_alias_id is not None, 'Company alias ID is required'

        logger.info(f'Updating company alias {update_request.company_alias_id}')

        entity = self._repository.get_by_id(update_request.company_alias_id)
        if not entity:
            raise ValueError(f'Company alias not found with ID: {update_request.company_alias_id}')

        # Update only provided fields
        if update_request.alias_name is not None:
            entity.alias_name = update_request.alias_name
        if update_request.company_id is not None:
            entity.company_id = update_request.company_id
        if update_request.source is not None:
            entity.source = update_request.source

        updated = self._repository.update(entity)
        logger.info(f'Company alias updated successfully: {updated.id}')
        return CompanyAliasSchema.model_validate(updated)

    def get_company_alias_by_id(self, get_request: GetCompanyAliasByIdRequestSchema) -> Optional[CompanyAliasSchema]:
        """Get a company alias by ID."""
        assert get_request.company_alias_id is not None, 'Company alias ID is required'

        logger.info(f'Getting company alias {get_request.company_alias_id}')

        entity = self._repository.get_by_id(get_request.company_alias_id)
        if not entity:
            logger.info(f'Company alias not found: {get_request.company_alias_id}')
            return None

        return CompanyAliasSchema.model_validate(entity)

    def delete_company_alias_by_id(self, delete_request: DeleteCompanyAliasByIdRequestSchema) -> None:
        """Delete a company alias by ID."""
        assert delete_request.company_alias_id is not None, 'Company alias ID is required'

        logger.info(f'Deleting company alias {delete_request.company_alias_id}')

        entity = self._repository.get_by_id(delete_request.company_alias_id)
        if not entity:
            raise ValueError(f'Company alias not found with ID: {delete_request.company_alias_id}')

        self._repository.delete(entity)
        logger.info(f'Company alias deleted successfully: {delete_request.company_alias_id}')
