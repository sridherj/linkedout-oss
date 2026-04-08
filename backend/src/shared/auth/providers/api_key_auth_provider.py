# SPDX-License-Identifier: Apache-2.0
"""API key auth provider — bcrypt prefix lookup pattern."""
import threading
from typing import Dict, Any, Optional

import bcrypt
from sqlalchemy.orm import Session

from shared.auth.providers.base_auth_provider import BaseAuthProvider


class ApiKeyAuthProvider(BaseAuthProvider):
    """
    API key authentication via bcrypt prefix lookup.

    Pattern:
    1. Extract 8-char prefix from API key for O(1) DB lookup
    2. bcrypt verify full key against stored hash
    3. Return user info or None
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
        raise NotImplementedError(
            "Use verify_api_key(token, session) instead — API key verification needs a DB session"
        )

    def verify_api_key(self, api_key: str, session: Session) -> Optional[Dict[str, Any]]:
        """Verify API key via prefix lookup + bcrypt verify."""
        if len(api_key) < 8:
            return None

        prefix = api_key[:8]

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
            "tenant_id": getattr(user, "tenant_id", None),
        }

    def create_user(self, email: str, password: Optional[str] = None) -> str:
        raise NotImplementedError("API keys are managed through AppUser MVCS, not auth provider")

    def delete_user(self, provider_user_id: str) -> None:
        raise NotImplementedError("API keys are managed through AppUser MVCS, not auth provider")

    def update_user(self, provider_user_id: str, **kwargs) -> None:
        raise NotImplementedError("API keys are managed through AppUser MVCS, not auth provider")

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("API keys are managed through AppUser MVCS, not auth provider")
