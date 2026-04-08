# SPDX-License-Identifier: Apache-2.0
"""AppUserTenantRole entity - maps users to tenant roles."""
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from common.entities.base_entity import BaseEntity


class AppUserTenantRoleEntity(BaseEntity):
    __tablename__ = 'app_user_tenant_role'
    id_prefix = 'autr'

    app_user_id: Mapped[str] = mapped_column(
        String, ForeignKey('app_user.id'), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(
        String, ForeignKey('tenant.id'), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
