# SPDX-License-Identifier: Apache-2.0
"""Business unit entity for organizing resources within a tenant."""
from typing import Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.entities.base_entity import BaseEntity


class BuEntity(BaseEntity):
    """
    BU entity for organizing resources within a tenant.

    Domain entity relationships are auto-created via TenantBuMixin's backref.
    """
    __tablename__ = 'bu'

    id_prefix = 'bu'

    tenant_id: Mapped[str] = mapped_column(
        String,
        ForeignKey('tenant.id', ondelete='CASCADE'),
        nullable=False,
        comment='Foreign key to the parent tenant'
    )
    name: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment='The name of the business unit'
    )
    description: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
        comment='Optional description of the business unit'
    )

    # Only structural relationship — Tenant is the parent
    tenant = relationship('TenantEntity', back_populates='bu')
