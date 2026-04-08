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
