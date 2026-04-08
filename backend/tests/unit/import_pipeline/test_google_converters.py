# SPDX-License-Identifier: Apache-2.0
import io
import pytest

from src.linkedout.import_pipeline.converters.google_email import EmailOnlyContactConverter
from src.linkedout.import_pipeline.converters.google_job import GoogleJobContactConverter
from src.linkedout.import_pipeline.converters.google_phone import PhoneContactConverter
from src.linkedout.import_pipeline.converters.registry import detect_converter, get_converter


def _make_file(text: str) -> io.BytesIO:
    return io.BytesIO(text.encode('utf-8'))


# --- Google Job Converter ---

GOOGLE_JOB_CSV = """\
Name,Given Name,Additional Name,Family Name,Yomi Name,Given Name Yomi,Additional Name Yomi,Family Name Yomi,Name Prefix,Name Suffix,Initials,Nickname,Short Name,Maiden Name,Birthday,Gender,Location,Billing Information,Directory Server,Mileage,Occupation,Hobby,Sensitivity,Priority,Subject,Notes,Group Membership,E-mail 1 - Type,E-mail 1 - Value,Website 1 - Type,Website 1 - Value
Alice Brown,Alice,,Brown,,,,,,,,,,,,,,,,,,,,,,,* My Contacts ::: Exit,* Work,alice@google.com,Profile,http://www.google.com/profiles/12345
Bob Smith,Bob,,Smith,,,,,,,,,,,,,,,,,,,,,,,Exit,,bob@google.com,,
Jane,Jane,,,,,,,,,,,,,,,,,,,,,,,,,,*,,jane@example.com,,
"""


class TestGoogleJobConverter:
    def setup_method(self):
        self.converter = GoogleJobContactConverter()

    def test_parse_basic(self):
        contacts, failed = self.converter.parse(_make_file(GOOGLE_JOB_CSV))
        assert len(contacts) == 3
        assert len(failed) == 0

    def test_field_mapping(self):
        contacts, _ = self.converter.parse(_make_file(GOOGLE_JOB_CSV))
        c = contacts[0]
        assert c.first_name == 'Alice'
        assert c.last_name == 'Brown'
        assert c.full_name == 'Alice Brown'
        assert c.email == 'alice@google.com'
        assert c.phone is None
        assert c.company is None
        assert c.linkedin_url is None
        assert c.source_type == 'google_contacts_job'

    def test_missing_family_name(self):
        contacts, _ = self.converter.parse(_make_file(GOOGLE_JOB_CSV))
        jane = contacts[2]
        assert jane.first_name == 'Jane'
        assert jane.last_name is None

    def test_detect(self):
        assert self.converter.detect(_make_file(GOOGLE_JOB_CSV)) is True

    def test_detect_resets_position(self):
        f = _make_file(GOOGLE_JOB_CSV)
        self.converter.detect(f)
        assert f.tell() == 0


# --- Phone Contact Converter ---

# Build a 67-column header for Outlook format
_PHONE_COLS = [
    'First Name', 'Middle Name', 'Last Name', 'Title', 'Suffix',
    'Initials', 'Web Page', 'Gender', 'Birthday', 'Anniversary',
    'E-mail Address', 'E-mail 2 Address', 'E-mail 3 Address',
    'Primary Phone', 'Home Phone', 'Home Phone 2', 'Mobile Phone',
    'Pager', 'Home Fax', 'Home Address', 'Home Street', 'Home Street 2',
    'Home Street 3', 'Home City', 'Home Postal Code', 'Home State',
    'Home Country', 'Spouse', 'Children', 'Managers Name',
    'Assistants Name', 'Referred By', 'Company Main Phone', 'Business Phone',
    'Business Phone 2', 'Business Fax', 'Assistants Phone',
    'Company', 'Job Title', 'Department', 'Office Location',
    'Organizational ID Number', 'Profession', 'Account',
    'Business Address', 'Business Street', 'Business Street 2',
    'Business Street 3', 'Business City', 'Business Postal Code',
    'Business State', 'Business Country', 'Other Phone', 'Other Fax',
    'Other Address', 'Other Street', 'Other Street 2', 'Other Street 3',
    'Other City', 'Other Postal Code', 'Other State', 'Other Country',
    'Callback', 'Car Phone', 'ISDN', 'Radio Phone', 'Categories',
]

PHONE_HEADER = ','.join(_PHONE_COLS)


def _phone_row(**kwargs) -> str:
    vals = [''] * len(_PHONE_COLS)
    col_map = {col: i for i, col in enumerate(_PHONE_COLS)}
    for k, v in kwargs.items():
        vals[col_map[k]] = v
    return ','.join(vals)


class TestPhoneContactConverter:
    def setup_method(self):
        self.converter = PhoneContactConverter()

    def test_parse_basic(self):
        csv_text = PHONE_HEADER + '\n' + _phone_row(**{
            'First Name': 'Arjun',
            'Last Name': 'Patel',
            'Mobile Phone': '+91 79943 34501',
        }) + '\n'
        contacts, failed = self.converter.parse(_make_file(csv_text))
        assert len(contacts) == 1
        assert contacts[0].first_name == 'Arjun'
        assert contacts[0].phone == '+917994334501'
        assert contacts[0].source_type == 'contacts_phone'

    def test_phone_normalization_us(self):
        csv_text = PHONE_HEADER + '\n' + _phone_row(**{
            'First Name': 'Bob',
            'Mobile Phone': '+1 (408) 881-4767',
        }) + '\n'
        contacts, _ = self.converter.parse(_make_file(csv_text))
        assert contacts[0].phone == '+14088814767'

    def test_phone_coalesce_order(self):
        csv_text = PHONE_HEADER + '\n' + _phone_row(**{
            'First Name': 'Test',
            'Primary Phone': '+919876543210',
        }) + '\n'
        contacts, _ = self.converter.parse(_make_file(csv_text))
        assert contacts[0].phone == '+919876543210'

    def test_bare_indian_number(self):
        csv_text = PHONE_HEADER + '\n' + _phone_row(**{
            'First Name': 'Dev',
            'Mobile Phone': '93413 21918',
        }) + '\n'
        contacts, _ = self.converter.parse(_make_file(csv_text))
        assert contacts[0].phone == '+919341321918'

    def test_name_cleaning_strips_parens(self):
        csv_text = PHONE_HEADER + '\n' + _phone_row(**{
            'First Name': 'Abbas (friend)',
            'Mobile Phone': '+919876543210',
        }) + '\n'
        contacts, _ = self.converter.parse(_make_file(csv_text))
        assert contacts[0].first_name == 'Abbas'

    def test_missing_last_name(self):
        csv_text = PHONE_HEADER + '\n' + _phone_row(**{
            'First Name': 'Solo',
            'Mobile Phone': '+919876543210',
        }) + '\n'
        contacts, _ = self.converter.parse(_make_file(csv_text))
        assert contacts[0].last_name is None
        assert contacts[0].full_name == 'Solo'

    def test_detect(self):
        csv_text = PHONE_HEADER + '\n' + _phone_row(**{'First Name': 'A'}) + '\n'
        assert self.converter.detect(_make_file(csv_text)) is True

    def test_detect_resets_position(self):
        f = _make_file(PHONE_HEADER + '\n')
        self.converter.detect(f)
        assert f.tell() == 0


# --- Email-Only Converter ---

EMAIL_ONLY_CSV = """\
First Name,Middle Name,Last Name,Phonetic First Name,Phonetic Middle Name,Phonetic Last Name,Name Prefix,Name Suffix,Nickname,File As,Organization Name,Organization Title,Organization Department,Birthday,Notes,Photo,Labels,E-mail 1 - Label,E-mail 1 - Value,Phone 1 - Label,Phone 1 - Value,Address 1 - Label,Address 1 - Formatted,Website 1 - Label,Website 1 - Value,Event 1 - Label,Event 1 - Value
Alice,,Smith,,,,,,,,,,,,,,* Other Contacts,* ,alice@example.com,,,,,,,,
user@gmail.com,,,,,,,,,,,,,,,,* Other Contacts,* ,user@gmail.com,,,,,,,,
3966,,SBI,,,,,,,,,,,,,,* Other Contacts,* ,sbi.03966@sbi.co.in,,,,,,,,
91springboard,,Boosters,,,,,,,,,,,,,,* Other Contacts,* ,boosters@91springboard.com,,,,,,,,
,,,,,,,,,,,,,,,,* Other Contacts,* ,anonymous@test.com,,,,,,,,
"""


class TestEmailOnlyConverter:
    def setup_method(self):
        self.converter = EmailOnlyContactConverter()

    def test_parse_basic(self):
        contacts, failed = self.converter.parse(_make_file(EMAIL_ONLY_CSV))
        assert len(contacts) == 5
        assert len(failed) == 0

    def test_valid_name_kept(self):
        contacts, _ = self.converter.parse(_make_file(EMAIL_ONLY_CSV))
        assert contacts[0].first_name == 'Alice'
        assert contacts[0].last_name == 'Smith'
        assert contacts[0].full_name == 'Alice Smith'

    def test_email_as_name_rejected(self):
        contacts, _ = self.converter.parse(_make_file(EMAIL_ONLY_CSV))
        c = contacts[1]
        assert c.first_name is None
        assert c.email == 'user@gmail.com'

    def test_numeric_name_rejected(self):
        contacts, _ = self.converter.parse(_make_file(EMAIL_ONLY_CSV))
        c = contacts[2]
        assert c.first_name is None

    def test_empty_names(self):
        contacts, _ = self.converter.parse(_make_file(EMAIL_ONLY_CSV))
        anon = contacts[4]
        assert anon.first_name is None
        assert anon.last_name is None
        assert anon.full_name is None
        assert anon.email == 'anonymous@test.com'

    def test_source_type(self):
        contacts, _ = self.converter.parse(_make_file(EMAIL_ONLY_CSV))
        assert contacts[0].source_type == 'gmail_email_only'

    def test_detect(self):
        assert self.converter.detect(_make_file(EMAIL_ONLY_CSV)) is True

    def test_detect_resets_position(self):
        f = _make_file(EMAIL_ONLY_CSV)
        self.converter.detect(f)
        assert f.tell() == 0


# --- Registry Tests ---

class TestRegistry:
    def test_get_converter_valid(self):
        c = get_converter('linkedin_csv')
        assert c.source_type == 'linkedin_csv'

    def test_get_converter_invalid(self):
        with pytest.raises(ValueError, match='Unknown source_type'):
            get_converter('nonexistent')

    def test_detect_linkedin(self):
        csv_text = "Notes:\nblah\n\nFirst Name,Last Name,URL,Email Address,Company,Position,Connected On\nA,B,http://x,,C,D,1 Jan 2025\n"
        c = detect_converter(_make_file(csv_text))
        assert c is not None
        assert c.source_type == 'linkedin_csv'

    def test_detect_google_job(self):
        c = detect_converter(_make_file(GOOGLE_JOB_CSV))
        assert c is not None
        assert c.source_type == 'google_contacts_job'

    def test_detect_phone(self):
        csv_text = PHONE_HEADER + '\n' + _phone_row(**{'First Name': 'A'}) + '\n'
        c = detect_converter(_make_file(csv_text))
        assert c is not None
        assert c.source_type == 'contacts_phone'

    def test_detect_email_only(self):
        c = detect_converter(_make_file(EMAIL_ONLY_CSV))
        assert c is not None
        assert c.source_type == 'gmail_email_only'

    def test_detect_unknown(self):
        c = detect_converter(_make_file('col1,col2\na,b\n'))
        assert c is None
