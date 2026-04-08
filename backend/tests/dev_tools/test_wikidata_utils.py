# SPDX-License-Identifier: Apache-2.0
"""Unit tests for dev_tools.wikidata_utils (mocked httpx)."""

from unittest.mock import MagicMock, patch

import httpx
from dev_tools.wikidata_utils import batch_sparql_metadata, wikidata_search


class TestWikidataSearch:
    def test_success(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "search": [
                {"id": "Q95", "label": "Google", "description": "American company"}
            ]
        }
        mock_resp.raise_for_status = MagicMock()

        client = MagicMock(spec=httpx.Client)
        client.get.return_value = mock_resp

        result = wikidata_search(client, "Google")
        assert result == {"qid": "Q95", "label": "Google", "description": "American company"}

    def test_empty_results(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"search": []}
        mock_resp.raise_for_status = MagicMock()

        client = MagicMock(spec=httpx.Client)
        client.get.return_value = mock_resp

        result = wikidata_search(client, "xyznonexistent")
        assert result is None

    def test_http_error(self):
        client = MagicMock(spec=httpx.Client)
        client.get.side_effect = httpx.HTTPError("connection failed")

        result = wikidata_search(client, "Google")
        assert result is None


class TestBatchSparqlMetadata:
    def test_basic(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "results": {
                "bindings": [
                    {
                        "item": {"value": "http://www.wikidata.org/entity/Q95"},
                        "employees": {"value": "150000"},
                        "industryLabel": {"value": "Technology"},
                        "founded": {"value": "1998-09-04T00:00:00Z"},
                        "hqLabel": {"value": "Mountain View"},
                        "website": {"value": "https://google.com"},
                    }
                ]
            }
        }
        mock_resp.raise_for_status = MagicMock()

        client = MagicMock(spec=httpx.Client)
        client.get.return_value = mock_resp

        result = batch_sparql_metadata(client, ["Q95"])
        assert "Q95" in result
        assert result["Q95"]["employees"] == "150000"
        assert result["Q95"]["industry"] == "Technology"
        assert result["Q95"]["founded"] == "1998-09-04"
        assert result["Q95"]["hq"] == "Mountain View"

    def test_batching_multiple_calls(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": {"bindings": []}}
        mock_resp.raise_for_status = MagicMock()

        client = MagicMock(spec=httpx.Client)
        client.get.return_value = mock_resp

        qids = [f"Q{i}" for i in range(160)]
        with patch("dev_tools.wikidata_utils.time.sleep"):
            batch_sparql_metadata(client, qids)

        assert client.get.call_count == 2
