# SPDX-License-Identifier: Apache-2.0
"""Tests for the Apify JSONL archive utility."""
import json
from unittest.mock import patch

from shared.utils.apify_archive import append_apify_archive, append_apify_archive_batch

SAMPLE_URL = 'https://www.linkedin.com/in/jdoe'
SAMPLE_DATA = {
    'firstName': 'Jane',
    'lastName': 'Doe',
    'headline': 'Engineer at Acme',
    'experience': [{'companyName': 'Acme', 'position': 'Engineer'}],
}


def test_happy_path(tmp_path):
    """Single call writes one valid JSON line with correct envelope fields."""
    append_apify_archive(SAMPLE_URL, SAMPLE_DATA, source='test', data_dir=tmp_path)

    archive = tmp_path / 'crawled' / 'apify-responses.jsonl'
    assert archive.exists()

    line = json.loads(archive.read_text().strip())
    assert line['linkedin_url'] == SAMPLE_URL
    assert line['source'] == 'test'
    assert line['data'] == SAMPLE_DATA
    # archived_at should be a valid ISO timestamp
    assert 'T' in line['archived_at']


def test_append_semantics(tmp_path):
    """Multiple calls append to the same file, one line each."""
    append_apify_archive(SAMPLE_URL, SAMPLE_DATA, source='first', data_dir=tmp_path)
    append_apify_archive(SAMPLE_URL, {'firstName': 'John'}, source='second', data_dir=tmp_path)

    archive = tmp_path / 'crawled' / 'apify-responses.jsonl'
    lines = [json.loads(l) for l in archive.read_text().strip().splitlines()]
    assert len(lines) == 2
    assert lines[0]['source'] == 'first'
    assert lines[1]['source'] == 'second'


def test_creates_parent_directory(tmp_path):
    """Creates the crawled/ directory if it doesn't exist."""
    nested = tmp_path / 'deep' / 'nested'
    # Directory doesn't exist yet
    assert not nested.exists()

    append_apify_archive(SAMPLE_URL, SAMPLE_DATA, source='test', data_dir=nested)

    archive = nested / 'crawled' / 'apify-responses.jsonl'
    assert archive.exists()
    line = json.loads(archive.read_text().strip())
    assert line['data'] == SAMPLE_DATA


def test_write_failure_is_nonfatal(tmp_path):
    """Archive write failure does not raise — enrichment must not be blocked."""
    # Point at a file (not a directory) so mkdir fails
    blocker = tmp_path / 'crawled'
    blocker.write_text('not a directory')

    # Should not raise
    append_apify_archive(SAMPLE_URL, SAMPLE_DATA, source='test', data_dir=tmp_path)


def test_data_fidelity(tmp_path):
    """Unicode, nested objects, and nulls round-trip correctly."""
    complex_data = {
        'firstName': 'Ren\u00e9',
        'lastName': None,
        'location': {'parsed': {'city': 'Z\u00fcrich', 'state': None}},
        'skills': [{'name': '\u2764\ufe0f Coding'}],
        'about': 'Line1\nLine2\tTabbed',
    }

    append_apify_archive(SAMPLE_URL, complex_data, source='test', data_dir=tmp_path)

    archive = tmp_path / 'crawled' / 'apify-responses.jsonl'
    line = json.loads(archive.read_text().strip())
    assert line['data'] == complex_data
    assert line['data']['firstName'] == 'Ren\u00e9'
    assert line['data']['location']['parsed']['city'] == 'Z\u00fcrich'


# ---------------------------------------------------------------------------
# append_apify_archive_batch() tests
# ---------------------------------------------------------------------------

class TestAppendApifyArchiveBatch:
    """Tests for batch archive writes."""

    def test_batch_writes_multiple_entries(self, tmp_path):
        """Batch call writes all entries in one I/O cycle with correct fields."""
        entries = [
            {'linkedin_url': 'https://linkedin.com/in/alice', 'apify_data': {'firstName': 'Alice'}},
            {'linkedin_url': 'https://linkedin.com/in/bob', 'apify_data': {'firstName': 'Bob'}},
            {'linkedin_url': 'https://linkedin.com/in/carol', 'apify_data': {'firstName': 'Carol'}},
        ]

        append_apify_archive_batch(entries, source='bulk_enrichment', data_dir=tmp_path)

        archive = tmp_path / 'crawled' / 'apify-responses.jsonl'
        assert archive.exists()

        lines = [json.loads(l) for l in archive.read_text().strip().splitlines()]
        assert len(lines) == 3

        for i, line in enumerate(lines):
            assert line['linkedin_url'] == entries[i]['linkedin_url']
            assert line['source'] == 'bulk_enrichment'
            assert line['data'] == entries[i]['apify_data']
            assert 'T' in line['archived_at']

    def test_empty_entries_is_noop(self, tmp_path):
        """Empty entries list does not create any file."""
        append_apify_archive_batch([], source='bulk_enrichment', data_dir=tmp_path)

        archive = tmp_path / 'crawled' / 'apify-responses.jsonl'
        assert not archive.exists()

    def test_fire_and_forget_on_failure(self, tmp_path):
        """Write failure does not raise — logs warning instead."""
        entries = [
            {'linkedin_url': 'https://linkedin.com/in/alice', 'apify_data': {'firstName': 'Alice'}},
        ]

        with patch('builtins.open', side_effect=PermissionError('denied')):
            # Should not raise
            append_apify_archive_batch(entries, source='bulk_enrichment', data_dir=tmp_path)
