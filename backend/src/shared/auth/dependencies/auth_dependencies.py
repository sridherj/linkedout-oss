# SPDX-License-Identifier: Apache-2.0
"""3-layer auth dependency chain for FastAPI."""
from typing import Generator, Optional, List
from functools import partial

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from shared.auth.config import AuthConfig
from shared.auth.dependencies.schemas.auth_context import AuthContext, Principal, Actor, Subject
from shared.auth.dependencies.schemas.role_enums import TenantRole, BuRole
from shared.infra.db.db_session_manager import DbSessionType, db_session_manager

# Module-level config — initialized at app startup
_auth_config: Optional[AuthConfig] = None


def init_auth(config: AuthConfig) -> None:
    """Call once at app startup to set auth config."""
    global _auth_config
    _auth_config = config


def _get_auth_config() -> AuthConfig:
    if _auth_config is None:
        raise RuntimeError("Auth not initialized — call init_auth() at app startup")
    return _auth_config


def _get_read_session() -> Generator[Session, None, None]:
    with db_session_manager.get_session(DbSessionType.READ) as session:
        yield session


# ───────────────────────────────────────────────────────────────
# Layer 1: is_valid_user — validate credentials, return minimal AuthContext
# ───────────────────────────────────────────────────────────────

def is_valid_user(request: Request) -> AuthContext:
    """
    Layer 1: Validate Bearer token or API key. Zero DB queries.

    Routes:
    - AUTH_ENABLED=false -> bypass with dev context
    - Service account token -> check config map
    - API key header present -> placeholder principal (deferred to Layer 2)
    - Bearer token -> Firebase JWT verification
    """
    config = _get_auth_config()

    # Dev bypass
    if not config.AUTH_ENABLED:
        return AuthContext(
            principal=Principal(
                auth_provider_id=f"dev_bypass:{config.DEV_BYPASS_USER_ID}",
                user_id=config.DEV_BYPASS_USER_ID,
                email=config.DEV_BYPASS_USER_EMAIL,
                name=config.DEV_BYPASS_USER_NAME,
            ),
            actor=Actor(
                id=config.DEV_BYPASS_USER_ID,
                current_tenant_roles=[TenantRole.ADMIN],
                current_bu_roles=[BuRole.ADMIN],
            ),
            subject=None,
        )

    # Check API key header first (if enabled)
    if config.API_KEY_AUTH_ENABLED:
        api_key = request.headers.get(config.API_KEY_HEADER)
        if api_key:
            return AuthContext(
                principal=Principal(auth_provider_id=f"api_key_pending:{api_key[:8]}"),
            )

    # Bearer token required
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": 'Bearer realm="api"'},
        )

    token = auth_header.split(" ", 1)[1].strip()

    # Check service account tokens
    svc_map = config.get_service_account_map()
    if token in svc_map:
        service_name = svc_map[token]
        return AuthContext(
            principal=Principal(auth_provider_id=f"service_account:{service_name}"),
        )

    # Firebase JWT verification
    if not config.FIREBASE_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No auth provider configured",
        )

    try:
        from shared.auth.providers.firebase_auth_provider import FirebaseAuthProvider
        firebase = FirebaseAuthProvider.get_instance()
        decoded = firebase.verify_token(token)
        uid = decoded.get("uid")
        if not uid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format",
            )
        return AuthContext(
            principal=Principal(
                auth_provider_id=uid,
                email=decoded.get("email"),
            ),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": 'Bearer realm="api"'},
        ) from exc


# ───────────────────────────────────────────────────────────────
# Layer 2: get_valid_user — enrich context, validate tenant/BU access
# ───────────────────────────────────────────────────────────────

def get_valid_user(
    tenant_id: str,
    bu_id: Optional[str] = None,
    auth_ctx: AuthContext = Depends(is_valid_user),
    session: Session = Depends(_get_read_session),
) -> AuthContext:
    """
    Layer 2: Enrich AuthContext with user data, validate tenant/BU access.

    - Dev bypass: populate Subject from path params, pass through
    - Service accounts: auto-granted admin roles, no DB lookup
    - API key: defer to dedicated api_key_auth dependency
    - Firebase users: load app user by auth_provider_id, validate tenant access, load roles
    """
    config = _get_auth_config()
    provider_id = auth_ctx.principal.auth_provider_id

    # Dev bypass — just add Subject from path params
    if provider_id.startswith("dev_bypass:"):
        return AuthContext(
            principal=auth_ctx.principal,
            actor=auth_ctx.actor,
            subject=Subject(tenant_id=tenant_id, bu_id=bu_id),
        )

    # Service account — admin access, no DB
    if provider_id.startswith("service_account:"):
        service_name = provider_id.replace("service_account:", "")
        return AuthContext(
            principal=auth_ctx.principal,
            actor=Actor(
                id=f"service_account_{service_name}",
                current_tenant_roles=[TenantRole.ADMIN],
                current_bu_roles=[BuRole.ADMIN] if bu_id else [],
            ),
            subject=Subject(tenant_id=tenant_id, bu_id=bu_id),
        )

    # API key auth — requires dedicated dependency
    if provider_id.startswith("api_key_pending:"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key auth requires dedicated dependency",
        )

    # Firebase user — load from DB
    from organization.services.app_user_service import AppUserService
    from organization.services.app_user_tenant_role_service import AppUserTenantRoleService

    user_service = AppUserService(session)
    user = user_service.get_by_auth_provider_id(provider_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account not found",
        )

    # Validate tenant access
    tenant_role_service = AppUserTenantRoleService(session)
    if not tenant_role_service.has_tenant_access(user.id, tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to tenant denied",
        )

    tenant_roles = tenant_role_service.get_roles(user.id, tenant_id)

    # BU roles placeholder (BU role entity removed)
    bu_roles: List[str] = []

    return AuthContext(
        principal=Principal(
            auth_provider_id=provider_id,
            user_id=user.id,
            email=user.email,
            name=user.name,
        ),
        actor=Actor(
            id=user.id,
            current_tenant_roles=tenant_roles,
            current_bu_roles=bu_roles,
        ),
        subject=Subject(tenant_id=tenant_id, bu_id=bu_id),
    )


# ───────────────────────────────────────────────────────────────
# Layer 3: validate_role_access — role-based access checks
# ───────────────────────────────────────────────────────────────

def validate_role_access(
    tenant_id: str,
    bu_id: Optional[str] = None,
    tenant_roles: Optional[List[TenantRole]] = None,
    bu_roles: Optional[List[BuRole]] = None,
    require_both: bool = False,
    auth_ctx: AuthContext = Depends(get_valid_user),
) -> AuthContext:
    """
    Layer 3: Validate role-based access.

    - Service accounts and dev bypass auto-pass.
    - AND logic (require_both=True): needs BOTH tenant AND BU roles.
    - OR logic (require_both=False): needs EITHER tenant OR BU roles.
    """
    # Service accounts and dev bypass auto-pass
    if auth_ctx.is_service_account or auth_ctx.principal.auth_provider_id.startswith("dev_bypass:"):
        return auth_ctx

    # Tenant role check
    tenant_ok = True
    if tenant_roles is not None:
        tenant_ok = auth_ctx.has_tenant_role(*tenant_roles)
    else:
        tenant_ok = bool(auth_ctx.actor and auth_ctx.actor.current_tenant_roles)

    # BU role check (only if bu_id present)
    bu_ok = True
    if bu_id is not None:
        if bu_roles is not None:
            bu_ok = auth_ctx.has_bu_role(*bu_roles)
        else:
            bu_ok = bool(auth_ctx.actor and auth_ctx.actor.current_bu_roles)

    # Apply AND/OR logic
    if bu_id is not None:
        if require_both:
            if not (tenant_ok and bu_ok):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient roles (both tenant and BU required)")
        else:
            if not (tenant_ok or bu_ok):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient roles")
    else:
        if not tenant_ok:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient tenant roles")

    return auth_ctx


# ───────────────────────────────────────────────────────────────
# Convenience: pre-built dependency partials
# ───────────────────────────────────────────────────────────────

require_tenant_admin = partial(validate_role_access, tenant_roles=[TenantRole.ADMIN])
require_bu_admin = partial(validate_role_access, bu_roles=[BuRole.ADMIN])
require_any_admin = partial(validate_role_access, tenant_roles=[TenantRole.ADMIN], bu_roles=[BuRole.ADMIN])


# ───────────────────────────────────────────────────────────────
# Dedicated API key auth dependency (for API-key-only endpoints)
# ───────────────────────────────────────────────────────────────

def api_key_auth(
    request: Request,
    session: Session = Depends(_get_read_session),
) -> AuthContext:
    """Standalone dependency for API-key-authenticated endpoints."""
    config = _get_auth_config()
    if not config.API_KEY_AUTH_ENABLED:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key auth not enabled")

    api_key = request.headers.get(config.API_KEY_HEADER)
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Missing {config.API_KEY_HEADER} header")

    from shared.auth.providers.api_key_auth_provider import ApiKeyAuthProvider
    provider = ApiKeyAuthProvider.get_instance()
    result = provider.verify_api_key(api_key, session)
    if result is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    return AuthContext(
        principal=Principal(
            auth_provider_id=f"api_key:{result['app_user_id']}",
            user_id=result["app_user_id"],
        ),
        actor=Actor(
            id=result["app_user_id"],
            current_tenant_roles=[TenantRole.MEMBER],
            current_bu_roles=[],
        ),
        subject=Subject(tenant_id=result["tenant_id"]) if result.get("tenant_id") else None,
    )
