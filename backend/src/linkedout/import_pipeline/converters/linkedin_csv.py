# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import BinaryIO
from urllib.parse import urlparse, urlunparse

from src.linkedout.import_pipeline.converters.base import BaseContactConverter
from src.linkedout.import_pipeline.schemas import ParsedContact

EXPECTED_HEADER = ['First Name', 'Last Name', 'URL', 'Email Address', 'Company', 'Position', 'Connected On']


def _normalize_linkedin_url(url: str) -> str | None:
    if not url or not url.strip():
        return None
    url = url.strip().lower()
    parsed = urlparse(url)
    path = parsed.path.rstrip('/')
    return urlunparse((parsed.scheme, parsed.netloc, path, '', '', ''))


def _parse_connected_date(val: str) -> 'date | None':
    if not val or not val.strip():
        return None
    return datetime.strptime(val.strip(), '%d %b %Y').date()


class LinkedInCsvConverter(BaseContactConverter):
    source_type = 'linkedin_csv'

    def detect(self, file: BinaryIO) -> bool:
        pos = file.tell()
        try:
            text = file.read().decode('utf-8-sig')
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                if 'First Name' in stripped and 'Last Name' in stripped and 'URL' in stripped:
                    return True
            return False
        finally:
            file.seek(pos)

    def parse(self, file: BinaryIO) -> tuple[list[ParsedContact], list[tuple[int, dict, str]]]:
        text = file.read().decode('utf-8-sig')
        lines = text.splitlines()

        # Find header row (skip preamble)
        header_idx = None
        for i, line in enumerate(lines):
            if 'First Name' in line and 'Last Name' in line and 'URL' in line:
                header_idx = i
                break

        if header_idx is None:
            return [], [(0, {}, 'Could not find header row')]

        csv_text = '\n'.join(lines[header_idx:])
        reader = csv.DictReader(io.StringIO(csv_text))

        contacts: list[ParsedContact] = []
        failed: list[tuple[int, dict, str]] = []

        for row_num, row in enumerate(reader, start=header_idx + 2):
            try:
                first = row.get('First Name', '').strip() or None
                last = row.get('Last Name', '').strip() or None

                parts = [p for p in [first, last] if p]
                full = ' '.join(parts) if parts else None

                email_val = row.get('Email Address', '').strip()
                email = email_val if email_val else None

                company = row.get('Company', '').strip() or None
                title = row.get('Position', '').strip() or None

                linkedin_url = _normalize_linkedin_url(row.get('URL', ''))
                connected_at = _parse_connected_date(row.get('Connected On', ''))

                contacts.append(ParsedContact(
                    first_name=first,
                    last_name=last,
                    full_name=full,
                    email=email,
                    phone=None,
                    company=company,
                    title=title,
                    linkedin_url=linkedin_url,
                    connected_at=connected_at,
                    raw_record=dict(row),
                    source_type=self.source_type,
                ))
            except Exception as e:
                failed.append((row_num, dict(row), str(e)))

        return contacts, failed
