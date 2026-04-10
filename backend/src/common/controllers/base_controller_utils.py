# SPDX-License-Identifier: Apache-2.0
"""Shared utilities for CRUD controllers.

This module provides common utilities that are used across all CRUD controllers
to reduce code duplication and ensure consistency.

Utilities:
- build_pagination_links: Builds HATEOAS pagination links for list responses
- create_service_dependency: Factory for creating FastAPI service dependencies
"""

import math
from typing import Any, Dict, Generator, Optional, Type, TypeVar

from fastapi import Request

from common.schemas.base_response_schema import PaginationLinks
from shared.infra.db.db_session_manager import DbSessionType

TService = TypeVar('TService')


def build_pagination_links(
    request: Request,
    entity_path: str,
    tenant_id: str,
    bu_id: str,
    total: int,
    limit: int,
    offset: int,
    params: Dict[str, Any],
    prefix: Optional[str] = None,
) -> PaginationLinks:
    """
    Build HATEOAS pagination links for any entity.

    This function generates standard pagination links (self, first, last, prev, next)
    following the HATEOAS principle for REST APIs.

    Args:
        request: The FastAPI request object to extract scheme and host.
        entity_path: The entity path segment (e.g., 'lots', 'bins', 'demands').
        tenant_id: The tenant ID from the path.
        bu_id: The business unit ID from the path.
        total: Total number of items across all pages.
        limit: Maximum number of items per page.
        offset: Current offset (number of items skipped).
        params: Additional query parameters to include in links (filter values).
        prefix: Optional full URL prefix (e.g., '/tenants/{tenant_id}/bus/{bu_id}/lots').
                If provided, tenant_id and bu_id will be substituted in the prefix.
                If not provided, the default pattern is used.

    Returns:
        PaginationLinks: Object containing self, first, last, prev, and next links.

    Example:
        >>> links = build_pagination_links(
        ...     request=request,
        ...     entity_path='lots',
        ...     tenant_id='tenant_1',
        ...     bu_id='bu_1',
        ...     total=100,
        ...     limit=20,
        ...     offset=40,
        ...     params={'status': 'active'}
        ... )
        >>> links.self
        'http://localhost/tenants/tenant_1/bus/bu_1/lots?limit=20&offset=40&status=active'
    """
    if prefix:
        # Use provided prefix with substitutions
        resolved_prefix = prefix.replace('{tenant_id}', tenant_id).replace('{bu_id}', bu_id)
        base_url = f'{request.url.scheme}://{request.url.netloc}{resolved_prefix}'
    else:
        base_url = f'{request.url.scheme}://{request.url.netloc}/tenants/{tenant_id}/bus/{bu_id}/{entity_path}'

    # Build query string (exclude limit/offset, include non-None values)
    query_params = []
    for k, v in params.items():
        if k not in ['limit', 'offset'] and v is not None:
            if isinstance(v, list):
                for item in v:
                    query_params.append(f'{k}={item}')
            else:
                query_params.append(f'{k}={v}')

    query_string = '&'.join(query_params)
    if query_string:
        query_string = '&' + query_string

    page_count = math.ceil(total / limit) if total > 0 else 1
    has_prev = offset > 0
    has_next = offset + limit < total

    return PaginationLinks(
        self=f'{base_url}?limit={limit}&offset={offset}{query_string}',
        first=f'{base_url}?limit={limit}&offset=0{query_string}',
        last=f'{base_url}?limit={limit}&offset={(page_count - 1) * limit}{query_string}' if page_count > 1 else None,
        prev=f'{base_url}?limit={limit}&offset={max(0, offset - limit)}{query_string}' if has_prev else None,
        next=f'{base_url}?limit={limit}&offset={offset + limit}{query_string}' if has_next else None,
    )


def create_service_dependency(
    request: Request,
    service_class: Type[TService],
    session_type: DbSessionType = DbSessionType.READ,
    app_user_id: str | None = None,
) -> Generator[TService, None, None]:
    """
    Factory to create service instances with appropriate database sessions.

    This is a generator function that yields a service instance connected to a
    database session. The session is automatically managed (committed/rolled back
    and closed) when the generator exits.

    Args:
        request: The FastAPI request (provides app.state.db_manager).
        service_class: The service class to instantiate.
        session_type: The type of database session (READ or WRITE).
        app_user_id: Optional app user ID for RLS-enabled sessions.

    Yields:
        An instance of the service class connected to a database session.

    Example:
        >>> def _get_lot_service(request: Request) -> Generator[LotService, None, None]:
        ...     yield from create_service_dependency(request, LotService, DbSessionType.READ)
        ...
        >>> def _get_write_lot_service(request: Request) -> Generator[LotService, None, None]:
        ...     yield from create_service_dependency(request, LotService, DbSessionType.WRITE)
    """
    db_manager = request.app.state.db_manager
    with db_manager.get_session(session_type, app_user_id=app_user_id) as session:
        yield service_class(session)  # type: ignore[call-arg]
