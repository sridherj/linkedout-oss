"""Tests for the template engine (skills/lib/template.py)."""

from __future__ import annotations

import pytest

from skills.lib.template import load_template, render_template


class TestVariableResolution:
    def test_simple_variable(self):
        assert render_template('Hello {{NAME}}', {'NAME': 'World'}) == 'Hello World'

    def test_multiple_variables(self):
        template = '{{GREETING}} {{NAME}}, welcome to {{PLACE}}'
        variables = {'GREETING': 'Hi', 'NAME': 'Alice', 'PLACE': 'Wonderland'}
        assert render_template(template, variables) == 'Hi Alice, welcome to Wonderland'

    def test_repeated_variable(self):
        assert render_template('{{X}} and {{X}}', {'X': 'foo'}) == 'foo and foo'

    def test_unresolved_variable_raises_error(self):
        with pytest.raises(ValueError, match='Unresolved template variables: MISSING'):
            render_template('Hello {{MISSING}}', {})

    def test_unresolved_among_resolved(self):
        with pytest.raises(ValueError, match='MISSING'):
            render_template('{{OK}} {{MISSING}}', {'OK': 'fine'})

    def test_no_variables(self):
        assert render_template('plain text', {}) == 'plain text'


class TestConditionalBlocks:
    def test_equality_true(self):
        template = '{{#if HOST_NAME == "claude"}}visible{{/if}}'
        assert render_template(template, {'HOST_NAME': 'claude'}) == 'visible'

    def test_equality_false(self):
        template = '{{#if HOST_NAME == "claude"}}visible{{/if}}'
        assert render_template(template, {'HOST_NAME': 'codex'}) == ''

    def test_negation_true(self):
        template = '{{#if HOST_NAME != "codex"}}visible{{/if}}'
        assert render_template(template, {'HOST_NAME': 'claude'}) == 'visible'

    def test_negation_false(self):
        template = '{{#if HOST_NAME != "codex"}}visible{{/if}}'
        assert render_template(template, {'HOST_NAME': 'codex'}) == ''

    def test_conditional_with_variables_inside(self):
        template = '{{#if HOST_NAME == "claude"}}Install to {{PATH}}{{/if}}'
        variables = {'HOST_NAME': 'claude', 'PATH': '~/.claude'}
        assert render_template(template, variables) == 'Install to ~/.claude'

    def test_multiple_conditionals(self):
        template = (
            '{{#if HOST_NAME == "claude"}}A{{/if}}'
            '{{#if HOST_NAME == "codex"}}B{{/if}}'
        )
        assert render_template(template, {'HOST_NAME': 'claude'}) == 'A'
        assert render_template(template, {'HOST_NAME': 'codex'}) == 'B'

    def test_multiline_conditional(self):
        template = '{{#if HOST_NAME == "claude"}}\nline1\nline2\n{{/if}}'
        result = render_template(template, {'HOST_NAME': 'claude'})
        assert 'line1' in result
        assert 'line2' in result


class TestLoadTemplate:
    def test_load_existing_file(self, tmp_path):
        tmpl = tmp_path / 'test.tmpl'
        tmpl.write_text('Hello {{NAME}}', encoding='utf-8')
        content = load_template(str(tmpl))
        assert content == 'Hello {{NAME}}'

    def test_load_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_template('/nonexistent/path.tmpl')
