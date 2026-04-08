# Development Tools

This directory contains utility scripts for development and testing.

## 📂 Directory Structure

```
dev_tools/
├── db/                    # Database-related tools
│   ├── seed.py           # Seed database with sample data
│   ├── reset_db.py       # Reset database (drop + migrate)
│   └── validate_orm.py   # Validate ORM configuration
└── README.md             # This file
```

## 🛠️ Database Tools

### Seed Database (`db/seed.py`)

Seeds the database with sample data for development and testing.

**Usage:**
```bash
python dev_tools/db/seed.py
```

**What it creates:**
- 2 tenants (Acme Corporation, GlobalTech Inc)
- 3 workspaces (Engineering, Marketing, Product)
- 7 projects across the workspaces
- Multiple tasks for each project

**When to use:**
- After running migrations on a fresh database
- When you need sample data for manual testing
- To populate a development database

### Reset Database (`db/reset_db.py`)

Drops all tables and recreates them from migrations. **CAUTION: Deletes all data!**

**Usage:**
```bash
# Interactive (asks for confirmation)
python dev_tools/db/reset_db.py

# Auto-confirm (for scripts/CI)
python dev_tools/db/reset_db.py --yes

# Reset and seed in one command
python dev_tools/db/reset_db.py --yes --seed
```

**What it does:**
1. Asks for confirmation (unless --yes flag is used)
2. Drops all tables in the database
3. Runs Alembic migrations to recreate tables
4. Optionally seeds the database with sample data

**When to use:**
- When you want to start fresh with a clean database
- After making major schema changes
- To test migrations from scratch
- In CI/CD pipelines (with --yes flag)

**Flags:**
- `--yes`: Skip confirmation prompt (use with caution!)
- `--seed`: Automatically seed after reset

### Validate ORM (`db/validate_orm.py`)

Validates that all SQLAlchemy entities and relationships are properly configured.

**Usage:**
```bash
python dev_tools/db/validate_orm.py
```

**What it checks:**
- ✅ All entities can be imported
- ✅ All mappers can be configured without errors
- ✅ All relationships are properly configured
- ✅ All foreign keys reference valid tables/columns
- ✅ All `back_populates` relationships are bidirectional

**Output:**
- Console output with validation results
- `orm_relationship_report.txt` with detailed relationship information

**When to use:**
- After adding new entities
- After modifying relationships
- Before generating migrations
- In pre-commit hooks (automated)
- When debugging relationship issues

**Exit codes:**
- `0`: All validations passed
- `1`: One or more validations failed

## 🔄 Common Workflows

### Starting Fresh

```bash
# 1. Reset database (creates tables)
python dev_tools/db/reset_db.py --yes --seed

# 2. Start the server
python main.py
```

### After Adding a New Entity

```bash
# 1. Validate ORM configuration
python dev_tools/db/validate_orm.py

# 2. Generate migration
alembic revision --autogenerate -m "Add new entity"

# 3. Review the generated migration

# 4. Apply migration
alembic upgrade head

# 5. Update seed.py if needed

# 6. Test with fresh database
python dev_tools/db/reset_db.py --yes --seed
```

### Daily Development

```bash
# Just seed new data (keeps existing data)
python dev_tools/db/seed.py

# Or reset and seed for a clean slate
python dev_tools/db/reset_db.py --yes --seed
```

### CI/CD Pipeline

```bash
# In your CI script:
python dev_tools/db/reset_db.py --yes
python dev_tools/db/validate_orm.py
pytest
```

## 📝 Environment Variables

These tools respect the same environment variables as the main application:

- `DATABASE_URL`: Database connection string
- `ENVIRONMENT`: Environment name (dev, test, prod)

**Note:** For tests, these are automatically set in `conftest.py`.

## ⚠️ Safety Notes

### reset_db.py
- **NEVER** run in production!
- Always backup data before running
- Use `--yes` flag only in automated scripts where you're sure
- The script shows the DATABASE_URL before confirming

### seed.py
- Safe to run multiple times (creates new records each time)
- May create duplicate data if run repeatedly
- Use `reset_db.py` first if you want a clean slate

### validate_orm.py
- Safe to run anytime (read-only)
- No database modifications
- Can be run in pre-commit hooks

## 🎯 Best Practices

1. **Run validate_orm.py** before generating migrations
2. **Seed after reset** to always have test data
3. **Add new entities to ALL_ENTITIES** in validate_orm.py
4. **Update seed.py** when adding new entity types
5. **Use reset_db.py --yes --seed** for quick development resets
6. **Never use --yes in production environments**

## 🔍 Troubleshooting

### "Alembic not found"
```bash
pip install alembic
```

### "No module named 'shared'"
```bash
# Make sure you're running from the project root
cd /path/to/sample_backend
python dev_tools/db/seed.py
```

### "Database connection refused"
```bash
# Check your DATABASE_URL in .env
cat .env | grep DATABASE_URL

# For PostgreSQL, ensure it's running
pg_isready
```

### "Foreign key constraint failed"
```bash
# Check entity relationships with validate_orm
python dev_tools/db/validate_orm.py

# Or reset database completely
python dev_tools/db/reset_db.py --yes
```

## 🚀 Adding New Tools

When adding new development tools:

1. Create the script in the appropriate subdirectory
2. Add `if __name__ == "__main__":` guard
3. Use the logger from `shared.utilities.logger`
4. Add usage documentation to this README
5. Make the script executable: `chmod +x tool.py`
6. Test with both success and failure cases

## 📚 Related Documentation

- [README.md](../README.md) - Main project documentation
- [ENV_FILES.md](../ENV_FILES.md) - Environment configuration
- [QUICKSTART.md](../QUICKSTART.md) - Quick setup guide

---

**Questions?** Check the inline documentation in each script or the main README.

