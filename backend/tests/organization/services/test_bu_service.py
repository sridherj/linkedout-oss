# SPDX-License-Identifier: Apache-2.0
"""Service layer tests for BU.

These are unit tests that mock the repository layer to test business logic in isolation.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, create_autospec
from sqlalchemy.orm import Session

from organization.entities.bu_entity import BuEntity
from organization.repositories.bu_repository import BuRepository
from organization.services.bu_service import BuService
from organization.schemas.bu_schema import BuSchema
from organization.schemas.bus_api_schema import (
    ListBusRequestSchema,
    CreateBuRequestSchema,
    CreateBusRequestSchema,
    UpdateBuRequestSchema,
    GetBuByIdRequestSchema,
    DeleteBuByIdRequestSchema,
    BuSortByFields,
)
from common.schemas.base_enums_schemas import SortOrder


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_session() -> Mock:
    """Create a mock database session."""
    return create_autospec(Session, instance=True, spec_set=True)


@pytest.fixture
def mock_bu_repository() -> Mock:
    """Create a mock BuRepository."""
    return create_autospec(BuRepository, instance=True, spec_set=True)


@pytest.fixture
def bu_service(
    mock_session: Mock,
    mock_bu_repository: Mock,
) -> BuService:
    """Create a BuService with mocked dependencies."""
    service = BuService(mock_session)
    service._bu_repository = mock_bu_repository
    return service


@pytest.fixture
def mock_bu_entity() -> BuEntity:
    """Create a mock BuEntity for testing."""
    entity = BuEntity(
        tenant_id='tenant_test123',
        name='Test BU',
        description='A test business unit',
    )
    entity.id = 'bu_test123'
    entity.created_at = datetime.now(timezone.utc)
    entity.updated_at = datetime.now(timezone.utc)
    return entity


# =============================================================================
# LIST BUS TESTS
# =============================================================================


class TestBuServiceListBus:
    """Tests for list_bus method."""

    def test_list_bus_returns_schemas_and_count(
        self,
        bu_service: BuService,
        mock_bu_repository: Mock,
        mock_bu_entity: BuEntity,
    ):
        """Test that list_bus returns schemas and total count."""
        # Arrange
        mock_bu_repository.list_with_filters.return_value = [mock_bu_entity]
        mock_bu_repository.count_with_filters.return_value = 1

        list_request = ListBusRequestSchema(
            tenant_id='tenant_test123',
            limit=20,
            offset=0,
            sort_by=BuSortByFields.NAME,
            sort_order=SortOrder.ASC,
        )

        expected_count = 1

        # Act
        actual_schemas, actual_count = bu_service.list_bus(list_request)

        # Assert
        assert actual_count == expected_count
        assert len(actual_schemas) == 1
        assert isinstance(actual_schemas[0], BuSchema)
        assert actual_schemas[0].id == 'bu_test123'
        assert actual_schemas[0].name == 'Test BU'

        # Verify repository calls
        mock_bu_repository.list_with_filters.assert_called_once()
        mock_bu_repository.count_with_filters.assert_called_once()

    def test_list_bus_passes_filters_to_repository(
        self,
        bu_service: BuService,
        mock_bu_repository: Mock,
    ):
        """Test that list_bus passes filter parameters to repository."""
        # Arrange
        mock_bu_repository.list_with_filters.return_value = []
        mock_bu_repository.count_with_filters.return_value = 0

        list_request = ListBusRequestSchema(
            tenant_id='tenant_test123',
            limit=10,
            offset=5,
            sort_by=BuSortByFields.CREATED_AT,
            sort_order=SortOrder.DESC,
            search='Test',
        )

        # Act
        bu_service.list_bus(list_request)

        # Assert
        call_kwargs = mock_bu_repository.list_with_filters.call_args[1]
        assert call_kwargs['tenant_id'] == 'tenant_test123'
        assert call_kwargs['limit'] == 10
        assert call_kwargs['offset'] == 5
        assert call_kwargs['sort_by'] == BuSortByFields.CREATED_AT
        assert call_kwargs['sort_order'] == SortOrder.DESC
        assert call_kwargs['search'] == 'Test'

    @pytest.mark.parametrize(
        'missing_field_request',
        [
            ListBusRequestSchema(),  # Missing tenant_id
        ],
    )
    def test_list_bus_assertion_errors(
        self, bu_service: BuService, missing_field_request: ListBusRequestSchema
    ):
        """Test that list_bus raises AssertionError for missing required fields."""
        # Act & Assert
        with pytest.raises(AssertionError):
            bu_service.list_bus(missing_field_request)


# =============================================================================
# CREATE BU TESTS
# =============================================================================


class TestBuServiceCreateBu:
    """Tests for create_bu method."""

    def test_create_bu_returns_schema(
        self,
        bu_service: BuService,
        mock_bu_repository: Mock,
        mock_bu_entity: BuEntity,
    ):
        """Test that create_bu returns a schema."""
        # Arrange
        mock_bu_repository.create.return_value = mock_bu_entity

        create_request = CreateBuRequestSchema(
            tenant_id='tenant_test123',
            name='Test BU',
            description='A test business unit',
        )

        # Act
        actual_result = bu_service.create_bu(create_request)

        # Assert
        assert isinstance(actual_result, BuSchema)
        assert actual_result.id == 'bu_test123'
        assert actual_result.name == 'Test BU'

        # Verify repository was called
        mock_bu_repository.create.assert_called_once()

    def test_create_bu_missing_tenant_id_raises_assertion_error(
        self, bu_service: BuService
    ):
        """Test that create_bu raises AssertionError when tenant_id is missing."""
        # Arrange - tenant_id is Optional with default None
        create_request = CreateBuRequestSchema(name='Test BU')

        # Act & Assert
        with pytest.raises(AssertionError):
            bu_service.create_bu(create_request)


# =============================================================================
# CREATE BUS (BULK) TESTS
# =============================================================================


class TestBuServiceCreateBus:
    """Tests for create_bus method."""

    def test_create_bus_returns_schemas(
        self,
        bu_service: BuService,
        mock_bu_repository: Mock,
        mock_bu_entity: BuEntity,
    ):
        """Test that create_bus returns schemas."""
        # Arrange
        mock_bu_repository.create.return_value = mock_bu_entity

        create_request = CreateBusRequestSchema(
            tenant_id='tenant_test123',
            bus=[
                CreateBuRequestSchema(name='BU 1'),
                CreateBuRequestSchema(name='BU 2'),
            ]
        )

        # Act
        actual_results = bu_service.create_bus(create_request)

        # Assert
        assert len(actual_results) == 2
        for result in actual_results:
            assert isinstance(result, BuSchema)

        # Verify repository was called for each BU
        assert mock_bu_repository.create.call_count == 2


# =============================================================================
# UPDATE BU TESTS
# =============================================================================


class TestBuServiceUpdateBu:
    """Tests for update_bu method."""

    def test_update_bu_returns_schema(
        self,
        bu_service: BuService,
        mock_bu_repository: Mock,
        mock_bu_entity: BuEntity,
    ):
        """Test that update_bu returns a schema."""
        # Arrange
        mock_bu_repository.get_by_id.return_value = mock_bu_entity
        mock_bu_repository.update.return_value = mock_bu_entity

        update_request = UpdateBuRequestSchema(
            tenant_id='tenant_test123',
            bu_id='bu_test123',
            name='Updated BU',
        )

        # Act
        actual_result = bu_service.update_bu(update_request)

        # Assert
        assert isinstance(actual_result, BuSchema)
        mock_bu_repository.get_by_id.assert_called_once()
        mock_bu_repository.update.assert_called_once()

    def test_update_bu_not_found_raises_value_error(
        self,
        bu_service: BuService,
        mock_bu_repository: Mock,
    ):
        """Test that update_bu raises ValueError when BU not found."""
        # Arrange
        mock_bu_repository.get_by_id.return_value = None

        update_request = UpdateBuRequestSchema(
            tenant_id='tenant_test123',
            bu_id='nonexistent_bu',
            name='Updated BU',
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            bu_service.update_bu(update_request)

        assert 'not found' in str(exc_info.value).lower()
        mock_bu_repository.update.assert_not_called()

    @pytest.mark.parametrize(
        'missing_field_request',
        [
            UpdateBuRequestSchema(bu_id='bu_test123', name='Test'),  # Missing tenant_id
            UpdateBuRequestSchema(tenant_id='tenant_test123', name='Test'),  # Missing bu_id
        ],
    )
    def test_update_bu_assertion_errors(
        self, bu_service: BuService, missing_field_request: UpdateBuRequestSchema
    ):
        """Test that update_bu raises AssertionError for missing required fields."""
        # Act & Assert
        with pytest.raises(AssertionError):
            bu_service.update_bu(missing_field_request)


# =============================================================================
# GET BU BY ID TESTS
# =============================================================================


class TestBuServiceGetBuById:
    """Tests for get_bu_by_id method."""

    def test_get_bu_by_id_returns_schema_when_found(
        self,
        bu_service: BuService,
        mock_bu_repository: Mock,
        mock_bu_entity: BuEntity,
    ):
        """Test that get_bu_by_id returns a schema when BU exists."""
        # Arrange
        mock_bu_repository.get_by_id.return_value = mock_bu_entity

        get_request = GetBuByIdRequestSchema(
            tenant_id='tenant_test123',
            bu_id='bu_test123',
        )

        # Act
        actual_result = bu_service.get_bu_by_id(get_request)

        # Assert
        assert actual_result is not None
        assert isinstance(actual_result, BuSchema)
        assert actual_result.id == 'bu_test123'

    def test_get_bu_by_id_returns_none_when_not_found(
        self,
        bu_service: BuService,
        mock_bu_repository: Mock,
    ):
        """Test that get_bu_by_id returns None when BU doesn't exist."""
        # Arrange
        mock_bu_repository.get_by_id.return_value = None

        get_request = GetBuByIdRequestSchema(
            tenant_id='tenant_test123',
            bu_id='nonexistent_bu',
        )

        # Act
        actual_result = bu_service.get_bu_by_id(get_request)

        # Assert
        assert actual_result is None

    @pytest.mark.parametrize(
        'missing_field_request',
        [
            GetBuByIdRequestSchema(bu_id='bu_test123'),  # Missing tenant_id
            GetBuByIdRequestSchema(tenant_id='tenant_test123'),  # Missing bu_id
        ],
    )
    def test_get_bu_by_id_assertion_errors(
        self, bu_service: BuService, missing_field_request: GetBuByIdRequestSchema
    ):
        """Test that get_bu_by_id raises AssertionError for missing required fields."""
        # Act & Assert
        with pytest.raises(AssertionError):
            bu_service.get_bu_by_id(missing_field_request)


# =============================================================================
# DELETE BU BY ID TESTS
# =============================================================================


class TestBuServiceDeleteBuById:
    """Tests for delete_bu_by_id method."""

    def test_delete_bu_by_id_calls_repository(
        self,
        bu_service: BuService,
        mock_bu_repository: Mock,
        mock_bu_entity: BuEntity,
    ):
        """Test that delete_bu_by_id calls repository delete."""
        # Arrange
        mock_bu_repository.get_by_id.return_value = mock_bu_entity

        delete_request = DeleteBuByIdRequestSchema(
            tenant_id='tenant_test123',
            bu_id='bu_test123',
        )

        # Act
        bu_service.delete_bu_by_id(delete_request)

        # Assert
        mock_bu_repository.get_by_id.assert_called_once()
        mock_bu_repository.delete.assert_called_once_with(mock_bu_entity)

    def test_delete_bu_by_id_not_found_raises_value_error(
        self,
        bu_service: BuService,
        mock_bu_repository: Mock,
    ):
        """Test that delete_bu_by_id raises ValueError when BU not found."""
        # Arrange
        mock_bu_repository.get_by_id.return_value = None

        delete_request = DeleteBuByIdRequestSchema(
            tenant_id='tenant_test123',
            bu_id='nonexistent_bu',
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            bu_service.delete_bu_by_id(delete_request)

        assert 'not found' in str(exc_info.value).lower()
        mock_bu_repository.delete.assert_not_called()

    @pytest.mark.parametrize(
        'missing_field_request',
        [
            DeleteBuByIdRequestSchema(bu_id='bu_test123'),  # Missing tenant_id
            DeleteBuByIdRequestSchema(tenant_id='tenant_test123'),  # Missing bu_id
        ],
    )
    def test_delete_bu_by_id_assertion_errors(
        self, bu_service: BuService, missing_field_request: DeleteBuByIdRequestSchema
    ):
        """Test that delete_bu_by_id raises AssertionError for missing required fields."""
        # Act & Assert
        with pytest.raises(AssertionError):
            bu_service.delete_bu_by_id(missing_field_request)
