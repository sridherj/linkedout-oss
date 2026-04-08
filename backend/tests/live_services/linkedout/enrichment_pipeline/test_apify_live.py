# SPDX-License-Identifier: Apache-2.0
"""Live Apify enrichment tests — require real API keys.

These tests call the Apify actor directly and validate real data is returned.
Run with: precommit-tests --suite live_services
"""
import pytest

from linkedout.enrichment_pipeline.apify_client import LinkedOutApifyClient, get_platform_apify_key

SJ_LINKEDIN_URL = 'https://www.linkedin.com/in/sridher-jeyachandran'


@pytest.mark.live_services
def test_apify_enriches_sridher_profile():
    """Enrich SJ's LinkedIn profile and assert core fields are populated.

    Fails if Apify returns no data — this is the canary for enrichment health.
    """
    api_key = get_platform_apify_key()
    client = LinkedOutApifyClient(api_key=api_key)

    result = client.enrich_profile_sync(SJ_LINKEDIN_URL)

    assert result is not None, (
        f"Apify returned no data for {SJ_LINKEDIN_URL}. "
        "Check API key rotation, actor ID, and input format."
    )
    assert result.get('firstName') == 'Sridher', (
        f"Expected firstName='Sridher', got: {result.get('firstName')!r}"
    )
    assert result.get('lastName') == 'Jeyachandran', (
        f"Expected lastName='Jeyachandran', got: {result.get('lastName')!r}"
    )
    assert result.get('headline'), (
        f"Expected non-empty headline, got: {result.get('headline')!r}"
    )
    # Validate experiences are returned (enrichment pipeline depends on this)
    experiences = result.get('experience', []) or []
    assert len(experiences) > 0, "Expected at least one experience entry"
