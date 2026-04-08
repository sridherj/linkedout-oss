# SPDX-License-Identifier: Apache-2.0
"""Live service tests for Wikidata API (excluded from default test runs)."""

import httpx
import pytest

from dev_tools.wikidata_utils import HTTP_HEADERS, batch_sparql_metadata, wikidata_search


@pytest.mark.live_services
def test_search_google():
    with httpx.Client(headers=HTTP_HEADERS) as client:
        result = wikidata_search(client, "Google")
    assert result is not None
    assert result["qid"] == "Q95"


@pytest.mark.live_services
def test_metadata_google():
    with httpx.Client(headers=HTTP_HEADERS) as client:
        result = batch_sparql_metadata(client, ["Q95"])
    assert "Q95" in result
    meta = result["Q95"]
    assert meta["industry"]
    assert meta["employees"]
