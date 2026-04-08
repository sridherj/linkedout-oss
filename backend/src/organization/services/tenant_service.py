# SPDX-License-Identifier: Apache-2.0
"""Service layer for Tenant business logic."""

from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from organization.entities.tenant_entity import TenantEntity
from organization.repositories.tenant_repository import TenantRepository
from organization.schemas.tenant_schema import TenantSchema
from organization.schemas.tenants_api_schema import (
    CreateTenantRequestSchema,
    CreateTenantsRequestSchema,
    DeleteTenantByIdRequestSchema,
    GetTenantByIdRequestSchema,
    ListTenantsRequestSchema,
    UpdateTenantRequestSchema,
)
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class TenantService:
    """
    Service layer for Tenant business logic.

    Handles business logic and orchestrates repository operations.
    The service layer:
    - Receives request objects from controllers
    - Performs business logic and validation
    - Calls repository methods for data access
    - Returns schema objects to controllers

    Transaction management is handled at the controller level.
    """

    def __init__(self, session: Session = None):
        """
        Initialize the service with a database session.

        Args:
            session: SQLAlchemy session for database operations
        """
        self._session = session
        self._tenant_repository = TenantRepository(self._session)
        logger.debug('Initialized TenantService')

    def list_tenants(
        self, list_request: ListTenantsRequestSchema
    ) -> Tuple[List[TenantSchema], int]:
        """
        List tenants with filtering, sorting and pagination.

        Args:
            list_request: Request containing filter, sort, and pagination parameters

        Returns:
            Tuple containing:
                - List of TenantSchema objects
                - Total count of tenants matching the filters

        Raises:
            Exception: If database query fails
        """
        logger.debug('Listing tenants')

        # Get tenants from repository
        tenant_entities = self._tenant_repository.list_with_filters(
            limit=list_request.limit,
            offset=list_request.offset,
            sort_by=list_request.sort_by,
            sort_order=list_request.sort_order,
            search=list_request.search,
        )

        # Get total count
        total_count = self._tenant_repository.count_with_filters(
            search=list_request.search,
        )

        logger.debug(f'Found {len(tenant_entities)} tenants out of {total_count} total')

        # Convert entities to schemas
        tenant_schemas = [TenantSchema.model_validate(tenant) for tenant in tenant_entities]

        return tenant_schemas, total_count

    def create_tenant(self, create_request: CreateTenantRequestSchema) -> TenantSchema:
        """
        Create a new tenant.

        Assumptions:
        - create_request.name must be set

        Args:
            create_request: Request containing tenant creation data

        Returns:
            TenantSchema: The created tenant

        Raises:
            Exception: If tenant creation fails
        """
        assert create_request.name is not None, 'Tenant name is required'

        logger.info(f'Creating tenant: {create_request.name}')

        # Create entity from request
        tenant_entity = TenantEntity(
            name=create_request.name,
            description=create_request.description,
        )

        # Save to database
        created_tenant = self._tenant_repository.create(tenant_entity)
        logger.info(f'Tenant created successfully with ID: {created_tenant.id}')

        return TenantSchema.model_validate(created_tenant)

    def create_tenants(self, create_request: CreateTenantsRequestSchema) -> List[TenantSchema]:
        """
        Create multiple new tenants.

        Args:
            create_request: Request containing list of tenants to create

        Returns:
            List[TenantSchema]: The created tenants

        Raises:
            Exception: If tenant creation fails
        """
        logger.info(f'Creating {len(create_request.tenants)} tenants')

        tenant_entities = []
        for tenant_data in create_request.tenants:
            # Create entity from request
            tenant_entity = TenantEntity(
                name=tenant_data.name,
                description=tenant_data.description,
            )
            tenant_entities.append(tenant_entity)

        # Save to database
        created_tenants = []
        for entity in tenant_entities:
            created = self._tenant_repository.create(entity)
            created_tenants.append(created)

        logger.info(f'Successfully created {len(created_tenants)} tenants')

        return [TenantSchema.model_validate(tenant) for tenant in created_tenants]

    def update_tenant(self, update_request: UpdateTenantRequestSchema) -> TenantSchema:
        """
        Update a tenant.

        Only fields provided in the request are updated.

        Assumptions:
        - update_request.tenant_id must be set

        Args:
            update_request: Request containing update data

        Returns:
            TenantSchema: The updated tenant

        Raises:
            ValueError: If the tenant is not found
            Exception: If tenant update fails
        """
        assert update_request.tenant_id is not None, 'Tenant ID is required'

        logger.info(f'Updating tenant {update_request.tenant_id}')

        # Get existing tenant
        tenant_entity = self._tenant_repository.get_by_id(
            tenant_id=update_request.tenant_id,
        )

        if not tenant_entity:
            logger.error(f'Tenant not found: {update_request.tenant_id}')
            raise ValueError(f'Tenant not found with ID: {update_request.tenant_id}')

        # Update only provided fields
        if update_request.name is not None:
            tenant_entity.name = update_request.name
        if update_request.description is not None:
            tenant_entity.description = update_request.description

        # Save changes
        updated_tenant = self._tenant_repository.update(tenant_entity)
        logger.info(f'Tenant updated successfully: {updated_tenant.id}')

        return TenantSchema.model_validate(updated_tenant)

    def get_tenant_by_id(
        self, get_request: GetTenantByIdRequestSchema
    ) -> Optional[TenantSchema]:
        """
        Get a tenant by its ID.

        Assumptions:
        - get_request.tenant_id must be set

        Args:
            get_request: Request containing tenant ID

        Returns:
            Optional[TenantSchema]: The tenant if found, otherwise None

        Raises:
            Exception: If database query fails
        """
        assert get_request.tenant_id is not None, 'Tenant ID is required'

        logger.info(f'Getting tenant {get_request.tenant_id}')

        tenant_entity = self._tenant_repository.get_by_id(
            tenant_id=get_request.tenant_id,
        )

        if not tenant_entity:
            logger.info(f'Tenant not found: {get_request.tenant_id}')
            return None

        return TenantSchema.model_validate(tenant_entity)

    def delete_tenant_by_id(self, delete_request: DeleteTenantByIdRequestSchema) -> None:
        """
        Delete a tenant by its ID.

        Assumptions:
        - delete_request.tenant_id must be set

        Args:
            delete_request: Request containing tenant deletion data

        Raises:
            ValueError: If the tenant is not found
            Exception: If tenant deletion fails
        """
        assert delete_request.tenant_id is not None, 'Tenant ID is required'

        logger.info(f'Deleting tenant {delete_request.tenant_id}')

        # Get tenant to delete
        tenant_entity = self._tenant_repository.get_by_id(
            tenant_id=delete_request.tenant_id,
        )

        if not tenant_entity:
            logger.error(f'Tenant not found: {delete_request.tenant_id}')
            raise ValueError(f'Tenant not found with ID: {delete_request.tenant_id}')

        # Delete tenant
        self._tenant_repository.delete(tenant_entity)
        logger.info(f'Tenant deleted successfully: {delete_request.tenant_id}')
