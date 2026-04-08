# SPDX-License-Identifier: Apache-2.0
"""Generic base service for CRUD operations."""

from abc import ABC, abstractmethod
from typing import Any, Generic, List, Optional, Tuple, Type, TypeVar

from pydantic import BaseModel
from sqlalchemy.orm import Session

from common.entities.base_entity import BaseEntity
from common.repositories.base_repository import BaseRepository
from shared.utilities.logger import get_logger

logger = get_logger(__name__)

# Type variables for generics
TEntity = TypeVar('TEntity', bound=BaseEntity)
TSchema = TypeVar('TSchema', bound=BaseModel)
TRepository = TypeVar('TRepository', bound=BaseRepository)


class BaseService(ABC, Generic[TEntity, TSchema, TRepository]):
    """
    Generic base service implementing common CRUD operations.

    Subclasses should define:
    - _repository_class: The repository class to use
    - _schema_class: The Pydantic schema class for responses
    - _entity_class: The SQLAlchemy entity class
    - _entity_name: Human-readable entity name for logging/errors
    - _entity_id_field: Field name for entity ID in requests (e.g., 'lot_id')

    And implement:
    - _extract_filter_kwargs(): Extract filter kwargs from list request
    - _create_entity_from_request(): Create entity from create request
    - _update_entity_from_request(): Update entity from update request

    Example:
        class LabelService(BaseService[LabelEntity, LabelSchema, LabelRepository]):
            _repository_class = LabelRepository
            _schema_class = LabelSchema
            _entity_class = LabelEntity
            _entity_name = 'label'
            _entity_id_field = 'label_id'

            def _extract_filter_kwargs(self, list_request) -> dict:
                return {
                    'name': list_request.name,
                    'label_ids': list_request.label_ids,
                    ...
                }
    """

    _repository_class: Type[TRepository]
    _schema_class: Type[TSchema]
    _entity_class: Type[TEntity]
    _entity_name: str
    _entity_id_field: str
    _bulk_items_attr: Optional[str] = None  # Override for bulk create items attribute

    def __init__(self, session: Session):
        """
        Initialize the service with a database session.

        Args:
            session: SQLAlchemy session for database operations (required)
        """
        self._session = session
        self._repository: TRepository = self._repository_class(self._session)
        logger.debug(f'Initialized {self.__class__.__name__}')

    def commit(self) -> None:
        """Flush pending changes to the database."""
        self._session.commit()

    @abstractmethod
    def _extract_filter_kwargs(self, list_request: Any) -> dict:
        """
        Extract filter keyword arguments from list request.

        Override in subclass to extract entity-specific filters.

        Args:
            list_request: The list request schema

        Returns:
            Dict of filter kwargs to pass to repository
        """
        pass

    @abstractmethod
    def _create_entity_from_request(self, create_request: Any) -> TEntity:
        """
        Create an entity instance from a create request.

        Override in subclass to handle entity-specific field mapping.

        Args:
            create_request: The create request schema

        Returns:
            New entity instance (not yet persisted)
        """
        pass

    @abstractmethod
    def _update_entity_from_request(self, entity: TEntity, update_request: Any) -> None:
        """
        Update an entity from an update request.

        Override in subclass to handle entity-specific field mapping.
        Should only update fields that are not None in the request.

        Args:
            entity: The existing entity to update
            update_request: The update request schema
        """
        pass

    def _get_entity_id(self, request: Any) -> str:
        """Get entity ID from request using configured field name."""
        return getattr(request, self._entity_id_field)

    def list_entities(
        self, list_request: Any
    ) -> Tuple[List[TSchema], int]:
        """
        List entities with filtering, sorting and pagination.

        Args:
            list_request: Request containing filter, sort, and pagination parameters

        Returns:
            Tuple containing:
                - List of schema objects
                - Total count of entities matching the filters
        """
        assert list_request.tenant_id is not None, 'Tenant ID is required'
        assert list_request.bu_id is not None, 'Business unit ID is required'

        logger.debug(
            f'Listing {self._entity_name}s for tenant: {list_request.tenant_id}, '
            f'bu: {list_request.bu_id}'
        )

        # Extract filter kwargs from request
        filter_kwargs = self._extract_filter_kwargs(list_request)

        # Get is_active filter (optional, defaults to None if not present in schema)
        is_active = getattr(list_request, 'is_active', None)

        # Get entities from repository
        entities = self._repository.list_with_filters(
            tenant_id=list_request.tenant_id,
            bu_id=list_request.bu_id,
            limit=list_request.limit,
            offset=list_request.offset,
            sort_by=list_request.sort_by,
            sort_order=list_request.sort_order,
            is_active=is_active,
            **filter_kwargs,
        )

        # Get total count with same filters
        total_count = self._repository.count_with_filters(
            tenant_id=list_request.tenant_id,
            bu_id=list_request.bu_id,
            is_active=is_active,
            **filter_kwargs,
        )

        logger.debug(f'Found {len(entities)} {self._entity_name}s out of {total_count} total')

        # Convert entities to schemas
        schemas = [self._schema_class.model_validate(entity) for entity in entities]

        return schemas, total_count

    def create_entity(self, create_request: Any) -> TSchema:
        """
        Create a new entity.

        Args:
            create_request: Request containing entity creation data

        Returns:
            The created entity as a schema
        """
        assert create_request.tenant_id is not None, 'Tenant ID is required'
        assert create_request.bu_id is not None, 'Business unit ID is required'

        logger.info(
            f'Creating {self._entity_name} for tenant: {create_request.tenant_id}, '
            f'bu: {create_request.bu_id}'
        )

        # Create entity from request
        entity = self._create_entity_from_request(create_request)

        # Save to database
        created_entity = self._repository.create(entity)
        logger.info(f'{self._entity_name.capitalize()} created successfully with ID: {created_entity.id}')

        return self._schema_class.model_validate(created_entity)

    def create_entities_bulk(self, create_request: Any) -> List[TSchema]:
        """
        Create multiple new entities.

        Args:
            create_request: Request containing list of entities to create.
                           Must have 'tenant_id', 'bu_id', and an items list attribute.

        Returns:
            List of created entities as schemas
        """
        assert create_request.tenant_id is not None, 'Tenant ID is required'
        assert create_request.bu_id is not None, 'Business unit ID is required'

        # Get the bulk items attribute (e.g., 'lots', 'bins', 'forecasts')
        # Use _bulk_items_attr if defined, otherwise default to '{entity_name}s'
        items_attr = self._bulk_items_attr or f'{self._entity_name}s'
        items = getattr(create_request, items_attr, None)
        if items is None:
            raise ValueError(f'Bulk create request must have {items_attr} attribute')

        logger.info(
            f'Creating {len(items)} {self._entity_name}s for tenant: {create_request.tenant_id}, '
            f'bu: {create_request.bu_id}'
        )

        created_entities = []
        for item_data in items:
            # Set tenant_id and bu_id from parent request
            item_data.tenant_id = create_request.tenant_id
            item_data.bu_id = create_request.bu_id

            # Create entity from request
            entity = self._create_entity_from_request(item_data)
            created = self._repository.create(entity)
            created_entities.append(created)

        logger.info(f'Successfully created {len(created_entities)} {self._entity_name}s')

        return [self._schema_class.model_validate(entity) for entity in created_entities]

    def update_entity(self, update_request: Any) -> TSchema:
        """
        Update an entity.

        Args:
            update_request: Request containing update data

        Returns:
            The updated entity as a schema

        Raises:
            ValueError: If the entity is not found
        """
        assert update_request.tenant_id is not None, 'Tenant ID is required'
        assert update_request.bu_id is not None, 'Business unit ID is required'

        entity_id = self._get_entity_id(update_request)
        assert entity_id is not None, f'{self._entity_name.capitalize()} ID is required'

        logger.info(
            f'Updating {self._entity_name} {entity_id} for tenant: {update_request.tenant_id}, '
            f'bu: {update_request.bu_id}'
        )

        # Get existing entity
        entity = self._repository.get_by_id(
            tenant_id=update_request.tenant_id,
            bu_id=update_request.bu_id,
            entity_id=entity_id,
        )

        if not entity:
            logger.error(f'{self._entity_name.capitalize()} not found: {entity_id}')
            raise ValueError(f'{self._entity_name.capitalize()} not found with ID: {entity_id}')

        # Update entity from request
        self._update_entity_from_request(entity, update_request)

        # Save changes
        updated_entity = self._repository.update(entity)
        logger.info(f'{self._entity_name.capitalize()} updated successfully: {updated_entity.id}')

        return self._schema_class.model_validate(updated_entity)

    def get_entity_by_id(self, get_request: Any) -> Optional[TSchema]:
        """
        Get an entity by its ID.

        Args:
            get_request: Request containing entity ID

        Returns:
            The entity as a schema if found, otherwise None
        """
        assert get_request.tenant_id is not None, 'Tenant ID is required'
        assert get_request.bu_id is not None, 'Business unit ID is required'

        entity_id = self._get_entity_id(get_request)
        assert entity_id is not None, f'{self._entity_name.capitalize()} ID is required'

        logger.info(
            f'Getting {self._entity_name} {entity_id} for tenant: {get_request.tenant_id}, '
            f'bu: {get_request.bu_id}'
        )

        entity = self._repository.get_by_id(
            tenant_id=get_request.tenant_id,
            bu_id=get_request.bu_id,
            entity_id=entity_id,
        )

        if not entity:
            logger.info(f'{self._entity_name.capitalize()} not found: {entity_id}')
            return None

        return self._schema_class.model_validate(entity)

    def delete_entity_by_id(self, delete_request: Any) -> None:
        """
        Delete an entity by its ID.

        Args:
            delete_request: Request containing entity deletion data

        Raises:
            ValueError: If the entity is not found
        """
        assert delete_request.tenant_id is not None, 'Tenant ID is required'
        assert delete_request.bu_id is not None, 'Business unit ID is required'

        entity_id = self._get_entity_id(delete_request)
        assert entity_id is not None, f'{self._entity_name.capitalize()} ID is required'

        logger.info(
            f'Deleting {self._entity_name} {entity_id} for tenant: {delete_request.tenant_id}, '
            f'bu: {delete_request.bu_id}'
        )

        # Get entity to delete
        entity = self._repository.get_by_id(
            tenant_id=delete_request.tenant_id,
            bu_id=delete_request.bu_id,
            entity_id=entity_id,
        )

        if not entity:
            logger.error(f'{self._entity_name.capitalize()} not found: {entity_id}')
            raise ValueError(f'{self._entity_name.capitalize()} not found with ID: {entity_id}')

        # Delete entity
        self._repository.delete(entity)
        logger.info(f'{self._entity_name.capitalize()} deleted successfully: {entity_id}')
