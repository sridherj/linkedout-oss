# SPDX-License-Identifier: Apache-2.0
"""Nanoid generator for unique IDs.

Nanoid sizes are data-format constants. Changing them would break existing IDs
in the database. 21 chars: standard entity IDs. 8 chars: timestamped suffix
component. These are NOT user-configurable — they are part of the data contract.
"""
from datetime import datetime, timezone

import nanoid


class Nanoid:
    """
    Nanoid generator for unique IDs.

    Generates compact, URL-safe, unique IDs with optional prefixes.
    """

    @staticmethod
    def make_nanoid() -> str:
        """
        Generate a basic nanoid without prefix.

        Returns:
            str: A unique nanoid (21 characters)
        """
        return nanoid.generate(size=21)

    @staticmethod
    def make_nanoid_with_prefix(prefix: str) -> str:
        """
        Generate a nanoid with a prefix.

        Args:
            prefix: Prefix to prepend to the nanoid (e.g., 'project', 'task')

        Returns:
            str: Prefixed nanoid (e.g., 'project_abc123xyz')
        """
        return f'{prefix}_{nanoid.generate(size=21)}'

    @staticmethod
    def make_timestamped_id(prefix: str) -> str:
        """
        Generate a human-readable timestamped ID with a short nanoid suffix.

        Args:
            prefix: Prefix to prepend (e.g., 'arn', 'plg')

        Returns:
            str: ID like 'arn_2026-02-12-14-30-00_xK9mNpQ2'
        """
        ts = datetime.now(timezone.utc).strftime('%Y-%m-%d-%H-%M-%S')
        return f'{prefix}_{ts}_{nanoid.generate(size=8)}'

