# Version Migration Scripts

This directory contains Python scripts that run during `linkedout upgrade` when upgrading between specific versions. These scripts handle data transformations, config migrations, or other changes that can't be expressed as Alembic schema migrations.

## Naming Convention

Scripts follow the pattern: `v{from}_to_v{to}.py`

- Replace dots with underscores in version numbers
- Example: `v0_1_0_to_v0_2_0.py` (runs when upgrading from 0.1.0 to 0.2.0)

## Script Template

Each script must define a `migrate(config)` function:

```python
# SPDX-License-Identifier: Apache-2.0
"""Version migration: v0.1.0 -> v0.2.0.

Describe what this migration does and why it's needed.
"""
from loguru import logger


def migrate(config):
    """Run the version migration.

    Args:
        config: The application config object (may be None in v1).
    """
    logger.info("Running v0.1.0 -> v0.2.0 migration")
    # Your migration logic here
    logger.info("Migration complete")
```

## Execution Order

Scripts are discovered and executed in ascending version order. Only scripts whose version range falls within the upgrade range are executed.

## Important Notes

- Scripts run **after** Alembic migrations — the database schema is already at the target version.
- If a script fails, the upgrade stops and reports the error. The user gets rollback instructions.
- Scripts should be idempotent where possible — a re-run after partial failure should not corrupt data.
- The `config` parameter may be `None` in v1. Access the database through your own connection if needed.
