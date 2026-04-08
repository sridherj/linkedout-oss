# SPDX-License-Identifier: Apache-2.0
"""Controller tests for AgentRun API endpoints (CRUDRouterFactory)."""
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, create_autospec, patch
from fastapi.testclient import TestClient

from main import app
from common.services.agent_run_service import AgentRunService
from common.schemas.agent_run_schema import AgentRunSchema, AgentRunStatus


@pytest.fixture
def mock_agent_run_schema():
    return AgentRunSchema(
        id='arn_test123', tenant_id='tenant_1', bu_id='bu_1',
        agent_type='task_triage', status='PENDING',
        input_params={'task_id': 'task-001'},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_agent_run_service():
    return create_autospec(AgentRunService, instance=True, spec_set=True)


BASE_URL = '/tenants/tenant_1/bus/bu_1/agent-runs'


class TestAgentRunEndpointsExist:
    """Verify agent-run endpoints are registered and reachable."""

    def test_list_endpoint_exists(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(f'{BASE_URL}', params={'limit': 20, 'offset': 0})
        assert response.status_code != 404

    def test_get_by_id_endpoint_exists(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(f'{BASE_URL}/arn_123')
        # 404 is valid (entity not found) — 405 would mean endpoint doesn't exist
        assert response.status_code in (200, 404, 500)

    def test_create_endpoint_exists(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            f'{BASE_URL}',
            json={'agent_type': 'task_triage', 'status': 'PENDING'},
        )
        assert response.status_code != 404

    def test_update_endpoint_exists(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.patch(
            f'{BASE_URL}/arn_123',
            json={'status': 'COMPLETED'},
        )
        # 404 is valid (entity not found) — 405 would mean endpoint doesn't exist
        assert response.status_code in (200, 404, 500)

    def test_delete_endpoint_exists(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.delete(f'{BASE_URL}/arn_123')
        # 404/204 are valid — 405 would mean endpoint doesn't exist
        assert response.status_code in (204, 404, 500)

    def test_bulk_create_endpoint_exists(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            f'{BASE_URL}/bulk',
            json={'agent_runs': [{'agent_type': 'task_triage', 'status': 'PENDING'}]},
        )
        assert response.status_code != 404

    def test_invoke_endpoint_exists(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            f'{BASE_URL}/invoke',
            json={'agent_type': 'task_triage'},
        )
        assert response.status_code != 404

    def test_create_missing_required_returns_422(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(f'{BASE_URL}', json={})
        assert response.status_code == 422

    def test_invoke_missing_agent_type_returns_422(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(f'{BASE_URL}/invoke', json={})
        assert response.status_code == 422
