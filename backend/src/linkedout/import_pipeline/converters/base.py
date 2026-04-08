# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO

from src.linkedout.import_pipeline.schemas import ParsedContact


class BaseContactConverter(ABC):
    source_type: str

    @abstractmethod
    def parse(self, file: BinaryIO) -> tuple[list[ParsedContact], list[tuple[int, dict, str]]]:
        """Parse uploaded file into normalized contacts.

        Returns:
            (parsed_contacts, failed_rows) where failed_rows = [(row_number, raw_data, error_reason)]
        """

    @abstractmethod
    def detect(self, file: BinaryIO) -> bool:
        """Return True if this converter can handle the file."""
