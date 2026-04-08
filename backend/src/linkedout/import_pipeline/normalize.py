# SPDX-License-Identifier: Apache-2.0
"""Contact field normalization utilities.

URL normalization lives in shared/utils/linkedin_url.py — import from there.
This module handles email and phone normalization only.
"""
from __future__ import annotations

import phonenumbers


def normalize_email(email: str) -> str:
    """Lowercase, strip whitespace. Returns empty string if invalid."""
    if not email:
        return ''
    cleaned = email.strip().lower()
    # Basic sanity: must have @ and a dot after @
    if '@' not in cleaned or '.' not in cleaned.split('@')[-1]:
        return ''
    return cleaned


def normalize_phone(phone: str, default_country: str = 'IN') -> str | None:
    """E.164 format via phonenumbers library. Returns None if unparseable."""
    if not phone or not phone.strip():
        return None
    try:
        parsed = phonenumbers.parse(phone.strip(), default_country)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        return None
    except phonenumbers.NumberParseException:
        return None
