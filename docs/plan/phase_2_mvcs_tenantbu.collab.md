# Phase 2: Generalize MVCS Stack + TenantBu Multi-Tenancy — Detailed Execution Plan

## Goal
Generalize the `common/` base classes to be domain-agnostic. Remove all linkedout/rcm references from base infrastructure while keeping rcm domain code functional as the test consumer.

## Pre-Conditions
- Phase 1 DONE: linkedout-agent copied wholesale into reference_code_v2
- `precommit-tests` passes (unit + integration + live_llm)

## Post-Conditions (Definition of Done)
- `precommit-tests` passes
- Zero linkedout-specific references in `src/common/`, `src/organization/` entities, `src/shared/` infra
- `TableName` enum is a clean registry (no `get_rcm_*` helpers)
- Base classes remain backward-compatible with existing rcm consumers
- Adding a new CRUD entity requires only: entity, repo, service, controller, schemas (no base class changes)

---

## Key Findings from Code Review

### What's Already Generic (No Changes Needed)
| File | Status |
|------|--------|
| `src/common/entities/soft_delete_mixin.py` | Clean — no domain refs |
| `src/common/repositories/base_repository.py` | Clean — uses `TEntity` generics, `FilterSpec` is generic |
| `src/common/services/base_service.py` | Clean — uses `TEntity`, `TSchema`, `TRepository` generics |
| `src/common/controllers/crud_router_factory.py` | Clean — uses `CRUDRouterConfig`, no domain refs |
| `src/common/controllers/base_controller_utils.py` | Clean — generic pagination + service dependency |
| `src/common/schemas/base_request_schema.py` | Clean |
| `src/common/schemas/base_response_schema.py` | Clean |
| `src/common/schemas/base_enums_schemas.py` | Clean |
| `src/common/schemas/crud_schema_mixins.py` | Clean |

### What Needs Changes
| File | Issue |
|------|-------|
| `src/common/entities/base_entity.py` | `TableName` enum has 25+ rcm entries and `get_rcm_*` helpers |
| `src/common/entities/tenant_bu_mixin.py` | Uses `back_populates` requiring Tenant/BU to declare all reverse relationships |
| `src/organization/entities/tenant_entity.py` | 40+ explicit relationship declarations to rcm domain entities |
| `src/organization/entities/bu_entity.py` | 40+ explicit relationship declarations to rcm domain entities |

### Important Observations
1. **`CRUDRouterFactory` is NOT used by any rcm entity** — all rcm controllers are manual. The factory exists but has zero consumers. It will get its first real consumer in Phase 3.
2. **`tests/seed_db.py` has its OWN `TableName` enum** — independent of `base_entity.TableName`. No import chain to break.
3. **`dev_tools/db/seed.py` does NOT import `TableName` from base_entity** — uses `BaseSeeder` + `EntityFactory` directly.
4. **`FilterSpec` already supports all R3 filter types**: eq, in, ilike, bool, gte, lte, jsonb_overlap.
5. **Schema mixins are complete** but rcm entities don't use them (they inline tenant_id/bu_id). Phase 3's new domain will use the mixins properly.

---

## Step 1: Clean Up `TableName` Enum

### File: `src/common/entities/base_entity.py`

**Current state** (lines 91-180): `TableName` has 25+ rcm-specific enum values and 5 helper methods (`get_rcm_tables()`, `get_rcm_demand_tables()`, etc.).

**Changes**:
1. Remove all rcm-specific enum values (COMMODITY_MASTER through CONSUMABLE_INVENTORY)
2. Remove all `get_rcm_*` helper methods
3. Keep: TENANT, BU, `get_all_table_names()`, `get_organization_tables()`

**After** (`base_entity.py` lines 91+):
```python
class TableName(StrEnum):
    """
    Enum for table names in the database.

    Organization tables are registered here. Domain-specific tables
    should be registered in their own module-level enums.
    """
    # Organization
    TENANT = 'tenant'
    BU = 'bu'

    @classmethod
    def get_all_table_names(cls):
        """Get list of all table names."""
        return [table_name.value for table_name in cls]

    @classmethod
    def get_organization_tables(cls):
        """Get organization table names."""
        return [cls.TENANT, cls.BU]
```

### New file: `src/rcm/common/table_names.py`
```python
"""Packhouse-specific table name registry."""
from enum import StrEnum


class PackhouseTableName(StrEnum):
    """Table names for rcm domain entities (dependency order)."""
    # Common / Masters
    COMMODITY_MASTER = 'commodity_master'
    VARIETY_MASTER = 'variety_master'
    GRADE_SIZE_MASTER = 'grade_size_master'
    PACK_SPEC_MASTER = 'pack_spec_master'
    SKU_MASTER = 'sku_master'
    # Inventory
    LOT = 'lot'
    BIN = 'bin'
    STORAGE_ROOM = 'storage_room'
    QUALITY_ASSESSMENT = 'quality_assessment'
    GRADE_ASSESSMENT = 'grade_assessment'
    SIZE_ASSESSMENT = 'size_assessment'
    # Demand
    ORDER = 'order'
    DEMAND = 'demand'
    # Planner
    INVENTORY_ASSESSMENT = 'inventory_assessment'
    # Resources
    WORKER = 'worker'
    MACHINE = 'machine'
    WORKER_SKILL = 'worker_skill'
    WORKER_ATTENDANCE = 'worker_attendance'
    WORKER_ROSTER = 'worker_roster'
    WORKER_SHIFT_LOG = 'worker_shift_log'
    WORKER_AVAILABILITY_FORECAST = 'worker_availability_forecast'
    MACHINE_SHIFT_ACTIVITY = 'machine_shift_activity'
    MACHINE_AVAILABILITY = 'machine_availability'
    MACHINE_DOWNTIME_FORECAST = 'machine_downtime_forecast'
    MAINTENANCE_SCHEDULE = 'maintenance_schedule'
    DOWNTIME_LOG = 'downtime_log'
    CONSUMABLE_INVENTORY = 'consumable_inventory'
```

### Ripple effects to check
1. **`src/dev_tools/db/fixed_data.py`** — grep for `TableName` import from `common.entities.base_entity`
2. **`src/dev_tools/db/validate_orm.py`** — grep for `TableName` import
3. **Any other imports of `TableName` from `common.entities`** — update to use `PackhouseTableName` if they reference rcm tables

If any file in `src/dev_tools/` imports `TableName` from `base_entity` and uses rcm values, update to import from `rcm.common.table_names` instead.

### Files to check (grep targets)
```bash
grep -rn "from common.entities.base_entity import.*TableName\|from common.entities import.*TableName" src/ --include="*.py"
```

### Verify
```bash
pytest tests/ -k "not integration and not live_llm" -x --tb=short
```

---

## Step 2: Decouple Tenant/BU from Domain Entities via `backref`

### Problem
`TenantEntity` has 40+ relationship declarations like:
```python
commodity_master = relationship('CommodityMasterEntity', back_populates='tenant')
lot = relationship('LotEntity', back_populates='tenant')
# ... 38 more
```
Same for `BuEntity`. This means adding ANY new domain entity requires editing Tenant and BU files.

### Solution: Switch `TenantBuMixin` from `back_populates` to `backref`

**How it works**:
- `back_populates` requires BOTH sides to declare the relationship explicitly
- `backref` auto-creates the reverse relationship on the related model
- Switching to `backref` in the mixin means TenantEntity/BuEntity no longer need explicit declarations

### File: `src/common/entities/tenant_bu_mixin.py`

**Before** (current):
```python
class TenantBuMixin:
    tenant_id = Column(String, ForeignKey('tenant.id'), nullable=False)
    bu_id = Column(String, ForeignKey('bu.id'), nullable=False)

    @declared_attr
    def tenant(cls):
        return relationship('TenantEntity', back_populates=cls.__tablename__)

    @declared_attr
    def bu(cls):
        return relationship('BuEntity', back_populates=cls.__tablename__)
```

**After**:
```python
class TenantBuMixin:
    """
    Mixin for entities scoped to a tenant and business unit.

    Provides tenant_id and bu_id foreign keys plus relationships.
    The reverse relationships on TenantEntity/BuEntity are auto-created
    via backref (named by the entity's __tablename__).

    Usage:
        class MyEntity(TenantBuMixin, BaseEntity):
            id_prefix = 'my'
            # No need to edit TenantEntity or BuEntity
    """
    tenant_id = Column(String, ForeignKey('tenant.id'), nullable=False)
    bu_id = Column(String, ForeignKey('bu.id'), nullable=False)

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
```

**Key changes**:
- `back_populates=cls.__tablename__` -> `backref=cls.__tablename__`
- Added `foreign_keys=[cls.tenant_id]` / `foreign_keys=[cls.bu_id]` for explicitness (avoids ambiguity if entity has multiple FKs to tenant)

### File: `src/organization/entities/tenant_entity.py`

**Before**: 87 lines with 40+ domain relationship declarations.

**After** (strip ALL domain relationships, keep only BU):
```python
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
        String, nullable=False,
        comment='The name of the tenant organization'
    )
    description: Mapped[Optional[str]] = mapped_column(
        String, nullable=True,
        comment='Optional description of the tenant'
    )

    # Only structural relationship — BU is a child of Tenant
    bu = relationship('BuEntity', back_populates='tenant', cascade='all, delete-orphan')
```

### File: `src/organization/entities/bu_entity.py`

**Before**: 97 lines with 40+ domain relationship declarations.

**After** (strip ALL domain relationships, keep only Tenant):
```python
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
        String, ForeignKey('tenant.id', ondelete='CASCADE'), nullable=False,
        comment='Foreign key to the parent tenant'
    )
    name: Mapped[str] = mapped_column(
        String, nullable=False,
        comment='The name of the business unit'
    )
    description: Mapped[Optional[str]] = mapped_column(
        String, nullable=True,
        comment='Optional description of the business unit'
    )

    # Only structural relationship — Tenant is the parent
    tenant = relationship('TenantEntity', back_populates='bu')
```

### Potential Conflict: `backref` vs existing `back_populates`

There's a subtle risk: if any rcm entity uses both `TenantBuMixin` (which now uses `backref`) AND its own explicit `back_populates='tenant'`, SQLAlchemy may error because both `backref` and `back_populates` try to create the same attribute.

**Check**: The mixin already provides the `tenant` and `bu` relationships. Individual domain entities (like `DemandEntity`) inherit them via the mixin — they do NOT declare their own `tenant`/`bu` relationships. So there should be no conflict.

**But verify this assumption**:
```bash
grep -rn "back_populates='tenant'\|back_populates='bu'" src/rcm/ --include="*.py" | grep -v "__pycache__"
```

If any rcm entity has its own `tenant = relationship(...)` separate from the mixin, it must be removed.

### Verify
```bash
# Quick smoke test
python -c "
import sys; sys.path.insert(0, 'src')
from organization.entities.tenant_entity import TenantEntity
from organization.entities.bu_entity import BuEntity
from rcm.demand.entities.demand_entity import DemandEntity
print('Imports OK')
"

# Full unit tests
pytest tests/ -k "not integration and not live_llm" -x --tb=short
```

---

## Step 3: Verify `shared/` Infrastructure Has No Domain Coupling

### Files to check
| File | Expected |
|------|----------|
| `src/shared/config/config.py` | Should be generic — check for rcm/linkedout refs |
| `src/shared/infra/db/db_session_manager.py` | Should be generic |
| `src/shared/common/nanoids.py` | Should be generic |
| `src/shared/utilities/logger.py` | Should be generic |

### Command
```bash
grep -rn "rcm\|linkedout" src/shared/config/ src/shared/infra/ src/shared/common/ src/shared/utilities/ --include="*.py"
```

### What NOT to touch
- `src/shared/test_utils/entity_factories.py` — 50+ rcm entity factories. Leave for Phase 3.
- `src/shared/test_utils/seeders/` — rcm entity ordering. Leave for Phase 3.

### Decision
If `shared/config/`, `shared/infra/`, `shared/common/`, or `shared/utilities/` have linkedout references: clean them. If only `shared/test_utils/` has them: leave it.

### Verify
```bash
grep -rn "rcm\|linkedout" src/shared/ --include="*.py" | grep -v "test_utils"
# Should return 0 results after cleanup
```

---

## Step 4: Verify All `common/` Exports Are Clean

### File: `src/common/entities/__init__.py`

**Current exports**: `['Base', 'BaseEntity', 'TableName', 'SoftDeleteMixin', 'TenantBuMixin']`

After Step 1, `TableName` still exists (with only TENANT, BU) — exports stay the same.

### File: `src/common/repositories/__init__.py`

**Current exports**: `['BaseRepository', 'FilterSpec']` — no changes needed.

### All `common/` `__init__.py` files
No changes needed unless they import rcm-specific things.

```bash
grep -rn "rcm\|linkedout" src/common/ --include="*.py"
# Should return 0 results after Steps 1-2
```

---

## Step 5: Run Full Test Suite

### Verification sequence
```bash
# 1. Unit tests (SQLite, fast)
pytest tests/ -k "not integration and not live_llm" -x --tb=short

# 2. Integration tests (PostgreSQL)
pytest tests/integration/ -x --tb=short

# 3. Full precommit suite
precommit-tests
```

### What to watch for
- **`RelationshipError`** — most likely from backref/back_populates conflict (Step 2)
- **`ImportError`** — from removed TableName values (Step 1)
- **`AttributeError`** on `TenantEntity.commodity_master` etc. — test code accessing removed relationships. These should now be auto-created by `backref`, so they should still work.

---

## Execution Order Summary

| Order | Step | Files Changed | Files Created | Risk | Key Test |
|-------|------|--------------|---------------|------|----------|
| 1 | Clean `TableName` enum | `src/common/entities/base_entity.py` | `src/rcm/common/table_names.py` | Low | `pytest tests/ -k "not integration"` |
| 2 | Switch mixin to `backref` + strip Tenant/BU relationships | `tenant_bu_mixin.py`, `tenant_entity.py`, `bu_entity.py` | — | **Medium** | Same + watch for RelationshipError |
| 3 | Verify `shared/` infra is clean | 0-2 files in `shared/` | — | Low | grep check |
| 4 | Verify `common/` exports | 0 files | — | None | import check |
| 5 | Full test suite | — | — | — | `precommit-tests` |

---

## Risks and Mitigations

### Risk 1: `backref` vs `back_populates` compatibility
**Issue**: If any rcm entity explicitly declares `tenant = relationship(...)` outside of `TenantBuMixin`, the `backref` will conflict.
**Mitigation**: grep for `back_populates='tenant'` in rcm before changing. If found, remove the duplicate declaration.

### Risk 2: Test code accessing `TenantEntity.lot`, `TenantEntity.demand`, etc.
**Issue**: Integration tests or seed code may do `tenant.demand` to navigate relationships.
**Expected behavior**: `backref` auto-creates these attributes, so `tenant.demand` still works.
**Mitigation**: If tests break, the backref approach is verified correct — debug the specific failure.

### Risk 3: SQLAlchemy lazy loading changes with backref
**Issue**: `backref` creates a `dynamic` relationship by default vs `back_populates` using `select` (lazy load).
**Mitigation**: Explicitly pass `lazy='select'` in the backref if needed:
```python
backref=backref(cls.__tablename__, lazy='select')
```
Need to import `from sqlalchemy.orm import backref` in the mixin.

### Risk 4: Import ordering in conftest.py
**Issue**: SQLAlchemy needs all entities imported before `Base.metadata.create_all()`. Current `conftest.py` has ~40 noqa imports.
**Expected**: No change needed — those imports stay until Phase 3.

---

## What This Phase Does NOT Do (Deferred)

| Deferred Work | Phase |
|---------------|-------|
| Replace rcm domain entities | Phase 3 |
| Refactor test infrastructure / seeders / entity_factories | Phase 3 |
| Add new project-management entities | Phase 3 |
| Touch auth | Phase 4 |
| Create new Alembic migrations | Phase 3/7 |
| Refactor main.py router imports | Phase 3 |
| Add TenantWorkspace or TenantAppUser alternatives | Documented per R1, not built |
| Refactor rcm schemas to use mixins | Phase 3 |
| Get `CRUDRouterFactory` its first consumer | Phase 3 |

---

## Total Estimated Changes

| Type | Count |
|------|-------|
| Files modified | 4 (`base_entity.py`, `tenant_bu_mixin.py`, `tenant_entity.py`, `bu_entity.py`) |
| Files created | 1 (`src/rcm/common/table_names.py`) |
| Files deleted | 0 |
| Lines added | ~50 (PackhouseTableName enum + backref imports) |
| Lines removed | ~130 (relationship declarations + rcm helpers from TableName) |

**This is a small, focused phase.** The base classes are already well-generalized. The main work is cleaning linkedout coupling from `TableName` and decoupling Tenant/BU entities from domain relationships via `backref`.
