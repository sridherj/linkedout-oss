# SPDX-License-Identifier: Apache-2.0
"""Firebase JWT auth provider — thread-safe singleton."""
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
    # Firebase auth preserved for potential multi-user support — see Phase 0B decision.
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
