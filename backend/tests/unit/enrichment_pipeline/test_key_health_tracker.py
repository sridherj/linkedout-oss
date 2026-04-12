# SPDX-License-Identifier: Apache-2.0
"""Unit tests for KeyHealthTracker."""
import pytest

from linkedout.enrichment_pipeline.apify_client import (
    AllKeysExhaustedError,
    KeyHealthTracker,
)


class TestKeyHealthTracker:
    """Tests for per-key health tracking and round-robin selection."""

    def test_round_robin_rotation(self):
        tracker = KeyHealthTracker(['key_a', 'key_b', 'key_c'])
        keys = [tracker.next_key() for _ in range(6)]
        assert keys == ['key_a', 'key_b', 'key_c', 'key_a', 'key_b', 'key_c']

    def test_mark_exhausted_skips_key(self):
        tracker = KeyHealthTracker(['key_a', 'key_b', 'key_c'])
        tracker.mark_exhausted('key_b')

        keys = [tracker.next_key() for _ in range(4)]
        assert 'key_b' not in keys
        assert keys == ['key_a', 'key_c', 'key_a', 'key_c']

    def test_mark_invalid_skips_key(self):
        tracker = KeyHealthTracker(['key_a', 'key_b', 'key_c'])
        tracker.mark_invalid('key_a')

        keys = [tracker.next_key() for _ in range(4)]
        assert 'key_a' not in keys
        assert keys == ['key_b', 'key_c', 'key_b', 'key_c']

    def test_all_keys_exhausted_raises(self):
        tracker = KeyHealthTracker(['key_a', 'key_b'])
        tracker.mark_exhausted('key_a')
        tracker.mark_invalid('key_b')

        with pytest.raises(AllKeysExhaustedError, match='All Apify keys are exhausted'):
            tracker.next_key()

    def test_healthy_count(self):
        tracker = KeyHealthTracker(['key_a', 'key_b', 'key_c'])
        assert tracker.healthy_count() == 3

        tracker.mark_exhausted('key_a')
        assert tracker.healthy_count() == 2

        tracker.mark_invalid('key_c')
        assert tracker.healthy_count() == 1

    def test_summary_format(self):
        tracker = KeyHealthTracker(['apify_key_a1b2', 'apify_key_c3d4', 'apify_key_e5f6'])
        tracker.mark_exhausted('apify_key_a1b2')
        tracker.mark_invalid('apify_key_c3d4')

        summary = tracker.summary()
        lines = summary.split('\n')

        assert len(lines) == 3
        # Key hints show only last 4 chars
        assert 'a1b2' in lines[0]
        assert 'credits exhausted' in lines[0]
        assert 'c3d4' in lines[1]
        assert 'invalid or revoked' in lines[1]
        assert 'e5f6' in lines[2]
        assert 'healthy' in lines[2]
