# SPDX-License-Identifier: Apache-2.0
import io
from datetime import date

import pytest

from src.linkedout.import_pipeline.converters.linkedin_csv import LinkedInCsvConverter


def _make_file(text: str) -> io.BytesIO:
    return io.BytesIO(text.encode('utf-8'))


SAMPLE_CSV = """\
Notes:
"When exporting your connection data, you may notice..."

First Name,Last Name,URL,Email Address,Company,Position,Connected On
Rahul,Kumar,https://www.linkedin.com/in/rahulkumar,rk@example.com,Acme Analytics,Senior ML Engineer,22 Feb 2026
Maya,,https://www.linkedin.com/in/mayaprofile,,,,7 Feb 2026
Uday,(UT),https://www.linkedin.com/in/udayprofile/,,xmplify.tech,"Founder, CTA",22 Jan 2026
John,Doe,https://www.linkedin.com/in/johndoe?utm_source=connect,,Acme Inc,Engineer,15 Mar 2025
Alice,Smith,https://www.linkedin.com/in/ALICESMITH,alice@example.com,BigCo,VP of Eng,1 Jan 2024
"""


class TestLinkedInCsvConverter:
    def setup_method(self):
        self.converter = LinkedInCsvConverter()

    def test_parse_basic(self):
        contacts, failed = self.converter.parse(_make_file(SAMPLE_CSV))
        assert len(contacts) == 5
        assert len(failed) == 0

    def test_preamble_skipped(self):
        contacts, _ = self.converter.parse(_make_file(SAMPLE_CSV))
        assert contacts[0].first_name == 'Rahul'

    def test_field_mapping(self):
        contacts, _ = self.converter.parse(_make_file(SAMPLE_CSV))
        c = contacts[0]
        assert c.first_name == 'Rahul'
        assert c.last_name == 'Kumar'
        assert c.full_name == 'Rahul Kumar'
        assert c.email == 'rk@example.com'
        assert c.company == 'Acme Analytics'
        assert c.title == 'Senior ML Engineer'
        assert c.source_type == 'linkedin_csv'

    def test_date_parsing_two_digit_day(self):
        contacts, _ = self.converter.parse(_make_file(SAMPLE_CSV))
        assert contacts[0].connected_at == date(2026, 2, 22)

    def test_date_parsing_single_digit_day(self):
        contacts, _ = self.converter.parse(_make_file(SAMPLE_CSV))
        assert contacts[1].connected_at == date(2026, 2, 7)

    def test_missing_fields_are_none(self):
        contacts, _ = self.converter.parse(_make_file(SAMPLE_CSV))
        maya = contacts[1]
        assert maya.last_name is None
        assert maya.email is None
        assert maya.company is None
        assert maya.title is None
        assert maya.full_name == 'Maya'

    def test_nickname_in_last_name_preserved(self):
        contacts, _ = self.converter.parse(_make_file(SAMPLE_CSV))
        uday = contacts[2]
        assert uday.last_name == '(UT)'

    def test_linkedin_url_normalized(self):
        contacts, _ = self.converter.parse(_make_file(SAMPLE_CSV))
        # Trailing slash stripped
        assert contacts[2].linkedin_url == 'https://www.linkedin.com/in/udayprofile'
        # Query params stripped
        assert contacts[3].linkedin_url == 'https://www.linkedin.com/in/johndoe'
        # Lowercased
        assert contacts[4].linkedin_url == 'https://www.linkedin.com/in/alicesmith'

    def test_comma_in_position(self):
        contacts, _ = self.converter.parse(_make_file(SAMPLE_CSV))
        assert contacts[2].title == 'Founder, CTA'

    def test_malformed_row_collected_in_failed(self):
        bad_csv = """\
First Name,Last Name,URL,Email Address,Company,Position,Connected On
Good,Row,https://www.linkedin.com/in/good,,Co,Eng,22 Feb 2026
Bad,Row,https://www.linkedin.com/in/bad,,Co,Eng,INVALID_DATE
"""
        contacts, failed = self.converter.parse(_make_file(bad_csv))
        assert len(contacts) == 1
        assert len(failed) == 1
        assert 'INVALID_DATE' in failed[0][2] or 'does not match' in failed[0][2]

    def test_detect_linkedin_csv(self):
        f = _make_file(SAMPLE_CSV)
        assert self.converter.detect(f) is True

    def test_detect_non_linkedin(self):
        f = _make_file('Given Name,Family Name,E-mail 1 - Value\nA,B,a@b.com\n')
        assert self.converter.detect(f) is False

    def test_detect_resets_file_position(self):
        f = _make_file(SAMPLE_CSV)
        self.converter.detect(f)
        assert f.tell() == 0

    def test_raw_record_stored(self):
        contacts, _ = self.converter.parse(_make_file(SAMPLE_CSV))
        assert 'First Name' in contacts[0].raw_record
        assert contacts[0].raw_record['First Name'] == 'Rahul'
