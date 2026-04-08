# SPDX-License-Identifier: Apache-2.0
"""Unit tests for dev_tools.company_utils."""

import pytest

from dev_tools.company_utils import compute_size_tier, normalize_company_name, resolve_subsidiary


@pytest.mark.parametrize(
    "count, expected",
    [
        (None, None),
        (1, "tiny"),
        (10, "tiny"),
        (11, "small"),
        (50, "small"),
        (51, "mid"),
        (200, "mid"),
        (201, "large"),
        (1000, "large"),
        (1001, "enterprise"),
        (50000, "enterprise"),
    ],
)
def test_compute_size_tier(count, expected):
    assert compute_size_tier(count) == expected


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Google LLC", "Google"),
        ("Tata Consultancy Services Limited", "Tata Consultancy Services"),
        (None, None),
        ("", None),
    ],
)
def test_normalize_company_name(name, expected):
    assert normalize_company_name(name) == expected


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Amazon Web Services", "Amazon"),
        ("Google", None),
        ("Deloitte India", "Deloitte"),
        ("Cisco India", "Cisco"),
        (None, None),
        ("", None),
    ],
)
def test_resolve_subsidiary(name, expected):
    assert resolve_subsidiary(name) == expected
