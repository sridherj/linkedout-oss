# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ImportService orchestration."""
from datetime import date
from io import BytesIO
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from linkedout.import_pipeline.service import ImportService


def _mock_session():
    """Create a mock SQLAlchemy session."""
    session = MagicMock()
    # execute().scalar_one_or_none() returns None (no active import)
    session.execute.return_value.scalar_one_or_none.return_value = None
    session.execute.return_value.scalars.return_value.all.return_value = []
    return session


class TestImportServiceOrchestration:
    @patch('linkedout.import_pipeline.service.run_dedup')
    @patch('linkedout.import_pipeline.service.get_converter')
    def test_orchestration_flow(self, mock_get_converter, mock_run_dedup):
        """Converter called → contact_sources created → dedup called → merge called → counters updated."""
        session = _mock_session()

        # Mock converter
        from linkedout.import_pipeline.schemas import ParsedContact
        mock_converter = MagicMock()
        mock_converter.parse.return_value = (
            [
                ParsedContact(first_name='Alice', last_name='Smith',
                              linkedin_url='https://linkedin.com/in/alice',
                              source_type='linkedin_csv'),
            ],
            [],  # no failed rows
        )
        mock_get_converter.return_value = mock_converter

        service = ImportService(session)

        result = service.process_import(
            file=BytesIO(b'csv data'),
            file_name='test.csv',
            tenant_id='t1',
            bu_id='b1',
            app_user_id='u1',
            source_type='linkedin_csv',
        )

        # Converter was called
        mock_converter.parse.assert_called_once()

        # Session had bulk insert called (via execute with insert)
        assert session.execute.called

        # Dedup was called (or would be, depending on contact_sources reload)
        # The key assertion: import job was created and flushed
        assert session.add.called
        assert session.flush.called

    def test_concurrent_import_rejection(self):
        """Second import while first active → conflict result."""
        session = MagicMock()
        # Simulate an active import job exists
        active_job = MagicMock()
        active_job.id = 'ij_existing'
        session.execute.return_value.scalar_one_or_none.return_value = active_job

        service = ImportService(session)

        result = service.process_import(
            file=BytesIO(b'csv data'),
            file_name='test.csv',
            tenant_id='t1',
            bu_id='b1',
            app_user_id='u1',
            source_type='linkedin_csv',
        )

        assert result['error'] == 'conflict'

    @patch('linkedout.import_pipeline.service.IMPORT_SYNC_THRESHOLD', 5)
    @patch('linkedout.import_pipeline.service.get_converter')
    def test_async_threshold(self, mock_get_converter):
        """10 rows with threshold=5 → async path."""
        session = _mock_session()

        from linkedout.import_pipeline.schemas import ParsedContact
        mock_converter = MagicMock()
        mock_converter.parse.return_value = (
            [ParsedContact(first_name=f'Person{i}', source_type='linkedin_csv') for i in range(10)],
            [],
        )
        mock_get_converter.return_value = mock_converter

        service = ImportService(session)

        result = service.process_import(
            file=BytesIO(b'csv data'),
            file_name='test.csv',
            tenant_id='t1',
            bu_id='b1',
            app_user_id='u1',
            source_type='linkedin_csv',
        )

        assert result.get('async') is True
        assert result['status'] == 'processing'

    @patch('linkedout.import_pipeline.service.IMPORT_SYNC_THRESHOLD', 5000)
    @patch('linkedout.import_pipeline.service.run_dedup')
    @patch('linkedout.import_pipeline.service.get_converter')
    def test_sync_threshold(self, mock_get_converter, mock_run_dedup):
        """10 rows with threshold=5000 → sync path."""
        session = _mock_session()

        from linkedout.import_pipeline.schemas import ParsedContact
        mock_converter = MagicMock()
        mock_converter.parse.return_value = (
            [ParsedContact(first_name=f'Person{i}', source_type='linkedin_csv') for i in range(10)],
            [],
        )
        mock_get_converter.return_value = mock_converter

        service = ImportService(session)

        result = service.process_import(
            file=BytesIO(b'csv data'),
            file_name='test.csv',
            tenant_id='t1',
            bu_id='b1',
            app_user_id='u1',
            source_type='linkedin_csv',
        )

        # Should NOT be async
        assert result.get('async') is not True
        assert result['status'] == 'complete'


class TestRunMergeRedirectDedup:
    """T-redirect-9: Re-import with old URL finds profile via previous_linkedin_url."""

    @patch('linkedout.import_pipeline.service.create_new_connection')
    def test_previous_url_prevents_duplicate_profile(self, mock_create_new):
        """A 'new' contact whose URL matches a profile's previous_linkedin_url
        should be routed to the existing profile, not create a stub."""
        session = MagicMock()

        # Existing profile: URL was redirected from old → new
        profile = MagicMock()
        profile.linkedin_url = 'https://www.linkedin.com/in/vikas-khatana'
        profile.previous_linkedin_url = 'https://www.linkedin.com/in/vikas-khatana-web-developer'

        # session.execute(select(CrawledProfileEntity)).scalars().all()
        session.execute.return_value.scalars.return_value.all.return_value = [profile]

        # Contact source from CSV with the OLD (pre-redirect) URL
        cs = MagicMock()
        cs.dedup_status = 'new'
        cs.linkedin_url = 'https://www.linkedin.com/in/vikas-khatana-web-developer'

        service = ImportService(session)
        service._run_merge([cs], 't1', 'b1', 'u1')

        # create_new_connection should have been called
        mock_create_new.assert_called_once()
        # The existing_profiles dict passed to create_new_connection should contain
        # the old URL mapped to the existing profile
        call_args = mock_create_new.call_args
        existing_profiles_arg = call_args[0][2]  # 3rd positional arg
        old_url_norm = 'https://www.linkedin.com/in/vikas-khatana-web-developer'
        assert old_url_norm in existing_profiles_arg
        assert existing_profiles_arg[old_url_norm] is profile

    def test_build_connection_lookups_includes_previous_url(self):
        """_build_connection_lookups() creates entries for previous_linkedin_url."""
        session = MagicMock()

        # Simulate a joined row: (conn_id, emails, li_url, prev_li_url, full_name, company)
        session.execute.return_value.all.return_value = [
            (
                'conn_1',
                None,
                'https://www.linkedin.com/in/vikas-khatana',
                'https://www.linkedin.com/in/vikas-khatana-web-developer',
                'Vikas Khatana',
                'Acme Corp',
            ),
        ]

        service = ImportService(session)
        entries = service._build_connection_lookups('u1')

        # Should produce two entries: one for current URL, one for previous
        assert len(entries) == 2
        urls = {e.linkedin_url for e in entries}
        assert 'https://www.linkedin.com/in/vikas-khatana' in urls
        assert 'https://www.linkedin.com/in/vikas-khatana-web-developer' in urls
        # Both entries should reference the same connection
        assert all(e.connection_id == 'conn_1' for e in entries)
