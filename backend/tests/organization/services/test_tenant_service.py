# SPDX-License-Identifier: Apache-2.0
"""Service layer tests for Tenant.

These are unit tests that mock the repository layer to test business logic in isolation.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, create_autospec
from sqlalchemy.orm import Session

from organization.entities.tenant_entity import TenantEntity
from organization.repositories.tenant_repository import TenantRepository
from organization.services.tenant_service import TenantService
from organization.schemas.tenant_schema import TenantSchema
from organization.schemas.tenants_api_schema import (
    ListTenantsRequestSchema,
    CreateTenantRequestSchema,
    CreateTenantsRequestSchema,
    UpdateTenantRequestSchema,
    GetTenantByIdRequestSchema,
    DeleteTenantByIdRequestSchema,
    TenantSortByFields,
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
def mock_tenant_repository() -> Mock:
    """Create a mock TenantRepository."""
    return create_autospec(TenantRepository, instance=True, spec_set=True)


@pytest.fixture
def tenant_service(
    mock_session: Mock,
    mock_tenant_repository: Mock,
) -> TenantService:
    """Create a TenantService with mocked dependencies."""
    service = TenantService(mock_session)
    service._tenant_repository = mock_tenant_repository
    return service


@pytest.fixture
def mock_tenant_entity() -> TenantEntity:
    """Create a mock TenantEntity for testing."""
    entity = TenantEntity(
        name='Test Tenant',
        description='A test tenant',
    )
    entity.id = 'tenant_test123'
    entity.created_at = datetime.now(timezone.utc)
    entity.updated_at = datetime.now(timezone.utc)
    return entity


# =============================================================================
# LIST TENANTS TESTS
# =============================================================================


class TestTenantServiceListTenants:
    """Tests for list_tenants method."""

    def test_list_tenants_returns_schemas_and_count(
        self,
        tenant_service: TenantService,
        mock_tenant_repository: Mock,
        mock_tenant_entity: TenantEntity,
    ):
        """Test that list_tenants returns schemas and total count."""
        # Arrange
        mock_tenant_repository.list_with_filters.return_value = [mock_tenant_entity]
        mock_tenant_repository.count_with_filters.return_value = 1

        list_request = ListTenantsRequestSchema(
            limit=20,
            offset=0,
            sort_by=TenantSortByFields.NAME,
            sort_order=SortOrder.ASC,
        )

        expected_count = 1

        # Act
        actual_schemas, actual_count = tenant_service.list_tenants(list_request)

        # Assert
        assert actual_count == expected_count
        assert len(actual_schemas) == 1
        assert isinstance(actual_schemas[0], TenantSchema)
        assert actual_schemas[0].id == 'tenant_test123'
        assert actual_schemas[0].name == 'Test Tenant'

        # Verify repository calls
        mock_tenant_repository.list_with_filters.assert_called_once()
        mock_tenant_repository.count_with_filters.assert_called_once()

    def test_list_tenants_passes_filters_to_repository(
        self,
        tenant_service: TenantService,
        mock_tenant_repository: Mock,
    ):
        """Test that list_tenants passes filter parameters to repository."""
        # Arrange
        mock_tenant_repository.list_with_filters.return_value = []
        mock_tenant_repository.count_with_filters.return_value = 0

        list_request = ListTenantsRequestSchema(
            limit=10,
            offset=5,
            sort_by=TenantSortByFields.CREATED_AT,
            sort_order=SortOrder.DESC,
            search='Test',
        )

        # Act
        tenant_service.list_tenants(list_request)

        # Assert
        call_kwargs = mock_tenant_repository.list_with_filters.call_args[1]
        assert call_kwargs['limit'] == 10
        assert call_kwargs['offset'] == 5
        assert call_kwargs['sort_by'] == TenantSortByFields.CREATED_AT
        assert call_kwargs['sort_order'] == SortOrder.DESC
        assert call_kwargs['search'] == 'Test'

    def test_list_tenants_empty_result(
        self,
        tenant_service: TenantService,
        mock_tenant_repository: Mock,
    ):
        """Test that list_tenants handles empty results."""
        # Arrange
        mock_tenant_repository.list_with_filters.return_value = []
        mock_tenant_repository.count_with_filters.return_value = 0

        list_request = ListTenantsRequestSchema()

        # Act
        actual_schemas, actual_count = tenant_service.list_tenants(list_request)

        # Assert
        assert actual_count == 0
        assert len(actual_schemas) == 0


# =============================================================================
# CREATE TENANT TESTS
# =============================================================================


class TestTenantServiceCreateTenant:
    """Tests for create_tenant method."""

    def test_create_tenant_returns_schema(
        self,
        tenant_service: TenantService,
        mock_tenant_repository: Mock,
        mock_tenant_entity: TenantEntity,
    ):
        """Test that create_tenant returns a schema."""
        # Arrange
        mock_tenant_repository.create.return_value = mock_tenant_entity

        create_request = CreateTenantRequestSchema(
            name='Test Tenant',
            description='A test tenant',
        )

        # Act
        actual_result = tenant_service.create_tenant(create_request)

        # Assert
        assert isinstance(actual_result, TenantSchema)
        assert actual_result.id == 'tenant_test123'
        assert actual_result.name == 'Test Tenant'

        # Verify repository was called
        mock_tenant_repository.create.assert_called_once()

    def test_create_tenant_passes_fields_to_repository(
        self,
        tenant_service: TenantService,
        mock_tenant_repository: Mock,
        mock_tenant_entity: TenantEntity,
    ):
        """Test that create_tenant passes correct fields to repository."""
        # Arrange
        mock_tenant_repository.create.return_value = mock_tenant_entity

        create_request = CreateTenantRequestSchema(
            name='New Tenant',
            description='New description',
        )

        # Act
        tenant_service.create_tenant(create_request)

        # Assert
        call_args = mock_tenant_repository.create.call_args[0][0]
        assert call_args.name == 'New Tenant'
        assert call_args.description == 'New description'

    # Note: Pydantic validates required fields (name), so assertion tests are not needed.
    # Service assertions are a secondary safety net after Pydantic validation.


# =============================================================================
# CREATE TENANTS (BULK) TESTS
# =============================================================================


class TestTenantServiceCreateTenants:
    """Tests for create_tenants method."""

    def test_create_tenants_returns_schemas(
        self,
        tenant_service: TenantService,
        mock_tenant_repository: Mock,
        mock_tenant_entity: TenantEntity,
    ):
        """Test that create_tenants returns schemas."""
        # Arrange
        mock_tenant_repository.create.return_value = mock_tenant_entity

        create_request = CreateTenantsRequestSchema(
            tenants=[
                CreateTenantRequestSchema(name='Tenant 1'),
                CreateTenantRequestSchema(name='Tenant 2'),
            ]
        )

        # Act
        actual_results = tenant_service.create_tenants(create_request)

        # Assert
        assert len(actual_results) == 2
        for result in actual_results:
            assert isinstance(result, TenantSchema)

        # Verify repository was called for each tenant
        assert mock_tenant_repository.create.call_count == 2


# =============================================================================
# UPDATE TENANT TESTS
# =============================================================================


class TestTenantServiceUpdateTenant:
    """Tests for update_tenant method."""

    def test_update_tenant_returns_schema(
        self,
        tenant_service: TenantService,
        mock_tenant_repository: Mock,
        mock_tenant_entity: TenantEntity,
    ):
        """Test that update_tenant returns a schema."""
        # Arrange
        mock_tenant_repository.get_by_id.return_value = mock_tenant_entity
        mock_tenant_repository.update.return_value = mock_tenant_entity

        update_request = UpdateTenantRequestSchema(
            tenant_id='tenant_test123',
            name='Updated Tenant',
        )

        # Act
        actual_result = tenant_service.update_tenant(update_request)

        # Assert
        assert isinstance(actual_result, TenantSchema)
        mock_tenant_repository.get_by_id.assert_called_once()
        mock_tenant_repository.update.assert_called_once()

    def test_update_tenant_not_found_raises_value_error(
        self,
        tenant_service: TenantService,
        mock_tenant_repository: Mock,
    ):
        """Test that update_tenant raises ValueError when tenant not found."""
        # Arrange
        mock_tenant_repository.get_by_id.return_value = None

        update_request = UpdateTenantRequestSchema(
            tenant_id='nonexistent_tenant',
            name='Updated Tenant',
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            tenant_service.update_tenant(update_request)

        assert 'not found' in str(exc_info.value).lower()
        mock_tenant_repository.update.assert_not_called()

    def test_update_tenant_partial_update(
        self,
        tenant_service: TenantService,
        mock_tenant_repository: Mock,
        mock_tenant_entity: TenantEntity,
    ):
        """Test that update_tenant only updates provided fields."""
        # Arrange
        mock_tenant_repository.get_by_id.return_value = mock_tenant_entity
        mock_tenant_repository.update.return_value = mock_tenant_entity

        update_request = UpdateTenantRequestSchema(
            tenant_id='tenant_test123',
            name='Updated Name Only',
            # description not provided
        )

        # Act
        tenant_service.update_tenant(update_request)

        # Assert
        updated_entity = mock_tenant_repository.update.call_args[0][0]
        assert updated_entity.name == 'Updated Name Only'

    @pytest.mark.parametrize(
        'missing_field_request',
        [
            UpdateTenantRequestSchema(name='Test'),  # Missing tenant_id
        ],
    )
    def test_update_tenant_assertion_errors(
        self, tenant_service: TenantService, missing_field_request: UpdateTenantRequestSchema
    ):
        """Test that update_tenant raises AssertionError for missing required fields."""
        # Act & Assert
        with pytest.raises(AssertionError):
            tenant_service.update_tenant(missing_field_request)


# =============================================================================
# GET TENANT BY ID TESTS
# =============================================================================


class TestTenantServiceGetTenantById:
    """Tests for get_tenant_by_id method."""

    def test_get_tenant_by_id_returns_schema_when_found(
        self,
        tenant_service: TenantService,
        mock_tenant_repository: Mock,
        mock_tenant_entity: TenantEntity,
    ):
        """Test that get_tenant_by_id returns a schema when tenant exists."""
        # Arrange
        mock_tenant_repository.get_by_id.return_value = mock_tenant_entity

        get_request = GetTenantByIdRequestSchema(tenant_id='tenant_test123')

        # Act
        actual_result = tenant_service.get_tenant_by_id(get_request)

        # Assert
        assert actual_result is not None
        assert isinstance(actual_result, TenantSchema)
        assert actual_result.id == 'tenant_test123'

    def test_get_tenant_by_id_returns_none_when_not_found(
        self,
        tenant_service: TenantService,
        mock_tenant_repository: Mock,
    ):
        """Test that get_tenant_by_id returns None when tenant doesn't exist."""
        # Arrange
        mock_tenant_repository.get_by_id.return_value = None

        get_request = GetTenantByIdRequestSchema(tenant_id='nonexistent_tenant')

        # Act
        actual_result = tenant_service.get_tenant_by_id(get_request)

        # Assert
        assert actual_result is None

    @pytest.mark.parametrize(
        'missing_field_request',
        [
            GetTenantByIdRequestSchema(),  # Missing tenant_id
        ],
    )
    def test_get_tenant_by_id_assertion_errors(
        self, tenant_service: TenantService, missing_field_request: GetTenantByIdRequestSchema
    ):
        """Test that get_tenant_by_id raises AssertionError for missing required fields."""
        # Act & Assert
        with pytest.raises(AssertionError):
            tenant_service.get_tenant_by_id(missing_field_request)


# =============================================================================
# DELETE TENANT BY ID TESTS
# =============================================================================


class TestTenantServiceDeleteTenantById:
    """Tests for delete_tenant_by_id method."""

    def test_delete_tenant_by_id_calls_repository(
        self,
        tenant_service: TenantService,
        mock_tenant_repository: Mock,
        mock_tenant_entity: TenantEntity,
    ):
        """Test that delete_tenant_by_id calls repository delete."""
        # Arrange
        mock_tenant_repository.get_by_id.return_value = mock_tenant_entity

        delete_request = DeleteTenantByIdRequestSchema(tenant_id='tenant_test123')

        # Act
        tenant_service.delete_tenant_by_id(delete_request)

        # Assert
        mock_tenant_repository.get_by_id.assert_called_once()
        mock_tenant_repository.delete.assert_called_once_with(mock_tenant_entity)

    def test_delete_tenant_by_id_not_found_raises_value_error(
        self,
        tenant_service: TenantService,
        mock_tenant_repository: Mock,
    ):
        """Test that delete_tenant_by_id raises ValueError when tenant not found."""
        # Arrange
        mock_tenant_repository.get_by_id.return_value = None

        delete_request = DeleteTenantByIdRequestSchema(tenant_id='nonexistent_tenant')

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            tenant_service.delete_tenant_by_id(delete_request)

        assert 'not found' in str(exc_info.value).lower()
        mock_tenant_repository.delete.assert_not_called()

    @pytest.mark.parametrize(
        'missing_field_request',
        [
            DeleteTenantByIdRequestSchema(),  # Missing tenant_id
        ],
    )
    def test_delete_tenant_by_id_assertion_errors(
        self, tenant_service: TenantService, missing_field_request: DeleteTenantByIdRequestSchema
    ):
        """Test that delete_tenant_by_id raises AssertionError for missing required fields."""
        # Act & Assert
        with pytest.raises(AssertionError):
            tenant_service.delete_tenant_by_id(missing_field_request)
