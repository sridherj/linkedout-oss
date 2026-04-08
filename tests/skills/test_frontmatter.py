"""Tests for the frontmatter processor (skills/lib/frontmatter.py)."""

from __future__ import annotations

from skills.lib.frontmatter import join_frontmatter, process_frontmatter, split_frontmatter


class TestSplitFrontmatter:
    def test_with_frontmatter(self):
        content = '---\nname: test\n---\nBody content'
        fm, body = split_frontmatter(content)
        assert 'name: test' in fm
        assert body == 'Body content'

    def test_without_frontmatter(self):
        content = 'Just body content'
        fm, body = split_frontmatter(content)
        assert fm == ''
        assert body == 'Just body content'

    def test_multiline_frontmatter(self):
        content = '---\nname: test\ndescription: A skill\ntags:\n  - foo\n---\nBody'
        fm, body = split_frontmatter(content)
        assert 'name: test' in fm
        assert 'description: A skill' in fm
        assert body == 'Body'


class TestJoinFrontmatter:
    def test_with_frontmatter(self):
        result = join_frontmatter('name: test\n', 'Body')
        assert result == '---\nname: test\n---\nBody'

    def test_empty_frontmatter(self):
        result = join_frontmatter('', 'Body')
        assert result == 'Body'

    def test_frontmatter_without_trailing_newline(self):
        result = join_frontmatter('name: test', 'Body')
        assert result == '---\nname: test\n---\nBody'


class TestProcessFrontmatter:
    def test_denylist_strips_fields(self):
        frontmatter = 'name: test\nsensitive: secret\ndescription: A skill\n'
        host_config = {
            'frontmatter': {
                'mode': 'denylist',
                'strip_fields': ['sensitive'],
                'description_limit': None,
            }
        }
        result = process_frontmatter(frontmatter, host_config)
        assert 'name: test' in result
        assert 'description: A skill' in result
        assert 'sensitive' not in result

    def test_denylist_empty_strip_fields(self):
        frontmatter = 'name: test\ndescription: A skill\n'
        host_config = {
            'frontmatter': {
                'mode': 'denylist',
                'strip_fields': [],
                'description_limit': None,
            }
        }
        result = process_frontmatter(frontmatter, host_config)
        assert 'name: test' in result
        assert 'description: A skill' in result

    def test_allowlist_keeps_only_specified(self):
        frontmatter = 'name: test\ndescription: A skill\nauthor: someone\n'
        host_config = {
            'frontmatter': {
                'mode': 'allowlist',
                'keep_fields': ['name', 'description'],
                'description_limit': None,
            }
        }
        result = process_frontmatter(frontmatter, host_config)
        assert 'name: test' in result
        assert 'description: A skill' in result
        assert 'author' not in result

    def test_description_limit_truncates(self):
        frontmatter = 'name: test\ndescription: This is a very long description that exceeds the limit\n'
        host_config = {
            'frontmatter': {
                'mode': 'denylist',
                'strip_fields': [],
                'description_limit': 20,
            }
        }
        result = process_frontmatter(frontmatter, host_config)
        assert 'name: test' in result
        # Description should be truncated to 20 chars
        assert 'This is a very long ' in result
        assert 'exceeds the limit' not in result

    def test_description_limit_null_no_truncation(self):
        long_desc = 'A' * 500
        frontmatter = f'name: test\ndescription: {long_desc}\n'
        host_config = {
            'frontmatter': {
                'mode': 'denylist',
                'strip_fields': [],
                'description_limit': None,
            }
        }
        result = process_frontmatter(frontmatter, host_config)
        assert long_desc in result

    def test_empty_frontmatter(self):
        host_config = {'frontmatter': {'mode': 'denylist', 'strip_fields': []}}
        assert process_frontmatter('', host_config) == ''

    def test_roundtrip_preserves_body(self):
        original = '---\nname: test\ndescription: A skill\n---\n# Body\n\nSome content here.\n'
        host_config = {
            'frontmatter': {
                'mode': 'denylist',
                'strip_fields': [],
                'description_limit': None,
            }
        }
        fm, body = split_frontmatter(original)
        processed_fm = process_frontmatter(fm, host_config)
        result = join_frontmatter(processed_fm, body)
        assert '# Body' in result
        assert 'Some content here.' in result
        assert 'name: test' in result
