# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import csv
import io
from typing import BinaryIO

from src.linkedout.import_pipeline.converters.base import BaseContactConverter
from src.linkedout.import_pipeline.schemas import ParsedContact


class GoogleJobContactConverter(BaseContactConverter):
    source_type = 'google_contacts_job'

    def detect(self, file: BinaryIO) -> bool:
        pos = file.tell()
        try:
            head = file.read(4096).decode('utf-8-sig')
            first_line = head.split('\n', 1)[0]
            return 'Given Name' in first_line and 'E-mail 1 - Value' in first_line and 'Group Membership' in first_line
        finally:
            file.seek(pos)

    def parse(self, file: BinaryIO) -> tuple[list[ParsedContact], list[tuple[int, dict, str]]]:
        text = file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(text))

        contacts: list[ParsedContact] = []
        failed: list[tuple[int, dict, str]] = []

        for row_num, row in enumerate(reader, start=2):
            try:
                first = row.get('Given Name', '').strip() or None
                last = row.get('Family Name', '').strip() or None
                full = row.get('Name', '').strip() or None

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
