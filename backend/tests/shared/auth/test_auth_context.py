# SPDX-License-Identifier: Apache-2.0
"""Tests for auth context schemas — Principal, Actor, Subject, AuthContext."""
import pytest

from shared.auth.dependencies.schemas.auth_context import AuthContext, Principal, Actor, Subject
from shared.auth.dependencies.schemas.role_enums import TenantRole, BuRole


class TestPrincipal:
    def test_minimal_principal(self):
        p = Principal(auth_provider_id="firebase-uid-001")
        assert p.auth_provider_id == "firebase-uid-001"
        assert p.user_id is None
        assert p.email is None
        assert p.name is None

    def test_enriched_principal(self):
        p = Principal(
            auth_provider_id="firebase-uid-001",
            user_id="usr_abc123",
            email="alice@example.com",
            name="Alice",
        )
        assert p.user_id == "usr_abc123"
        assert p.email == "alice@example.com"
        assert p.name == "Alice"


class TestActor:
    def test_has_tenant_role(self):
        actor = Actor(id="usr_001", current_tenant_roles=[TenantRole.ADMIN, TenantRole.MEMBER])
        assert actor.has_tenant_role(TenantRole.ADMIN) is True
        assert actor.has_tenant_role(TenantRole.VIEWER) is False

    def test_has_bu_role(self):
        actor = Actor(id="usr_001", current_bu_roles=[BuRole.MANAGER])
        assert actor.has_bu_role(BuRole.MANAGER) is True
        assert actor.has_bu_role(BuRole.ADMIN) is False

    def test_is_admin_tenant(self):
        actor = Actor(id="usr_001", current_tenant_roles=[TenantRole.ADMIN])
        assert actor.is_tenant_admin() is True
        assert actor.is_admin() is True

    def test_is_admin_bu(self):
        actor = Actor(id="usr_001", current_bu_roles=[BuRole.ADMIN])
        assert actor.is_bu_admin() is True
        assert actor.is_admin() is True

    def test_is_admin_neither(self):
        actor = Actor(id="usr_001", current_tenant_roles=[TenantRole.VIEWER])
        assert actor.is_admin() is False

    def test_default_not_impersonating(self):
        actor = Actor(id="usr_001")
        assert actor.is_impersonating is False


class TestAuthContext:
    def test_progressive_enrichment(self):
        # Layer 1: minimal principal
        ctx = AuthContext(principal=Principal(auth_provider_id="uid-001"))
        assert ctx.principal.auth_provider_id == "uid-001"
        assert ctx.actor is None
        assert ctx.subject is None

        # Layer 2: add actor and subject
        ctx = AuthContext(
            principal=Principal(auth_provider_id="uid-001", user_id="usr_001", email="a@b.com"),
            actor=Actor(id="usr_001", current_tenant_roles=[TenantRole.MEMBER]),
            subject=Subject(tenant_id="t-001", bu_id="bu-001"),
        )
        assert ctx.actor is not None
        assert ctx.subject.tenant_id == "t-001"
        assert ctx.has_tenant_role(TenantRole.MEMBER) is True

    def test_is_service_account(self):
        ctx = AuthContext(principal=Principal(auth_provider_id="service_account:agent_service"))
        assert ctx.is_service_account is True
        assert ctx.is_api_key_auth is False

    def test_is_api_key_auth(self):
        ctx = AuthContext(principal=Principal(auth_provider_id="api_key:usr_001"))
        assert ctx.is_api_key_auth is True
        assert ctx.is_service_account is False

    def test_delegate_methods_with_no_actor(self):
        ctx = AuthContext(principal=Principal(auth_provider_id="uid-001"))
        assert ctx.has_tenant_role(TenantRole.ADMIN) is False
        assert ctx.has_bu_role(BuRole.ADMIN) is False
        assert ctx.is_admin() is False
        assert ctx.is_tenant_admin() is False
        assert ctx.is_bu_admin() is False

    def test_regular_user_not_service_account(self):
        ctx = AuthContext(principal=Principal(auth_provider_id="firebase-uid-123"))
        assert ctx.is_service_account is False
        assert ctx.is_api_key_auth is False
