# SPDX-License-Identifier: Apache-2.0
"""RoleAlias entity -- shared (no tenant/BU scoping)."""
from typing import Optional

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from common.entities.base_entity import BaseEntity


class RoleAliasEntity(BaseEntity):
    __tablename__ = 'role_alias'
    id_prefix = 'ra'

    alias_title: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    canonical_title: Mapped[str] = mapped_column(String(255), nullable=False)
    seniority_level: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    function_area: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        Index('ix_ra_alias_title', 'alias_title', unique=True),
        Index('ix_ra_canonical_title', 'canonical_title'),
        Index('ix_ra_seniority_level', 'seniority_level'),
        Index('ix_ra_function_area', 'function_area'),
    )
