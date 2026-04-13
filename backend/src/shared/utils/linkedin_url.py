# SPDX-License-Identifier: Apache-2.0
"""LinkedIn URL normalization utility.

Canonical form: https://www.linkedin.com/in/<slug>
"""
import re
from typing import Optional
from urllib.parse import unquote, urlparse


def normalize_linkedin_url(url: str) -> Optional[str]:
    """Normalize a LinkedIn profile URL to canonical form.

    Strips query params, trailing slashes, country prefixes, forces lowercase slug.
    Decodes URL-encoded characters (%e3%83%87 -> ディル) so that DB-stored
    percent-encoded URLs match Apify-returned decoded URLs.

    Returns None for empty/invalid URLs.
    """
    if not url or not url.strip():
        return None

    url = url.strip()

    # Must contain linkedin.com/in/
    if 'linkedin.com/in/' not in url.lower():
        return None

    # Parse the URL
    parsed = urlparse(url if '://' in url else f'https://{url}')

    # Extract the path, strip trailing slashes, decode percent-encoded chars
    path = unquote(parsed.path).rstrip('/')

    # Find the /in/<slug> portion
    match = re.search(r'/in/([^/]+)', path)
    if not match:
        return None

    slug = match.group(1).lower()

    if not slug:
        return None

    return f'https://www.linkedin.com/in/{slug}'
