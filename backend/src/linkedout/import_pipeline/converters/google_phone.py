# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import csv
import io
import re
from typing import BinaryIO

import phonenumbers

from src.linkedout.import_pipeline.converters.base import BaseContactConverter
from src.linkedout.import_pipeline.schemas import ParsedContact

_PAREN_RE = re.compile(r'\(.*?\)')


def _clean_name(val: str | None) -> str | None:
    if not val:
        return None
    cleaned = _PAREN_RE.sub('', val).strip()
    return cleaned if cleaned else None


def _normalize_phone(row: dict) -> str | None:
    for col in ['Mobile Phone', 'Primary Phone', 'Home Phone', 'Business Phone']:
        raw = row.get(col, '').strip()
        if not raw:
            continue
        try:
            parsed = phonenumbers.parse(raw, 'IN')
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.NumberParseException:
            continue
    return None


class PhoneContactConverter(BaseContactConverter):
    source_type = 'contacts_phone'

    def detect(self, file: BinaryIO) -> bool:
        pos = file.tell()
        try:
            head = file.read(8192).decode('utf-8-sig')
            first_line = head.split('\n', 1)[0]
            cols = first_line.split(',')
            return 'Mobile Phone' in first_line and len(cols) >= 60
        finally:
            file.seek(pos)

    def parse(self, file: BinaryIO) -> tuple[list[ParsedContact], list[tuple[int, dict, str]]]:
        text = file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(text))

        contacts: list[ParsedContact] = []
        failed: list[tuple[int, dict, str]] = []

        for row_num, row in enumerate(reader, start=2):
            try:
                first = _clean_name(row.get('First Name', ''))
                last = row.get('Last Name', '').strip() or None

                parts = [p for p in [first, last] if p]
                full = ' '.join(parts) if parts else None

                email = row.get('E-mail Address', '').strip() or None
                phone = _normalize_phone(row)
                company = row.get('Company', '').strip() or None
                title = row.get('Job Title', '').strip() or None

                contacts.append(ParsedContact(
                    first_name=first,
                    last_name=last,
                    full_name=full,
                    email=email,
                    phone=phone,
                    company=company,
                    title=title,
                    linkedin_url=None,
                    connected_at=None,
                    raw_record=dict(row),
                    source_type=self.source_type,
                ))
            except Exception as e:
                failed.append((row_num, dict(row), str(e)))

        return contacts, failed
