# SPDX-License-Identifier: Apache-2.0
"""Unit tests for LinkedOutSettings config module."""

import os

import pytest
from pydantic import ValidationError

from shared.config.settings import LinkedOutSettings
from shared.config.agent_context import generate_agent_context


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_config_env_vars():
    """Remove env vars that LinkedOutSettings reads so each test starts clean."""
    keys_to_remove = [
        'DATABASE_URL',
        'OPENAI_API_KEY',
        'APIFY_API_KEY',
        # LINKEDOUT_ prefixed vars
        *(k for k in os.environ if k.startswith('LINKEDOUT_')),
        # Langfuse
        'LANGFUSE_ENABLED', 'LANGFUSE_PUBLIC_KEY',
        'LANGFUSE_SECRET_KEY', 'LANGFUSE_HOST',
    ]
    for key in keys_to_remove:
        os.environ.pop(key, None)


@pytest.fixture(autouse=True)
def clean_env(data_dir):
    """Every test gets a temp data_dir and starts with a clean env."""
    _clear_config_env_vars()
    # Restore LINKEDOUT_DATA_DIR after clearing (data_dir fixture set it,
    # but _clear_config_env_vars removed it).
    os.environ['LINKEDOUT_DATA_DIR'] = str(data_dir)
    # Set minimum required env for a valid config:
    os.environ['DATABASE_URL'] = 'postgresql://test:test@localhost/test'
    os.environ['LINKEDOUT_EMBEDDING_PROVIDER'] = 'local'
    yield
    _clear_config_env_vars()


# ===========================================================================
# 3a. Config loading tests
# ===========================================================================

class TestConfigLoading:
    def test_loads_from_env_vars_only(self, data_dir):
        """Settings loads with just env vars, no YAML."""
        os.environ['DATABASE_URL'] = 'postgresql://test:test@localhost/testdb'
        s = LinkedOutSettings()
        assert s.database_url == 'postgresql://test:test@localhost/testdb'

    def test_loads_from_yaml_only(self, data_dir):
        """Settings loads from config.yaml when present."""
        # Remove the env var so YAML is the only source
        os.environ.pop('DATABASE_URL', None)
        config_dir = data_dir / 'config'
        config_dir.mkdir()
        (config_dir / 'config.yaml').write_text(
            'database_url: postgresql://yaml:yaml@localhost/yaml\n'
        )
        s = LinkedOutSettings()
        assert 'yaml' in s.database_url

    def test_env_overrides_yaml(self, data_dir):
        """Env vars take precedence over YAML values."""
        config_dir = data_dir / 'config'
        config_dir.mkdir()
        (config_dir / 'config.yaml').write_text(
            'database_url: postgresql://yaml:yaml@localhost/yaml\n'
        )
        os.environ['DATABASE_URL'] = 'postgresql://env:env@localhost/env'
        s = LinkedOutSettings()
        assert 'env' in s.database_url


# ===========================================================================
# 3b. YAML sources tests
# ===========================================================================

class TestYamlSources:
    def test_yaml_config_source_missing_file(self, data_dir):
        """Missing config.yaml returns empty dict — no error."""
        # No config.yaml created
        s = LinkedOutSettings()
        assert s.database_url  # still gets default/env value

    def test_yaml_secrets_source_missing_file(self, data_dir):
        """Missing secrets.yaml returns empty dict — no error."""
        # No secrets.yaml created
        s = LinkedOutSettings()
        assert s is not None

    def test_yaml_secrets_permission_warning(self, data_dir, capsys):
        """Warns if secrets.yaml permissions are too open."""
        config_dir = data_dir / 'config'
        config_dir.mkdir()
        secrets_path = config_dir / 'secrets.yaml'
        secrets_path.write_text('apify_api_key: test-key\n')
        secrets_path.chmod(0o644)  # too open
        LinkedOutSettings()
        captured = capsys.readouterr()
        assert 'WARNING' in captured.err or '0o644' in captured.err


# ===========================================================================
# 3c. Validation tests
# ===========================================================================

class TestValidation:
    def test_invalid_port_rejected(self, data_dir):
        os.environ['LINKEDOUT_BACKEND_PORT'] = '99999'
        with pytest.raises(ValidationError):
            LinkedOutSettings()

    def test_invalid_log_level_rejected(self, data_dir):
        os.environ['LINKEDOUT_LOG_LEVEL'] = 'TRACE'
        with pytest.raises(ValidationError):
            LinkedOutSettings()

    def test_log_level_case_insensitive(self, data_dir):
        os.environ['LINKEDOUT_LOG_LEVEL'] = 'debug'
        s = LinkedOutSettings()
        assert s.log_level == 'DEBUG'

    def test_openai_key_missing_warns_not_errors(self, data_dir):
        os.environ['LINKEDOUT_EMBEDDING__PROVIDER'] = 'openai'
        os.environ.pop('OPENAI_API_KEY', None)
        # Should warn but not raise — key is only needed at embed time
        s = LinkedOutSettings()
        assert s.embedding.provider == 'openai'

    def test_openai_key_not_required_when_local_provider(self, data_dir):
        os.environ['LINKEDOUT_EMBEDDING__PROVIDER'] = 'local'
        os.environ.pop('OPENAI_API_KEY', None)
        s = LinkedOutSettings()  # should not raise
        assert s.embedding.provider == 'local'

    def test_invalid_database_url_rejected(self, data_dir):
        os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
        with pytest.raises(ValidationError):
            LinkedOutSettings()


# ===========================================================================
# 3d. Path expansion tests
# ===========================================================================

class TestPathExpansion:
    def test_tilde_expansion(self):
        """Tilde in LINKEDOUT_DATA_DIR is expanded."""
        os.environ['LINKEDOUT_DATA_DIR'] = '~/test-linkedout'
        s = LinkedOutSettings()
        assert '~' not in s.data_dir
        assert os.path.expanduser('~') in s.data_dir
        # Restore so other tests still use temp dir
        os.environ.pop('LINKEDOUT_DATA_DIR', None)

    def test_custom_data_dir(self, data_dir):
        s = LinkedOutSettings()
        assert str(data_dir) in s.data_dir


# ===========================================================================
# 3e. Data directory tests
# ===========================================================================

class TestDataDirectory:
    def test_ensure_data_dirs_creates_tree(self, data_dir):
        s = LinkedOutSettings()
        s.ensure_data_dirs()
        for subdir in ['config', 'db', 'crawled', 'uploads', 'logs',
                       'queries', 'reports', 'metrics', 'seed', 'state']:
            assert (data_dir / subdir).is_dir()

    def test_ensure_data_dirs_idempotent(self, data_dir):
        s = LinkedOutSettings()
        s.ensure_data_dirs()
        s.ensure_data_dirs()  # second call should not error
        assert (data_dir / 'config').is_dir()


# ===========================================================================
# 3f. Agent context tests
# ===========================================================================

class TestAgentContext:
    def test_agent_context_generation(self, data_dir):
        s = LinkedOutSettings()
        s.ensure_data_dirs()
        path = generate_agent_context(s)
        content = path.read_text()
        assert 'DATABASE_URL=' in content
        assert 'LINKEDOUT_TENANT_ID=tenant_sys_001' in content
        assert 'LINKEDOUT_BU_ID=bu_sys_001' in content

    def test_agent_context_idempotent(self, data_dir):
        s = LinkedOutSettings()
        s.ensure_data_dirs()
        path1 = generate_agent_context(s)
        path2 = generate_agent_context(s)
        assert path1 == path2
        assert path1.read_text() == path2.read_text()
