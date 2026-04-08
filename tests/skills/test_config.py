"""Tests for the config loader (skills/lib/config.py)."""

from __future__ import annotations

import pytest

from skills.lib.config import get_global_context, list_hosts, load_host_config


class TestLoadHostConfig:
    def test_load_claude(self):
        config = load_host_config('claude')
        assert config['name'] == 'claude'
        assert config['display_name'] == 'Claude Code'
        assert config['skill_install_path'] == '~/.claude/skills/linkedout'
        assert config['local_skill_path'] == '.claude/skills/linkedout'
        assert 'frontmatter' in config
        assert 'path_rewrites' in config
        assert 'tool_rewrites' in config

    def test_load_codex(self):
        config = load_host_config('codex')
        assert config['name'] == 'codex'
        assert config['display_name'] == 'Codex'
        assert config['frontmatter']['mode'] == 'allowlist'
        assert 'name' in config['frontmatter']['keep_fields']

    def test_load_copilot(self):
        config = load_host_config('copilot')
        assert config['name'] == 'copilot'
        assert config['display_name'] == 'GitHub Copilot'

    def test_missing_host_raises_error(self):
        with pytest.raises(FileNotFoundError, match='Host config not found'):
            load_host_config('nonexistent')


class TestListHosts:
    def test_returns_all_hosts(self):
        hosts = list_hosts()
        assert hosts == ['claude', 'codex', 'copilot']


class TestGetGlobalContext:
    def test_includes_all_expected_keys(self):
        ctx = get_global_context()
        assert 'VERSION' in ctx
        assert 'DATA_DIR' in ctx
        assert 'CONFIG_DIR' in ctx
        assert 'CLI_PREFIX' in ctx
        assert 'AGENT_CONTEXT_PATH' in ctx

    def test_version_is_string(self):
        ctx = get_global_context()
        assert isinstance(ctx['VERSION'], str)
        assert ctx['VERSION']  # not empty

    def test_data_dir_value(self):
        ctx = get_global_context()
        assert ctx['DATA_DIR'] == '~/linkedout-data/'

    def test_config_dir_value(self):
        ctx = get_global_context()
        assert ctx['CONFIG_DIR'] == '~/linkedout-data/config/'

    def test_cli_prefix_value(self):
        ctx = get_global_context()
        assert ctx['CLI_PREFIX'] == 'linkedout'

    def test_agent_context_path_value(self):
        ctx = get_global_context()
        assert ctx['AGENT_CONTEXT_PATH'] == '~/linkedout-data/config/agent-context.env'
