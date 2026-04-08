# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import csv
import io
from typing import BinaryIO

from src.linkedout.import_pipeline.converters.base import BaseContactConverter
from src.linkedout.import_pipeline.schemas import ParsedContact


def _valid_name(val: str | None) -> str | None:
    if not val:
        return None
    val = val.strip()
    if not val:
        return None
    if '@' in val:
        return None
    if val.isdigit():
        return None
    return val


class EmailOnlyContactConverter(BaseContactConverter):
    source_type = 'gmail_email_only'

    def detect(self, file: BinaryIO) -> bool:
        pos = file.tell()
        try:
            head = file.read(4096).decode('utf-8-sig')
            first_line = head.split('\n', 1)[0]
            cols = first_line.split(',')
            return 'E-mail 1 - Value' in first_line and 'Labels' in first_line and len(cols) < 30
        finally:
            file.seek(pos)

    def parse(self, file: BinaryIO) -> tuple[list[ParsedContact], list[tuple[int, dict, str]]]:
        text = file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(text))

        contacts: list[ParsedContact] = []
        failed: list[tuple[int, dict, str]] = []

        for row_num, row in enumerate(reader, start=2):
            try:
                first = _valid_name(row.get('First Name', ''))
                last = _valid_name(row.get('Last Name', ''))

                parts = [p for p in [first, last] if p]
                full = ' '.join(parts) if parts else None

                email = row.get('E-mail 1 - Value', '').strip() or None

                contacts.append(ParsedContact(
                    first_name=first,
                    last_name=last,
                    full_name=full,
                    email=email,
                    phone=None,
                    company=None,
                    title=None,
                    linkedin_url=None,
                    connected_at=None,
                    raw_record=dict(row),
                    source_type=self.source_type,
                ))
            except Exception as e:
                failed.append((row_num, dict(row), str(e)))

        return contacts, failed
