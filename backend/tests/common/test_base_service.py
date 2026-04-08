# SPDX-License-Identifier: Apache-2.0
"""Base test classes for service testing.

Provides reusable test patterns for BaseService implementations.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Type
from unittest.mock import Mock, create_autospec

import pytest
from pydantic import BaseModel
from sqlalchemy.orm import Session

from common.entities.base_entity import BaseEntity
from common.repositories.base_repository import BaseRepository
from common.services.base_service import BaseService


class BaseServiceTestMixin(ABC):
    """
    Abstract base mixin for service tests.

    Subclasses must define:
    - service_class: The service class to test
    - repository_class: The repository class (for mocking)
    - entity_class: The entity class
    - schema_class: The schema class

    And implement:
    - create_mock_entity(): Create a mock entity with test data
    - create_list_request(): Create a list request schema
    - create_create_request(): Create a create request schema
    - create_update_request(): Create an update request schema
    - create_get_by_id_request(): Create a get-by-ID request schema
    - create_delete_request(): Create a delete request schema
    """

    service_class: Type[BaseService]
    repository_class: Type[BaseRepository]
    entity_class: Type[BaseEntity]
    schema_class: Type[BaseModel]
    entity_id_field: str = 'id'

    @pytest.fixture
    def mock_session(self) -> Mock:
        """Create a mock database session."""
        return create_autospec(Session, instance=True, spec_set=True)

    @pytest.fixture
    def mock_repository(self) -> Mock:
        """Create a mock repository."""
        return create_autospec(self.repository_class, instance=True, spec_set=True)

    @pytest.fixture
    def service(self, mock_session: Mock, mock_repository: Mock):
        """Create a service with mocked dependencies."""
        svc = self.service_class(mock_session)
        svc._repository = mock_repository
        return svc

    @abstractmethod
    def create_mock_entity(self) -> Any:
        """Create a mock entity with test data."""
        pass

    @abstractmethod
    def create_list_request(
        self,
        tenant_id: str = 'tenant_test',
        bu_id: str = 'bu_test',
    ) -> Any:
        """Create a list request schema."""
        pass

    @abstractmethod
    def create_create_request(
        self,
        tenant_id: str = 'tenant_test',
        bu_id: str = 'bu_test',
    ) -> Any:
        """Create a create request schema."""
        pass

    @abstractmethod
    def create_update_request(
        self,
        tenant_id: str = 'tenant_test',
        bu_id: str = 'bu_test',
        entity_id: str = 'test_id',
    ) -> Any:
        """Create an update request schema."""
        pass

    @abstractmethod
    def create_get_by_id_request(
        self,
        tenant_id: str = 'tenant_test',
        bu_id: str = 'bu_test',
        entity_id: str = 'test_id',
    ) -> Any:
        """Create a get-by-ID request schema."""
        pass

    @abstractmethod
    def create_delete_request(
        self,
        tenant_id: str = 'tenant_test',
        bu_id: str = 'bu_test',
        entity_id: str = 'test_id',
    ) -> Any:
        """Create a delete request schema."""
        pass


class ListEntitiesTests(BaseServiceTestMixin):
    """Tests for list_entities method."""

    def test_list_entities_returns_schemas_and_count(
        self,
        service: BaseService,
        mock_repository: Mock,
    ):
        """Test that list_entities returns schemas and total count."""
        # Arrange
        mock_entity = self.create_mock_entity()
        mock_repository.list_with_filters.return_value = [mock_entity]
        mock_repository.count_with_filters.return_value = 1

        list_request = self.create_list_request()

        # Act
        actual_schemas, actual_count = service.list_entities(list_request)

        # Assert
        assert actual_count == 1
        assert len(actual_schemas) == 1
        assert isinstance(actual_schemas[0], self.schema_class)

        mock_repository.list_with_filters.assert_called_once()
        mock_repository.count_with_filters.assert_called_once()

    def test_list_entities_handles_empty_results(
        self,
        service: BaseService,
        mock_repository: Mock,
    ):
        """Test that list_entities handles empty results."""
        # Arrange
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        list_request = self.create_list_request()

        # Act
        actual_schemas, actual_count = service.list_entities(list_request)

        # Assert
        assert actual_count == 0
        assert len(actual_schemas) == 0

    def test_list_entities_missing_tenant_id_raises(
        self,
        service: BaseService,
    ):
        """Test that list_entities raises AssertionError for missing tenant_id."""
        list_request = self.create_list_request(tenant_id=None)

        with pytest.raises(AssertionError):
            service.list_entities(list_request)

    def test_list_entities_missing_bu_id_raises(
        self,
        service: BaseService,
    ):
        """Test that list_entities raises AssertionError for missing bu_id."""
        list_request = self.create_list_request(bu_id=None)

        with pytest.raises(AssertionError):
            service.list_entities(list_request)


class CreateEntityTests(BaseServiceTestMixin):
    """Tests for create_entity method."""

    def test_create_entity_returns_schema(
        self,
        service: BaseService,
        mock_repository: Mock,
    ):
        """Test that create_entity returns a schema."""
        # Arrange
        mock_entity = self.create_mock_entity()
        mock_repository.create.return_value = mock_entity

        create_request = self.create_create_request()

        # Act
        actual_result = service.create_entity(create_request)

        # Assert
        assert isinstance(actual_result, self.schema_class)
        mock_repository.create.assert_called_once()

    def test_create_entity_missing_tenant_id_raises(
        self,
        service: BaseService,
    ):
        """Test that create_entity raises AssertionError for missing tenant_id."""
        create_request = self.create_create_request(tenant_id=None)

        with pytest.raises(AssertionError):
            service.create_entity(create_request)

    def test_create_entity_missing_bu_id_raises(
        self,
        service: BaseService,
    ):
        """Test that create_entity raises AssertionError for missing bu_id."""
        create_request = self.create_create_request(bu_id=None)

        with pytest.raises(AssertionError):
            service.create_entity(create_request)


class UpdateEntityTests(BaseServiceTestMixin):
    """Tests for update_entity method."""

    def test_update_entity_returns_schema(
        self,
        service: BaseService,
        mock_repository: Mock,
    ):
        """Test that update_entity returns an updated schema."""
        # Arrange
        mock_entity = self.create_mock_entity()
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        update_request = self.create_update_request()

        # Act
        actual_result = service.update_entity(update_request)

        # Assert
        assert isinstance(actual_result, self.schema_class)
        mock_repository.get_by_id.assert_called_once()
        mock_repository.update.assert_called_once()

    def test_update_entity_not_found_raises_value_error(
        self,
        service: BaseService,
        mock_repository: Mock,
    ):
        """Test that update_entity raises ValueError when entity not found."""
        # Arrange
        mock_repository.get_by_id.return_value = None

        update_request = self.create_update_request(entity_id='nonexistent')

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            service.update_entity(update_request)

        assert 'not found' in str(exc_info.value).lower()
        mock_repository.update.assert_not_called()


class GetEntityByIdTests(BaseServiceTestMixin):
    """Tests for get_entity_by_id method."""

    def test_get_entity_by_id_returns_schema_when_found(
        self,
        service: BaseService,
        mock_repository: Mock,
    ):
        """Test that get_entity_by_id returns a schema when found."""
        # Arrange
        mock_entity = self.create_mock_entity()
        mock_repository.get_by_id.return_value = mock_entity

        get_request = self.create_get_by_id_request()

        # Act
        actual_result = service.get_entity_by_id(get_request)

        # Assert
        assert actual_result is not None
        assert isinstance(actual_result, self.schema_class)

    def test_get_entity_by_id_returns_none_when_not_found(
        self,
        service: BaseService,
        mock_repository: Mock,
    ):
        """Test that get_entity_by_id returns None when not found."""
        # Arrange
        mock_repository.get_by_id.return_value = None

        get_request = self.create_get_by_id_request(entity_id='nonexistent')

        # Act
        actual_result = service.get_entity_by_id(get_request)

        # Assert
        assert actual_result is None


class DeleteEntityByIdTests(BaseServiceTestMixin):
    """Tests for delete_entity_by_id method."""

    def test_delete_entity_by_id_success(
        self,
        service: BaseService,
        mock_repository: Mock,
    ):
        """Test that delete_entity_by_id deletes successfully."""
        # Arrange
        mock_entity = self.create_mock_entity()
        mock_repository.get_by_id.return_value = mock_entity

        delete_request = self.create_delete_request()

        # Act
        service.delete_entity_by_id(delete_request)

        # Assert
        mock_repository.get_by_id.assert_called_once()
        mock_repository.delete.assert_called_once_with(mock_entity)

    def test_delete_entity_by_id_not_found_raises_value_error(
        self,
        service: BaseService,
        mock_repository: Mock,
    ):
        """Test that delete_entity_by_id raises ValueError when not found."""
        # Arrange
        mock_repository.get_by_id.return_value = None

        delete_request = self.create_delete_request(entity_id='nonexistent')

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            service.delete_entity_by_id(delete_request)

        assert 'not found' in str(exc_info.value).lower()
        mock_repository.delete.assert_not_called()
