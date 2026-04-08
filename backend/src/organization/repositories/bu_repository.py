# SPDX-License-Identifier: Apache-2.0
"""Repository layer for BU entity."""

from typing import List, Optional

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from common.schemas.base_enums_schemas import SortOrder
from organization.entities.bu_entity import BuEntity
from organization.schemas.bus_api_schema import BuSortByFields
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class BuRepository:
    """
    Repository for BU entity database operations.

    Handles all database interactions for business units including:
    - CRUD operations
    - Filtering and searching
    - Pagination and sorting

    Follows the repository pattern to encapsulate data access logic.
    Note: BU is scoped by tenant_id.
    """

    def __init__(self, session: Session):
        """
        Initialize the repository with a database session.

        Args:
            session: SQLAlchemy session for database operations
        """
        self._session = session
        logger.debug('Initialized BuRepository with database session')

    def list_with_filters(
        self,
        tenant_id: str,
        limit: int = 20,
        offset: int = 0,
        sort_by: BuSortByFields = BuSortByFields.NAME,
        sort_order: SortOrder = SortOrder.ASC,
        search: Optional[str] = None,
    ) -> List[BuEntity]:
        """
        Retrieve a paginated list of business units with various filtering options.

        Assumptions:
        - tenant_id must be provided for scoping

        Args:
            tenant_id: Tenant ID for scoping
            limit: Maximum number of BUs to return (default: 20)
            offset: Number of BUs to skip (default: 0)
            sort_by: Field to sort by (default: NAME)
            sort_order: Sort direction (default: ASC)
            search: Text to search in BU name

        Returns:
            List[BuEntity]: List of business units matching the filters

        Raises:
            Exception: If database query fails
        """
        assert tenant_id is not None, 'Tenant ID is required'

        logger.debug(
            f'Fetching BUs for tenant: {tenant_id} - sort_by: {sort_by}, sort_order: {sort_order}'
        )

        # Base query scoped to tenant
        query = self._session.query(BuEntity).filter(
            BuEntity.tenant_id == tenant_id
        )

        # Apply search filter
        if search:
            search_pattern = f'%{search}%'
            query = query.filter(BuEntity.name.ilike(search_pattern))
            logger.debug(f'Applied search filter: "{search}"')

        # Apply sorting
        sort_column = getattr(BuEntity, sort_by, BuEntity.name)
        if sort_order == SortOrder.DESC:
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))
        logger.debug(f'Applied sorting by {sort_by} in {sort_order} order')

        # Apply pagination
        results = query.limit(limit).offset(offset).all()
        logger.debug(
            f'Fetched {len(results)} BUs (limit: {limit}, offset: {offset})'
        )
        return results

    def count_with_filters(
        self,
        tenant_id: str,
        search: Optional[str] = None,
    ) -> int:
        """
        Count the total number of business units matching the specified filters.

        Assumptions:
        - tenant_id must be provided for scoping

        Args:
            tenant_id: Tenant ID for scoping
            search: Text to search in BU name

        Returns:
            int: Total count of BUs matching the filters

        Raises:
            Exception: If database query fails
        """
        assert tenant_id is not None, 'Tenant ID is required'

        logger.debug(f'Counting BUs for tenant: {tenant_id}')

        # Base query scoped to tenant
        query = self._session.query(BuEntity).filter(
            BuEntity.tenant_id == tenant_id
        )

        # Apply search filter
        if search:
            search_pattern = f'%{search}%'
            query = query.filter(BuEntity.name.ilike(search_pattern))

        count = query.count()
        logger.debug(f'Total count with filters: {count}')
        return count

    def create(self, bu: BuEntity) -> BuEntity:
        """
        Create a new business unit.

        The BU is added to the session and flushed, but not committed.
        Commit should be handled at the service/controller level.

        Assumptions:
        - bu.tenant_id must be set
        - bu.name must be set

        Args:
            bu: The BU entity to create

        Returns:
            BuEntity: The created BU with ID populated

        Raises:
            Exception: If the BU creation fails
        """
        assert bu.tenant_id is not None, 'Tenant ID is required'
        assert bu.name is not None, 'BU name is required'

        logger.debug(f'Creating BU: {bu.name} for tenant: {bu.tenant_id}')
        try:
            self._session.add(bu)
            self._session.flush()
            self._session.refresh(bu)
            logger.info(f'Successfully created BU with ID: {bu.id}')
            return bu
        except Exception as e:
            logger.error(f'Failed to create BU: {str(e)}')
            raise

    def get_by_id(self, tenant_id: str, bu_id: str) -> Optional[BuEntity]:
        """
        Get a business unit by its ID.

        Assumptions:
        - tenant_id must be provided for scoping

        Args:
            tenant_id: Tenant ID for scoping
            bu_id: The ID of the BU to get

        Returns:
            Optional[BuEntity]: The BU if found, otherwise None

        Raises:
            Exception: If database query fails
        """
        assert tenant_id is not None, 'Tenant ID is required'
        assert bu_id is not None, 'BU ID is required'

        logger.debug(f'Fetching BU by ID: {bu_id} for tenant: {tenant_id}')

        try:
            bu = (
                self._session.query(BuEntity)
                .filter(
                    BuEntity.tenant_id == tenant_id,
                    BuEntity.id == bu_id
                )
                .one_or_none()
            )

            if bu is None:
                logger.debug(f'BU not found: {bu_id}')
            else:
                logger.info(f'Successfully fetched BU: {bu_id}')
            return bu
        except Exception as e:
            logger.error(f'Failed to fetch BU {bu_id}: {str(e)}')
            raise

    def update(self, bu: BuEntity) -> BuEntity:
        """
        Update a business unit.

        The BU is merged and flushed, but not committed.
        Commit should be handled at the service/controller level.

        Assumptions:
        - bu.id must be set
        - bu.tenant_id must be set

        Args:
            bu: The BU entity to update

        Returns:
            BuEntity: The updated BU

        Raises:
            Exception: If the BU update fails
        """
        assert bu.id is not None, 'BU ID is required'
        assert bu.tenant_id is not None, 'Tenant ID is required'

        logger.debug(f'Updating BU: {bu.id}')
        try:
            self._session.merge(bu)
            self._session.flush()
            self._session.refresh(bu)
            logger.info(f'Successfully updated BU: {bu.id}')
            return bu
        except Exception as e:
            logger.error(f'Failed to update BU: {str(e)}')
            raise

    def delete(self, bu: BuEntity) -> None:
        """
        Delete a business unit.

        The BU is deleted but not committed.
        Commit should be handled at the service/controller level.

        Assumptions:
        - bu.id must be set

        Args:
            bu: The BU entity to delete

        Raises:
            Exception: If the BU deletion fails
        """
        assert bu.id is not None, 'BU ID is required'

        logger.debug(f'Deleting BU: {bu.id}')
        try:
            self._session.delete(bu)
            logger.info(f'Successfully deleted BU: {bu.id}')
        except Exception as e:
            logger.error(f'Failed to delete BU: {str(e)}')
            raise
