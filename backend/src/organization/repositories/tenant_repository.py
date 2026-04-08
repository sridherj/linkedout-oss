# SPDX-License-Identifier: Apache-2.0
"""Repository layer for Tenant entity."""

from typing import List, Optional

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from common.schemas.base_enums_schemas import SortOrder
from organization.entities.tenant_entity import TenantEntity
from organization.schemas.tenants_api_schema import TenantSortByFields
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class TenantRepository:
    """
    Repository for Tenant entity database operations.

    Handles all database interactions for tenants including:
    - CRUD operations
    - Filtering and searching
    - Pagination and sorting

    Follows the repository pattern to encapsulate data access logic.
    Note: Tenant is the top-level entity with no scoping.
    """

    def __init__(self, session: Session):
        """
        Initialize the repository with a database session.

        Args:
            session: SQLAlchemy session for database operations
        """
        self._session = session
        logger.debug('Initialized TenantRepository with database session')

    def list_with_filters(
        self,
        limit: int = 20,
        offset: int = 0,
        sort_by: TenantSortByFields = TenantSortByFields.NAME,
        sort_order: SortOrder = SortOrder.ASC,
        search: Optional[str] = None,
    ) -> List[TenantEntity]:
        """
        Retrieve a paginated list of tenants with various filtering options.

        Args:
            limit: Maximum number of tenants to return (default: 20)
            offset: Number of tenants to skip (default: 0)
            sort_by: Field to sort by (default: NAME)
            sort_order: Sort direction (default: ASC)
            search: Text to search in tenant name

        Returns:
            List[TenantEntity]: List of tenants matching the filters

        Raises:
            Exception: If database query fails
        """
        logger.debug(
            f'Fetching tenants - sort_by: {sort_by}, sort_order: {sort_order}'
        )

        # Base query
        query = self._session.query(TenantEntity)

        # Apply search filter
        if search:
            search_pattern = f'%{search}%'
            query = query.filter(TenantEntity.name.ilike(search_pattern))
            logger.debug(f'Applied search filter: "{search}"')

        # Apply sorting
        sort_column = getattr(TenantEntity, sort_by, TenantEntity.name)
        if sort_order == SortOrder.DESC:
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))
        logger.debug(f'Applied sorting by {sort_by} in {sort_order} order')

        # Apply pagination
        results = query.limit(limit).offset(offset).all()
        logger.debug(
            f'Fetched {len(results)} tenants (limit: {limit}, offset: {offset})'
        )
        return results

    def count_with_filters(
        self,
        search: Optional[str] = None,
    ) -> int:
        """
        Count the total number of tenants matching the specified filters.

        Args:
            search: Text to search in tenant name

        Returns:
            int: Total count of tenants matching the filters

        Raises:
            Exception: If database query fails
        """
        logger.debug('Counting tenants')

        # Base query
        query = self._session.query(TenantEntity)

        # Apply search filter
        if search:
            search_pattern = f'%{search}%'
            query = query.filter(TenantEntity.name.ilike(search_pattern))

        count = query.count()
        logger.debug(f'Total count with filters: {count}')
        return count

    def create(self, tenant: TenantEntity) -> TenantEntity:
        """
        Create a new tenant.

        The tenant is added to the session and flushed, but not committed.
        Commit should be handled at the service/controller level.

        Assumptions:
        - tenant.name must be set

        Args:
            tenant: The tenant entity to create

        Returns:
            TenantEntity: The created tenant with ID populated

        Raises:
            Exception: If the tenant creation fails
        """
        assert tenant.name is not None, 'Tenant name is required'

        logger.debug(f'Creating tenant: {tenant.name}')
        try:
            self._session.add(tenant)
            self._session.flush()
            self._session.refresh(tenant)
            logger.info(f'Successfully created tenant with ID: {tenant.id}')
            return tenant
        except Exception as e:
            logger.error(f'Failed to create tenant: {str(e)}')
            raise

    def get_by_id(self, tenant_id: str) -> Optional[TenantEntity]:
        """
        Get a tenant by its ID.

        Args:
            tenant_id: The ID of the tenant to get

        Returns:
            Optional[TenantEntity]: The tenant if found, otherwise None

        Raises:
            Exception: If database query fails
        """
        assert tenant_id is not None, 'Tenant ID is required'

        logger.debug(f'Fetching tenant by ID: {tenant_id}')

        try:
            tenant = (
                self._session.query(TenantEntity)
                .filter(TenantEntity.id == tenant_id)
                .one_or_none()
            )

            if tenant is None:
                logger.debug(f'Tenant not found: {tenant_id}')
            else:
                logger.info(f'Successfully fetched tenant: {tenant_id}')
            return tenant
        except Exception as e:
            logger.error(f'Failed to fetch tenant {tenant_id}: {str(e)}')
            raise

    def update(self, tenant: TenantEntity) -> TenantEntity:
        """
        Update a tenant.

        The tenant is merged and flushed, but not committed.
        Commit should be handled at the service/controller level.

        Assumptions:
        - tenant.id must be set

        Args:
            tenant: The tenant entity to update

        Returns:
            TenantEntity: The updated tenant

        Raises:
            Exception: If the tenant update fails
        """
        assert tenant.id is not None, 'Tenant ID is required'

        logger.debug(f'Updating tenant: {tenant.id}')
        try:
            self._session.merge(tenant)
            self._session.flush()
            self._session.refresh(tenant)
            logger.info(f'Successfully updated tenant: {tenant.id}')
            return tenant
        except Exception as e:
            logger.error(f'Failed to update tenant: {str(e)}')
            raise

    def delete(self, tenant: TenantEntity) -> None:
        """
        Delete a tenant.

        The tenant is deleted but not committed.
        Commit should be handled at the service/controller level.

        Assumptions:
        - tenant.id must be set

        Args:
            tenant: The tenant entity to delete

        Raises:
            Exception: If the tenant deletion fails
        """
        assert tenant.id is not None, 'Tenant ID is required'

        logger.debug(f'Deleting tenant: {tenant.id}')
        try:
            self._session.delete(tenant)
            logger.info(f'Successfully deleted tenant: {tenant.id}')
        except Exception as e:
            logger.error(f'Failed to delete tenant: {str(e)}')
            raise
