# SPDX-License-Identifier: Apache-2.0
"""Repository layer tests for BU entity.

Organized by operation type with separate base classes for read-only and mutation tests.
Note: BU is scoped under tenant.
"""

import pytest
from typing import Any, Dict

from sqlalchemy.orm import Session

from common.schemas.base_enums_schemas import SortOrder
from organization.entities.bu_entity import BuEntity
from organization.repositories.bu_repository import BuRepository
from organization.schemas.bus_api_schema import BuSortByFields
from tests.seed_db import SeedDb, TableName


# =============================================================================
# SEED CONFIGS FOR MUTATION TESTS
# =============================================================================

# Config for create tests - seed tenant but no BUs
CREATE_SEED_CONFIG = SeedDb.SeedConfig(
    tables_to_populate=[TableName.TENANT],
    tenant_count=1,
    bu_count_per_tenant=0,
)

# Config for update/delete tests - seed tenant and some BUs
MUTATION_WITH_DATA_SEED_CONFIG = SeedDb.SeedConfig(
    tables_to_populate=[TableName.TENANT, TableName.BU],
    tenant_count=1,
    bu_count_per_tenant=3,
)


# =============================================================================
# BASE TEST CLASSES
# =============================================================================


class TestBuRepositoryBase:
    """Base class with common fixtures for all BU repository tests."""

    @pytest.fixture
    def repository(self, db_session: Session) -> BuRepository:
        """Create a repository instance for testing."""
        return BuRepository(db_session)

    @pytest.fixture
    def test_tenant_id(
        self,
        seeded_data: Dict[TableName, list[Any]]
    ) -> str:
        """Test tenant ID from seeded data."""
        return seeded_data[TableName.TENANT][0].id


class TestBuRepositoryReadOnlyBase(TestBuRepositoryBase):
    """
    Base class for read-only tests using the shared database.

    These tests do not modify data, so they can safely share a pre-seeded database
    for faster execution.
    """

    @pytest.fixture
    def db_session(self, shared_db_session: Session) -> Session:
        """Use the shared database session for read-only tests."""
        return shared_db_session

    @pytest.fixture
    def seeded_data(
        self, all_seeded_data_for_shared_db: Dict[TableName, list[Any]]
    ) -> Dict[TableName, list[Any]]:
        """Use the shared seeded data."""
        return all_seeded_data_for_shared_db


class TestBuRepositoryMutationBase(TestBuRepositoryBase):
    """
    Base class for mutation tests using isolated databases.

    These tests modify data, so each test class gets its own isolated database.
    """

    @pytest.fixture(scope='class')
    def class_db_resources(self, class_scoped_isolated_db_session):
        """Get isolated database resources for the entire test class."""
        return class_scoped_isolated_db_session

    @pytest.fixture(scope='class')
    def db_session(self, class_db_resources) -> Session:
        """Extract session from class resources."""
        session, _ = class_db_resources
        return session

    @pytest.fixture(scope='class')
    def seeded_data(self, class_db_resources) -> Dict[TableName, list[Any]]:
        """Extract seeded data from class resources."""
        _, data = class_db_resources
        return data


# =============================================================================
# READ-ONLY TESTS: LIST WITH FILTERS
# =============================================================================


class TestBuRepositoryListWithFilters(TestBuRepositoryReadOnlyBase):
    """Tests for list_with_filters method."""

    def test_list_with_filters_returns_all_bus(
        self,
        repository: BuRepository,
        test_tenant_id: str,
        seeded_data: Dict[TableName, list[Any]],
    ):
        """Test that list_with_filters returns all seeded BUs for tenant."""
        # Arrange
        expected_bus = [bu for bu in seeded_data[TableName.BU] if bu.tenant_id == test_tenant_id]
        expected_count = len(expected_bus)

        # Act
        actual_results = repository.list_with_filters(tenant_id=test_tenant_id)

        # Assert
        assert len(actual_results) == expected_count

    def test_list_with_filters_with_limit(
        self,
        repository: BuRepository,
        test_tenant_id: str,
        seeded_data: Dict[TableName, list[Any]],
    ):
        """Test that list_with_filters respects the limit parameter."""
        # Arrange
        expected_limit = 2

        # Act
        actual_results = repository.list_with_filters(
            tenant_id=test_tenant_id,
            limit=expected_limit,
        )

        # Assert
        assert len(actual_results) <= expected_limit

    def test_list_with_filters_with_search(
        self,
        repository: BuRepository,
        test_tenant_id: str,
        seeded_data: Dict[TableName, list[Any]],
    ):
        """Test that list_with_filters searches in BU name."""
        # Arrange
        # Use first 3 characters of the first seeded BU's name to ensure we find it
        first_bu = next((bu for bu in seeded_data[TableName.BU] if bu.tenant_id == test_tenant_id), None)
        assert first_bu is not None, "No BU found for test tenant"
        search_term = first_bu.name[:3]

        # Act
        actual_results = repository.list_with_filters(
            tenant_id=test_tenant_id,
            search=search_term,
        )

        # Assert
        assert len(actual_results) > 0
        for result in actual_results:
            assert search_term.lower() in result.name.lower()

    def test_list_with_filters_sorted_by_name_asc(
        self,
        repository: BuRepository,
        test_tenant_id: str,
        seeded_data: Dict[TableName, list[Any]],
    ):
        """Test that list_with_filters sorts by name ascending."""
        # Arrange
        sort_by = BuSortByFields.NAME
        sort_order = SortOrder.ASC

        # Act
        actual_results = repository.list_with_filters(
            tenant_id=test_tenant_id,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        # Assert
        if len(actual_results) > 1:
            for i in range(len(actual_results) - 1):
                assert actual_results[i].name <= actual_results[i + 1].name


# =============================================================================
# READ-ONLY TESTS: COUNT WITH FILTERS
# =============================================================================


class TestBuRepositoryCountWithFilters(TestBuRepositoryReadOnlyBase):
    """Tests for count_with_filters method."""

    def test_count_with_filters_returns_total(
        self,
        repository: BuRepository,
        test_tenant_id: str,
        seeded_data: Dict[TableName, list[Any]],
    ):
        """Test that count_with_filters returns correct total count."""
        # Arrange
        expected_bus = [bu for bu in seeded_data[TableName.BU] if bu.tenant_id == test_tenant_id]
        expected_count = len(expected_bus)

        # Act
        actual_count = repository.count_with_filters(tenant_id=test_tenant_id)

        # Assert
        assert actual_count == expected_count


# =============================================================================
# READ-ONLY TESTS: GET BY ID
# =============================================================================


class TestBuRepositoryGetById(TestBuRepositoryReadOnlyBase):
    """Tests for get_by_id method."""

    def test_get_by_id_returns_bu_when_found(
        self,
        repository: BuRepository,
        test_tenant_id: str,
        seeded_data: Dict[TableName, list[Any]],
    ):
        """Test that get_by_id returns the BU when it exists."""
        # Arrange
        seeded_bu = seeded_data[TableName.BU][0]
        expected_id = seeded_bu.id

        # Act
        actual_result = repository.get_by_id(
            tenant_id=seeded_bu.tenant_id,
            bu_id=expected_id,
        )

        # Assert
        assert actual_result is not None
        assert actual_result.id == expected_id
        assert actual_result.name == seeded_bu.name

    def test_get_by_id_returns_none_when_not_found(
        self,
        repository: BuRepository,
        test_tenant_id: str,
    ):
        """Test that get_by_id returns None when BU doesn't exist."""
        # Arrange
        nonexistent_id = 'bu_nonexistent_999'

        # Act
        actual_result = repository.get_by_id(
            tenant_id=test_tenant_id,
            bu_id=nonexistent_id,
        )

        # Assert
        assert actual_result is None


# =============================================================================
# MUTATION TESTS: CREATE
# =============================================================================


@pytest.mark.seed_config(CREATE_SEED_CONFIG)
class TestBuRepositoryCreate(TestBuRepositoryMutationBase):
    """Tests for create method."""

    def test_create_bu_with_minimal_fields(
        self,
        repository: BuRepository,
        db_session: Session,
        seeded_data: Dict[TableName, list[Any]],
    ):
        """Test creating a BU with only required fields."""
        # Arrange
        tenant = seeded_data[TableName.TENANT][0]
        test_bu = BuEntity(
            tenant_id=tenant.id,
            name='Test BU Minimal',
        )

        # Act
        actual_result = repository.create(test_bu)
        db_session.commit()

        # Assert
        assert actual_result.id is not None
        assert actual_result.id.startswith('bu_')
        assert actual_result.name == 'Test BU Minimal'
        assert actual_result.tenant_id == tenant.id
        assert actual_result.description is None
        assert actual_result.created_at is not None

    def test_create_bu_with_all_fields(
        self,
        repository: BuRepository,
        db_session: Session,
        seeded_data: Dict[TableName, list[Any]],
    ):
        """Test creating a BU with all fields populated."""
        # Arrange
        tenant = seeded_data[TableName.TENANT][0]
        expected_description = 'A test BU with all fields'
        test_bu = BuEntity(
            tenant_id=tenant.id,
            name='Test BU Full',
            description=expected_description,
        )

        # Act
        actual_result = repository.create(test_bu)
        db_session.commit()

        # Assert
        assert actual_result.id is not None
        assert actual_result.name == 'Test BU Full'
        assert actual_result.description == expected_description


# =============================================================================
# MUTATION TESTS: UPDATE
# =============================================================================


@pytest.mark.seed_config(MUTATION_WITH_DATA_SEED_CONFIG)
class TestBuRepositoryUpdate(TestBuRepositoryMutationBase):
    """Tests for update method."""

    def test_update_bu_single_field(
        self,
        repository: BuRepository,
        db_session: Session,
        seeded_data: Dict[TableName, list[Any]],
    ):
        """Test updating a single field on a BU."""
        # Arrange
        bu_to_update = seeded_data[TableName.BU][0]
        expected_new_name = 'Updated BU Name'
        bu_to_update.name = expected_new_name

        # Act
        actual_result = repository.update(bu_to_update)
        db_session.commit()

        # Assert
        assert actual_result.name == expected_new_name

        # Verify by fetching fresh
        fetched = repository.get_by_id(
            tenant_id=bu_to_update.tenant_id,
            bu_id=bu_to_update.id,
        )
        assert fetched.name == expected_new_name


# =============================================================================
# MUTATION TESTS: DELETE
# =============================================================================


@pytest.mark.seed_config(MUTATION_WITH_DATA_SEED_CONFIG)
class TestBuRepositoryDelete(TestBuRepositoryMutationBase):
    """Tests for delete method."""

    def test_delete_bu(
        self,
        repository: BuRepository,
        db_session: Session,
        seeded_data: Dict[TableName, list[Any]],
    ):
        """Test deleting a BU."""
        # Arrange
        bu_to_delete = seeded_data[TableName.BU][0]
        bu_id = bu_to_delete.id
        tenant_id = bu_to_delete.tenant_id

        # Verify it exists first
        fetched_before = repository.get_by_id(tenant_id=tenant_id, bu_id=bu_id)
        assert fetched_before is not None

        # Act
        repository.delete(bu_to_delete)
        db_session.commit()

        # Assert - verify it no longer exists
        fetched_after = repository.get_by_id(tenant_id=tenant_id, bu_id=bu_id)
        assert fetched_after is None
