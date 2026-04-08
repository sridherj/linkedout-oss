# SPDX-License-Identifier: Apache-2.0
"""Integration tests for AgentRun API endpoints.

Tests invoke, list, and get-by-id operations against
a real PostgreSQL database.
"""

import pytest

from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


class TestAgentRunControllerIntegration:
    """Integration tests for AgentRun API endpoints."""

    # =========================================================================
    # INVOKE (POST) TESTS
    # =========================================================================

    def test_invoke_agent_returns_202(
        self, test_client: TestClient, test_tenant_id: str, test_bu_id: str,
    ):
        response = test_client.post(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/agent-runs/invoke',
            json={'agent_type': 'task_triage', 'input_params': {'task_id': 'task-001'}},
        )
        assert response.status_code == 202
        data = response.json()
        assert 'agent_run_id' in data
        assert data['agent_run_id'].startswith('arn_')
        assert data['status'] == 'PENDING'

    def test_invoke_agent_missing_type_returns_422(
        self, test_client: TestClient, test_tenant_id: str, test_bu_id: str,
    ):
        response = test_client.post(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/agent-runs',
            json={},
        )
        assert response.status_code == 422

    # =========================================================================
    # LIST TESTS
    # =========================================================================

    def test_list_agent_runs_returns_seeded_data(
        self, test_client: TestClient, test_tenant_id: str, test_bu_id: str, seeded_data: dict,
    ):
        response = test_client.get(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/agent-runs'
        )
        assert response.status_code == 200
        data = response.json()
        assert 'agent_runs' in data
        assert data['total'] >= 1

    def test_list_agent_runs_pagination(
        self, test_client: TestClient, test_tenant_id: str, test_bu_id: str,
    ):
        response = test_client.get(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/agent-runs',
            params={'limit': 1, 'offset': 0},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data['agent_runs']) <= 1

    # =========================================================================
    # GET BY ID TESTS
    # =========================================================================

    def test_get_agent_run_by_id_success(
        self, test_client: TestClient, test_tenant_id: str, test_bu_id: str,
    ):
        # Create one first
        create_resp = test_client.post(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/agent-runs/invoke',
            json={'agent_type': 'task_triage'},
        )
        agent_run_id = create_resp.json()['agent_run_id']

        response = test_client.get(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/agent-runs/{agent_run_id}'
        )
        assert response.status_code == 200
        data = response.json()
        assert 'agent_run' in data
        assert data['agent_run']['id'] == agent_run_id

    def test_get_agent_run_by_id_not_found(
        self, test_client: TestClient, test_tenant_id: str, test_bu_id: str,
    ):
        response = test_client.get(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/agent-runs/arn_nonexistent'
        )
        assert response.status_code == 404
