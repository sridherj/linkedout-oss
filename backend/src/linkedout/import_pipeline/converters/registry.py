# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from typing import BinaryIO

from src.linkedout.import_pipeline.converters.base import BaseContactConverter
from src.linkedout.import_pipeline.converters.google_email import EmailOnlyContactConverter
from src.linkedout.import_pipeline.converters.google_job import GoogleJobContactConverter
from src.linkedout.import_pipeline.converters.google_phone import PhoneContactConverter
from src.linkedout.import_pipeline.converters.linkedin_csv import LinkedInCsvConverter

CONVERTER_REGISTRY: dict[str, type[BaseContactConverter]] = {
    'linkedin_csv': LinkedInCsvConverter,
    'google_contacts_job': GoogleJobContactConverter,
    'contacts_phone': PhoneContactConverter,
    'gmail_email_only': EmailOnlyContactConverter,
}

# Detection order matters: more specific first
_DETECTION_ORDER: list[type[BaseContactConverter]] = [
    LinkedInCsvConverter,
    GoogleJobContactConverter,
    PhoneContactConverter,
    EmailOnlyContactConverter,
]


def get_converter(source_type: str) -> BaseContactConverter:
    cls = CONVERTER_REGISTRY.get(source_type)
    if cls is None:
        raise ValueError(f'Unknown source_type: {source_type}')
    return cls()


def detect_converter(file: BinaryIO) -> BaseContactConverter | None:
    for cls in _DETECTION_ORDER:
        converter = cls()
        if converter.detect(file):
            return converter
    return None
