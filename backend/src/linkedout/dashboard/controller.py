# SPDX-License-Identifier: Apache-2.0
"""Dashboard controller — read-only network aggregation endpoint."""
import asyncio

from fastapi import APIRouter, Header

from linkedout.dashboard.repository import DashboardRepository
from linkedout.dashboard.schemas import DashboardResponse
from linkedout.dashboard.service import DashboardService
from shared.infra.db.db_session_manager import DbSessionManager, DbSessionType

dashboard_router = APIRouter(
    prefix="/tenants/{tenant_id}/bus/{bu_id}/dashboard",
    tags=["dashboard"],
)


@dashboard_router.get("", response_model=DashboardResponse)
async def get_dashboard(
    tenant_id: str,
    bu_id: str,
    app_user_id: str = Header(..., alias="X-App-User-Id"),
) -> DashboardResponse:
    """Return network aggregation data for the authenticated user."""

    def _run() -> DashboardResponse:
        db = DbSessionManager()
        with db.get_session(DbSessionType.READ, app_user_id=app_user_id) as session:
            repo = DashboardRepository(session)
            service = DashboardService(repo)
            return service.get_dashboard(tenant_id, bu_id, app_user_id)

    return await asyncio.to_thread(_run)
