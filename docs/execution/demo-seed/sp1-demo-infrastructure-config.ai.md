# Sub-phase 1: Demo Infrastructure & Config Plumbing

## Metadata

| Field | Value |
|-------|-------|
| Sub-phase | SP1 |
| Dependencies | None |
| Estimated effort | 1 session (~3 hours) |
| Branch | main |
| Plan reference | `docs/plan/2026-04-08-demo-seed-plan.md` — Sub-phase 1 |
| Spec reference | `backend/docs/specs/onboarding-experience.md` |

## Objective

The application can detect, switch between, and persist which database mode it's in (demo vs real). A `demo_mode` flag exists in config, the `linkedout_demo` database name is a constant, and all downstream code can ask "am I in demo mode?" without touching the orchestrator or CLI yet.

## Context

LinkedOut OSS is adding a demo mode so new users can experience semantic search, affinity scoring, and the AI agent without importing their own data. This sub-phase lays the config foundation that all subsequent demo sub-phases build on.

### Key existing files

- `backend/src/shared/config/settings.py` — `LinkedOutSettings` Pydantic model (add `demo_mode` here)
- `backend/src/linkedout/setup/database.py` — Contains `_CONFIG_YAML_TEMPLATE` (add `demo_mode` line here)
- `backend/src/linkedout/setup/state.py` — `SetupState` and `save_setup_state` (atomic write pattern reference)

## Tasks

### 1. Add `demo_mode` to LinkedOutSettings

In `backend/src/shared/config/settings.py`, add `demo_mode: bool = Field(default=False)` to `LinkedOutSettings` in the "Core" section next to `database_url`. No validation needed — it's a simple boolean.

### 2. Create demo module with constants and helpers

Create `backend/src/linkedout/demo/__init__.py` with:

```python
DEMO_DB_NAME = "linkedout_demo"
DEMO_CACHE_DIR = "cache"
DEMO_DUMP_FILENAME = "demo-seed.dump"
```

Also create these helper functions in the same file:

- `is_demo_mode() -> bool` — reads from config and returns the boolean. This is the canonical check all code uses.
- `get_demo_db_url(base_url: str) -> str` — takes a database URL and replaces the database name with `linkedout_demo`. Uses simple string replacement on the URL path component.
- `set_demo_mode(data_dir: Path, enabled: bool)` — reads config.yaml, sets `demo_mode`, and writes it back. Also updates `database_url` to point at `linkedout_demo` or `linkedout` accordingly. Uses atomic write (tempfile + rename), following the pattern in `save_setup_state`.

### 3. Add `demo_mode` to config YAML template

In `backend/src/linkedout/setup/database.py`, add a `demo_mode` line to `_CONFIG_YAML_TEMPLATE`:

```
demo_mode: false          # true when using demo database
```

### 4. Write unit tests

Create `backend/tests/unit/test_demo_config.py` with:

- `test_demo_mode_default_false` — LinkedOutSettings without demo_mode set defaults to False
- `test_demo_mode_from_yaml` — LinkedOutSettings parses `demo_mode: true` from YAML correctly
- `test_get_demo_db_url` — Replaces DB name correctly in a standard postgres URL
- `test_set_demo_mode_toggles_config` — Toggles demo_mode in config.yaml and updates database_url

## Verification Checklist

- [ ] `LinkedOutSettings` has a `demo_mode: bool` field defaulting to `False`
- [ ] `config.yaml` written by setup includes `demo_mode: false`
- [ ] `get_config().demo_mode` returns the correct value based on config
- [ ] Unit test: settings parse `demo_mode: true` from YAML correctly
- [ ] The constant `DEMO_DB_NAME = "linkedout_demo"` exists in `backend/src/linkedout/demo/__init__.py`
- [ ] All unit tests pass

## Design Notes

- **Naming:** `demo_mode` follows the `snake_case` boolean pattern used by `auto_upgrade`, `debug`, `langfuse_enabled` in the same settings class.
- **Architecture:** Adding to `LinkedOutSettings` means it participates in the standard config resolution chain (env > .env > secrets.yaml > config.yaml > defaults). A user could override with `LINKEDOUT_DEMO_MODE=true` env var.
- **Config write-back:** `set_demo_mode` modifies config.yaml, same pattern as `write_config_yaml` in database.py. Atomic write (tempfile + rename) is already used by `save_setup_state`.
