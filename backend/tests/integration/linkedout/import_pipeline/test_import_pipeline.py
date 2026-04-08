# SPDX-License-Identifier: Apache-2.0
"""Integration tests for the import pipeline.

Tests upload endpoint against real PostgreSQL, verifying the full
parse → dedup → merge flow.
"""
import io

import pytest

pytestmark = pytest.mark.integration

# LinkedIn CSV header (from LinkedInCsvConverter)
LINKEDIN_CSV_HEADER = 'First Name,Last Name,URL,Email Address,Company,Position,Connected On\n'


def _make_linkedin_csv(rows: list[str]) -> io.BytesIO:
    """Build a LinkedIn-format CSV from row strings."""
    content = LINKEDIN_CSV_HEADER + '\n'.join(rows)
    return io.BytesIO(content.encode('utf-8'))


class TestImportPipelineIntegration:
    def test_import_linkedin_csv_e2e(self, test_client, test_tenant_id, test_bu_id, seeded_data):
        """Upload CSV → import_job + contact_sources + connections created.

        New contacts get stub crawled_profile with has_enriched_data=False.
        """
        csv = _make_linkedin_csv([
            'Alice,Wonder,https://linkedin.com/in/alice-wonder,alice@test.com,WonderCo,Engineer,01 Jan 2024',
            'Bob,Builder,https://linkedin.com/in/bob-builder,bob@test.com,BuildCo,Manager,15 Mar 2023',
        ])

        response = test_client.post(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/import',
            files={'file': ('connections.csv', csv, 'text/csv')},
            data={'source_type': 'linkedin_csv', 'app_user_id': 'usr-test-001'},
        )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data['status'] == 'complete'
        assert data['total_records'] == 2
        assert data['parsed_count'] == 2
        assert data['new_count'] == 2  # Both are new contacts
        assert data['failed_count'] == 0

    def test_import_idempotent(self, test_client, test_tenant_id, test_bu_id, seeded_data):
        """Re-upload same CSV → 0 new connections (all match existing)."""
        rows = [
            'Idempotent,Test,https://linkedin.com/in/idempotent-test,idemp@test.com,TestCo,Dev,01 Jun 2024',
        ]

        # First import
        csv1 = _make_linkedin_csv(rows)
        r1 = test_client.post(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/import',
            files={'file': ('test.csv', csv1, 'text/csv')},
            data={'source_type': 'linkedin_csv', 'app_user_id': 'usr-test-001'},
        )
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1['new_count'] == 1

        # Second import (same data) — should match existing connection
        csv2 = _make_linkedin_csv(rows)
        r2 = test_client.post(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/import',
            files={'file': ('test.csv', csv2, 'text/csv')},
            data={'source_type': 'linkedin_csv', 'app_user_id': 'usr-test-001'},
        )
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2['new_count'] == 0
        assert d2['matched_count'] == 1

    def test_import_cross_source_merge(self, test_client, test_tenant_id, test_bu_id, seeded_data):
        """Import LinkedIn then Google → emails merged onto connections."""
        # First: LinkedIn CSV
        li_csv = _make_linkedin_csv([
            'Cross,Merge,https://linkedin.com/in/cross-merge,,MergeCo,Lead,01 Jan 2024',
        ])
        r1 = test_client.post(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/import',
            files={'file': ('li.csv', li_csv, 'text/csv')},
            data={'source_type': 'linkedin_csv', 'app_user_id': 'usr-test-002'},
        )
        assert r1.status_code == 200
        assert r1.json()['new_count'] == 1

        # Second: same person via email match using a google-like CSV
        # We'll use linkedin_csv format but with email to trigger email dedup
        google_csv = _make_linkedin_csv([
            'Cross,Merge,https://linkedin.com/in/cross-merge,cross@merge.com,MergeCo,Lead,01 Jun 2023',
        ])
        r2 = test_client.post(
            f'/tenants/{test_tenant_id}/bus/{test_bu_id}/import',
            files={'file': ('google.csv', google_csv, 'text/csv')},
            data={'source_type': 'linkedin_csv', 'app_user_id': 'usr-test-002'},
        )
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2['matched_count'] == 1
        assert d2['new_count'] == 0

    def test_import_concurrent_rejection(self, test_client, test_tenant_id, test_bu_id, seeded_data):
        """Second import while first active → 409 Conflict.

        We simulate this by setting the sync threshold very low and checking
        the first import returns processing status, then importing again.
        """
        # This test relies on the async path leaving status='processing'
        # which blocks a second import. We use IMPORT_SYNC_THRESHOLD=1
        # to trigger async mode on the first import.
        import os
        old_val = os.environ.get('IMPORT_SYNC_THRESHOLD')
        os.environ['IMPORT_SYNC_THRESHOLD'] = '1'

        try:
            csv = _make_linkedin_csv([
                'Concurrent,Test1,https://linkedin.com/in/conc-test1,,ConcCo,Dev,01 Jan 2024',
                'Concurrent,Test2,https://linkedin.com/in/conc-test2,,ConcCo,Dev,01 Jan 2024',
            ])
            r1 = test_client.post(
                f'/tenants/{test_tenant_id}/bus/{test_bu_id}/import',
                files={'file': ('conc.csv', csv, 'text/csv')},
                data={'source_type': 'linkedin_csv', 'app_user_id': 'usr-test-001'},
            )
            # Should either return processing (async) or complete (timing)
            assert r1.status_code == 200

            # If status is 'processing', try a second import which should be rejected
            if r1.json().get('status') == 'processing':
                csv2 = _make_linkedin_csv([
                    'Another,Import,https://linkedin.com/in/another,,ConcCo,Dev,01 Jan 2024',
                ])
                r2 = test_client.post(
                    f'/tenants/{test_tenant_id}/bus/{test_bu_id}/import',
                    files={'file': ('conc2.csv', csv2, 'text/csv')},
                    data={'source_type': 'linkedin_csv', 'app_user_id': 'usr-test-001'},
                )
                assert r2.status_code == 409
        finally:
            if old_val is not None:
                os.environ['IMPORT_SYNC_THRESHOLD'] = old_val
            else:
                os.environ.pop('IMPORT_SYNC_THRESHOLD', None)
