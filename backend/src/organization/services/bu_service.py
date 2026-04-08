# SPDX-License-Identifier: Apache-2.0
"""Service layer for BU business logic."""

from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from organization.entities.bu_entity import BuEntity
from organization.repositories.bu_repository import BuRepository
from organization.schemas.bu_schema import BuSchema
from organization.schemas.bus_api_schema import (
    CreateBuRequestSchema,
    CreateBusRequestSchema,
    DeleteBuByIdRequestSchema,
    GetBuByIdRequestSchema,
    ListBusRequestSchema,
    UpdateBuRequestSchema,
)
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class BuService:
    """
    Service layer for BU business logic.

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
        self._bu_repository = BuRepository(self._session)
        logger.debug('Initialized BuService')

    def list_bus(
        self, list_request: ListBusRequestSchema
    ) -> Tuple[List[BuSchema], int]:
        """
        List business units with filtering, sorting and pagination.

        Assumptions:
        - list_request.tenant_id must be set

        Args:
            list_request: Request containing filter, sort, and pagination parameters

        Returns:
            Tuple containing:
                - List of BuSchema objects
                - Total count of BUs matching the filters

        Raises:
            Exception: If database query fails
        """
        assert list_request.tenant_id is not None, 'Tenant ID is required'

        logger.debug(f'Listing BUs for tenant: {list_request.tenant_id}')

        # Get BUs from repository
        bu_entities = self._bu_repository.list_with_filters(
            tenant_id=list_request.tenant_id,
            limit=list_request.limit,
            offset=list_request.offset,
            sort_by=list_request.sort_by,
            sort_order=list_request.sort_order,
            search=list_request.search,
        )

        # Get total count
        total_count = self._bu_repository.count_with_filters(
            tenant_id=list_request.tenant_id,
            search=list_request.search,
        )

        logger.debug(f'Found {len(bu_entities)} BUs out of {total_count} total')

        # Convert entities to schemas
        bu_schemas = [BuSchema.model_validate(bu) for bu in bu_entities]

        return bu_schemas, total_count

    def create_bu(self, create_request: CreateBuRequestSchema) -> BuSchema:
        """
        Create a new business unit.

        Assumptions:
        - create_request.tenant_id must be set
        - create_request.name must be set

        Args:
            create_request: Request containing BU creation data

        Returns:
            BuSchema: The created BU

        Raises:
            Exception: If BU creation fails
        """
        assert create_request.tenant_id is not None, 'Tenant ID is required'
        assert create_request.name is not None, 'BU name is required'

        logger.info(
            f'Creating BU: {create_request.name} for tenant: {create_request.tenant_id}'
        )

        # Create entity from request
        bu_entity = BuEntity(
            tenant_id=create_request.tenant_id,
            name=create_request.name,
            description=create_request.description,
        )

        # Save to database
        created_bu = self._bu_repository.create(bu_entity)
        logger.info(f'BU created successfully with ID: {created_bu.id}')

        return BuSchema.model_validate(created_bu)

    def create_bus(self, create_request: CreateBusRequestSchema) -> List[BuSchema]:
        """
        Create multiple new business units.

        Assumptions:
        - create_request.tenant_id must be set

        Args:
            create_request: Request containing list of BUs to create

        Returns:
            List[BuSchema]: The created BUs

        Raises:
            Exception: If BU creation fails
        """
        assert create_request.tenant_id is not None, 'Tenant ID is required'

        logger.info(
            f'Creating {len(create_request.bus)} BUs for tenant: {create_request.tenant_id}'
        )

        bu_entities = []
        for bu_data in create_request.bus:
            # Set tenant_id from parent request
            bu_data.tenant_id = create_request.tenant_id

            # Create entity from request
            bu_entity = BuEntity(
                tenant_id=bu_data.tenant_id,
                name=bu_data.name,
                description=bu_data.description,
            )
            bu_entities.append(bu_entity)

        # Save to database
        created_bus = []
        for entity in bu_entities:
            created = self._bu_repository.create(entity)
            created_bus.append(created)

        logger.info(f'Successfully created {len(created_bus)} BUs')

        return [BuSchema.model_validate(bu) for bu in created_bus]

    def update_bu(self, update_request: UpdateBuRequestSchema) -> BuSchema:
        """
        Update a business unit.

        Only fields provided in the request are updated.

        Assumptions:
        - update_request.tenant_id and update_request.bu_id must be set

        Args:
            update_request: Request containing update data

        Returns:
            BuSchema: The updated BU

        Raises:
            ValueError: If the BU is not found
            Exception: If BU update fails
        """
        assert update_request.tenant_id is not None, 'Tenant ID is required'
        assert update_request.bu_id is not None, 'BU ID is required'

        logger.info(
            f'Updating BU {update_request.bu_id} for tenant: {update_request.tenant_id}'
        )

        # Get existing BU
        bu_entity = self._bu_repository.get_by_id(
            tenant_id=update_request.tenant_id,
            bu_id=update_request.bu_id,
        )

        if not bu_entity:
            logger.error(f'BU not found: {update_request.bu_id}')
            raise ValueError(f'BU not found with ID: {update_request.bu_id}')

        # Update only provided fields
        if update_request.name is not None:
            bu_entity.name = update_request.name
        if update_request.description is not None:
            bu_entity.description = update_request.description

        # Save changes
        updated_bu = self._bu_repository.update(bu_entity)
        logger.info(f'BU updated successfully: {updated_bu.id}')

        return BuSchema.model_validate(updated_bu)

    def get_bu_by_id(
        self, get_request: GetBuByIdRequestSchema
    ) -> Optional[BuSchema]:
        """
        Get a business unit by its ID.

        Assumptions:
        - get_request.tenant_id and get_request.bu_id must be set

        Args:
            get_request: Request containing BU ID

        Returns:
            Optional[BuSchema]: The BU if found, otherwise None

        Raises:
            Exception: If database query fails
        """
        assert get_request.tenant_id is not None, 'Tenant ID is required'
        assert get_request.bu_id is not None, 'BU ID is required'

        logger.info(
            f'Getting BU {get_request.bu_id} for tenant: {get_request.tenant_id}'
        )

        bu_entity = self._bu_repository.get_by_id(
            tenant_id=get_request.tenant_id,
            bu_id=get_request.bu_id,
        )

        if not bu_entity:
            logger.info(f'BU not found: {get_request.bu_id}')
            return None

        return BuSchema.model_validate(bu_entity)

    def delete_bu_by_id(self, delete_request: DeleteBuByIdRequestSchema) -> None:
        """
        Delete a business unit by its ID.

        Assumptions:
        - delete_request.tenant_id and delete_request.bu_id must be set

        Args:
            delete_request: Request containing BU deletion data

        Raises:
            ValueError: If the BU is not found
            Exception: If BU deletion fails
        """
        assert delete_request.tenant_id is not None, 'Tenant ID is required'
        assert delete_request.bu_id is not None, 'BU ID is required'

        logger.info(
            f'Deleting BU {delete_request.bu_id} for tenant: {delete_request.tenant_id}'
        )

        # Get BU to delete
        bu_entity = self._bu_repository.get_by_id(
            tenant_id=delete_request.tenant_id,
            bu_id=delete_request.bu_id,
        )

        if not bu_entity:
            logger.error(f'BU not found: {delete_request.bu_id}')
            raise ValueError(f'BU not found with ID: {delete_request.bu_id}')

        # Delete BU
        self._bu_repository.delete(bu_entity)
        logger.info(f'BU deleted successfully: {delete_request.bu_id}')
