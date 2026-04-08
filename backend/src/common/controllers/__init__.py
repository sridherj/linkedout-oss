# SPDX-License-Identifier: Apache-2.0
"""Common controller classes."""
from common.controllers.base_controller_utils import build_pagination_links, create_service_dependency
from common.controllers.crud_router_factory import CRUDRouterConfig, CRUDRouterResult, create_crud_router

__all__ = [
    'build_pagination_links',
    'create_service_dependency',
    'CRUDRouterConfig',
    'CRUDRouterResult',
    'create_crud_router',
]
