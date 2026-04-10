# SP7: Test Infrastructure + Integration Verification

**Sub-phase:** 7 of 7
**Tasks covered:** 2J + Phase exit criteria verification
**Size:** M
**Dependencies:** SP2-SP6 (all must be complete — this is the final verification)
**Estimated effort:** 45-60 minutes

---

## Objective

Update test fixtures and conftest to work with the new config system. Write unit tests for the new config module. Verify all phase exit criteria.

**Agent/skill references:**
- `.claude/skills/pytest-best-practices/SKILL.md` — Follow naming conventions, AAA pattern, fixture organization
- `.claude/agents/integration-test-creator-agent.md` — Reference for session-scoped DB fixtures, `test_client` setup, config test patterns

---

## Steps

### 1. Update `backend/conftest.py`

The current `conftest.py` (682 lines) has extensive env var setup. Update it to work with the new config system:

**1a. Replace env var setup:**
- Set `LINKEDOUT_DATA_DIR` to a temp directory (use `tmp_path` fixture or `tempfile.mkdtemp()`)
- Set `DATABASE_URL` via env var or test config
- Remove any references to `ENVIRONMENT`, `.env.local`, `.env.test`, `.env.prod`

**1b. Add config reset fixture:**
```python
@pytest.fixture(autouse=True)
def reset_config():
    """Reset the config singleton between tests."""
    from shared.config.settings import _settings_instance
    import shared.config.settings as settings_module
    settings_module._settings_instance = None
    yield
    settings_module._settings_instance = None
```

**1c. Add temp data dir fixture:**
```python
@pytest.fixture
def data_dir(tmp_path):
    """Provide a temp data directory for tests."""
    os.environ['LINKEDOUT_DATA_DIR'] = str(tmp_path)
    yield tmp_path
    os.environ.pop('LINKEDOUT_DATA_DIR', None)
```

**1d. Ensure no test writes to `~/linkedout-data/`:**
- All tests that create settings must use the `data_dir` fixture or set `LINKEDOUT_DATA_DIR` to a temp path
- Add a check in conftest that `~/linkedout-data/` is not in the test data dir

### 2. Update `backend/pytest.ini` (if needed)

If pytest.ini sets env vars like `ENVIRONMENT=test`, update to new names:
```ini
[pytest]
env =
    LINKEDOUT_ENVIRONMENT=test
    LINKEDOUT_DATA_DIR=/tmp/linkedout-test
    DATABASE_URL=postgresql://linkedout:test@localhost:5432/linkedout_test
```

Or use `pytest-env` / env setup in conftest if pytest.ini doesn't support this.

### 3. Write Config Module Unit Tests

Create `backend/tests/shared/config/test_settings.py` (or appropriate test path):

**3a. Config loading tests:**
```python
def test_loads_from_env_vars_only(data_dir):
    """Settings loads with just env vars, no YAML."""
    os.environ['DATABASE_URL'] = 'postgresql://test:test@localhost/test'
    s = LinkedOutSettings()
    assert s.database_url == 'postgresql://test:test@localhost/test'

def test_loads_from_yaml_only(data_dir):
    """Settings loads from config.yaml when present."""
    config_dir = data_dir / 'config'
    config_dir.mkdir()
    (config_dir / 'config.yaml').write_text('database_url: postgresql://yaml@localhost/yaml')
    s = LinkedOutSettings()
    assert 'yaml' in s.database_url

def test_env_overrides_yaml(data_dir):
    """Env vars take precedence over YAML values."""
    config_dir = data_dir / 'config'
    config_dir.mkdir()
    (config_dir / 'config.yaml').write_text('database_url: postgresql://yaml@localhost/yaml')
    os.environ['DATABASE_URL'] = 'postgresql://env@localhost/env'
    s = LinkedOutSettings()
    assert 'env' in s.database_url
```

**3b. YAML sources tests:**
```python
def test_yaml_config_source_missing_file(data_dir):
    """Missing config.yaml returns empty dict."""
    # No config.yaml created — should not error

def test_yaml_secrets_source_missing_file(data_dir):
    """Missing secrets.yaml returns empty dict."""
    # No secrets.yaml created — should not error

def test_yaml_secrets_permission_warning(data_dir, capsys):
    """Warns if secrets.yaml permissions are too open."""
    config_dir = data_dir / 'config'
    config_dir.mkdir()
    secrets_path = config_dir / 'secrets.yaml'
    secrets_path.write_text('openai_api_key: sk-test')
    secrets_path.chmod(0o644)  # too open
    s = LinkedOutSettings()
    # Check stderr for warning
```

**3c. Validation tests:**
```python
def test_invalid_port_rejected(data_dir):
    os.environ['LINKEDOUT_BACKEND_PORT'] = '99999'
    with pytest.raises(ValidationError):
        LinkedOutSettings()

def test_invalid_log_level_rejected(data_dir):
    os.environ['LINKEDOUT_LOG_LEVEL'] = 'TRACE'
    with pytest.raises(ValidationError):
        LinkedOutSettings()

def test_log_level_case_insensitive(data_dir):
    os.environ['LINKEDOUT_LOG_LEVEL'] = 'debug'
    s = LinkedOutSettings()
    assert s.log_level == 'DEBUG'

def test_openai_key_required_when_openai_provider(data_dir):
    os.environ['LINKEDOUT_EMBEDDING_PROVIDER'] = 'openai'
    # Do NOT set OPENAI_API_KEY
    with pytest.raises(ValidationError):
        LinkedOutSettings()

def test_openai_key_not_required_when_local_provider(data_dir):
    os.environ['LINKEDOUT_EMBEDDING_PROVIDER'] = 'local'
    s = LinkedOutSettings()  # should not raise
```

**3d. Path expansion tests:**
```python
def test_tilde_expansion(data_dir):
    os.environ['LINKEDOUT_DATA_DIR'] = '~/test-linkedout'
    s = LinkedOutSettings()
    assert '~' not in s.data_dir
    assert os.path.expanduser('~') in s.data_dir

def test_custom_data_dir(data_dir):
    s = LinkedOutSettings()
    assert str(data_dir) in s.data_dir
```

**3e. Data directory tests:**
```python
def test_ensure_data_dirs_creates_tree(data_dir):
    s = LinkedOutSettings()
    s.ensure_data_dirs()
    for subdir in ['config', 'db', 'crawled', 'uploads', 'logs', 'queries', 'reports', 'metrics', 'seed', 'state']:
        assert (data_dir / subdir).is_dir()

def test_ensure_data_dirs_idempotent(data_dir):
    s = LinkedOutSettings()
    s.ensure_data_dirs()
    s.ensure_data_dirs()  # second call should not error
```

**3f. Agent context tests:**
```python
def test_agent_context_generation(data_dir):
    s = LinkedOutSettings()
    s.ensure_data_dirs()
    path = generate_agent_context(s)
    content = path.read_text()
    assert 'DATABASE_URL=' in content
    assert 'LINKEDOUT_TENANT_ID=tenant_sys_001' in content
    assert 'LINKEDOUT_BU_ID=bu_sys_001' in content

def test_agent_context_idempotent(data_dir):
    s = LinkedOutSettings()
    s.ensure_data_dirs()
    path1 = generate_agent_context(s)
    path2 = generate_agent_context(s)
    assert path1 == path2
    assert path1.read_text() == path2.read_text()
```

### 4. Run Full Test Suite

```bash
cd backend && python -m pytest -x -v
```

Fix any failures caused by the config migration. Common issues:
- Tests that set old env var names
- Tests that import from old config structure
- Tests that expect specific config class names
- Tests that don't use temp dirs for data

### 5. Verify Phase Exit Criteria

Run the complete verification checklist from the phase plan:

```bash
echo "=== Phase 02 Exit Criteria Verification ==="

# 1. Backend boots with only env vars
DATABASE_URL=postgresql://linkedout:test@localhost:5432/linkedout \
  python -c "from shared.config import get_config; c = get_config(); print(f'PASS: boots with env, db={c.database_url}')"

# 2. Backend boots with only config.yaml
# (need temp dir with config.yaml for this test)

# 3. Env vars override YAML values
# (tested in unit tests)

# 4. No hardcoded secrets
grep -rn "sk-\|apify_api_" backend/src/ extension/lib/ --include="*.py" --include="*.ts" | grep -v "\.example\|test\|mock\|#\|comment" && echo "FAIL: hardcoded secrets found" || echo "PASS: no hardcoded secrets"

# 5. No old env file references
grep -rn "\.env\.local\|\.env\.test\|\.env\.prod" backend/src/ && echo "FAIL" || echo "PASS: no old env file refs"

# 6. Data directory tree creation
# (tested in unit tests)

# 7. secrets.yaml permission warning
# (tested in unit tests)

# 8. Extension builds with VITE_BACKEND_URL
cd extension && VITE_BACKEND_URL=http://custom:9999 npm run build && echo "PASS: extension build with custom URL" || echo "FAIL"

# 9. Extension reads from browser.storage.local
grep "browser.storage.local" extension/lib/config.ts && echo "PASS" || echo "FAIL"

# 10. All unit tests pass
cd backend && python -m pytest -x -q && echo "PASS: all tests pass" || echo "FAIL"

# 11. No os.getenv for covered config vars
grep -rn "os\.getenv" backend/src/ --include="*.py" | grep -v "conftest\|test_" | grep "DATABASE_URL\|ENVIRONMENT\|LOG_LEVEL\|BACKEND_PORT\|LLM_PROVIDER\|LLM_MODEL\|EMBEDDING_MODEL\|OPENAI_API_KEY\|APIFY_API_KEY\|ENABLE_TRACING" && echo "FAIL" || echo "PASS: no old getenv calls"
```

---

## Verification

All verification is built into Steps 4 and 5 above. The test suite + exit criteria checklist together form the verification.

---

## Acceptance Criteria

- [ ] `pytest` runs without needing real `config.yaml` or `secrets.yaml`
- [ ] Tests use temp directories for `LINKEDOUT_DATA_DIR`
- [ ] No test pollutes the real `~/linkedout-data/` directory
- [ ] Config singleton reset between tests (no cross-test pollution)
- [ ] All existing tests pass with the new config system
- [ ] Unit tests cover: env-only loading, YAML-only loading, env-overrides-YAML, missing required fields, validation errors, path expansion, data dir creation, agent context generation
- [ ] All phase exit criteria verified and passing
