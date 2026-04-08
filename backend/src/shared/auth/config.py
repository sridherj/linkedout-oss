# SPDX-License-Identifier: Apache-2.0
"""Auth-related configuration, loaded from environment."""
from typing import Dict

from pydantic import Field
from pydantic_settings import BaseSettings


class AuthConfig(BaseSettings):
    AUTH_ENABLED: bool = Field(default=True, description="Set to False to disable auth for local dev")

    FIREBASE_ENABLED: bool = Field(default=True)
    FIREBASE_PROJECT_ID: str = Field(default="")
    FIREBASE_CREDENTIALS_PATH: str = Field(default="")

    SERVICE_ACCOUNT_TOKENS: str = Field(default="", description="Comma-separated token:name pairs")

    API_KEY_AUTH_ENABLED: bool = Field(default=False)
    API_KEY_HEADER: str = Field(default="X-API-Key")

    DEV_BYPASS_USER_ID: str = Field(default="dev-user-001")
    DEV_BYPASS_USER_EMAIL: str = Field(default="dev@localhost")
    DEV_BYPASS_USER_NAME: str = Field(default="Local Developer")
    DEV_BYPASS_TENANT_ID: str = Field(default="dev-tenant-001")
    DEV_BYPASS_BU_ID: str = Field(default="dev-bu-001")

    class Config:
        env_prefix = ""
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
