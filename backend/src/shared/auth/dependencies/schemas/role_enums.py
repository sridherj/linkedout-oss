# SPDX-License-Identifier: Apache-2.0
"""Role enums for tenant and business unit access control."""
from enum import StrEnum


class TenantRole(StrEnum):
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"


class BuRole(StrEnum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    VIEWER = "VIEWER"
