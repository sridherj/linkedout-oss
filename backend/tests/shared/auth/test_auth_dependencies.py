# SPDX-License-Identifier: Apache-2.0
"""Tests for the 3-layer auth dependency chain."""
import pytest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from shared.auth.config import AuthConfig
from shared.auth.dependencies.auth_dependencies import (
    init_auth,
    is_valid_user,
    get_valid_user,
    validate_role_access,
    _get_auth_config,
)
from shared.auth.dependencies.schemas.auth_context import AuthContext, Principal, Actor, Subject
from shared.auth.dependencies.schemas.role_enums import TenantRole, BuRole


def _make_request(headers=None):
    """Create a mock Request with given headers."""
    req = MagicMock()
    req.headers = headers or {}
    return req


@pytest.fixture(autouse=True)
def _reset_auth_config():
    """Ensure auth config is reset between tests."""
    import shared.auth.dependencies.auth_dependencies as mod
    old = mod._auth_config
    yield
    mod._auth_config = old


class TestIsValidUser:
    def test_dev_bypass_when_auth_disabled(self):
        config = AuthConfig(AUTH_ENABLED=False)
        init_auth(config)
        request = _make_request()

        ctx = is_valid_user(request)

        assert ctx.principal.auth_provider_id.startswith("dev_bypass:")
        assert ctx.actor is not None
        assert TenantRole.ADMIN in ctx.actor.current_tenant_roles
        assert BuRole.ADMIN in ctx.actor.current_bu_roles
        assert ctx.principal.user_id == config.DEV_BYPASS_USER_ID
        assert ctx.principal.email == config.DEV_BYPASS_USER_EMAIL

    def test_missing_auth_header_returns_401(self):
        config = AuthConfig(AUTH_ENABLED=True, API_KEY_AUTH_ENABLED=False)
        init_auth(config)
        request = _make_request(headers={})

        with pytest.raises(HTTPException) as exc_info:
            is_valid_user(request)
        assert exc_info.value.status_code == 401

    def test_service_account_token_from_config(self):
        config = AuthConfig(
            AUTH_ENABLED=True,
            SERVICE_ACCOUNT_TOKENS="svc_abc123:agent_service,svc_def456:worker_service",
        )
        init_auth(config)
        request = _make_request(headers={"Authorization": "Bearer svc_abc123"})

        ctx = is_valid_user(request)

        assert ctx.principal.auth_provider_id == "service_account:agent_service"
        assert ctx.is_service_account is True

    def test_valid_firebase_jwt(self):
        config = AuthConfig(AUTH_ENABLED=True, FIREBASE_ENABLED=True)
        init_auth(config)
        request = _make_request(headers={"Authorization": "Bearer firebase-jwt-token"})

        mock_provider = MagicMock()
        mock_provider.verify_token.return_value = {"uid": "fb-uid-001", "email": "user@test.com"}

        mock_cls = MagicMock()
        mock_cls.get_instance.return_value = mock_provider

        with patch(
            "shared.auth.providers.firebase_auth_provider.FirebaseAuthProvider",
            mock_cls,
        ):
            ctx = is_valid_user(request)

        assert ctx.principal.auth_provider_id == "fb-uid-001"
        assert ctx.principal.email == "user@test.com"

    def test_expired_firebase_jwt_returns_401(self):
        config = AuthConfig(AUTH_ENABLED=True, FIREBASE_ENABLED=True)
        init_auth(config)
        request = _make_request(headers={"Authorization": "Bearer expired-token"})

        mock_provider = MagicMock()
        mock_provider.verify_token.side_effect = Exception("Token expired")

        mock_cls = MagicMock()
        mock_cls.get_instance.return_value = mock_provider

        with patch(
            "shared.auth.providers.firebase_auth_provider.FirebaseAuthProvider",
            mock_cls,
        ):
            with pytest.raises(HTTPException) as exc_info:
                is_valid_user(request)
            assert exc_info.value.status_code == 401

    def test_api_key_header_returns_pending(self):
        config = AuthConfig(AUTH_ENABLED=True, API_KEY_AUTH_ENABLED=True, API_KEY_HEADER="X-API-Key")
        init_auth(config)
        request = _make_request(headers={"X-API-Key": "abcdefgh_full_key"})

        ctx = is_valid_user(request)

        assert ctx.principal.auth_provider_id.startswith("api_key_pending:")

    def test_no_auth_provider_configured_returns_401(self):
        config = AuthConfig(AUTH_ENABLED=True, FIREBASE_ENABLED=False, API_KEY_AUTH_ENABLED=False)
        init_auth(config)
        request = _make_request(headers={"Authorization": "Bearer some-token"})

        with pytest.raises(HTTPException) as exc_info:
            is_valid_user(request)
        assert exc_info.value.status_code == 401

    def test_malformed_bearer_header_returns_401(self):
        config = AuthConfig(AUTH_ENABLED=True)
        init_auth(config)
        request = _make_request(headers={"Authorization": "Basic some-token"})

        with pytest.raises(HTTPException) as exc_info:
            is_valid_user(request)
        assert exc_info.value.status_code == 401


class TestGetValidUser:
    def test_dev_bypass_populates_subject(self):
        config = AuthConfig(AUTH_ENABLED=False)
        init_auth(config)

        auth_ctx = is_valid_user(_make_request())
        session = MagicMock()

        result = get_valid_user(
            tenant_id="t-001", bu_id="bu-001", auth_ctx=auth_ctx, session=session
        )

        assert result.subject is not None
        assert result.subject.tenant_id == "t-001"
        assert result.subject.bu_id == "bu-001"
        assert result.actor is not None

    def test_service_account_gets_admin_roles(self):
        config = AuthConfig(
            AUTH_ENABLED=True,
            SERVICE_ACCOUNT_TOKENS="svc_token:test_service",
        )
        init_auth(config)

        auth_ctx = AuthContext(
            principal=Principal(auth_provider_id="service_account:test_service"),
        )
        session = MagicMock()

        result = get_valid_user(
            tenant_id="t-001", bu_id="bu-001", auth_ctx=auth_ctx, session=session
        )

        assert TenantRole.ADMIN in result.actor.current_tenant_roles
        assert BuRole.ADMIN in result.actor.current_bu_roles
        assert result.subject.tenant_id == "t-001"

    def test_service_account_no_bu_roles_when_bu_id_none(self):
        config = AuthConfig(AUTH_ENABLED=True, SERVICE_ACCOUNT_TOKENS="svc_token:test_service")
        init_auth(config)

        auth_ctx = AuthContext(
            principal=Principal(auth_provider_id="service_account:test_service"),
        )
        session = MagicMock()

        result = get_valid_user(
            tenant_id="t-001", bu_id=None, auth_ctx=auth_ctx, session=session
        )

        assert result.actor.current_bu_roles == []

    def test_firebase_user_loaded_from_db(self):
        config = AuthConfig(AUTH_ENABLED=True)
        init_auth(config)

        auth_ctx = AuthContext(
            principal=Principal(auth_provider_id="firebase-uid-001"),
        )

        mock_user = MagicMock()
        mock_user.id = "usr_001"
        mock_user.email = "alice@test.com"
        mock_user.name = "Alice"

        mock_user_service = MagicMock()
        mock_user_service.get_by_auth_provider_id.return_value = mock_user

        mock_tenant_role_service = MagicMock()
        mock_tenant_role_service.has_tenant_access.return_value = True
        mock_tenant_role_service.get_roles.return_value = [TenantRole.MEMBER]

        session = MagicMock()

        with patch("organization.services.app_user_service.AppUserService", return_value=mock_user_service), \
             patch("organization.services.app_user_tenant_role_service.AppUserTenantRoleService", return_value=mock_tenant_role_service):
            result = get_valid_user(
                tenant_id="t-001", bu_id=None, auth_ctx=auth_ctx, session=session
            )

        assert result.principal.user_id == "usr_001"
        assert result.principal.email == "alice@test.com"
        assert TenantRole.MEMBER in result.actor.current_tenant_roles

    def test_user_not_found_returns_403(self):
        config = AuthConfig(AUTH_ENABLED=True)
        init_auth(config)

        auth_ctx = AuthContext(
            principal=Principal(auth_provider_id="firebase-uid-unknown"),
        )

        mock_user_service = MagicMock()
        mock_user_service.get_by_auth_provider_id.return_value = None
        session = MagicMock()

        with patch("organization.services.app_user_service.AppUserService", return_value=mock_user_service):
            with pytest.raises(HTTPException) as exc_info:
                get_valid_user(
                    tenant_id="t-001", bu_id=None, auth_ctx=auth_ctx, session=session
                )
            assert exc_info.value.status_code == 403

    def test_tenant_access_denied_returns_403(self):
        config = AuthConfig(AUTH_ENABLED=True)
        init_auth(config)

        auth_ctx = AuthContext(
            principal=Principal(auth_provider_id="firebase-uid-001"),
        )

        mock_user = MagicMock()
        mock_user.id = "usr_001"
        mock_user_service = MagicMock()
        mock_user_service.get_by_auth_provider_id.return_value = mock_user

        mock_tenant_role_service = MagicMock()
        mock_tenant_role_service.has_tenant_access.return_value = False
        session = MagicMock()

        with patch("organization.services.app_user_service.AppUserService", return_value=mock_user_service), \
             patch("organization.services.app_user_tenant_role_service.AppUserTenantRoleService", return_value=mock_tenant_role_service):
            with pytest.raises(HTTPException) as exc_info:
                get_valid_user(
                    tenant_id="t-001", bu_id=None, auth_ctx=auth_ctx, session=session
                )
            assert exc_info.value.status_code == 403


class TestValidateRoleAccess:
    def _make_auth_ctx(self, provider_id="firebase-uid-001", tenant_roles=None, bu_roles=None):
        return AuthContext(
            principal=Principal(auth_provider_id=provider_id, user_id="usr_001"),
            actor=Actor(
                id="usr_001",
                current_tenant_roles=tenant_roles or [],
                current_bu_roles=bu_roles or [],
            ),
            subject=Subject(tenant_id="t-001", bu_id="bu-001"),
        )

    def test_service_account_auto_passes(self):
        ctx = self._make_auth_ctx(provider_id="service_account:test")
        result = validate_role_access(
            tenant_id="t-001", bu_id="bu-001",
            tenant_roles=[TenantRole.ADMIN], auth_ctx=ctx,
        )
        assert result is ctx

    def test_dev_bypass_auto_passes(self):
        ctx = self._make_auth_ctx(provider_id="dev_bypass:dev-user-001")
        result = validate_role_access(
            tenant_id="t-001", bu_id="bu-001",
            tenant_roles=[TenantRole.ADMIN], auth_ctx=ctx,
        )
        assert result is ctx

    def test_tenant_role_check_passes(self):
        ctx = self._make_auth_ctx(tenant_roles=[TenantRole.ADMIN])
        result = validate_role_access(
            tenant_id="t-001", tenant_roles=[TenantRole.ADMIN], auth_ctx=ctx,
        )
        assert result is ctx

    def test_tenant_role_check_fails(self):
        ctx = self._make_auth_ctx(tenant_roles=[TenantRole.VIEWER])
        with pytest.raises(HTTPException) as exc_info:
            validate_role_access(
                tenant_id="t-001", tenant_roles=[TenantRole.ADMIN], auth_ctx=ctx,
            )
        assert exc_info.value.status_code == 403

    def test_bu_role_check_passes(self):
        ctx = self._make_auth_ctx(
            tenant_roles=[TenantRole.MEMBER], bu_roles=[BuRole.ADMIN]
        )
        result = validate_role_access(
            tenant_id="t-001", bu_id="bu-001",
            bu_roles=[BuRole.ADMIN], auth_ctx=ctx,
        )
        assert result is ctx

    def test_require_both_and_logic(self):
        ctx = self._make_auth_ctx(
            tenant_roles=[TenantRole.ADMIN], bu_roles=[BuRole.VIEWER]
        )
        # Has tenant admin but not bu admin — with require_both should still pass
        # because we're checking "has any of the specified roles", not "has ADMIN"
        result = validate_role_access(
            tenant_id="t-001", bu_id="bu-001",
            tenant_roles=[TenantRole.ADMIN], bu_roles=[BuRole.VIEWER],
            require_both=True, auth_ctx=ctx,
        )
        assert result is ctx

    def test_require_both_fails_when_missing_bu(self):
        ctx = self._make_auth_ctx(
            tenant_roles=[TenantRole.ADMIN], bu_roles=[]
        )
        with pytest.raises(HTTPException) as exc_info:
            validate_role_access(
                tenant_id="t-001", bu_id="bu-001",
                tenant_roles=[TenantRole.ADMIN], bu_roles=[BuRole.ADMIN],
                require_both=True, auth_ctx=ctx,
            )
        assert exc_info.value.status_code == 403

    def test_or_logic_passes_with_tenant_only(self):
        ctx = self._make_auth_ctx(
            tenant_roles=[TenantRole.ADMIN], bu_roles=[]
        )
        result = validate_role_access(
            tenant_id="t-001", bu_id="bu-001",
            tenant_roles=[TenantRole.ADMIN], bu_roles=[BuRole.ADMIN],
            require_both=False, auth_ctx=ctx,
        )
        assert result is ctx
