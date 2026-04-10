# Phase 2: Generalize MVCS Stack + TenantBu Multi-Tenancy

## Execution Context
**Depends on**: Phase 1 (DONE — linkedout copied, precommit-tests passes)
**Blocks**: Phase 3
**Parallel with**: Nothing — this is the first phase

## Goal
Generalize `common/` base classes to be domain-agnostic. Remove linkedout references from base infrastructure while keeping rcm domain code functional.

## Pre-Conditions
- `precommit-tests` passes
- All linkedout code is present in `src/rcm/`, `src/organization/`

## Post-Conditions (Definition of Done)
- `precommit-tests` passes
- Zero linkedout-specific references in `src/common/`, `src/organization/` entities, `src/shared/` infra
- `TableName` enum is a clean registry (only TENANT, BU — no `get_rcm_*` helpers)
- Base classes backward-compatible with existing rcm consumers
- Adding a new CRUD entity requires only: entity, repo, service, controller, schemas (no base class changes)

---

## Step 1: Clean Up `TableName` Enum

### File: `src/common/entities/base_entity.py`

**Action**: Remove all rcm-specific enum values (COMMODITY_MASTER through CONSUMABLE_INVENTORY) and all `get_rcm_*` helper methods. Keep only:

```python
class TableName(StrEnum):
    """Organization tables. Domain-specific tables in module-level enums."""
    TENANT = 'tenant'
    BU = 'bu'

    @classmethod
    def get_all_table_names(cls):
        return [table_name.value for table_name in cls]

    @classmethod
    def get_organization_tables(cls):
        return [cls.TENANT, cls.BU]
```

### New File: `src/rcm/common/table_names.py`

Move all rcm-specific table names here as `PackhouseTableName(StrEnum)` with all 25+ entries.

### Ripple Effects
- Grep for `from common.entities.base_entity import.*TableName` and `from common.entities import.*TableName` in `src/`
- If any file in `src/dev_tools/` imports `TableName` and uses rcm values, update to import `PackhouseTableName` from `rcm.common.table_names`
- `tests/seed_db.py` has its OWN `TableName` enum — no import chain to break
- `dev_tools/db/seed.py` does NOT import `TableName` from base_entity

### Verify
```bash
pytest tests/ -k "not integration and not live_llm" -x --tb=short
```

---

## Step 2: Switch TenantBuMixin from `back_populates` to `backref`

### File: `src/common/entities/tenant_bu_mixin.py`

**Before**: Uses `back_populates=cls.__tablename__` requiring Tenant/BU to declare all reverse relationships.

**After**:
```python
from sqlalchemy.orm import relationship, backref as sa_backref

class TenantBuMixin:
    """
    Mixin for entities scoped to a tenant and business unit.
    Reverse relationships on TenantEntity/BuEntity are auto-created via backref.
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
- `back_populates` -> `backref`
- Added `foreign_keys=` for explicitness
- May need `lazy='select'` in backref if tests break on lazy loading

### File: `src/organization/entities/tenant_entity.py`

Strip ALL domain relationship declarations (40+ lines). Keep only BU:
```python
class TenantEntity(BaseEntity):
    __tablename__ = 'tenant'
    id_prefix = 'tenant'
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bu = relationship('BuEntity', back_populates='tenant', cascade='all, delete-orphan')
```

### File: `src/organization/entities/bu_entity.py`

Strip ALL domain relationship declarations. Keep only Tenant:
```python
class BuEntity(BaseEntity):
    __tablename__ = 'bu'
    id_prefix = 'bu'
    tenant_id: Mapped[str] = mapped_column(String, ForeignKey('tenant.id', ondelete='CASCADE'), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tenant = relationship('TenantEntity', back_populates='bu')
```

### Pre-Check
```bash
# Verify no rcm entity has its own tenant/bu relationship outside the mixin
grep -rn "back_populates='tenant'\|back_populates='bu'" src/rcm/ --include="*.py" | grep -v "__pycache__"
```
If any rcm entity has a duplicate, remove it.

### Verify
```bash
python -c "
import sys; sys.path.insert(0, 'src')
from organization.entities.tenant_entity import TenantEntity
from organization.entities.bu_entity import BuEntity
from rcm.demand.entities.demand_entity import DemandEntity
print('Imports OK')
"
pytest tests/ -k "not integration and not live_llm" -x --tb=short
```

---

## Step 3: Verify `shared/` Infrastructure Has No Domain Coupling

```bash
grep -rn "rcm\|linkedout" src/shared/config/ src/shared/infra/ src/shared/common/ src/shared/utilities/ --include="*.py"
```

Clean any results found. Do NOT touch `src/shared/test_utils/` (leave for Phase 5).

---

## Step 4: Verify `common/` Exports Are Clean

```bash
grep -rn "rcm\|linkedout" src/common/ --include="*.py"
# Should return 0 results
```

No changes expected — base classes are already generic.

---

## Step 5: Full Test Suite

```bash
pytest tests/ -k "not integration and not live_llm" -x --tb=short
pytest tests/integration/ -x --tb=short
precommit-tests
```

### What to Watch For
- **RelationshipError** — backref/back_populates conflict (Step 2)
- **ImportError** — removed TableName values (Step 1)
- **AttributeError** on `TenantEntity.commodity_master` — should still work via auto-created backref

---

## Files Summary

| Action | File | Change |
|--------|------|--------|
| Modify | `src/common/entities/base_entity.py` | Strip rcm TableName entries + helpers |
| Modify | `src/common/entities/tenant_bu_mixin.py` | Switch to backref |
| Modify | `src/organization/entities/tenant_entity.py` | Strip 40+ domain relationships |
| Modify | `src/organization/entities/bu_entity.py` | Strip 40+ domain relationships |
| Create | `src/rcm/common/table_names.py` | PackhouseTableName enum |
| Modify | 0-3 files in `src/dev_tools/` | Update TableName imports if needed |

## Risks
1. **backref lazy loading** — if tests fail, add `lazy='select'` to backref: `backref=sa_backref(cls.__tablename__, lazy='select')`
2. **Duplicate relationships** — if any rcm entity declares its own tenant/bu relationship, remove it
3. **Import ordering** — conftest.py has ~40 noqa imports; they stay until Phase 8
