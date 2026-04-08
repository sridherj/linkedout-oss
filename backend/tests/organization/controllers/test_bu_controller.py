# SPDX-License-Identifier: Apache-2.0
"""Controller layer tests for BU API endpoints.

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
from organization.services.bu_service import BuService
from organization.schemas.bu_schema import BuSchema
from organization.controllers.bu_controller import (
    _get_bu_service,
    _get_write_bu_service,
)


# =============================================================================
# SHARED FIXTURES
# =============================================================================


@pytest.fixture
def mock_bu_schema() -> BuSchema:
    """Create a mock BuSchema."""
    return BuSchema(
        id='bu_test123',
        tenant_id='tenant_test123',
        name='Test BU',
        description='A test business unit',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_bu_service() -> Mock:
    """Create a mock BuService."""
    return create_autospec(BuService, instance=True, spec_set=True)


@pytest.fixture
def override_dependencies(mock_bu_service: Mock) -> Generator[None, None, None]:
    """
    Override FastAPI dependencies for testing.

    Args:
        mock_bu_service: Mock service to use

    Returns:
        Generator that sets up and tears down dependency overrides
    """

    def _get_mock_service():
        yield mock_bu_service

    # Override both read and write service dependencies
    app.dependency_overrides[_get_bu_service] = _get_mock_service
    app.dependency_overrides[_get_write_bu_service] = _get_mock_service

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
# LIST BUS ENDPOINT
# =============================================================================


class TestListBusEndpoint:
    """Tests for BU listing API endpoint."""

    def test_list_bus_success_default_pagination(
        self,
        test_client: TestClient,
        mock_bu_service: Mock,
        mock_bu_schema: BuSchema,
    ):
        """Test listing BUs with default pagination."""
        # Arrange
        mock_bu_service.list_bus.return_value = ([mock_bu_schema], 1)
        expected_status_code = 200
        expected_total = 1

        # Act
        actual_response = test_client.get(
            '/tenants/tenant_test123/bus',
            params={'limit': 20, 'offset': 0},
        )

        # Assert
        assert actual_response.status_code == expected_status_code
        actual_data = actual_response.json()
        assert actual_data['total'] == expected_total
        assert len(actual_data['bus']) == 1
        assert actual_data['bus'][0]['id'] == 'bu_test123'
        assert actual_data['bus'][0]['name'] == 'Test BU'
        assert 'links' in actual_data

    def test_list_bus_with_filters(
        self,
        test_client: TestClient,
        mock_bu_service: Mock,
        mock_bu_schema: BuSchema,
    ):
        """Test listing BUs with filters."""
        # Arrange
        mock_bu_service.list_bus.return_value = ([mock_bu_schema], 1)
        expected_status_code = 200

        # Act
        actual_response = test_client.get(
            '/tenants/tenant_test123/bus',
            params={
                'limit': 20,
                'offset': 0,
                'search': 'Test',
            },
        )

        # Assert
        assert actual_response.status_code == expected_status_code

        # Verify service was called with filters
        mock_bu_service.list_bus.assert_called_once()

    def test_list_bus_empty(
        self,
        test_client: TestClient,
        mock_bu_service: Mock,
    ):
        """Test listing BUs when none exist."""
        # Arrange
        mock_bu_service.list_bus.return_value = ([], 0)
        expected_status_code = 200
        expected_total = 0

        # Act
        actual_response = test_client.get(
            '/tenants/tenant_test123/bus',
            params={'limit': 20, 'offset': 0},
        )

        # Assert
        assert actual_response.status_code == expected_status_code
        actual_data = actual_response.json()
        assert actual_data['total'] == expected_total
        assert len(actual_data['bus']) == 0


# =============================================================================
# GET BU BY ID ENDPOINT
# =============================================================================


class TestGetBuByIdEndpoint:
    """Tests for get BU by ID API endpoint."""

    def test_get_bu_by_id_success(
        self,
        test_client: TestClient,
        mock_bu_service: Mock,
        mock_bu_schema: BuSchema,
    ):
        """Test getting a BU by ID when it exists."""
        # Arrange
        mock_bu_service.get_bu_by_id.return_value = mock_bu_schema
        expected_status_code = 200

        # Act
        actual_response = test_client.get('/tenants/tenant_test123/bus/bu_test123')

        # Assert
        assert actual_response.status_code == expected_status_code
        actual_data = actual_response.json()
        assert actual_data['bu']['id'] == 'bu_test123'
        assert actual_data['bu']['name'] == 'Test BU'

    def test_get_bu_by_id_not_found(
        self,
        test_client: TestClient,
        mock_bu_service: Mock,
    ):
        """Test getting a BU by ID when it doesn't exist."""
        # Arrange
        mock_bu_service.get_bu_by_id.return_value = None
        expected_status_code = 404

        # Act
        actual_response = test_client.get('/tenants/tenant_test123/bus/nonexistent_bu')

        # Assert
        assert actual_response.status_code == expected_status_code


# =============================================================================
# CREATE BU ENDPOINT
# =============================================================================


class TestCreateBuEndpoint:
    """Tests for create BU API endpoint."""

    def test_create_bu_success(
        self,
        test_client: TestClient,
        mock_bu_service: Mock,
        mock_bu_schema: BuSchema,
    ):
        """Test creating a BU successfully."""
        # Arrange
        mock_bu_service.create_bu.return_value = mock_bu_schema
        expected_status_code = 201

        # Act
        actual_response = test_client.post(
            '/tenants/tenant_test123/bus',
            json={
                'name': 'New BU',
                'description': 'A new test business unit',
            },
        )

        # Assert
        assert actual_response.status_code == expected_status_code
        actual_data = actual_response.json()
        assert actual_data['bu']['id'] == 'bu_test123'
        mock_bu_service.create_bu.assert_called_once()

    def test_create_bu_validation_error(
        self,
        test_client: TestClient,
        mock_bu_service: Mock,
    ):
        """Test creating a BU with invalid data."""
        # Arrange
        expected_status_code = 422

        # Act - missing required field 'name'
        actual_response = test_client.post(
            '/tenants/tenant_test123/bus',
            json={
                'description': 'Only description, no name',
            },
        )

        # Assert
        assert actual_response.status_code == expected_status_code


# =============================================================================
# CREATE BUS BULK ENDPOINT
# =============================================================================


class TestCreateBusBulkEndpoint:
    """Tests for bulk create BUs API endpoint."""

    def test_create_bus_bulk_success(
        self,
        test_client: TestClient,
        mock_bu_service: Mock,
        mock_bu_schema: BuSchema,
    ):
        """Test creating multiple BUs successfully."""
        # Arrange
        mock_bu_service.create_bus.return_value = [mock_bu_schema, mock_bu_schema]
        expected_status_code = 201

        # Act
        actual_response = test_client.post(
            '/tenants/tenant_test123/bus/bulk',
            json={
                'bus': [
                    {'name': 'BU 1'},
                    {'name': 'BU 2'},
                ],
            },
        )

        # Assert
        assert actual_response.status_code == expected_status_code
        actual_data = actual_response.json()
        assert len(actual_data['bus']) == 2
        mock_bu_service.create_bus.assert_called_once()


# =============================================================================
# UPDATE BU ENDPOINT
# =============================================================================


class TestUpdateBuEndpoint:
    """Tests for update BU API endpoint."""

    def test_update_bu_success(
        self,
        test_client: TestClient,
        mock_bu_service: Mock,
        mock_bu_schema: BuSchema,
    ):
        """Test updating a BU successfully."""
        # Arrange
        mock_bu_service.update_bu.return_value = mock_bu_schema
        expected_status_code = 200

        # Act
        actual_response = test_client.patch(
            '/tenants/tenant_test123/bus/bu_test123',
            json={
                'name': 'Updated BU Name',
            },
        )

        # Assert
        assert actual_response.status_code == expected_status_code
        actual_data = actual_response.json()
        assert actual_data['bu']['id'] == 'bu_test123'
        mock_bu_service.update_bu.assert_called_once()

    def test_update_bu_not_found(
        self,
        test_client: TestClient,
        mock_bu_service: Mock,
    ):
        """Test updating a BU that doesn't exist."""
        # Arrange
        mock_bu_service.update_bu.side_effect = ValueError('BU not found')
        expected_status_code = 404

        # Act
        actual_response = test_client.patch(
            '/tenants/tenant_test123/bus/nonexistent_bu',
            json={
                'name': 'Updated BU Name',
            },
        )

        # Assert
        assert actual_response.status_code == expected_status_code


# =============================================================================
# DELETE BU ENDPOINT
# =============================================================================


class TestDeleteBuEndpoint:
    """Tests for delete BU API endpoint."""

    def test_delete_bu_success(
        self,
        test_client: TestClient,
        mock_bu_service: Mock,
    ):
        """Test deleting a BU successfully."""
        # Arrange
        mock_bu_service.delete_bu_by_id.return_value = None
        expected_status_code = 204

        # Act
        actual_response = test_client.delete('/tenants/tenant_test123/bus/bu_test123')

        # Assert
        assert actual_response.status_code == expected_status_code
        mock_bu_service.delete_bu_by_id.assert_called_once()

    def test_delete_bu_not_found(
        self,
        test_client: TestClient,
        mock_bu_service: Mock,
    ):
        """Test deleting a BU that doesn't exist."""
        # Arrange
        mock_bu_service.delete_bu_by_id.side_effect = ValueError('BU not found')
        expected_status_code = 404

        # Act
        actual_response = test_client.delete('/tenants/tenant_test123/bus/nonexistent_bu')

        # Assert
        assert actual_response.status_code == expected_status_code
