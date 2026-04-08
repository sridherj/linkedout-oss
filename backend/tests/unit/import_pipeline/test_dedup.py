# SPDX-License-Identifier: Apache-2.0
"""Unit tests for cascading dedup pipeline."""
from unittest.mock import MagicMock

from linkedout.import_pipeline.dedup import ConnectionLookupEntry, run_dedup


def _make_cs(**kwargs):
    """Create a mock ContactSourceEntity."""
    cs = MagicMock()
    cs.linkedin_url = kwargs.get('linkedin_url')
    cs.email = kwargs.get('email')
    cs.first_name = kwargs.get('first_name')
    cs.last_name = kwargs.get('last_name')
    cs.company = kwargs.get('company')
    cs.dedup_status = 'pending'
    cs.dedup_method = None
    cs.dedup_confidence = None
    cs.connection_id = None
    return cs


def _make_entries():
    """Create lookup entries simulating existing connections."""
    return [
        ConnectionLookupEntry(
            connection_id='conn_1',
            linkedin_url='https://www.linkedin.com/in/alice-smith',
            emails=['alice@example.com'],
            full_name='Alice Smith',
            company='Acme Corp',
        ),
        ConnectionLookupEntry(
            connection_id='conn_2',
            linkedin_url='https://www.linkedin.com/in/bob-jones',
            emails=['bob@test.com'],
            full_name='Bob Jones',
            company='Widgets Inc',
        ),
        ConnectionLookupEntry(
            connection_id='conn_3',
            linkedin_url=None,
            emails=['carol@corp.com'],
            full_name='Carol Davis',
            company='TechCo',
        ),
    ]


class TestCascadingDedup:
    def test_10_contacts_mixed_match(self):
        """10 contacts: 3 exact URL, 2 email, 1 fuzzy, 4 new."""
        entries = _make_entries()
        contacts = [
            # 3 exact URL matches
            _make_cs(linkedin_url='https://linkedin.com/in/alice-smith'),
            _make_cs(linkedin_url='https://www.linkedin.com/in/bob-jones/'),
            _make_cs(linkedin_url='linkedin.com/in/Alice-Smith'),  # duplicate within import
            # 2 exact email matches
            _make_cs(email='Carol@Corp.com'),
            _make_cs(email='  bob@test.com  '),
            # 1 fuzzy name+company match
            _make_cs(first_name='Alice', last_name='Smth', company='Acme Corp'),
            # 4 new contacts
            _make_cs(first_name='New', last_name='Person1'),
            _make_cs(email='unknown@nowhere.com'),
            _make_cs(linkedin_url='https://linkedin.com/in/totally-new'),
            _make_cs(first_name='Another', last_name='New', company='Unknown LLC'),
        ]

        run_dedup(contacts, entries)

        # Exact URL matches
        assert contacts[0].dedup_status == 'matched'
        assert contacts[0].dedup_method == 'exact_url'
        assert contacts[0].dedup_confidence == 1.0
        assert contacts[0].connection_id == 'conn_1'

        assert contacts[1].dedup_status == 'matched'
        assert contacts[1].dedup_method == 'exact_url'
        assert contacts[1].connection_id == 'conn_2'

        # Within-import URL dedup (same normalized URL as contacts[0])
        assert contacts[2].dedup_status == 'matched'
        assert contacts[2].dedup_method == 'exact_url'
        assert contacts[2].connection_id == 'conn_1'

        # Email matches
        assert contacts[3].dedup_status == 'matched'
        assert contacts[3].dedup_method == 'exact_email'
        assert contacts[3].dedup_confidence == 0.95
        assert contacts[3].connection_id == 'conn_3'

        assert contacts[4].dedup_status == 'matched'
        assert contacts[4].dedup_method == 'exact_email'
        assert contacts[4].connection_id == 'conn_2'

        # Fuzzy name+company match (Alice Smth ≈ Alice Smith, same company)
        assert contacts[5].dedup_status == 'matched'
        assert contacts[5].dedup_method == 'fuzzy_name_company'
        assert contacts[5].dedup_confidence >= 0.85
        assert contacts[5].connection_id == 'conn_1'

        # New contacts
        for i in [6, 7, 8, 9]:
            assert contacts[i].dedup_status == 'new'
            assert contacts[i].dedup_method is None
            assert contacts[i].connection_id is None

    def test_idempotent_reimport(self):
        """Re-import same CSV → all match existing connections → 0 new."""
        entries = _make_entries()
        contacts = [
            _make_cs(linkedin_url='https://linkedin.com/in/alice-smith'),
            _make_cs(linkedin_url='https://linkedin.com/in/bob-jones'),
            _make_cs(email='carol@corp.com'),
        ]

        run_dedup(contacts, entries)

        for cs in contacts:
            assert cs.dedup_status == 'matched'
        assert contacts[0].connection_id == 'conn_1'
        assert contacts[1].connection_id == 'conn_2'
        assert contacts[2].connection_id == 'conn_3'

    def test_empty_contacts(self):
        """No contacts to dedup — should not error."""
        run_dedup([], _make_entries())

    def test_empty_entries(self):
        """No existing connections — all should be new."""
        contacts = [
            _make_cs(linkedin_url='https://linkedin.com/in/someone'),
            _make_cs(email='test@example.com'),
        ]
        run_dedup(contacts, [])
        for cs in contacts:
            assert cs.dedup_status == 'new'
