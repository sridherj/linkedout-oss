# SPDX-License-Identifier: Apache-2.0
"""Tenant entity for multi-tenancy support."""
from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.entities.base_entity import BaseEntity


class TenantEntity(BaseEntity):
    """
    Tenant entity representing an organization.

    A tenant is the top-level organizational unit in the system.
    Domain entity relationships are auto-created via TenantBuMixin's backref.
    """
    __tablename__ = 'tenant'

    id_prefix = 'tenant'

    name: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment='The name of the tenant organization'
    )
    description: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
        comment='Optional description of the tenant'
    )

    # Only structural relationship — BU is a child of Tenant
    bu = relationship('BuEntity', back_populates='tenant', cascade='all, delete-orphan')
