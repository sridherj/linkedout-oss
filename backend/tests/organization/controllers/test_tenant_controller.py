# SPDX-License-Identifier: Apache-2.0
"""Controller layer tests for Tenant API endpoints.

Organized by endpoint for better test isolation and navigation.
Each class focuses on a single API operation.
"""

import pytest
from datetime import datetime, timezone
from typing import Generator
from unittest.mock import Mock, create_autospec
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from main import app
from organization.services.tenant_service import TenantService
from organization.schemas.tenant_schema import TenantSchema
from organization.controllers.tenant_controller import (
    _get_tenant_service,
    _get_write_tenant_service,
)


# =============================================================================
# SHARED FIXTURES
# =============================================================================


@pytest.fixture
def mock_tenant_schema() -> TenantSchema:
    """Create a mock TenantSchema."""
    return TenantSchema(
        id='tenant_test123',
        name='Test Tenant',
        description='A test tenant',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_tenant_service() -> Mock:
    """Create a mock TenantService."""
    return create_autospec(TenantService, instance=True, spec_set=True)


@pytest.fixture
def override_dependencies(mock_tenant_service: Mock) -> Generator[None, None, None]:
    """
    Override FastAPI dependencies for testing.

    Args:
        mock_tenant_service: Mock service to use

    Returns:
        Generator that sets up and tears down dependency overrides
    """

    def _get_mock_service():
        yield mock_tenant_service

    # Override both read and write service dependencies
    app.dependency_overrides[_get_tenant_service] = _get_mock_service
    app.dependency_overrides[_get_write_tenant_service] = _get_mock_service

    yield

    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture
def test_client(override_dependencies: None) -> TestClient:
    """
    Create a test client with overridden dependencies.

    Args:
        override_dependencies: Fixture that sets up dependency overrides

    Returns:
        TestClient: FastAPI test client
    """
    return TestClient(app)


# =============================================================================
# LIST TENANTS ENDPOINT
# =============================================================================


class TestListTenantsEndpoint:
    """Tests for tenant listing API endpoint."""

    def test_list_tenants_success_default_pagination(
        self,
        test_client: TestClient,
        mock_tenant_service: Mock,
        mock_tenant_schema: TenantSchema,
    ):
        """Test listing tenants with default pagination."""
        # Arrange
        mock_tenant_service.list_tenants.return_value = ([mock_tenant_schema], 1)
        expected_status_code = 200
        expected_total = 1

        # Act
        actual_response = test_client.get(
            '/tenants',
            params={'limit': 20, 'offset': 0},
        )

        # Assert
        assert actual_response.status_code == expected_status_code
        actual_data = actual_response.json()
        assert actual_data['total'] == expected_total
        assert len(actual_data['tenants']) == 1
        assert actual_data['tenants'][0]['id'] == 'tenant_test123'
        assert actual_data['tenants'][0]['name'] == 'Test Tenant'
        assert 'links' in actual_data

    def test_list_tenants_with_filters(
        self,
        test_client: TestClient,
        mock_tenant_service: Mock,
        mock_tenant_schema: TenantSchema,
    ):
        """Test listing tenants with filters."""
        # Arrange
        mock_tenant_service.list_tenants.return_value = ([mock_tenant_schema], 1)
        expected_status_code = 200

        # Act
        actual_response = test_client.get(
            '/tenants',
            params={
                'limit': 20,
                'offset': 0,
                'search': 'Test',
            },
        )

        # Assert
        assert actual_response.status_code == expected_status_code

        # Verify service was called with filters
        mock_tenant_service.list_tenants.assert_called_once()

    def test_list_tenants_empty(
        self,
        test_client: TestClient,
        mock_tenant_service: Mock,
    ):
        """Test listing tenants when none exist."""
        # Arrange
        mock_tenant_service.list_tenants.return_value = ([], 0)
        expected_status_code = 200
        expected_total = 0

        # Act
        actual_response = test_client.get(
            '/tenants',
            params={'limit': 20, 'offset': 0},
        )

        # Assert
        assert actual_response.status_code == expected_status_code
        actual_data = actual_response.json()
        assert actual_data['total'] == expected_total
        assert len(actual_data['tenants']) == 0

    def test_list_tenants_pagination_links(
        self,
        test_client: TestClient,
        mock_tenant_service: Mock,
        mock_tenant_schema: TenantSchema,
    ):
        """Test that pagination links are included in response."""
        # Arrange
        mock_tenant_service.list_tenants.return_value = ([mock_tenant_schema], 50)
        expected_status_code = 200
        expected_page_count = 3  # 50 / 20 = 3 pages

        # Act
        actual_response = test_client.get(
            '/tenants',
            params={'limit': 20, 'offset': 0},
        )

        # Assert
        assert actual_response.status_code == expected_status_code
        actual_data = actual_response.json()
        assert actual_data['page_count'] == expected_page_count
        assert 'links' in actual_data
        assert actual_data['links']['self'] is not None


# =============================================================================
# GET TENANT BY ID ENDPOINT
# =============================================================================


class TestGetTenantByIdEndpoint:
    """Tests for get tenant by ID API endpoint."""

    def test_get_tenant_by_id_success(
        self,
        test_client: TestClient,
        mock_tenant_service: Mock,
        mock_tenant_schema: TenantSchema,
    ):
        """Test getting a tenant by ID when it exists."""
        # Arrange
        mock_tenant_service.get_tenant_by_id.return_value = mock_tenant_schema
        expected_status_code = 200

        # Act
        actual_response = test_client.get('/tenants/tenant_test123')

        # Assert
        assert actual_response.status_code == expected_status_code
        actual_data = actual_response.json()
        assert actual_data['tenant']['id'] == 'tenant_test123'
        assert actual_data['tenant']['name'] == 'Test Tenant'

    def test_get_tenant_by_id_not_found(
        self,
        test_client: TestClient,
        mock_tenant_service: Mock,
    ):
        """Test getting a tenant by ID when it doesn't exist."""
        # Arrange
        mock_tenant_service.get_tenant_by_id.return_value = None
        expected_status_code = 404

        # Act
        actual_response = test_client.get('/tenants/nonexistent_tenant')

        # Assert
        assert actual_response.status_code == expected_status_code


# =============================================================================
# CREATE TENANT ENDPOINT
# =============================================================================


class TestCreateTenantEndpoint:
    """Tests for create tenant API endpoint."""

    def test_create_tenant_success(
        self,
        test_client: TestClient,
        mock_tenant_service: Mock,
        mock_tenant_schema: TenantSchema,
    ):
        """Test creating a tenant successfully."""
        # Arrange
        mock_tenant_service.create_tenant.return_value = mock_tenant_schema
        expected_status_code = 201

        # Act
        actual_response = test_client.post(
            '/tenants',
            json={
                'name': 'New Tenant',
                'description': 'A new test tenant',
            },
        )

        # Assert
        assert actual_response.status_code == expected_status_code
        actual_data = actual_response.json()
        assert actual_data['tenant']['id'] == 'tenant_test123'
        mock_tenant_service.create_tenant.assert_called_once()

    def test_create_tenant_validation_error(
        self,
        test_client: TestClient,
        mock_tenant_service: Mock,
    ):
        """Test creating a tenant with invalid data."""
        # Arrange
        expected_status_code = 422

        # Act - missing required field 'name'
        actual_response = test_client.post(
            '/tenants',
            json={
                'description': 'Only description, no name',
            },
        )

        # Assert
        assert actual_response.status_code == expected_status_code


# =============================================================================
# CREATE TENANTS BULK ENDPOINT
# =============================================================================


class TestCreateTenantsBulkEndpoint:
    """Tests for bulk create tenants API endpoint."""

    def test_create_tenants_bulk_success(
        self,
        test_client: TestClient,
        mock_tenant_service: Mock,
        mock_tenant_schema: TenantSchema,
    ):
        """Test creating multiple tenants successfully."""
        # Arrange
        mock_tenant_service.create_tenants.return_value = [mock_tenant_schema, mock_tenant_schema]
        expected_status_code = 201

        # Act
        actual_response = test_client.post(
            '/tenants/bulk',
            json={
                'tenants': [
                    {'name': 'Tenant 1'},
                    {'name': 'Tenant 2'},
                ],
            },
        )

        # Assert
        assert actual_response.status_code == expected_status_code
        actual_data = actual_response.json()
        assert len(actual_data['tenants']) == 2
        mock_tenant_service.create_tenants.assert_called_once()


# =============================================================================
# UPDATE TENANT ENDPOINT
# =============================================================================


class TestUpdateTenantEndpoint:
    """Tests for update tenant API endpoint."""

    def test_update_tenant_success(
        self,
        test_client: TestClient,
        mock_tenant_service: Mock,
        mock_tenant_schema: TenantSchema,
    ):
        """Test updating a tenant successfully."""
        # Arrange
        mock_tenant_service.update_tenant.return_value = mock_tenant_schema
        expected_status_code = 200

        # Act
        actual_response = test_client.patch(
            '/tenants/tenant_test123',
            json={
                'name': 'Updated Tenant Name',
            },
        )

        # Assert
        assert actual_response.status_code == expected_status_code
        actual_data = actual_response.json()
        assert actual_data['tenant']['id'] == 'tenant_test123'
        mock_tenant_service.update_tenant.assert_called_once()

    def test_update_tenant_not_found(
        self,
        test_client: TestClient,
        mock_tenant_service: Mock,
    ):
        """Test updating a tenant that doesn't exist."""
        # Arrange
        mock_tenant_service.update_tenant.side_effect = ValueError('Tenant not found')
        expected_status_code = 404

        # Act
        actual_response = test_client.patch(
            '/tenants/nonexistent_tenant',
            json={
                'name': 'Updated Tenant Name',
            },
        )

        # Assert
        assert actual_response.status_code == expected_status_code


# =============================================================================
# DELETE TENANT ENDPOINT
# =============================================================================


class TestDeleteTenantEndpoint:
    """Tests for delete tenant API endpoint."""

    def test_delete_tenant_success(
        self,
        test_client: TestClient,
        mock_tenant_service: Mock,
    ):
        """Test deleting a tenant successfully."""
        # Arrange
        mock_tenant_service.delete_tenant_by_id.return_value = None
        expected_status_code = 204

        # Act
        actual_response = test_client.delete('/tenants/tenant_test123')

        # Assert
        assert actual_response.status_code == expected_status_code
        mock_tenant_service.delete_tenant_by_id.assert_called_once()

    def test_delete_tenant_not_found(
        self,
        test_client: TestClient,
        mock_tenant_service: Mock,
    ):
        """Test deleting a tenant that doesn't exist."""
        # Arrange
        mock_tenant_service.delete_tenant_by_id.side_effect = ValueError('Tenant not found')
        expected_status_code = 404

        # Act
        actual_response = test_client.delete('/tenants/nonexistent_tenant')

        # Assert
        assert actual_response.status_code == expected_status_code
