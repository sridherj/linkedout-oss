# SPDX-License-Identifier: Apache-2.0
"""Mixin for soft delete functionality."""
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime


class SoftDeleteMixin:
    """
    Mixin to add soft delete functionality to entities.
    
    Soft delete allows marking records as deleted without actually
    removing them from the database. This is useful for:
    - Audit trails
    - Data recovery
    - Maintaining referential integrity
    
    Usage:
        class MyEntity(SoftDeleteMixin, BaseEntity):
            __tablename__ = 'my_entity'
            # Add other columns...
            
        # To soft delete:
        entity.soft_delete()
        
        # To restore:
        entity.restore()
        
        # To check if deleted:
        if entity.is_deleted:
            print('This entity is deleted')
    """
    
    # Note: deleted_at is already defined in BaseEntity
    # This mixin adds helper methods for working with it
    
    def soft_delete(self, deleted_by: str = None):
        """
        Soft delete the entity.
        
        Args:
            deleted_by: ID of the user performing the deletion
        """
        self.deleted_at = datetime.now(timezone.utc)
        if deleted_by:
            self.updated_by = deleted_by
        self.is_active = False
    
    def restore(self, restored_by: str = None):
        """
        Restore a soft-deleted entity.
        
        Args:
            restored_by: ID of the user performing the restoration
        """
        self.deleted_at = None
        if restored_by:
            self.updated_by = restored_by
        self.is_active = True
    
    @property
    def is_deleted(self) -> bool:
        """Check if the entity is soft-deleted."""
        return self.deleted_at is not None

