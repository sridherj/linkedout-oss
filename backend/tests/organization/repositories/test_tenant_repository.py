# SPDX-License-Identifier: Apache-2.0
"""Repository layer tests for Tenant entity.

Organized by operation type with separate base classes for read-only and mutation tests.
Note: Tenant is the top-level entity with no scoping.
"""

import pytest
from typing import Any, Dict

from sqlalchemy.orm import Session

from common.schemas.base_enums_schemas import SortOrder
from organization.entities.tenant_entity import TenantEntity
from organization.repositories.tenant_repository import TenantRepository
from organization.schemas.tenants_api_schema import TenantSortByFields
from tests.seed_db import SeedDb, TableName


# =============================================================================
# SEED CONFIGS FOR MUTATION TESTS
# =============================================================================

# Config for create tests - no tenants seeded (tests create their own)
CREATE_SEED_CONFIG = SeedDb.SeedConfig(
    tables_to_populate=[TableName.TENANT],
    tenant_count=0,
)

# Config for update/delete tests - seed some tenants to operate on
MUTATION_WITH_DATA_SEED_CONFIG = SeedDb.SeedConfig(
    tables_to_populate=[TableName.TENANT],
    tenant_count=3,
)


# =============================================================================
# BASE TEST CLASSES
# =============================================================================


class TestTenantRepositoryBase:
    """Base class with common fixtures for all Tenant repository tests."""

    @pytest.fixture
    def repository(self, db_session: Session) -> TenantRepository:
        """Create a repository instance for testing."""
        return TenantRepository(db_session)


class TestTenantRepositoryReadOnlyBase(TestTenantRepositoryBase):
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


class TestTenantRepositoryMutationBase(TestTenantRepositoryBase):
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


class TestTenantRepositoryListWithFilters(TestTenantRepositoryReadOnlyBase):
    """Tests for list_with_filters method."""

    def test_list_with_filters_returns_all_tenants(
        self,
        repository: TenantRepository,
        seeded_data: Dict[TableName, list[Any]],
    ):
        """Test that list_with_filters returns all seeded tenants."""
        # Arrange
        expected_count = len(seeded_data[TableName.TENANT])

        # Act
        actual_results = repository.list_with_filters()

        # Assert
        assert len(actual_results) == expected_count

    def test_list_with_filters_with_limit(
        self,
        repository: TenantRepository,
        seeded_data: Dict[TableName, list[Any]],
    ):
        """Test that list_with_filters respects the limit parameter."""
        # Arrange
        expected_limit = 2

        # Act
        actual_results = repository.list_with_filters(limit=expected_limit)

        # Assert
        assert len(actual_results) <= expected_limit

    def test_list_with_filters_with_offset(
        self,
        repository: TenantRepository,
        seeded_data: Dict[TableName, list[Any]],
    ):
        """Test that list_with_filters respects the offset parameter."""
        # Arrange
        seeded_tenants = seeded_data[TableName.TENANT]
        offset = 1

        # Act
        all_results = repository.list_with_filters(
            sort_by=TenantSortByFields.CREATED_AT
        )
        offset_results = repository.list_with_filters(
            offset=offset,
            sort_by=TenantSortByFields.CREATED_AT
        )

        # Assert
        expected_count = max(0, len(seeded_tenants) - offset)
        assert len(offset_results) == expected_count
        if expected_count > 0 and len(all_results) > offset:
            assert offset_results[0].id == all_results[offset].id

    def test_list_with_filters_with_search(
        self,
        repository: TenantRepository,
        seeded_data: Dict[TableName, list[Any]],
    ):
        """Test that list_with_filters searches in tenant name."""
        # Arrange
        search_term = seeded_data[TableName.TENANT][0].name[0:5]

        # Act
        actual_results = repository.list_with_filters(search=search_term)

        # Assert
        assert len(actual_results) > 0
        for result in actual_results:
            assert search_term.lower() in result.name.lower()

    def test_list_with_filters_sorted_by_name_asc(
        self,
        repository: TenantRepository,
        seeded_data: Dict[TableName, list[Any]],
    ):
        """Test that list_with_filters sorts by name ascending."""
        # Arrange
        sort_by = TenantSortByFields.NAME
        sort_order = SortOrder.ASC

        # Act
        actual_results = repository.list_with_filters(
            sort_by=sort_by,
            sort_order=sort_order
        )

        # Assert
        if len(actual_results) > 1:
            for i in range(len(actual_results) - 1):
                assert actual_results[i].name <= actual_results[i + 1].name

    def test_list_with_filters_sorted_by_name_desc(
        self,
        repository: TenantRepository,
        seeded_data: Dict[TableName, list[Any]],
    ):
        """Test that list_with_filters sorts by name descending."""
        # Arrange
        sort_by = TenantSortByFields.NAME
        sort_order = SortOrder.DESC

        # Act
        actual_results = repository.list_with_filters(
            sort_by=sort_by,
            sort_order=sort_order
        )

        # Assert
        if len(actual_results) > 1:
            for i in range(len(actual_results) - 1):
                assert actual_results[i].name >= actual_results[i + 1].name


# =============================================================================
# READ-ONLY TESTS: COUNT WITH FILTERS
# =============================================================================


class TestTenantRepositoryCountWithFilters(TestTenantRepositoryReadOnlyBase):
    """Tests for count_with_filters method."""

    def test_count_with_filters_returns_total(
        self,
        repository: TenantRepository,
        seeded_data: Dict[TableName, list[Any]],
    ):
        """Test that count_with_filters returns correct total count."""
        # Arrange
        expected_count = len(seeded_data[TableName.TENANT])

        # Act
        actual_count = repository.count_with_filters()

        # Assert
        assert actual_count == expected_count

    def test_count_with_filters_with_search(
        self,
        repository: TenantRepository,
        seeded_data: Dict[TableName, list[Any]],
    ):
        """Test that count_with_filters respects search filter."""
        # Arrange
        search_term = seeded_data[TableName.TENANT][0].name[0:5]

        # Act
        actual_count = repository.count_with_filters(search=search_term)
        list_results = repository.list_with_filters(search=search_term)

        # Assert
        assert actual_count == len(list_results)


# =============================================================================
# READ-ONLY TESTS: GET BY ID
# =============================================================================


class TestTenantRepositoryGetById(TestTenantRepositoryReadOnlyBase):
    """Tests for get_by_id method."""

    def test_get_by_id_returns_tenant_when_found(
        self,
        repository: TenantRepository,
        seeded_data: Dict[TableName, list[Any]],
    ):
        """Test that get_by_id returns the tenant when it exists."""
        # Arrange
        seeded_tenant = seeded_data[TableName.TENANT][0]
        expected_id = seeded_tenant.id

        # Act
        actual_result = repository.get_by_id(tenant_id=expected_id)

        # Assert
        assert actual_result is not None
        assert actual_result.id == expected_id
        assert actual_result.name == seeded_tenant.name

    def test_get_by_id_returns_none_when_not_found(
        self,
        repository: TenantRepository,
    ):
        """Test that get_by_id returns None when tenant doesn't exist."""
        # Arrange
        nonexistent_id = 'tenant_nonexistent_999'

        # Act
        actual_result = repository.get_by_id(tenant_id=nonexistent_id)

        # Assert
        assert actual_result is None


# =============================================================================
# MUTATION TESTS: CREATE
# =============================================================================


@pytest.mark.seed_config(CREATE_SEED_CONFIG)
class TestTenantRepositoryCreate(TestTenantRepositoryMutationBase):
    """Tests for create method."""

    def test_create_tenant_with_minimal_fields(
        self,
        repository: TenantRepository,
        db_session: Session,
    ):
        """Test creating a tenant with only required fields."""
        # Arrange
        test_tenant = TenantEntity(
            name='Test Tenant Minimal',
        )

        # Act
        actual_result = repository.create(test_tenant)
        db_session.commit()

        # Assert
        assert actual_result.id is not None
        assert actual_result.id.startswith('tenant_')
        assert actual_result.name == 'Test Tenant Minimal'
        assert actual_result.description is None
        assert actual_result.created_at is not None
        assert actual_result.updated_at is not None

    def test_create_tenant_with_all_fields(
        self,
        repository: TenantRepository,
        db_session: Session,
    ):
        """Test creating a tenant with all fields populated."""
        # Arrange
        expected_description = 'A test tenant with all fields'
        test_tenant = TenantEntity(
            name='Test Tenant Full',
            description=expected_description,
        )

        # Act
        actual_result = repository.create(test_tenant)
        db_session.commit()

        # Assert
        assert actual_result.id is not None
        assert actual_result.name == 'Test Tenant Full'
        assert actual_result.description == expected_description

    def test_create_multiple_tenants(
        self,
        repository: TenantRepository,
        db_session: Session,
    ):
        """Test creating multiple tenants."""
        # Arrange
        test_tenants = [
            TenantEntity(name=f'Tenant Create Multiple {i}')
            for i in range(3)
        ]

        # Act
        created_tenants = []
        for tenant in test_tenants:
            created = repository.create(tenant)
            created_tenants.append(created)
        db_session.commit()

        # Assert
        assert len(created_tenants) == 3
        for i, created in enumerate(created_tenants):
            assert created.id is not None
            assert created.name == f'Tenant Create Multiple {i}'


# =============================================================================
# MUTATION TESTS: UPDATE
# =============================================================================


@pytest.mark.seed_config(MUTATION_WITH_DATA_SEED_CONFIG)
class TestTenantRepositoryUpdate(TestTenantRepositoryMutationBase):
    """Tests for update method."""

    def test_update_tenant_single_field(
        self,
        repository: TenantRepository,
        db_session: Session,
        seeded_data: Dict[TableName, list[Any]],
    ):
        """Test updating a single field on a tenant."""
        # Arrange
        tenant_to_update = seeded_data[TableName.TENANT][0]
        expected_new_name = 'Updated Tenant Name'
        tenant_to_update.name = expected_new_name

        # Act
        actual_result = repository.update(tenant_to_update)
        db_session.commit()

        # Assert
        assert actual_result.name == expected_new_name

        # Verify by fetching fresh
        fetched = repository.get_by_id(tenant_id=tenant_to_update.id)
        assert fetched.name == expected_new_name

    def test_update_tenant_multiple_fields(
        self,
        repository: TenantRepository,
        db_session: Session,
        seeded_data: Dict[TableName, list[Any]],
    ):
        """Test updating multiple fields on a tenant."""
        # Arrange
        tenant_to_update = seeded_data[TableName.TENANT][1]
        expected_new_name = 'Multi-Updated Tenant'
        expected_description = 'Updated description'

        tenant_to_update.name = expected_new_name
        tenant_to_update.description = expected_description

        # Act
        actual_result = repository.update(tenant_to_update)
        db_session.commit()

        # Assert
        assert actual_result.name == expected_new_name
        assert actual_result.description == expected_description


# =============================================================================
# MUTATION TESTS: DELETE
# =============================================================================


@pytest.mark.seed_config(MUTATION_WITH_DATA_SEED_CONFIG)
class TestTenantRepositoryDelete(TestTenantRepositoryMutationBase):
    """Tests for delete method."""

    def test_delete_tenant(
        self,
        repository: TenantRepository,
        db_session: Session,
        seeded_data: Dict[TableName, list[Any]],
    ):
        """Test deleting a tenant."""
        # Arrange
        tenant_to_delete = seeded_data[TableName.TENANT][0]
        tenant_id = tenant_to_delete.id

        # Verify it exists first
        fetched_before = repository.get_by_id(tenant_id=tenant_id)
        assert fetched_before is not None

        # Act
        repository.delete(tenant_to_delete)
        db_session.commit()

        # Assert - verify it no longer exists
        fetched_after = repository.get_by_id(tenant_id=tenant_id)
        assert fetched_after is None
