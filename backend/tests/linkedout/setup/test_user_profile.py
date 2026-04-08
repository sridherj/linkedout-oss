# SPDX-License-Identifier: Apache-2.0
"""Tests for user profile setup module."""
from unittest.mock import MagicMock, patch

from linkedout.setup.user_profile import (
    create_user_profile,
    prompt_linkedin_url,
    validate_linkedin_url,
)


class TestValidateLinkedinUrl:
    def test_basic_url(self):
        assert validate_linkedin_url('https://linkedin.com/in/johndoe') == 'johndoe'

    def test_url_with_www(self):
        assert validate_linkedin_url('https://www.linkedin.com/in/john-doe/') == 'john-doe'

    def test_url_with_trailing_slash(self):
        assert validate_linkedin_url('https://linkedin.com/in/johndoe/') == 'johndoe'

    def test_not_a_url(self):
        assert validate_linkedin_url('not-a-url') is None

    def test_company_url_rejected(self):
        assert validate_linkedin_url('https://linkedin.com/company/acme') is None

    def test_school_url_rejected(self):
        assert validate_linkedin_url('https://linkedin.com/school/mit') is None

    def test_empty_string(self):
        assert validate_linkedin_url('') is None

    def test_http_url(self):
        assert validate_linkedin_url('http://linkedin.com/in/johndoe') == 'johndoe'

    def test_hyphenated_username(self):
        assert validate_linkedin_url('https://linkedin.com/in/jane-doe-123') == 'jane-doe-123'

    def test_underscore_in_username(self):
        assert validate_linkedin_url('https://linkedin.com/in/john_doe') == 'john_doe'

    def test_whitespace_stripped(self):
        assert validate_linkedin_url('  https://linkedin.com/in/johndoe  ') == 'johndoe'

    def test_feed_url_rejected(self):
        assert validate_linkedin_url('https://linkedin.com/feed') is None


class TestPromptLinkedinUrl:
    @patch('builtins.input', return_value='https://linkedin.com/in/testuser')
    def test_returns_valid_url(self, _mock_input):
        result = prompt_linkedin_url()
        assert result == 'https://linkedin.com/in/testuser'

    @patch('builtins.input', side_effect=['bad-url', 'https://linkedin.com/in/testuser'])
    def test_retries_on_invalid_url(self, _mock_input):
        result = prompt_linkedin_url()
        assert result == 'https://linkedin.com/in/testuser'
        assert _mock_input.call_count == 2


class TestCreateUserProfile:
    @patch('linkedout.setup.user_profile.get_setup_logger')
    def test_creates_new_profile(self, _mock_logger):
        mock_session = MagicMock()
        # First query: no existing profile
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.__enter__ = MagicMock(return_value=mock_engine)
        mock_engine.__exit__ = MagicMock(return_value=False)

        with patch('linkedout.setup.user_profile.create_engine') as mock_create_engine, \
             patch('linkedout.setup.user_profile.Session') as mock_session_cls, \
             patch('shared.common.nanoids.Nanoid.make_nanoid_with_prefix', return_value='cp_test123'):
            mock_create_engine.return_value = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

            result = create_user_profile(
                'johndoe',
                'https://linkedin.com/in/johndoe',
                'postgresql://test@localhost/test',
            )

        assert result == 'cp_test123'
        # Should have called execute twice: SELECT + INSERT
        assert mock_session.execute.call_count == 2
        mock_session.commit.assert_called_once()

    @patch('linkedout.setup.user_profile.get_setup_logger')
    def test_updates_existing_profile(self, _mock_logger):
        mock_session = MagicMock()
        # First query: existing profile found
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ('cp_existing',)
        mock_session.execute.return_value = mock_result

        with patch('linkedout.setup.user_profile.create_engine') as mock_create_engine, \
             patch('linkedout.setup.user_profile.Session') as mock_session_cls:
            mock_create_engine.return_value = MagicMock()
            mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)

            result = create_user_profile(
                'johndoe',
                'https://linkedin.com/in/johndoe',
                'postgresql://test@localhost/test',
            )

        assert result == 'cp_existing'
        # Should have called execute twice: SELECT + UPDATE
        assert mock_session.execute.call_count == 2
        mock_session.commit.assert_called_once()
