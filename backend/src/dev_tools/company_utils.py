# SPDX-License-Identifier: Apache-2.0
"""Company-specific utilities for LinkedOut enrichment.

Provides: normalize_company_name, resolve_subsidiary, compute_size_tier,
SUBSIDIARY_MAP.
"""

import re
from typing import Optional

from cleanco import basename as cleanco_basename

# Hardcoded subsidiary → parent mapping.
# Keys are lowercased. Values are the canonical parent name.
SUBSIDIARY_MAP = {
    # Amazon
    "amazon web services": "Amazon",
    "aws": "Amazon",
    # Google
    "google india": "Google",
    "google cloud": "Google",
    "google cloud - minnesota": "Google",
    "google deepmind": "Google",
    "google[x]": "Google",
    "google for startups": "Google",
    # Meta
    "meta platforms": "Meta",
    "facebook": "Meta",
    "instagram": "Meta",
    "whatsapp": "Meta",
    # Microsoft
    "microsoft india": "Microsoft",
    "linkedin": "Microsoft",
    "github": "Microsoft",
    # Consulting
    "accenture in india": "Accenture",
    "kpmg india": "KPMG",
    "kpmg in india": "KPMG",
    "deloitte india": "Deloitte",
    "deloitte in india": "Deloitte",
    "ey india": "EY",
    "ernst & young india": "EY",
    "pwc india": "PwC",
    # Samsung
    "samsung r&d institute india": "Samsung",
    "samsung india": "Samsung",
    # Dell
    "dell technologies": "Dell",
    # IBM
    "ibm india": "IBM",
    # Oracle
    "oracle india": "Oracle",
    # Cisco
    "cisco india": "Cisco",
    # NetApp
    "netapp inc": "NetApp",
    "netapp india": "NetApp",
    "netapp systems (india) private ltd": "NetApp",
    "netapp cloud data services": "NetApp",
    "network appliance inc. (netapp)": "NetApp",
    "netapp (network appliance, inc.)": "NetApp",
    # Mindtree / LTIMindtree
    "ltimindtree": "Mindtree",
    "mindtree limited": "Mindtree",
    "mindtree ltd": "Mindtree",
    "mindtree consulting": "Mindtree",
    "mindtree consulting pvt ltd.": "Mindtree",
    # VMware
    "vmware by broadcom": "VMware",
    # Crio
    "crio": "Crio.Do",
    "crio.tech": "Crio.Do",
}

_REGIONAL_SUFFIX_RE = re.compile(
    r"^(.+?)\s+(?:in\s+)?(?:india|china|japan|germany|uk|us|usa|brazil|singapore|australia)\s*$",
    re.IGNORECASE,
)


def normalize_company_name(name: Optional[str]) -> Optional[str]:
    """Strip legal suffixes (LLC, Inc, Pvt Ltd, etc.) from company name.

    Returns None if name is None or empty after stripping.
    """
    if not name:
        return None
    stripped = cleanco_basename(name.strip())
    return stripped if stripped else None


def resolve_subsidiary(name: Optional[str]) -> Optional[str]:
    """Check if name is a known subsidiary or regional variant.

    Returns the parent company name, or None if not a subsidiary.
    """
    if not name:
        return None

    lowered = name.strip().lower()

    if lowered in SUBSIDIARY_MAP:
        return SUBSIDIARY_MAP[lowered]

    match = _REGIONAL_SUFFIX_RE.match(name.strip())
    if match:
        base = match.group(1).strip()
        if base:
            return base

    return None


def compute_size_tier(employee_count: Optional[int]) -> Optional[str]:
    """Compute company size tier from employee count.

    Thresholds (5-tier):
        tiny: ≤10, small: ≤50, mid: ≤200, large: ≤1000, enterprise: >1000

    Returns None when no employee data is available.
    """
    if employee_count is None:
        return None
    if employee_count <= 10:
        return "tiny"
    if employee_count <= 50:
        return "small"
    if employee_count <= 200:
        return "mid"
    if employee_count <= 1000:
        return "large"
    return "enterprise"
