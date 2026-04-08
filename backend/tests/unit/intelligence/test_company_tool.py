# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the company resolution and classification tools."""
from unittest.mock import MagicMock, patch

import pytest

from linkedout.intelligence.tools.company_tool import (
    _infer_company_type,
    classify_company,
    resolve_company_aliases,
)


class TestResolveCompanyAliases:
    def _mock_session(self, company_row=None, alias_rows=None):
        session = MagicMock()
        found_company = [False]

        def mock_execute(query, params=None):
            result = MagicMock()
            query_text = str(query.text) if hasattr(query, 'text') else str(query)
            if "company_alias" in query_text:
                result.fetchall.return_value = alias_rows or []
            elif "FROM company" in query_text:
                if company_row and not found_company[0]:
                    result.fetchone.return_value = company_row
                    found_company[0] = True
                else:
                    result.fetchone.return_value = None
            else:
                result.fetchone.return_value = None
                result.fetchall.return_value = []
            return result

        session.execute.side_effect = mock_execute
        return session

    def test_empty_name_returns_error(self):
        session = MagicMock()
        result = resolve_company_aliases("", session)
        assert "error" in result

    def test_whitespace_name_returns_error(self):
        session = MagicMock()
        result = resolve_company_aliases("   ", session)
        assert "error" in result

    def test_resolves_known_subsidiary(self):
        session = self._mock_session(
            company_row=("co_123", "Amazon", "Internet", "enterprise", 1500000, "Seattle", "US"),
            alias_rows=[("AWS",), ("Amazon Web Services",)],
        )
        result = resolve_company_aliases("AWS", session)
        assert result["subsidiary_of"] == "Amazon"
        assert result["company_id"] == "co_123"
        assert len(result["aliases"]) == 2

    def test_no_db_match_returns_input_name(self):
        session = self._mock_session(company_row=None)
        result = resolve_company_aliases("UnknownCorp", session)
        assert result["canonical_name"] == "UnknownCorp"
        assert result["company_id"] is None
        assert result["aliases"] == []

    def test_returns_structured_json(self):
        session = self._mock_session(
            company_row=("co_1", "Google", "Internet", "enterprise", 180000, "Mountain View", "US"),
            alias_rows=[],
        )
        result = resolve_company_aliases("Google", session)
        assert "canonical_name" in result
        assert "normalized_name" in result
        assert "subsidiary_of" in result
        assert "company_id" in result
        assert "aliases" in result
        assert isinstance(result["aliases"], list)


class TestClassifyCompany:
    def _mock_session(self, rows_by_name=None):
        """Create mock session that returns different rows based on company name."""
        session = MagicMock()
        rows_by_name = rows_by_name or {}

        def mock_execute(query, params=None):
            result = MagicMock()
            pattern = (params or {}).get("pattern", "")
            name = pattern.strip("%")
            row = rows_by_name.get(name)
            result.fetchone.return_value = row
            return result

        session.execute.side_effect = mock_execute
        return session

    def test_empty_list_returns_error(self):
        session = MagicMock()
        result = classify_company([], session)
        assert "error" in result

    def test_classifies_from_db_data(self):
        session = self._mock_session({
            "Google": ("Google", "Internet", "enterprise", 180000),
        })
        result = classify_company(["Google"], session)
        assert len(result["companies"]) == 1
        assert result["companies"][0]["type"] == "enterprise"

    def test_caps_at_10_companies(self):
        session = self._mock_session()
        names = [f"Company{i}" for i in range(15)]
        result = classify_company(names, session)
        assert len(result["companies"]) == 10

    def test_returns_structured_json(self):
        session = self._mock_session({
            "Startup": ("Startup", "Software", "small", 50),
        })
        result = classify_company(["Startup"], session)
        company = result["companies"][0]
        assert "name" in company
        assert "canonical_name" in company
        assert "type" in company
        assert "industry" in company
        assert "size_tier" in company


class TestInferCompanyType:
    def test_it_services_by_name(self):
        assert _infer_company_type("TCS", None, None, None) == "services"
        assert _infer_company_type("Infosys Limited", None, None, None) == "services"
        assert _infer_company_type("Wipro Technologies", None, None, None) == "services"

    def test_it_services_by_industry(self):
        assert _infer_company_type("RandomCo", "IT Outsourcing", None, None) == "services"

    def test_consulting_by_name(self):
        assert _infer_company_type("McKinsey & Company", None, None, None) == "consulting"
        assert _infer_company_type("Deloitte", None, None, None) == "consulting"

    def test_startup_by_size(self):
        assert _infer_company_type("CoolAI", "Software", "small", 30) == "startup"

    def test_enterprise_by_size(self):
        assert _infer_company_type("BigCorp", "Software", "enterprise", 50000) == "enterprise"

    def test_product_by_industry(self):
        assert _infer_company_type("SomeSaaS", "Software Development", None, 500) == "product"

    def test_unknown_when_no_data(self):
        assert _infer_company_type("Mystery Inc", None, None, None) == "unknown"
