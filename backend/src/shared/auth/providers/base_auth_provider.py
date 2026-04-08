# SPDX-License-Identifier: Apache-2.0
"""Abstract auth provider interface."""
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
