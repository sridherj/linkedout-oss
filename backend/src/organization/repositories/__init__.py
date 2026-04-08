# SPDX-License-Identifier: Apache-2.0
"""Organization domain repositories."""
from organization.repositories.tenant_repository import TenantRepository
from organization.repositories.bu_repository import BuRepository

__all__ = [
    'TenantRepository',
    'BuRepository',
]
