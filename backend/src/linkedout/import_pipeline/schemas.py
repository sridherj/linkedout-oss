# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class ParsedContact:
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    title: str | None = None
    linkedin_url: str | None = None
    connected_at: date | None = None
    raw_record: dict = field(default_factory=dict)
    source_type: str = ''
