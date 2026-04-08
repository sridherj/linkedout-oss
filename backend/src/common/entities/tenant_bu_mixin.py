# SPDX-License-Identifier: Apache-2.0
"""Mixin for entities that belong to a tenant and Business Unit (BU)."""
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship, declared_attr


class TenantBuMixin:
    """
    Mixin for entities scoped to a tenant and business unit.

    Reverse relationships on TenantEntity/BuEntity are auto-created via backref.

    Usage:
        class MyEntity(TenantBuMixin, BaseEntity):
            id_prefix = 'my'
            # No need to edit TenantEntity or BuEntity
    """

    tenant_id = Column(
        String,
        ForeignKey('tenant.id'),
        nullable=False
    )
    bu_id = Column(
        String,
        ForeignKey('bu.id'),
        nullable=False
    )

    @declared_attr
    def tenant(cls):
        return relationship(
            'TenantEntity',
            backref=cls.__tablename__,
            foreign_keys=[cls.tenant_id],
        )

    @declared_attr
    def bu(cls):
        return relationship(
            'BuEntity',
            backref=cls.__tablename__,
            foreign_keys=[cls.bu_id],
        )
