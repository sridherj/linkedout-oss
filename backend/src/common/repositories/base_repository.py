# SPDX-License-Identifier: Apache-2.0
"""Generic base repository for CRUD operations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Generic, List, Optional, Type, TypeVar

from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from common.entities.base_entity import BaseEntity
from common.schemas.base_enums_schemas import SortOrder
from shared.utilities.logger import get_logger

logger = get_logger(__name__)

# Type variables for generics
TEntity = TypeVar('TEntity', bound=BaseEntity)
TSortEnum = TypeVar('TSortEnum', bound=StrEnum)


@dataclass
class FilterSpec:
    """
    Specification for how to filter on a field.

    Attributes:
        field_name: The name of the filter parameter (e.g., 'commodity_id', 'search')
        filter_type: Type of filter operation ('eq', 'in', 'ilike', 'bool', 'gte', 'lte', 'jsonb_overlap')
        entity_field: The entity field name to filter on (defaults to field_name)

    Filter Types:
        - 'eq': Exact match (WHERE field = value)
        - 'in': In list (WHERE field IN (values))
        - 'ilike': Case-insensitive like (WHERE field ILIKE '%value%')
        - 'bool': Boolean (WHERE field = True/False)
        - 'gte': Greater than or equal (WHERE field >= value)
        - 'lte': Less than or equal (WHERE field <= value)
        - 'jsonb_overlap': JSONB array overlap (WHERE field && ARRAY[values] - finds rows where JSONB array has any common elements)
    """
    field_name: str
    filter_type: str = 'eq'  # 'eq', 'in', 'ilike', 'bool', 'gte', 'lte', 'jsonb_overlap'
    entity_field: Optional[str] = None

    def __post_init__(self):
        """Set entity_field to field_name if not provided."""
        if self.entity_field is None:
            self.entity_field = self.field_name


class BaseRepository(ABC, Generic[TEntity, TSortEnum]):
    """
    Generic base repository implementing common CRUD operations.

    Subclasses should define:
    - _entity_class: The SQLAlchemy entity class
    - _default_sort_field: Default field for sorting
    - _entity_name: Human-readable entity name for logging
    - _get_filter_specs(): Returns list of FilterSpec for entity-specific filters

    Example:
        class LabelRepository(BaseRepository[LabelEntity, LabelSortByFields]):
            _entity_class = LabelEntity
            _default_sort_field = 'name'
            _entity_name = 'label'

            def _get_filter_specs(self) -> List[FilterSpec]:
                return [
                    FilterSpec('name', 'ilike'),
                    FilterSpec('label_ids', 'in', entity_field='id'),
                ]
    """

    _entity_class: Type[TEntity]
    _default_sort_field: str
    _entity_name: str

    def __init__(self, session: Session):
        """
        Initialize the repository with a database session.

        Args:
            session: SQLAlchemy session for database operations
        """
        self._session = session
        logger.debug(f'Initialized {self.__class__.__name__} with database session')

    @abstractmethod
    def _get_filter_specs(self) -> List[FilterSpec]:
        """
        Return filter specifications for this entity.

        Override in subclass to define entity-specific filters.

        Returns:
            List of FilterSpec defining how to filter the entity.
        """
        pass

    def _apply_filters(self, query: Any, filter_kwargs: dict) -> Any:
        """
        Apply filters to query based on filter specs.

        Args:
            query: SQLAlchemy query object
            filter_kwargs: Dict of filter parameter values

        Returns:
            Query with filters applied
        """
        for spec in self._get_filter_specs():
            value = filter_kwargs.get(spec.field_name)
            if value is None:
                continue

            # entity_field is guaranteed to be set in __post_init__
            entity_field = getattr(self._entity_class, spec.entity_field)  # type: ignore[arg-type]

            if spec.filter_type == 'eq':
                query = query.filter(entity_field == value)
                logger.debug(f'Applied {spec.field_name} filter (eq): {value}')
            elif spec.filter_type == 'in':
                if isinstance(value, list) and value:
                    query = query.filter(entity_field.in_(value))
                    logger.debug(f'Applied {spec.field_name} filter (in): {value}')
            elif spec.filter_type == 'ilike':
                if value:
                    search_pattern = f'%{value}%'
                    query = query.filter(entity_field.ilike(search_pattern))
                    logger.debug(f'Applied {spec.field_name} filter (ilike): "{value}"')
            elif spec.filter_type == 'bool':
                query = query.filter(entity_field == value)
                logger.debug(f'Applied {spec.field_name} filter (bool): {value}')
            elif spec.filter_type == 'gte':
                query = query.filter(entity_field >= value)
                logger.debug(f'Applied {spec.field_name} filter (gte): {value}')
            elif spec.filter_type == 'lte':
                query = query.filter(entity_field <= value)
                logger.debug(f'Applied {spec.field_name} filter (lte): {value}')
            elif spec.filter_type == 'jsonb_overlap':
                # JSONB array overlap: find rows where JSONB array has any common elements with filter values
                # Uses PostgreSQL ?| operator (has any key/element)
                if isinstance(value, list) and value:
                    from sqlalchemy.dialects.postgresql import array
                    from sqlalchemy import cast, String
                    # Cast the list to a PostgreSQL text array and use the overlap operator
                    query = query.filter(entity_field.op('?|')(cast(array(value), type_=array(String))))
                    logger.debug(f'Applied {spec.field_name} filter (jsonb_overlap): {value}')

        return query

    def _get_base_query(self, tenant_id: str, bu_id: str) -> Any:
        """
        Get base query scoped to tenant and BU.

        Args:
            tenant_id: Tenant ID for scoping
            bu_id: Business unit ID for scoping

        Returns:
            SQLAlchemy query scoped to tenant and BU
        """
        return self._session.query(self._entity_class).filter(
            self._entity_class.tenant_id == tenant_id,
            self._entity_class.bu_id == bu_id
        )

    def list_with_filters(
        self,
        tenant_id: str,
        bu_id: str,
        limit: int = 20,
        offset: int = 0,
        sort_by: Optional[TSortEnum] = None,
        sort_order: SortOrder = SortOrder.ASC,
        is_active: Optional[bool] = None,
        **filter_kwargs,
    ) -> List[TEntity]:
        """
        Retrieve a paginated list of entities with various filtering options.

        Args:
            tenant_id: Tenant ID for scoping
            bu_id: Business unit ID for scoping
            limit: Maximum number of items to return (default: 20)
            offset: Number of items to skip (default: 0)
            sort_by: Field to sort by (default: _default_sort_field)
            sort_order: Sort direction (default: ASC)
            is_active: Filter by active status
            **filter_kwargs: Entity-specific filter parameters

        Returns:
            List of entities matching the filters
        """
        assert tenant_id is not None, 'Tenant ID is required'
        assert bu_id is not None, 'Business unit ID is required'

        sort_by_value = sort_by.value if sort_by else self._default_sort_field
        logger.debug(
            f'Fetching {self._entity_name}s for tenant: {tenant_id}, bu: {bu_id} - '
            f'sort_by: {sort_by_value}, sort_order: {sort_order}'
        )

        # Base query scoped to tenant and BU
        query = self._get_base_query(tenant_id, bu_id)

        # Apply is_active filter (common to all entities)
        if is_active is not None:
            query = query.filter(self._entity_class.is_active == is_active)
            logger.debug(f'Applied is_active filter: {is_active}')

        # Apply entity-specific filters
        query = self._apply_filters(query, filter_kwargs)

        # Apply sorting
        sort_column = getattr(
            self._entity_class,
            sort_by_value,
            getattr(self._entity_class, self._default_sort_field)
        )
        if sort_order == SortOrder.DESC:
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))
        logger.debug(f'Applied sorting by {sort_by_value} in {sort_order} order')

        # Apply pagination
        results = query.limit(limit).offset(offset).all()
        logger.debug(
            f'Fetched {len(results)} {self._entity_name}s (limit: {limit}, offset: {offset})'
        )
        return results

    def count_with_filters(
        self,
        tenant_id: str,
        bu_id: str,
        is_active: Optional[bool] = None,
        **filter_kwargs,
    ) -> int:
        """
        Count the total number of entities matching the specified filters.

        Args:
            tenant_id: Tenant ID for scoping
            bu_id: Business unit ID for scoping
            is_active: Filter by active status
            **filter_kwargs: Entity-specific filter parameters

        Returns:
            Total count of entities matching the filters
        """
        assert tenant_id is not None, 'Tenant ID is required'
        assert bu_id is not None, 'Business unit ID is required'

        logger.debug(f'Counting {self._entity_name}s for tenant: {tenant_id}, bu: {bu_id}')

        # Base query scoped to tenant and BU
        query = self._get_base_query(tenant_id, bu_id)

        # Apply is_active filter
        if is_active is not None:
            query = query.filter(self._entity_class.is_active == is_active)

        # Apply entity-specific filters
        query = self._apply_filters(query, filter_kwargs)

        count = query.count()
        logger.debug(f'Total {self._entity_name} count with filters: {count}')
        return count

    def create(self, entity: TEntity) -> TEntity:
        """
        Create a new entity.

        The entity is added to the session and flushed, but not committed.
        Commit should be handled at the service/controller level.

        Args:
            entity: The entity to create

        Returns:
            The created entity with ID populated
        """
        assert entity.tenant_id is not None, 'Tenant ID is required'
        assert entity.bu_id is not None, 'Business unit ID is required'

        logger.debug(f'Creating {self._entity_name} for tenant: {entity.tenant_id}, bu: {entity.bu_id}')
        try:
            self._session.add(entity)
            self._session.flush()
            self._session.refresh(entity)
            logger.info(f'Successfully created {self._entity_name} with ID: {entity.id}')
            return entity
        except Exception as e:
            logger.error(f'Failed to create {self._entity_name}: {str(e)}')
            raise

    def get_by_id(
        self,
        tenant_id: str,
        bu_id: str,
        entity_id: str
    ) -> Optional[TEntity]:
        """
        Get an entity by its ID.

        Args:
            tenant_id: Tenant ID for scoping
            bu_id: Business unit ID for scoping
            entity_id: The ID of the entity to get

        Returns:
            The entity if found, otherwise None
        """
        assert tenant_id is not None, 'Tenant ID is required'
        assert bu_id is not None, 'Business unit ID is required'
        assert entity_id is not None, f'{self._entity_name.capitalize()} ID is required'

        logger.debug(
            f'Fetching {self._entity_name} by ID: {entity_id} for tenant: {tenant_id}, bu: {bu_id}'
        )

        try:
            entity = (
                self._get_base_query(tenant_id, bu_id)
                .filter(self._entity_class.id == entity_id)
                .one_or_none()
            )

            if entity is None:
                logger.debug(f'{self._entity_name.capitalize()} not found: {entity_id}')
            else:
                logger.info(f'Successfully fetched {self._entity_name}: {entity_id}')
            return entity
        except Exception as e:
            logger.error(f'Failed to fetch {self._entity_name} {entity_id}: {str(e)}')
            raise

    def get_by_ids(
        self,
        tenant_id: str,
        bu_id: str,
        entity_ids: List[str]
    ) -> List[TEntity]:
        """
        Get multiple entities by their IDs in a single query.

        Args:
            tenant_id: Tenant ID for scoping
            bu_id: Business unit ID for scoping
            entity_ids: List of entity IDs to fetch

        Returns:
            List of entities found. May be fewer than requested if some IDs don't exist.
        """
        assert tenant_id is not None, 'Tenant ID is required'
        assert bu_id is not None, 'Business unit ID is required'
        assert entity_ids is not None, f'{self._entity_name.capitalize()} IDs list is required'

        if not entity_ids:
            logger.debug(f'Empty {self._entity_name}_ids list provided, returning empty list')
            return []

        logger.debug(
            f'Fetching {len(entity_ids)} {self._entity_name}s by IDs for tenant: {tenant_id}, bu: {bu_id}'
        )

        try:
            entities = (
                self._get_base_query(tenant_id, bu_id)
                .filter(self._entity_class.id.in_(entity_ids))
                .all()
            )

            logger.info(
                f'Successfully fetched {len(entities)} {self._entity_name}s out of {len(entity_ids)} requested'
            )
            return entities
        except Exception as e:
            logger.error(f'Failed to fetch {self._entity_name}s by IDs: {str(e)}')
            raise

    def update(self, entity: TEntity) -> TEntity:
        """
        Update an entity.

        The entity is merged and flushed, but not committed.
        Commit should be handled at the service/controller level.

        Args:
            entity: The entity to update

        Returns:
            The updated entity
        """
        assert entity.id is not None, f'{self._entity_name.capitalize()} ID is required'
        assert entity.tenant_id is not None, 'Tenant ID is required'
        assert entity.bu_id is not None, 'Business unit ID is required'

        logger.debug(f'Updating {self._entity_name}: {entity.id}')
        try:
            self._session.merge(entity)
            self._session.flush()
            self._session.refresh(entity)
            logger.info(f'Successfully updated {self._entity_name}: {entity.id}')
            return entity
        except Exception as e:
            logger.error(f'Failed to update {self._entity_name}: {str(e)}')
            raise

    def delete(self, entity: TEntity) -> None:
        """
        Delete an entity.

        The entity is deleted but not committed.
        Commit should be handled at the service/controller level.

        Args:
            entity: The entity to delete
        """
        assert entity.id is not None, f'{self._entity_name.capitalize()} ID is required'

        logger.debug(f'Deleting {self._entity_name}: {entity.id}')
        try:
            self._session.delete(entity)
            logger.info(f'Successfully deleted {self._entity_name}: {entity.id}')
        except Exception as e:
            logger.error(f'Failed to delete {self._entity_name}: {str(e)}')
            raise
