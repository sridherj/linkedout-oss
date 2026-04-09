# SPDX-License-Identifier: Apache-2.0
"""Base entity for all database models."""
from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base, declared_attr

from shared.common.nanoids import Nanoid

Base = declarative_base()


class BaseEntity(Base):
    """
    Base class for all entities.
    
    This abstract base class provides common fields and functionality for all
    database entities in the application. It includes:
    - Primary key with nanoid-based IDs with prefix
    - Timestamp fields (created_at, updated_at)
    - Soft delete support (deleted_at)
    - Audit fields (created_by, updated_by)
    - Active status flag
    - Version field for optimistic locking
    - Source tracking
    - Notes field for additional information
    
    Subclasses should:
    - Set __abstract__ = False (or omit it)
    - Define id_prefix class variable for nanoid prefix
    - Add their specific columns and relationships
    """
    
    __abstract__ = True
    
    # Entity ID prefix is a data-format constant. Changing it would break existing
    # records. Not user-configurable. Subclasses set this (e.g., 'conn', 'co').
    id_prefix: str = None
    
    @declared_attr
    def __tablename__(cls):
        """
        Auto-generate table name from class name.
        
        Converts CamelCase to snake_case and removes 'Entity' suffix.
        Example: ProjectEntity -> project
        """
        import re
        name = cls.__name__
        if name.endswith('Entity'):
            name = name[:-6]
        
        # Convert CamelCase to snake_case
        name = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
        return name
    
    @declared_attr
    def id(cls):
        """
        Primary key column with default value.
        
        Uses nanoid with prefix if id_prefix is defined,
        otherwise uses plain nanoid.
        """
        if cls.id_prefix:
            default = lambda: Nanoid.make_nanoid_with_prefix(cls.id_prefix)
        else:
            default = lambda: Nanoid.make_nanoid()
        return Column(String, primary_key=True, default=default)

    created_at = Column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc), 
        nullable=False
    )
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String, nullable=True)
    updated_by = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, server_default='true', nullable=False)
    version = Column(Integer, default=1, server_default='1', nullable=False)
    source = Column(String, nullable=True)
    notes = Column(Text, nullable=True)


class TableName(StrEnum):
    """Organization and domain tables."""
    TENANT = 'tenant'
    BU = 'bu'
    # Organization (auth)
    APP_USER = 'app_user'
    APP_USER_TENANT_ROLE = 'app_user_tenant_role'
    ENRICHMENT_CONFIG = 'enrichment_config'
    # LinkedOut domain
    COMPANY = 'company'
    ROLE_ALIAS = 'role_alias'
    # Funding / startup pipeline
    FUNDING_ROUND = 'funding_round'
    GROWTH_SIGNAL = 'growth_signal'
    STARTUP_TRACKING = 'startup_tracking'

    @classmethod
    def get_all_table_names(cls):
        """Get list of all table names."""
        return [table_name.value for table_name in cls]

    @classmethod
    def get_organization_tables(cls):
        """Get organization table names."""
        return [cls.TENANT, cls.BU]


