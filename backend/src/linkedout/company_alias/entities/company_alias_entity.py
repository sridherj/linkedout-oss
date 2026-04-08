# SPDX-License-Identifier: Apache-2.0
"""CompanyAlias entity -- shared (no tenant/BU scoping)."""
from typing import Optional

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from common.entities.base_entity import BaseEntity


class CompanyAliasEntity(BaseEntity):
    __tablename__ = 'company_alias'
    id_prefix = 'ca'

    alias_name: Mapped[str] = mapped_column(String, nullable=False, comment='An alternative known name for the company')
    company_id: Mapped[str] = mapped_column(
        String, ForeignKey('company.id', ondelete='CASCADE'), nullable=False, comment='Parent company this alias belongs to'
    )
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True, comment='System or provider that discovered this alias')

    __table_args__ = (
        UniqueConstraint('alias_name', 'company_id', name='uq_ca_alias_company'),
        Index('ix_ca_alias_name', 'alias_name'),
        Index('ix_ca_company_id', 'company_id'),
    )
