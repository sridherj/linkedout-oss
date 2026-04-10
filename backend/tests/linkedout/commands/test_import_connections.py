# SPDX-License-Identifier: Apache-2.0
"""Tests for import_connections — CSV batch loading counter correctness."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from linkedout.commands.import_connections import load_csv_batch


def _make_row(first='Alice', last='Smith', url='https://linkedin.com/in/alice',
              email='', company='Acme', position='Engineer', connected_on='01 Jan 2024'):
    """Build a CSV row dict matching LinkedIn export format."""
    return {
        'First Name': first,
        'Last Name': last,
        'URL': url,
        'Email Address': email,
        'Company': company,
        'Position': position,
        'Connected On': connected_on,
    }


@pytest.fixture
def mock_session():
    session = MagicMock()
    # begin_nested returns a savepoint mock
    savepoint = MagicMock()
    session.begin_nested.return_value = savepoint
    # flush sets an id on added objects
    def flush_side_effect():
        for call in session.add.call_args_list:
            obj = call[0][0]
            if not hasattr(obj, 'id') or obj.id is None:
                obj.id = f'stub_{id(obj)}'
    session.flush.side_effect = flush_side_effect
    return session


@pytest.fixture
def now():
    return datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


class TestLoadCsvBatchCounters:
    def test_counters_sum_to_total(self, mock_session, now):
        """matched + unenriched + no_url + errors must always equal total."""
        batch = [
            _make_row(url='https://linkedin.com/in/alice'),
            _make_row(first='Bob', url='https://linkedin.com/in/bob'),
            _make_row(first='Carol', url=''),  # no URL
        ]
        url_index = {'https://www.linkedin.com/in/alice': 'cp_existing'}

        with patch('linkedout.commands.import_connections.normalize_linkedin_url',
                   side_effect=lambda u: f'https://www.linkedin.com/in/{u.split("/")[-1]}'):
            counts = load_csv_batch(mock_session, batch, url_index, now)

        total = counts['matched'] + counts['unenriched'] + counts['no_url'] + counts['errors']
        assert total == counts['total']
        assert counts['total'] == 3

    def test_matched_counter_when_url_in_index(self, mock_session, now):
        """Row with URL already in index -> matched counter increments."""
        batch = [_make_row(url='https://linkedin.com/in/alice')]
        url_index = {'https://www.linkedin.com/in/alice': 'cp_existing'}

        with patch('linkedout.commands.import_connections.normalize_linkedin_url',
                   return_value='https://www.linkedin.com/in/alice'):
            counts = load_csv_batch(mock_session, batch, url_index, now)

        assert counts['matched'] == 1
        assert counts['unenriched'] == 0
        assert counts['no_url'] == 0

    def test_unenriched_counter_for_new_url(self, mock_session, now):
        """Row with URL NOT in index -> unenriched counter increments."""
        batch = [_make_row(url='https://linkedin.com/in/newperson')]
        url_index = {}

        with patch('linkedout.commands.import_connections.normalize_linkedin_url',
                   return_value='https://www.linkedin.com/in/newperson'):
            counts = load_csv_batch(mock_session, batch, url_index, now)

        assert counts['unenriched'] == 1
        assert counts['matched'] == 0

    def test_no_url_counter(self, mock_session, now):
        """Row with empty URL -> no_url counter increments."""
        batch = [_make_row(url='')]
        url_index = {}

        counts = load_csv_batch(mock_session, batch, url_index, now)

        assert counts['no_url'] == 1
        assert counts['matched'] == 0
        assert counts['unenriched'] == 0

    def test_error_counter_on_exception(self, mock_session, now):
        """When savepoint raises, error counter increments, not other counters."""
        batch = [_make_row(url='https://linkedin.com/in/alice')]
        url_index = {}

        # Make flush raise to simulate DB error
        mock_session.flush.side_effect = Exception('FK violation')

        with patch('linkedout.commands.import_connections.normalize_linkedin_url',
                   return_value='https://www.linkedin.com/in/alice'):
            counts = load_csv_batch(mock_session, batch, url_index, now)

        assert counts['errors'] == 1
        assert counts['matched'] == 0
        assert counts['unenriched'] == 0
        assert counts['no_url'] == 0
        # total still counts the row
        assert counts['total'] == 1

    def test_no_double_counting(self, mock_session, now):
        """Each row increments exactly one category counter."""
        batch = [
            _make_row(first='A', url='https://linkedin.com/in/matched'),
            _make_row(first='B', url='https://linkedin.com/in/new'),
            _make_row(first='C', url=''),
        ]
        url_index = {'https://www.linkedin.com/in/matched': 'cp_1'}

        def normalize(u):
            slug = u.rstrip('/').split('/')[-1]
            return f'https://www.linkedin.com/in/{slug}'

        with patch('linkedout.commands.import_connections.normalize_linkedin_url',
                   side_effect=normalize):
            counts = load_csv_batch(mock_session, batch, url_index, now)

        assert counts['matched'] == 1
        assert counts['unenriched'] == 1
        assert counts['no_url'] == 1
        assert counts['errors'] == 0
        assert counts['total'] == 3
        # Verify: sum of categories == total (no double counting)
        assert counts['matched'] + counts['unenriched'] + counts['no_url'] + counts['errors'] == counts['total']

    def test_url_index_updated_after_unenriched_insert(self, mock_session, now):
        """After inserting a stub profile, the URL index should be updated."""
        batch = [_make_row(url='https://linkedin.com/in/newperson')]
        url_index = {}

        with patch('linkedout.commands.import_connections.normalize_linkedin_url',
                   return_value='https://www.linkedin.com/in/newperson'):
            load_csv_batch(mock_session, batch, url_index, now)

        # The new URL should now be in the index
        assert 'https://www.linkedin.com/in/newperson' in url_index
