# SPDX-License-Identifier: Apache-2.0
"""Company matching and deduplication utility.

Used by the Apify loader (Phase 2) and connection enrichment (Phase 3) to
deduplicate companies by LinkedIn URL, normalized name, or subsidiary resolution.
"""
import re
from typing import Optional

from dev_tools.company_utils import resolve_subsidiary


def normalize_company_name(name: str) -> str:
    """Normalize a company name for deduplication.

    Lowercases, strips non-alphanumeric (except spaces), collapses whitespace.
    """
    if not name:
        return ''
    result = name.lower().strip()
    result = re.sub(r'[^a-z0-9\s]', '', result)
    result = re.sub(r'\s+', ' ', result).strip()
    return result


def normalize_company_linkedin_url(url: str) -> Optional[str]:
    """Normalize a LinkedIn company URL for deduplication.

    Extracts the company identifier from various URL formats:
    - https://www.linkedin.com/company/microsoft/
    - https://www.linkedin.com/company/1035/
    - https://www.linkedin.com/search/results/all/?keywords=...  (returns None)

    Returns canonical form: https://www.linkedin.com/company/<slug>
    Returns None for non-company URLs or invalid input.
    """
    if not url or not isinstance(url, str):
        return None

    url = url.strip()

    # Must be a company URL, not a search URL
    if '/company/' not in url.lower():
        return None

    match = re.search(r'/company/([^/?#]+)', url)
    if not match:
        return None

    slug = match.group(1).lower().rstrip('/')
    if not slug:
        return None

    return f'https://www.linkedin.com/company/{slug}'


class CompanyMatcher:
    """In-memory company deduplication.

    Deduplicates by normalized LinkedIn URL (primary) or normalized name (fallback).
    Returns the canonical_name to use as the unique key in the company table.
    """

    def __init__(self):
        # url -> canonical_name
        self._by_url: dict[str, str] = {}
        # normalized_name -> canonical_name
        self._by_name: dict[str, str] = {}
        # canonical_name -> full company dict
        self._companies: dict[str, dict] = {}

    def match_or_create(
        self,
        company_name: str,
        linkedin_url: Optional[str] = None,
        universal_name: Optional[str] = None,
    ) -> Optional[str]:
        """Match an existing company or register a new one.

        Returns the canonical_name if a company was matched/created, None if
        company_name is empty/None.
        """
        if not company_name or not company_name.strip():
            return None

        canonical = company_name.strip()
        norm_name = normalize_company_name(canonical)
        norm_url = normalize_company_linkedin_url(linkedin_url) if linkedin_url else None

        # Try URL match first (strongest signal)
        if norm_url and norm_url in self._by_url:
            existing_canonical = self._by_url[norm_url]
            # Merge universal_name if we didn't have it
            if universal_name and not self._companies[existing_canonical].get('universal_name'):
                self._companies[existing_canonical]['universal_name'] = universal_name
            return existing_canonical

        # Try name match
        if norm_name in self._by_name:
            existing_canonical = self._by_name[norm_name]
            # Merge URL if we didn't have it
            if norm_url and not self._companies[existing_canonical].get('linkedin_url'):
                self._companies[existing_canonical]['linkedin_url'] = norm_url
                self._by_url[norm_url] = existing_canonical
            if universal_name and not self._companies[existing_canonical].get('universal_name'):
                self._companies[existing_canonical]['universal_name'] = universal_name
            return existing_canonical

        # Try subsidiary resolution (e.g. "Google Cloud - Minnesota" → "Google")
        parent = resolve_subsidiary(canonical)
        if parent:
            parent_norm = normalize_company_name(parent)
            if parent_norm in self._by_name:
                existing_canonical = self._by_name[parent_norm]
                # Register this variant's URL under the parent
                if norm_url and not self._companies[existing_canonical].get('linkedin_url'):
                    self._companies[existing_canonical]['linkedin_url'] = norm_url
                    self._by_url[norm_url] = existing_canonical
                # Also register the variant's normalized name so future lookups hit directly
                self._by_name[norm_name] = existing_canonical
                return existing_canonical

        # New company
        company_data = {
            'canonical_name': canonical,
            'normalized_name': norm_name,
            'linkedin_url': norm_url,
            'universal_name': universal_name,
        }
        self._companies[canonical] = company_data
        self._by_name[norm_name] = canonical
        if norm_url:
            self._by_url[norm_url] = canonical

        return canonical

    def get_all_companies(self) -> list[dict]:
        """Return all unique companies as dicts."""
        return list(self._companies.values())

    def get_company(self, canonical_name: str) -> Optional[dict]:
        """Look up a company by canonical name."""
        return self._companies.get(canonical_name)

    def __len__(self) -> int:
        return len(self._companies)
