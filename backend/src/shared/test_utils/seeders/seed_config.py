# SPDX-License-Identifier: Apache-2.0
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class SeedConfig(BaseModel):
    """Configuration for database seeding."""
    
    # List of tables/entities to seed. If empty, nothing is seeded.
    # Use '*' to indicate all supported entities.
    tables: List[str] = Field(default_factory=list)
    
    # Counts for generating random entities.
    # For top-level entities (like Tenant), this is the total count.
    # For child entities (like BU), this can be interpreted as count per parent
    # or total count depending on the seeder implementation.
    # Default assumption: count per parent for child entities to ensure density.
    counts: Dict[str, int] = Field(default_factory=dict)
    
    # ID prefix for generated entities (useful for integration tests to avoid collisions)
    id_prefix: str = ""
    
    # Whether to seed fixed data (e.g. from fixed_data.py)
    include_fixed: bool = True
    
    # Specific overrides or configuration per entity type
    # e.g. {'label': {'include_fixed': True}}
    entity_configs: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    def get_count(self, entity_type: str, default: int = 0) -> int:
        """Get the number of random entities to generate for a type."""
        return self.counts.get(entity_type, default)

    def should_seed(self, entity_type: str) -> bool:
        """Check if an entity type should be seeded."""
        if '*' in self.tables:
            return True
        return entity_type in self.tables

class DevSeedConfig(SeedConfig):
    """Configuration for development seeding with sensible defaults."""
    def __init__(self, **data):
        if 'tables' not in data:
            data['tables'] = ['*']
        super().__init__(**data)
        
        # Default counts for dev seeding
        defaults = {
            'tenant': 3,
            'bu': 2,             # per tenant
            'app_user': 2,
            'app_user_tenant_role': 2,
            'agent_run': 2,
            'company': 2,
            'company_alias': 2,
            'role_alias': 2,
            'crawled_profile': 3,
            'experience': 2,
            'education': 1,
            'profile_skill': 3,
            'connection': 2,
            'import_job': 1,
            'contact_source': 2,
            'enrichment_event': 1,
        }
        for k, v in defaults.items():
            if k not in self.counts:
                self.counts[k] = v

class IntegrationSeedConfig(SeedConfig):
    """Configuration for integration tests."""
    def __init__(self, **data):
        # Use fixed data - simpler, deterministic, and well-tested
        # The isolated test schema already provides separation from dev data
        if 'include_fixed' not in data:
            data['include_fixed'] = True
        super().__init__(**data)

        # Integration tests usually want specific control, so minimal defaults
        if not self.id_prefix:
            self.id_prefix = "int_"
