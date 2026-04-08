# SPDX-License-Identifier: Apache-2.0
"""Wikidata API utilities for company enrichment.

Provides: wikidata_search, sparql_query, batch_sparql_metadata,
and constants WIKIDATA_API, SPARQL_ENDPOINT, USER_AGENT, HTTP_HEADERS,
SEARCH_DELAY.
"""

import json
import time
from typing import Optional

import httpx

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

SEARCH_DELAY = 0.3

USER_AGENT = "LinkedOut/1.0 (https://github.com/linkedout-oss/linkedout)"
HTTP_HEADERS = {"User-Agent": USER_AGENT}


def wikidata_search(client: httpx.Client, name: str) -> Optional[dict]:
    """Search Wikidata for a company by name, return best match or None.

    Returns {"qid": "Q95", "label": "Google", "description": "..."} or None.
    """
    params = {
        "action": "wbsearchentities",
        "search": name,
        "language": "en",
        "type": "item",
        "limit": 5,
        "format": "json",
    }
    try:
        resp = client.get(WIKIDATA_API, params=params)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, json.JSONDecodeError):
        return None

    results = data.get("search", [])
    if not results:
        return None

    best = results[0]
    return {
        "qid": best["id"],
        "label": best.get("label", ""),
        "description": best.get("description", ""),
    }


def sparql_query(client: httpx.Client, query: str) -> list[dict]:
    """Execute a SPARQL query against Wikidata, return rows as dicts."""
    headers = {"Accept": "application/sparql-results+json"}
    try:
        resp = client.get(
            SPARQL_ENDPOINT,
            params={"query": query},
            headers=headers,
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, json.JSONDecodeError) as e:
        print(f"  SPARQL error: {e}")
        return []

    bindings = data.get("results", {}).get("bindings", [])
    rows = []
    for b in bindings:
        row = {}
        for key, val in b.items():
            row[key] = val.get("value", "")
        rows.append(row)
    return rows


def batch_sparql_metadata(client: httpx.Client, qids: list[str]) -> dict:
    """Fetch P1128, P452, P571, P159, P856 for a batch of Q-numbers.

    Returns {qid: {"employees": str, "industry": str, "founded": str,
                    "hq": str, "website": str}}.
    """
    metadata: dict = {}
    batch_size = 80

    for i in range(0, len(qids), batch_size):
        batch = qids[i : i + batch_size]
        values = " ".join(f"wd:{q}" for q in batch)

        query = f"""
SELECT ?item ?employees ?industryLabel ?founded ?hqLabel ?website WHERE {{
  VALUES ?item {{ {values} }}
  OPTIONAL {{ ?item wdt:P1128 ?employees . }}
  OPTIONAL {{ ?item wdt:P452 ?industry . }}
  OPTIONAL {{ ?item wdt:P571 ?founded . }}
  OPTIONAL {{ ?item wdt:P159 ?hq . }}
  OPTIONAL {{ ?item wdt:P856 ?website . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}
"""
        rows = sparql_query(client, query)

        for row in rows:
            qid = row.get("item", "").split("/")[-1]
            if not qid:
                continue
            if qid not in metadata:
                metadata[qid] = {
                    "employees": row.get("employees", ""),
                    "industry": row.get("industryLabel", ""),
                    "founded": row.get("founded", "")[:10],
                    "hq": row.get("hqLabel", ""),
                    "website": row.get("website", ""),
                }
            else:
                existing = metadata[qid]
                for field, key in [
                    ("employees", "employees"),
                    ("industry", "industryLabel"),
                    ("founded", "founded"),
                    ("hq", "hqLabel"),
                    ("website", "website"),
                ]:
                    if not existing[field] and row.get(key, ""):
                        val = row.get(key, "")
                        existing[field] = val[:10] if field == "founded" else val

        if i + batch_size < len(qids):
            time.sleep(1)

    return metadata
