# SPDX-License-Identifier: Apache-2.0
"""Base test classes for repository testing.

Provides reusable test patterns for BaseRepository implementations.
Extend these classes to quickly create comprehensive repository tests.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Type, TypeVar

import pytest
from sqlalchemy.orm import Session

from common.entities.base_entity import BaseEntity, TableName
from common.repositories.base_repository import BaseRepository
from common.schemas.base_enums_schemas import SortOrder


TEntity = TypeVar('TEntity', bound=BaseEntity)
TRepository = TypeVar('TRepository', bound=BaseRepository)


class BaseRepositoryTestMixin(ABC, Generic[TEntity, TRepository]):
    """
    Abstract base mixin for repository tests.

    Subclasses must define:
    - repository_class: The repository class to test
    - entity_class: The entity class
    - table_name: TableName enum for seeded data access

    And implement fixtures:
    - repository: Create repository instance
    - test_tenant_id: Return test tenant ID
    - test_bu_id: Return test BU ID
    """

    repository_class: Type[TRepository]
    entity_class: Type[TEntity]
    table_name: TableName

    @pytest.fixture
    @abstractmethod
    def repository(self, db_session: Session) -> TRepository:
        """Create a repository instance for testing."""
        pass

    @pytest.fixture
    def test_tenant_id(self) -> str:
        """Test tenant ID."""
        return 'tenant_1'

    @pytest.fixture
    def test_bu_id(self) -> str:
        """Test business unit ID."""
        return 'bu_1'


class ReadOnlyRepositoryTests(BaseRepositoryTestMixin[TEntity, TRepository]):
    """
    Reusable read-only tests for repositories.

    Provides standard tests for:
    - list_with_filters
    - count_with_filters
    - get_by_id
    - get_by_ids

    These tests do not modify data.
    """

    def test_list_with_filters_returns_all_entities(
        self,
        repository: TRepository,
        test_tenant_id: str,
        test_bu_id: str,
        seeded_data: Dict[TableName, List[Any]],
    ):
        """Test that list_with_filters returns all seeded entities."""
        # Arrange
        expected_count = len(seeded_data[self.table_name])

        # Act
        actual_results = repository.list_with_filters(
            tenant_id=test_tenant_id,
            bu_id=test_bu_id,
        )

        # Assert
        assert len(actual_results) == expected_count

    def test_list_with_filters_respects_limit(
        self,
        repository: TRepository,
        test_tenant_id: str,
        test_bu_id: str,
        seeded_data: Dict[TableName, List[Any]],
    ):
        """Test that list_with_filters respects the limit parameter."""
        # Arrange
        expected_limit = 2

        # Act
        actual_results = repository.list_with_filters(
            tenant_id=test_tenant_id,
            bu_id=test_bu_id,
            limit=expected_limit,
        )

        # Assert
        assert len(actual_results) <= expected_limit

    def test_list_with_filters_respects_offset(
        self,
        repository: TRepository,
        test_tenant_id: str,
        test_bu_id: str,
        seeded_data: Dict[TableName, List[Any]],
    ):
        """Test that list_with_filters respects the offset parameter."""
        # Get all results first
        all_results = repository.list_with_filters(
            tenant_id=test_tenant_id,
            bu_id=test_bu_id,
        )

        if len(all_results) <= 1:
            pytest.skip('Not enough data to test offset')

        # Get with offset
        offset = 1
        offset_results = repository.list_with_filters(
            tenant_id=test_tenant_id,
            bu_id=test_bu_id,
            offset=offset,
        )

        # Assert - first result with offset should be second result without
        assert len(offset_results) == len(all_results) - offset

    def test_count_with_filters_returns_total(
        self,
        repository: TRepository,
        test_tenant_id: str,
        test_bu_id: str,
        seeded_data: Dict[TableName, List[Any]],
    ):
        """Test that count_with_filters returns correct total count."""
        # Arrange
        expected_count = len(seeded_data[self.table_name])

        # Act
        actual_count = repository.count_with_filters(
            tenant_id=test_tenant_id,
            bu_id=test_bu_id,
        )

        # Assert
        assert actual_count == expected_count

    def test_get_by_id_returns_entity_when_found(
        self,
        repository: TRepository,
        test_tenant_id: str,
        test_bu_id: str,
        seeded_data: Dict[TableName, List[Any]],
    ):
        """Test that get_by_id returns the entity when it exists."""
        # Arrange
        seeded_entity = seeded_data[self.table_name][0]
        expected_id = seeded_entity.id

        # Act
        actual_result = repository.get_by_id(
            tenant_id=test_tenant_id,
            bu_id=test_bu_id,
            entity_id=expected_id,
        )

        # Assert
        assert actual_result is not None
        assert actual_result.id == expected_id

    def test_get_by_id_returns_none_when_not_found(
        self,
        repository: TRepository,
        test_tenant_id: str,
        test_bu_id: str,
    ):
        """Test that get_by_id returns None when entity doesn't exist."""
        # Arrange
        nonexistent_id = 'nonexistent_id_999'

        # Act
        actual_result = repository.get_by_id(
            tenant_id=test_tenant_id,
            bu_id=test_bu_id,
            entity_id=nonexistent_id,
        )

        # Assert
        assert actual_result is None

    def test_get_by_ids_returns_matching_entities(
        self,
        repository: TRepository,
        test_tenant_id: str,
        test_bu_id: str,
        seeded_data: Dict[TableName, List[Any]],
    ):
        """Test that get_by_ids returns all matching entities."""
        # Arrange
        seeded_entities = seeded_data[self.table_name]
        if len(seeded_entities) < 2:
            pytest.skip('Not enough data to test get_by_ids')

        expected_ids = [seeded_entities[0].id, seeded_entities[1].id]

        # Act
        actual_results = repository.get_by_ids(
            tenant_id=test_tenant_id,
            bu_id=test_bu_id,
            entity_ids=expected_ids,
        )

        # Assert
        assert len(actual_results) == len(expected_ids)
        actual_ids = {e.id for e in actual_results}
        assert actual_ids == set(expected_ids)

    def test_get_by_ids_returns_empty_for_no_matches(
        self,
        repository: TRepository,
        test_tenant_id: str,
        test_bu_id: str,
    ):
        """Test that get_by_ids returns empty list when no IDs match."""
        # Arrange
        nonexistent_ids = ['nonexistent_1', 'nonexistent_2']

        # Act
        actual_results = repository.get_by_ids(
            tenant_id=test_tenant_id,
            bu_id=test_bu_id,
            entity_ids=nonexistent_ids,
        )

        # Assert
        assert len(actual_results) == 0

    def test_get_by_ids_returns_empty_for_empty_list(
        self,
        repository: TRepository,
        test_tenant_id: str,
        test_bu_id: str,
    ):
        """Test that get_by_ids returns empty list when given empty list."""
        # Act
        actual_results = repository.get_by_ids(
            tenant_id=test_tenant_id,
            bu_id=test_bu_id,
            entity_ids=[],
        )

        # Assert
        assert len(actual_results) == 0


class MutationRepositoryTests(BaseRepositoryTestMixin[TEntity, TRepository]):
    """
    Reusable mutation tests for repositories.

    Provides standard tests for:
    - create
    - update
    - delete

    These tests modify data and should use isolated database sessions.
    """

    @abstractmethod
    def create_test_entity(
        self,
        tenant_id: str,
        bu_id: str,
        seeded_data: Dict[TableName, List[Any]],
    ) -> TEntity:
        """
        Create a test entity for mutation tests.

        Override this to create an appropriate entity for your specific type.
        """
        pass

    def test_create_entity(
        self,
        repository: TRepository,
        test_tenant_id: str,
        test_bu_id: str,
        db_session: Session,
        seeded_data: Dict[TableName, List[Any]],
    ):
        """Test creating an entity."""
        # Arrange
        test_entity = self.create_test_entity(test_tenant_id, test_bu_id, seeded_data)

        # Act
        actual_result = repository.create(test_entity)
        db_session.commit()

        # Assert
        assert actual_result.id is not None
        assert actual_result.tenant_id == test_tenant_id
        assert actual_result.bu_id == test_bu_id
        assert actual_result.created_at is not None

    def test_update_entity(
        self,
        repository: TRepository,
        test_tenant_id: str,
        test_bu_id: str,
        db_session: Session,
        seeded_data: Dict[TableName, List[Any]],
    ):
        """Test updating an entity."""
        # Arrange - get existing entity
        entity_to_update = seeded_data[self.table_name][0]
        original_updated_at = entity_to_update.updated_at

        # Make a change (just mark is_active)
        entity_to_update.is_active = not entity_to_update.is_active

        # Act
        actual_result = repository.update(entity_to_update)
        db_session.commit()

        # Assert
        assert actual_result.is_active == entity_to_update.is_active

    def test_delete_entity(
        self,
        repository: TRepository,
        test_tenant_id: str,
        test_bu_id: str,
        db_session: Session,
        seeded_data: Dict[TableName, List[Any]],
    ):
        """Test deleting an entity."""
        # Arrange
        entity_to_delete = seeded_data[self.table_name][0]
        entity_id = entity_to_delete.id

        # Verify it exists
        fetched_before = repository.get_by_id(
            tenant_id=test_tenant_id,
            bu_id=test_bu_id,
            entity_id=entity_id,
        )
        assert fetched_before is not None

        # Act
        repository.delete(entity_to_delete)
        db_session.commit()

        # Assert - verify it no longer exists
        fetched_after = repository.get_by_id(
            tenant_id=test_tenant_id,
            bu_id=test_bu_id,
            entity_id=entity_id,
        )
        assert fetched_after is None
