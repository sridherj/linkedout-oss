# Upgrading

## Check for Updates

LinkedOut checks for new versions automatically. When a newer version is available, you'll see a notification when running CLI commands:

```
A new version of LinkedOut is available: v0.2.0 (current: v0.1.0)
Run /linkedout-upgrade in your AI assistant to update.
```

This check runs at most once per hour and never blocks command execution.

You can also check manually:

```bash
linkedout version
```

---

## Upgrade

### Recommended: Use the upgrade skill

Run `/linkedout-upgrade` in your AI assistant. It handles the full upgrade process and verifies everything works afterward.

### Manual upgrade

If you prefer to upgrade manually:

**1. Pull the latest code**

```bash
cd linkedout-oss
git pull origin main
```

**2. Install updated dependencies**

```bash
uv pip install -e .
```

**3. Run database migrations**

```bash
linkedout migrate
```

This runs any pending Alembic migrations to update your database schema. Migrations are safe to run on existing data — they add new tables/columns without dropping existing ones.

**4. Verify the upgrade**

```bash
linkedout status
```

You should see the new version number and all systems reporting healthy.

---

## What's New

Check [CHANGELOG.md](../CHANGELOG.md) for a list of changes in each version. The changelog follows [Keep a Changelog](https://keepachangelog.com/) format, organized by:

- **Added** — new features
- **Changed** — changes to existing features
- **Fixed** — bug fixes
- **Removed** — removed features

---

## Rollback

If an upgrade causes problems, you can roll back to a previous version:

**1. Check out the previous version**

```bash
cd linkedout-oss
git log --oneline -10          # find the commit or tag to roll back to
git checkout v0.1.0            # or the specific tag/commit
```

**2. Reinstall dependencies**

```bash
uv pip install -e .
```

**3. Run migrations**

```bash
linkedout migrate
```

Alembic migrations handle both forward and backward schema changes.

**4. Check for errors**

If something isn't working after a rollback, check the logs:

```bash
tail -50 ~/linkedout-data/logs/cli.log
```

Run diagnostics for a full health check:

```bash
linkedout diagnostics
```

---

## Troubleshooting Upgrades

| Symptom | Cause | Fix |
|---------|-------|-----|
| `git pull` fails with merge conflicts | Local changes to tracked files | `git stash`, pull, then `git stash pop` |
| `linkedout migrate` fails | Database schema conflict | Check `~/linkedout-data/logs/cli.log` for details |
| `linkedout status` shows errors after upgrade | Missing new config values | Run `linkedout diagnostics --repair` |
| Python import errors | Stale `.pyc` files or dependency mismatch | `uv pip install -e .` to reinstall |

For more help, see [Troubleshooting](troubleshooting.md) or run `linkedout report-issue`.
