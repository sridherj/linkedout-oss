# SPDX-License-Identifier: Apache-2.0
"""Organization domain controllers."""
from organization.controllers.tenant_controller import tenants_router
from organization.controllers.bu_controller import bus_router

__all__ = [
    'tenants_router',
    'bus_router',
]
