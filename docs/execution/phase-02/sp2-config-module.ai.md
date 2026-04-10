# SP2: Core Config Module — `LinkedOutSettings` + Data Dirs + Secrets

**Sub-phase:** 2 of 7
**Tasks covered:** 2B (Config module), 2C (Data directory), 2D (Secrets handling)
**Size:** L (core of the phase — everything else depends on this)
**Dependencies:** None (SP1 is independent)
**Estimated effort:** 60-90 minutes

---

## Objective

Create the new `LinkedOutSettings` pydantic-settings class with YAML custom sources, data directory creation, and secrets handling. This is the foundation all other sub-phases build on.

---

## Steps

### 1. Add PyYAML Dependency

**File:** `backend/requirements.txt`

Add `PyYAML>=6.0` to the requirements file.

### 2. Check pydantic-settings Version

```bash
cd backend && pip show pydantic-settings
```

Verify it's v2+. The `settings_customise_sources` API differs between v1 and v2. Use the v2 API (class method with `settings_cls` parameter).

### 3. Create `backend/src/shared/config/yaml_sources.py`

Two custom pydantic-settings sources:

**`YamlConfigSource`:**
- Reads `{data_dir}/config/config.yaml`
- `data_dir` resolved from `LINKEDOUT_DATA_DIR` env var, defaulting to `~/linkedout-data`
- Returns empty dict if file doesn't exist
- Uses `yaml.safe_load()`

**`YamlSecretsSource`:**
- Reads `{data_dir}/config/secrets.yaml`
- Same `data_dir` resolution
- Returns empty dict if file doesn't exist
- On Unix: checks file permissions, warns to stderr if not `0600`
- Skips permission check on Windows (`os.name != 'nt'`)
- Uses `yaml.safe_load()`

Both sources must implement the pydantic-settings v2 `EnvSettingsSource` protocol (or be callables that return `dict`). Check the pydantic-settings v2 docs for the correct base class — likely need to subclass `PydanticBaseSettingsSource`.

**Reference:** `docs/decision/env-config-design.md` section "Custom YAML sources (sketch)"

### 4. Create `backend/src/shared/config/settings.py`

**`LinkedOutSettings(BaseSettings)`** with all fields from `docs/decision/env-config-design.md` "Complete Environment Variable Table".

Key implementation details:

```python
model_config = SettingsConfigDict(
    env_prefix='LINKEDOUT_',
    env_file='.env',
    env_file_encoding='utf-8',
    extra='ignore',
    case_sensitive=False,
)
```

**Fields with `validation_alias`** (industry-standard vars, no prefix):
- `database_url` — `AliasChoices('DATABASE_URL', 'database_url')`
- `openai_api_key` — `AliasChoices('OPENAI_API_KEY', 'openai_api_key')`
- `apify_api_key` — `AliasChoices('APIFY_API_KEY', 'apify_api_key')`
- `langfuse_enabled` — `AliasChoices('LANGFUSE_ENABLED', 'langfuse_enabled')`
- `langfuse_public_key` — `AliasChoices('LANGFUSE_PUBLIC_KEY', 'langfuse_public_key')`
- `langfuse_secret_key` — `AliasChoices('LANGFUSE_SECRET_KEY', 'langfuse_secret_key')`
- `langfuse_host` — `AliasChoices('LANGFUSE_HOST', 'langfuse_host')`

**Computed fields:**
- `backend_url`: if empty, compute from `f"http://{backend_host}:{backend_port}"`
- `log_dir`: if empty, compute from `f"{data_dir}/logs"`
- `metrics_dir`: if empty, compute from `f"{data_dir}/metrics"`

**Path expansion:**
- `data_dir`, `log_dir`, `metrics_dir` — expand `~` via `os.path.expanduser()`
- Use a `@model_validator(mode='after')` to expand all path fields

**`ensure_data_dirs()` method:**
- Creates the full directory tree under `data_dir`:
  ```
  config/, db/, crawled/, uploads/, logs/, queries/, reports/, metrics/, seed/, state/
  ```
- Uses `pathlib.Path.mkdir(parents=True, exist_ok=True)`
- Called in the model validator after path expansion

**`settings_customise_sources` classmethod:**
```python
@classmethod
def settings_customise_sources(cls, settings_cls, **kwargs):
    return (
        kwargs['env_settings'],
        kwargs['dotenv_settings'],
        YamlSecretsSource(settings_cls),
        YamlConfigSource(settings_cls),
        kwargs['init_settings'],
    )
```

**Flatten LLMConfig/ReliabilityConfig:** All fields that were in `LLMConfig` and `ReliabilityConfig` should be top-level fields on `LinkedOutSettings`. Read the current `config.py` to identify all fields.

### 5. Update `backend/src/shared/config/__init__.py`

Export the new settings:

```python
from .settings import LinkedOutSettings, get_config

__all__ = ['LinkedOutSettings', 'get_config']
```

### 6. Update `backend/src/shared/config/config.py` (Backward Compat Facade)

Keep `config.py` working during the transition:

```python
from .settings import LinkedOutSettings, get_config

# Backward compatibility — will be removed in Phase 6
AppConfig = LinkedOutSettings
backend_config = get_config()
```

This allows existing code that imports `backend_config` or `AppConfig` to keep working while SP5 migrates consumers.

### 7. Create `get_config()` Singleton

In `settings.py`:

```python
_settings_instance: LinkedOutSettings | None = None

def get_config() -> LinkedOutSettings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = LinkedOutSettings()
    return _settings_instance
```

---

## Verification

```bash
# PyYAML installed
python -c "import yaml; print(yaml.__version__)"

# Settings loads with env var only
DATABASE_URL=postgresql://test:test@localhost/test python -c "
from backend.src.shared.config.settings import LinkedOutSettings
s = LinkedOutSettings()
print(f'db: {s.database_url}')
print(f'data_dir: {s.data_dir}')
print(f'backend_url: {s.backend_url}')
"

# Settings loads from YAML (create temp config)
mkdir -p /tmp/test-linkedout/config
echo 'database_url: postgresql://yaml:yaml@localhost/yaml' > /tmp/test-linkedout/config/config.yaml
LINKEDOUT_DATA_DIR=/tmp/test-linkedout python -c "
from backend.src.shared.config.settings import LinkedOutSettings
s = LinkedOutSettings()
print(f'db: {s.database_url}')  # should be yaml value
"

# Env overrides YAML
LINKEDOUT_DATA_DIR=/tmp/test-linkedout DATABASE_URL=postgresql://env:env@localhost/env python -c "
from backend.src.shared.config.settings import LinkedOutSettings
s = LinkedOutSettings()
print(f'db: {s.database_url}')  # should be env value, not yaml
"

# Data dirs created
LINKEDOUT_DATA_DIR=/tmp/test-linkedout-dirs python -c "
from backend.src.shared.config.settings import LinkedOutSettings
s = LinkedOutSettings()
s.ensure_data_dirs()
"
ls /tmp/test-linkedout-dirs/  # should show config/, db/, crawled/, etc.

# Backward compat facade works
python -c "from backend.src.shared.config.config import backend_config; print(type(backend_config))"

# Secrets permission warning (Unix only)
echo 'openai_api_key: sk-test' > /tmp/test-linkedout/config/secrets.yaml
chmod 644 /tmp/test-linkedout/config/secrets.yaml
LINKEDOUT_DATA_DIR=/tmp/test-linkedout python -c "
from backend.src.shared.config.settings import LinkedOutSettings
s = LinkedOutSettings()
print(f'openai_key: {s.openai_api_key}')
" 2>&1 | grep -i "permission"  # should see warning

# Cleanup
rm -rf /tmp/test-linkedout /tmp/test-linkedout-dirs
```

---

## Acceptance Criteria

- [ ] `LinkedOutSettings` loads from env vars alone (no YAML files needed)
- [ ] `LinkedOutSettings` loads from `config.yaml` when present
- [ ] `LinkedOutSettings` loads from `secrets.yaml` when present
- [ ] Env vars override YAML values
- [ ] `~` is expanded in all path fields
- [ ] Missing `DATABASE_URL` uses default `postgresql://linkedout:@localhost:5432/linkedout`
- [ ] `PyYAML` added to requirements
- [ ] Existing `backend_config` / `get_config()` still works (returns new settings)
- [ ] Data directories created under `data_dir` on `ensure_data_dirs()` call
- [ ] `LINKEDOUT_DATA_DIR` override respected for all paths
- [ ] `secrets.yaml` permission warning emitted when not `0600`
- [ ] Missing YAML files are not errors (return empty dict)
