# SPDX-License-Identifier: Apache-2.0
"""Auth module — import from submodules directly to avoid circular imports.

Usage:
    from shared.auth.dependencies.schemas.auth_context import AuthContext, Principal, Actor, Subject
    from shared.auth.dependencies.schemas.role_enums import TenantRole, BuRole
    from shared.auth.dependencies.auth_dependencies import is_valid_user, get_valid_user, init_auth
    from shared.auth.config import AuthConfig
"""
