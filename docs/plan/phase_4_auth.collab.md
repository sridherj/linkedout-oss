# Phase 4: Authentication & Authorization — Detailed Execution Plan

## Overview

Port and adapt the linkedout 3-layer dependency-based auth pattern into `src/shared/auth/`, replacing `workspace` with `bu`, making service account tokens config-driven, replacing the hardcoded local dev bypass with `AUTH_ENABLED` config, and adding an API key auth provider inspired by linkedout.

**Source references**:
- linkedout: `.-aragent/linkedout_backend/src/shared/auth/` — 3-layer chain, AuthContext, providers
- linkedout: `./src/middleware/auth.py` — API key auth with bcrypt prefix lookup

**Target directory**: `src/shared/auth/`

---

## File Tree (all files to create)

```
src/shared/
  __init__.py
  auth/
    __init__.py                          # Public exports
    dependencies/
      __init__.py
      auth_dependencies.py               # 3-layer dependency chain
      schemas/
        __init__.py
        auth_context.py                  # Principal, Actor, Subject, AuthContext
        role_enums.py                    # TenantRole, BuRole
    providers/
      __init__.py
      base_auth_provider.py              # Abstract provider interface
      firebase_auth_provider.py          # Firebase JWT implementation
      api_key_auth_provider.py           # API key implementation (bcrypt prefix lookup)
    config.py                            # Auth-specific config additions

tests/
  shared/
    auth/
      __init__.py
      test_auth_dependencies.py          # Unit tests for 3-layer chain
      test_auth_context.py               # Unit tests for AuthContext models
      test_firebase_auth_provider.py     # Unit tests for Firebase provider (mocked)
      test_api_key_auth_provider.py      # Unit tests for API key provider
  integration/
    test_auth_integration.py             # Integration tests with full stack
```

---

## Step 1: Role Enums

### File: `src/shared/auth/dependencies/schemas/role_enums.py`

```python
from enum import StrEnum


class TenantRole(StrEnum):
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"


class BuRole(StrEnum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    VIEWER = "VIEWER"
```

**Adaptation from linkedout**: `WorkspaceRole` becomes `BuRole`. Same values (ADMIN, MANAGER) plus VIEWER carried over. These enums live in the auth schemas package, not in entity files, because they're needed by auth context before any entity is loaded.

**Verify**: Import from test file, confirm StrEnum behavior.

---

## Step 2: AuthContext Schemas

### File: `src/shared/auth/dependencies/schemas/auth_context.py`

```python
from typing import Optional, List
from pydantic import BaseModel, Field


class Principal(BaseModel):
    """WHO is authenticated. Populated in Layer 1."""
    auth_provider_id: str = Field(..., description="Firebase UID, 'service_account:<name>', or 'api_key:<app_user_id>'")
    user_id: Optional[str] = Field(default=None, description="App user ID from DB (populated in Layer 2)")
    email: Optional[str] = Field(default=None, description="User email (populated in Layer 2)")
    name: Optional[str] = Field(default=None, description="User display name (populated in Layer 2)")


class Actor(BaseModel):
    """WHAT roles in current context. Populated in Layer 2."""
    id: str = Field(..., description="App user ID or service account ID")
    current_tenant_roles: List[TenantRole] = Field(default_factory=list)
    current_bu_roles: List[BuRole] = Field(default_factory=list)
    is_impersonating: bool = Field(default=False)

    def has_tenant_role(self, *roles: TenantRole) -> bool:
        return any(r in self.current_tenant_roles for r in roles)

    def has_bu_role(self, *roles: BuRole) -> bool:
        return any(r in self.current_bu_roles for r in roles)

    def is_tenant_admin(self) -> bool:
        return TenantRole.ADMIN in self.current_tenant_roles

    def is_bu_admin(self) -> bool:
        return BuRole.ADMIN in self.current_bu_roles

    def is_admin(self) -> bool:
        return self.is_tenant_admin() or self.is_bu_admin()


class Subject(BaseModel):
    """WHAT is being acted upon. Populated in Layer 2."""
    tenant_id: str
    bu_id: Optional[str] = None


class AuthContext(BaseModel):
    """Complete auth context, progressively enriched through the 3-layer chain."""
    principal: Principal
    actor: Optional[Actor] = None
    subject: Optional[Subject] = None

    # Delegate convenience methods to actor
    def has_tenant_role(self, *roles: TenantRole) -> bool:
        return self.actor.has_tenant_role(*roles) if self.actor else False

    def has_bu_role(self, *roles: BuRole) -> bool:
        return self.actor.has_bu_role(*roles) if self.actor else False

    def is_admin(self) -> bool:
        return self.actor.is_admin() if self.actor else False

    def is_tenant_admin(self) -> bool:
        return self.actor.is_tenant_admin() if self.actor else False

    def is_bu_admin(self) -> bool:
        return self.actor.is_bu_admin() if self.actor else False

    @property
    def is_service_account(self) -> bool:
        return self.principal.auth_provider_id.startswith("service_account:")

    @property
    def is_api_key_auth(self) -> bool:
        return self.principal.auth_provider_id.startswith("api_key:")
```

**Key adaptations from linkedout**:
1. `workspace_id` -> `bu_id` everywhere
2. `WorkspaceRole` -> `BuRole`
3. `has_workspace_role` -> `has_bu_role`
4. `is_workspace_admin` -> `is_bu_admin`
5. Principal simplified: no `user_schema` dependency — uses flat fields (`user_id`, `email`, `name`) instead of depending on a full UserSchema. This decouples auth from the user entity's Pydantic schema.
6. Added `is_service_account` and `is_api_key_auth` properties for cleaner conditional logic.

**Verify**: Unit tests for role checking, admin detection, progressive enrichment.

---

## Step 3: Auth Config

### File: `src/shared/auth/config.py`

```python
"""Auth-related configuration, loaded from environment."""
from typing import Dict, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class AuthConfig(BaseSettings):
    # Master switch — when False, all endpoints get a bypass AuthContext
    AUTH_ENABLED: bool = Field(default=True, description="Set to False to disable auth for local dev")

    # Firebase settings
    FIREBASE_ENABLED: bool = Field(default=True)
    FIREBASE_PROJECT_ID: str = Field(default="")
    FIREBASE_CREDENTIALS_PATH: str = Field(default="")

    # Service account tokens: JSON string or comma-separated "token:name" pairs
    # Example: "svc_abc123:agent_service,svc_def456:worker_service"
    SERVICE_ACCOUNT_TOKENS: str = Field(default="", description="Comma-separated token:name pairs")

    # API key auth
    API_KEY_AUTH_ENABLED: bool = Field(default=False)
    API_KEY_HEADER: str = Field(default="X-API-Key")

    # Local dev bypass user (used when AUTH_ENABLED=False)
    DEV_BYPASS_USER_ID: str = Field(default="dev-user-001")
    DEV_BYPASS_USER_EMAIL: str = Field(default="dev@localhost")
    DEV_BYPASS_USER_NAME: str = Field(default="Local Developer")
    DEV_BYPASS_TENANT_ID: str = Field(default="dev-tenant-001")
    DEV_BYPASS_BU_ID: str = Field(default="dev-bu-001")

    class Config:
        env_prefix = ""  # No prefix — use env var names directly
        extra = "ignore"

    def get_service_account_map(self) -> Dict[str, str]:
        """Parse SERVICE_ACCOUNT_TOKENS into {token: service_name} dict."""
        if not self.SERVICE_ACCOUNT_TOKENS:
            return {}
        result = {}
        for pair in self.SERVICE_ACCOUNT_TOKENS.split(","):
            pair = pair.strip()
            if ":" in pair:
                token, name = pair.split(":", 1)
                result[token.strip()] = name.strip()
        return result
```

**Key adaptation from linkedout**:
1. Replaces hardcoded `SERVICE_ACCOUNT_TOKENS` dict with config-driven parsing from env var
2. Replaces hardcoded local dev bypass (`fqZFijiTpZXxRgB101DafqQ1nzv2`) with explicit, documented config fields
3. `AUTH_ENABLED=false` is the local dev bypass — explicit, safe, no secrets in source

**New env vars to document**:
| Env Var | Default | Description |
|---------|---------|-------------|
| `AUTH_ENABLED` | `true` | Master auth switch |
| `FIREBASE_ENABLED` | `true` | Enable Firebase JWT verification |
| `FIREBASE_PROJECT_ID` | `""` | Firebase project ID |
| `FIREBASE_CREDENTIALS_PATH` | `""` | Path to Firebase service account JSON |
| `SERVICE_ACCOUNT_TOKENS` | `""` | Comma-separated `token:name` pairs |
| `API_KEY_AUTH_ENABLED` | `false` | Enable API key authentication |
| `API_KEY_HEADER` | `X-API-Key` | Header name for API key |
| `DEV_BYPASS_USER_ID` | `dev-user-001` | User ID for local dev bypass |
| `DEV_BYPASS_USER_EMAIL` | `dev@localhost` | Email for local dev bypass |
| `DEV_BYPASS_TENANT_ID` | `dev-tenant-001` | Tenant ID for local dev bypass |
| `DEV_BYPASS_BU_ID` | `dev-bu-001` | BU ID for local dev bypass |

**Verify**: Parse `SERVICE_ACCOUNT_TOKENS` correctly, handle empty/missing values.

---

## Step 4: Auth Providers

### File: `src/shared/auth/providers/base_auth_provider.py`

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseAuthProvider(ABC):
    """Abstract auth provider interface. Implementations must be singletons."""

    @abstractmethod
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify token, return decoded claims dict with at least 'uid' key."""
        ...

    @abstractmethod
    def create_user(self, email: str, password: Optional[str] = None) -> str:
        """Create user, return provider user ID."""
        ...

    @abstractmethod
    def delete_user(self, provider_user_id: str) -> None:
        """Delete user by provider ID."""
        ...

    @abstractmethod
    def update_user(self, provider_user_id: str, **kwargs) -> None:
        """Update user fields."""
        ...

    @abstractmethod
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Lookup user by email. Return dict or None."""
        ...

    @classmethod
    @abstractmethod
    def get_instance(cls) -> "BaseAuthProvider":
        """Return singleton instance."""
        ...
```

**Adaptation from linkedout**: Identical interface. Removed `generate_invitation_link` — that's linkedout-specific and not needed in the reference repo. Can be added by consumers.

### File: `src/shared/auth/providers/firebase_auth_provider.py`

```python
import threading
from typing import Dict, Any, Optional

import firebase_admin
from firebase_admin import auth, credentials

from shared.auth.config import AuthConfig
from shared.auth.providers.base_auth_provider import BaseAuthProvider


def initialize_firebase_global(config: AuthConfig) -> None:
    """Call at app startup. Fails fast if Firebase can't init."""
    if not config.FIREBASE_ENABLED:
        return
    if firebase_admin._apps:
        return
    cred = credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH)
    options = {}
    if config.FIREBASE_PROJECT_ID:
        options["projectId"] = config.FIREBASE_PROJECT_ID
    firebase_admin.initialize_app(cred, options or None)


class FirebaseAuthProvider(BaseAuthProvider):
    """Firebase JWT auth provider. Thread-safe singleton."""
    _instance: Optional["FirebaseAuthProvider"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> "FirebaseAuthProvider":
        return cls()

    def verify_token(self, token: str) -> Dict[str, Any]:
        if not firebase_admin._apps:
            raise RuntimeError("Firebase not initialized")
        return auth.verify_id_token(token)

    def create_user(self, email: str, password: Optional[str] = None) -> str:
        record = auth.create_user(email=email, password=password, email_verified=False)
        return record.uid

    def delete_user(self, provider_user_id: str) -> None:
        auth.delete_user(provider_user_id)

    def update_user(self, provider_user_id: str, **kwargs) -> None:
        auth.update_user(provider_user_id, **kwargs)

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        try:
            record = auth.get_user_by_email(email)
            return {"uid": record.uid, "email": record.email, "disabled": record.disabled}
        except auth.UserNotFoundError:
            return None
```

**Adaptation from linkedout**: Identical pattern. Takes `AuthConfig` instead of `linkedout_config`. Removed verbose logging and the `_ensure_initialized` / `_initialize_firebase` duplication — simplified to fail-fast check in `verify_token`.

### File: `src/shared/auth/providers/api_key_auth_provider.py`

```python
"""API key auth provider inspired by linkedout's bcrypt prefix-lookup pattern."""
import threading
from typing import Dict, Any, Optional

import bcrypt
from sqlalchemy.orm import Session

from shared.auth.providers.base_auth_provider import BaseAuthProvider


class ApiKeyAuthProvider(BaseAuthProvider):
    """
    API key authentication via bcrypt prefix lookup.

    Pattern (from linkedout):
    1. API key has an 8-char prefix stored in plaintext for O(1) lookup
    2. Full key is bcrypt-hashed and stored
    3. On auth: prefix lookup -> bcrypt verify -> return user info

    This provider does NOT implement create_user/delete_user/update_user
    (API keys are managed through the AppUser MVCS stack, not through the auth provider).
    Those methods raise NotImplementedError.
    """
    _instance: Optional["ApiKeyAuthProvider"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> "ApiKeyAuthProvider":
        return cls()

    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify API key against the database.

        NOTE: This method needs a DB session, which is not part of the base interface.
        The auth dependency layer handles session injection and calls verify_api_key() directly.
        This method exists to satisfy the interface but should not be called directly.
        """
        raise NotImplementedError(
            "Use verify_api_key(token, session) instead — API key verification needs a DB session"
        )

    def verify_api_key(self, api_key: str, session: Session) -> Optional[Dict[str, Any]]:
        """
        Verify API key via prefix lookup + bcrypt verify.

        Args:
            api_key: Raw API key from request header
            session: DB session for user lookup

        Returns:
            Dict with 'app_user_id', 'tenant_id' if valid, None otherwise.
        """
        if len(api_key) < 8:
            return None

        prefix = api_key[:8]

        # Import here to avoid circular dependency — AppUserEntity is a domain entity
        from organization.entities.app_user_entity import AppUserEntity

        user = (
            session.query(AppUserEntity)
            .filter(AppUserEntity.api_key_prefix == prefix)
            .first()
        )
        if user is None or not user.api_key_hash:
            return None

        if not bcrypt.checkpw(api_key.encode("utf-8"), user.api_key_hash.encode("utf-8")):
            return None

        return {
            "app_user_id": user.id,
            "tenant_id": user.tenant_id,
        }

    def create_user(self, email: str, password: Optional[str] = None) -> str:
        raise NotImplementedError("API keys are managed through AppUser MVCS, not auth provider")

    def delete_user(self, provider_user_id: str) -> None:
        raise NotImplementedError("API keys are managed through AppUser MVCS, not auth provider")

    def update_user(self, provider_user_id: str, **kwargs) -> None:
        raise NotImplementedError("API keys are managed through AppUser MVCS, not auth provider")

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("API keys are managed through AppUser MVCS, not auth provider")
```

**Adaptation from linkedout**: Linkedout uses middleware-based auth. We adapt the core pattern (prefix lookup + bcrypt verify) into the provider seam. The `verify_token` interface doesn't fit perfectly (needs DB session), so the dependency layer calls `verify_api_key()` directly.

**Note on AppUserEntity**: The API key provider needs `AppUserEntity` to exist with `api_key_prefix` and `api_key_hash` columns. This entity should be part of the organization domain (Phase 3). If it doesn't exist yet, the API key provider can be stubbed and completed when the entity is available.

---

## Step 5: 3-Layer Auth Dependency Chain

### File: `src/shared/auth/dependencies/auth_dependencies.py`

```python
from typing import Generator, Optional, List
from functools import partial

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from shared.auth.config import AuthConfig
from shared.auth.dependencies.schemas.auth_context import AuthContext, Principal, Actor, Subject
from shared.auth.dependencies.schemas.role_enums import TenantRole, BuRole
from shared.auth.providers.firebase_auth_provider import FirebaseAuthProvider
from shared.auth.providers.api_key_auth_provider import ApiKeyAuthProvider
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
    - AUTH_ENABLED=false → bypass with dev context
    - Service account token → check config map
    - API key (X-API-Key header) → defer to Layer 2 for DB lookup
    - Bearer token → Firebase JWT verification

    Returns AuthContext with minimal Principal only.
    Raises HTTPException(401) for auth failures.
    """
    config = _get_auth_config()

    # Dev bypass — explicit, config-driven
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
            subject=None,  # Will be populated in Layer 2 from path params
        )

    # Check API key header first (if enabled)
    if config.API_KEY_AUTH_ENABLED:
        api_key = request.headers.get(config.API_KEY_HEADER)
        if api_key:
            # API key auth defers DB lookup to Layer 2
            # Return a placeholder principal that Layer 2 will enrich
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

    # Check service account tokens (config-driven, O(1) lookup)
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
    - API key: verify via bcrypt, load user from result
    - Firebase users: load app user by auth_provider_id, validate tenant access, load roles

    Returns fully enriched AuthContext.
    Raises HTTPException(403) for authorization failures.
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

    # API key auth — verify key and load user
    if provider_id.startswith("api_key_pending:"):
        from shared.auth.providers.api_key_auth_provider import ApiKeyAuthProvider
        # Re-extract the full API key from the request
        # NOTE: The full key was not stored in principal for security.
        # Layer 2 has the session, so we can do the DB lookup here.
        # This requires the request object — get it via a sub-dependency or
        # store the key temporarily. For simplicity, we store the prefix and
        # do a dedicated lookup.
        #
        # IMPLEMENTATION NOTE: In practice, we'd need to thread the full API key
        # through. Two clean options:
        #   A) Store encrypted key in AuthContext._api_key_pending (private field)
        #   B) Make API key a separate Depends() that runs in Layer 2 directly
        #
        # For the reference repo, option B is cleaner:
        # The CRUDRouterFactory can inject a dedicated api_key_auth dependency
        # that combines Layer 1+2 for API key auth.
        #
        # For now, this path raises 401 — API key verification happens via
        # a dedicated dependency (see api_key_auth below).
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key auth requires dedicated dependency",
        )

    # Firebase user — load from DB
    # NOTE: These services must exist in the organization domain.
    # Import deferred to avoid circular imports.
    from organization.services.app_user_service import AppUserService
    from organization.services.app_user_tenant_role_service import AppUserTenantRoleService
    from organization.services.app_user_bu_role_service import AppUserBuRoleService

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

    # Validate BU access (if applicable)
    bu_roles: List[BuRole] = []
    if bu_id is not None:
        bu_role_service = AppUserBuRoleService(session)
        if not bu_role_service.has_bu_access(user.id, bu_id, tenant_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access to business unit denied",
            )
        bu_roles = bu_role_service.get_roles(user.id, bu_id, tenant_id)

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

    Returns AuthContext if validation passes.
    Raises HTTPException(403) for insufficient roles.
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
    """
    Standalone dependency for API-key-authenticated endpoints.
    Combines Layer 1+2 for API key flow.
    """
    config = _get_auth_config()
    if not config.API_KEY_AUTH_ENABLED:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key auth not enabled")

    api_key = request.headers.get(config.API_KEY_HEADER)
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Missing {config.API_KEY_HEADER} header")

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
            current_tenant_roles=[TenantRole.MEMBER],  # API keys get MEMBER by default
            current_bu_roles=[],
        ),
        subject=Subject(tenant_id=result["tenant_id"]),
    )
```

**Key adaptations from linkedout**:
1. `workspace_id` -> `bu_id` in get_valid_user and validate_role_access
2. Service account tokens from config instead of hardcoded dict
3. Dev bypass from config instead of hardcoded Firebase UID
4. API key auth as a dedicated dependency (linkedout used middleware; we use the dependency pattern for consistency)
5. `AppUserService` / `AppUserTenantRoleService` / `AppUserBuRoleService` are deferred imports from the organization domain

---

## Step 6: Wire Auth into CRUDRouterFactory

### Changes to `src/common/controllers/crud_router_factory.py`

Add auth dependency injection to `CRUDRouterConfig` and the generated router:

```python
# Add to CRUDRouterConfig:
auth_dependency: Optional[Callable] = None  # Default: is_valid_user (or None for no auth)

# In create_crud_router():
if config.auth_dependency:
    router = APIRouter(
        prefix=config.prefix,
        tags=config.tags,
        dependencies=[Depends(config.auth_dependency)],  # Router-level defense-in-depth
    )
```

For per-endpoint auth, the `auth_ctx` parameter is added to write endpoints:

```python
# In create/update/delete endpoints, add:
auth_ctx: AuthContext = Depends(get_valid_user),

# Then pass auth_ctx.principal.user_id as created_by/updated_by to the service
```

### Changes to `src/common/schemas/base_request_schema.py`

Replace the placeholder `auth_context: Optional[object] = None` with proper typing:

```python
from shared.auth.dependencies.schemas.auth_context import AuthContext

class BaseRequestSchema(BaseModel):
    auth_context: Optional[AuthContext] = None
```

---

## Step 7: App Startup Wiring

### Changes to `main.py`

```python
from shared.auth.config import AuthConfig
from shared.auth.dependencies.auth_dependencies import init_auth
from shared.auth.providers.firebase_auth_provider import initialize_firebase_global

# At startup:
auth_config = AuthConfig()
init_auth(auth_config)
if auth_config.FIREBASE_ENABLED:
    initialize_firebase_global(auth_config)
```

---

## Step 8: `__init__.py` Exports

### `src/shared/__init__.py`
Empty.

### `src/shared/auth/__init__.py`
```python
from shared.auth.dependencies.schemas.auth_context import AuthContext, Principal, Actor, Subject
from shared.auth.dependencies.schemas.role_enums import TenantRole, BuRole
from shared.auth.dependencies.auth_dependencies import (
    is_valid_user,
    get_valid_user,
    validate_role_access,
    api_key_auth,
    require_tenant_admin,
    require_bu_admin,
    init_auth,
)
from shared.auth.providers.base_auth_provider import BaseAuthProvider
from shared.auth.config import AuthConfig
```

### `src/shared/auth/dependencies/__init__.py`, `src/shared/auth/dependencies/schemas/__init__.py`, `src/shared/auth/providers/__init__.py`
Empty `__init__.py` files.

---

## Step 9: Organization Domain Dependencies

The auth Layer 2 (`get_valid_user`) requires these services to exist in the organization domain. They should have been created in Phase 3 or need to be created as part of this phase:

### Required services (deferred imports in auth_dependencies.py):
1. `organization.services.app_user_service.AppUserService`
   - Method needed: `get_by_auth_provider_id(auth_provider_id: str) -> Optional[AppUserSchema]`

2. `organization.services.app_user_tenant_role_service.AppUserTenantRoleService`
   - Methods needed: `has_tenant_access(user_id, tenant_id) -> bool`, `get_roles(user_id, tenant_id) -> List[TenantRole]`

3. `organization.services.app_user_bu_role_service.AppUserBuRoleService`
   - Methods needed: `has_bu_access(user_id, bu_id, tenant_id) -> bool`, `get_roles(user_id, bu_id, tenant_id) -> List[BuRole]`

### Required entities:
1. `AppUserEntity` — needs `auth_provider_id`, `api_key_prefix`, `api_key_hash` columns
2. `AppUserTenantRoleEntity` — junction table: `app_user_id`, `tenant_id`, `role` (TenantRole)
3. `AppUserBuRoleEntity` — junction table: `app_user_id`, `bu_id`, `tenant_id`, `role` (BuRole)

**Decision point**: If Phase 3 already created these entities, wire them in. If not, create stubs that the auth layer can import, and fill in the full MVCS in Phase 3.

---

## Step 10: Test Files

### `tests/shared/auth/test_auth_context.py`

```python
class TestPrincipal:
    def test_minimal_principal(self): ...       # Just auth_provider_id
    def test_enriched_principal(self): ...      # All fields populated

class TestActor:
    def test_has_tenant_role(self): ...
    def test_has_bu_role(self): ...
    def test_is_admin_tenant(self): ...
    def test_is_admin_bu(self): ...
    def test_is_admin_neither(self): ...

class TestAuthContext:
    def test_progressive_enrichment(self): ...   # Layer 1 -> Layer 2 -> Layer 3
    def test_is_service_account(self): ...
    def test_is_api_key_auth(self): ...
    def test_delegate_methods_with_no_actor(self): ...  # Returns False, not error
```

### `tests/shared/auth/test_auth_dependencies.py`

```python
# Use FastAPI TestClient with mocked providers

class TestIsValidUser:
    def test_dev_bypass_when_auth_disabled(self): ...
    def test_missing_auth_header_returns_401(self): ...
    def test_service_account_token_from_config(self): ...
    def test_valid_firebase_jwt(self): ...              # Mock FirebaseAuthProvider
    def test_expired_firebase_jwt_returns_401(self): ...
    def test_api_key_header_returns_pending(self): ...   # When API_KEY_AUTH_ENABLED

class TestGetValidUser:
    def test_dev_bypass_populates_subject(self): ...
    def test_service_account_gets_admin_roles(self): ...
    def test_firebase_user_loaded_from_db(self): ...     # Mock AppUserService
    def test_user_not_found_returns_403(self): ...
    def test_tenant_access_denied_returns_403(self): ...
    def test_bu_access_denied_returns_403(self): ...

class TestValidateRoleAccess:
    def test_service_account_auto_passes(self): ...
    def test_dev_bypass_auto_passes(self): ...
    def test_tenant_role_check_passes(self): ...
    def test_tenant_role_check_fails(self): ...
    def test_bu_role_check_passes(self): ...
    def test_require_both_and_logic(self): ...
    def test_require_both_or_logic(self): ...
```

### How to mock auth in tests

```python
# conftest.py addition for tests:

@pytest.fixture
def mock_auth_context():
    """Pre-built AuthContext for tests that need authenticated requests."""
    return AuthContext(
        principal=Principal(auth_provider_id="test-uid-001", user_id="test-user-001", email="test@example.com"),
        actor=Actor(id="test-user-001", current_tenant_roles=[TenantRole.ADMIN], current_bu_roles=[BuRole.ADMIN]),
        subject=Subject(tenant_id="test-tenant-001", bu_id="test-bu-001"),
    )

@pytest.fixture
def override_auth(mock_auth_context):
    """Override auth dependency in FastAPI app for testing."""
    from main import app
    from shared.auth.dependencies.auth_dependencies import is_valid_user, get_valid_user

    app.dependency_overrides[is_valid_user] = lambda: mock_auth_context
    app.dependency_overrides[get_valid_user] = lambda: mock_auth_context
    yield mock_auth_context
    app.dependency_overrides.clear()
```

This pattern uses FastAPI's `dependency_overrides` — the standard approach for mocking Depends() in tests. Each test layer can override at the appropriate level:
- Controller tests: override `is_valid_user` (skip all auth)
- Integration tests: override at service account level or use actual auth flow

### `tests/shared/auth/test_api_key_auth_provider.py`

```python
class TestApiKeyAuthProvider:
    def test_verify_valid_key(self): ...           # Seed user with known key, verify
    def test_verify_invalid_key(self): ...         # Wrong key, bcrypt fails
    def test_verify_unknown_prefix(self): ...      # No user with that prefix
    def test_verify_short_key(self): ...           # < 8 chars returns None
    def test_singleton_pattern(self): ...          # Same instance returned
```

---

## Execution Order

| Step | Description | Dependencies | Verify |
|------|-------------|-------------|--------|
| 1 | Create `role_enums.py` | None | Import and test StrEnum values |
| 2 | Create `auth_context.py` | Step 1 | Unit tests for all models |
| 3 | Create `auth/config.py` | None | Parse SERVICE_ACCOUNT_TOKENS |
| 4a | Create `base_auth_provider.py` | None | N/A (abstract) |
| 4b | Create `firebase_auth_provider.py` | Step 4a, Step 3 | Mock tests |
| 4c | Create `api_key_auth_provider.py` | Step 4a | Unit tests with SQLite |
| 5 | Create `auth_dependencies.py` | Steps 1-4 | Full dependency chain tests |
| 6 | Wire into CRUDRouterFactory | Step 5 | Existing controller tests pass |
| 7 | Wire into main.py startup | Step 3, Step 5 | App starts without error |
| 8 | Create `__init__.py` exports | Steps 1-7 | Clean imports work |
| 9 | Verify org domain services | Step 5 | Layer 2 can import services |
| 10 | Write all test files | Steps 1-9 | `precommit-tests` passes |

---

## Open Questions / Decisions Needed

1. **AppUser entity location**: Phase 3 should have created `AppUserEntity` in the organization domain. If not, auth Layer 2 will fail on import. Need to confirm Phase 3 status.

2. **API key columns on AppUserEntity**: The API key provider needs `api_key_prefix` (String, 8 chars) and `api_key_hash` (String, bcrypt hash) columns. These need to be added to AppUserEntity if not already present.

3. **Role storage**: TenantRole and BuRole enums are defined in the auth package, but the role junction tables (AppUserTenantRoleEntity, AppUserBuRoleEntity) live in the organization domain. The enums should be importable without pulling in entity code.

4. **API key auth scope**: Linkedout gives API keys tenant-level access only. Should API keys also get BU-level access in the reference repo? Current plan: MEMBER-level tenant access, no BU access. Can be enriched later.
