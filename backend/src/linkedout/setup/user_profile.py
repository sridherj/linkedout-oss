# SPDX-License-Identifier: Apache-2.0
"""User profile setup — LinkedIn URL to profile record to affinity anchor.

Prompts the user for their LinkedIn URL, validates the format, creates
(or updates) a ``crawled_profile`` record in the database marked as the
owner profile, and explains how affinity scoring uses this anchor.

All operations are idempotent:
- Detects existing owner profile and offers to update or keep
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from linkedout.setup.logging_integration import get_setup_logger
from shared.utilities.operation_report import OperationCounts, OperationReport

# Regex: https://linkedin.com/in/username or https://www.linkedin.com/in/user-name/
_LINKEDIN_URL_RE = re.compile(
    r'^https?://(www\.)?linkedin\.com/in/([\w-]+)/?$'
)

# ── Prompt text (exact wording from setup-flow-ux.md) ────────────────

_PROMPT_LINKEDIN_URL = """\
Step 6 of 14: User Profile

Your LinkedIn profile is the anchor for affinity scoring \u2014 it
determines how "close" each connection is to you based on career
overlap, shared education, and professional signals.

Enter your LinkedIn profile URL
(e.g., https://linkedin.com/in/yourname): """

_MSG_INVALID_URL = """\
  \u2717 That does not look like a LinkedIn profile URL.
    Expected format: https://linkedin.com/in/yourname
    or https://www.linkedin.com/in/yourname

  Enter your LinkedIn profile URL: """


def prompt_linkedin_url() -> str:
    """Prompt the user for their LinkedIn profile URL.

    Loops until a valid URL is entered.

    Returns:
        The validated LinkedIn profile URL.
    """
    url = input(_PROMPT_LINKEDIN_URL).strip()
    while not validate_linkedin_url(url):
        url = input(_MSG_INVALID_URL).strip()
    return url


def validate_linkedin_url(url: str) -> str | None:
    """Validate a LinkedIn profile URL and extract the public ID.

    Accepts URLs like:
    - ``https://linkedin.com/in/johndoe``
    - ``https://www.linkedin.com/in/john-doe/``

    Rejects non-profile URLs like ``/company/`` or ``/school/``.

    Args:
        url: The URL to validate.

    Returns:
        The LinkedIn public identifier (e.g., ``"johndoe"``), or ``None``
        if the URL is not a valid LinkedIn profile URL.
    """
    match = _LINKEDIN_URL_RE.match(url.strip())
    if match:
        return match.group(2)
    return None


def create_user_profile(public_id: str, linkedin_url: str, db_url: str) -> str:
    """Create or update the owner's crawled_profile record in the database.

    Connects directly using SQLAlchemy to avoid circular dependencies
    with the full application stack. The profile is marked with
    ``data_source='setup'`` to identify it as the owner profile.

    Args:
        public_id: LinkedIn public identifier (e.g., ``"johndoe"``).
        linkedin_url: Full LinkedIn profile URL.
        db_url: PostgreSQL connection string.

    Returns:
        The ID of the created or updated profile record.
    """
    log = get_setup_logger('user_profile')

    engine = create_engine(db_url)

    # Normalize the URL to canonical form
    if not linkedin_url.startswith('https://'):
        linkedin_url = f'https://{linkedin_url}'

    with Session(engine) as session:
        # Check for existing profile with this LinkedIn URL
        result = session.execute(
            text(
                "SELECT id FROM crawled_profile "
                "WHERE linkedin_url = :url OR public_identifier = :pid "
                "LIMIT 1"
            ),
            {'url': linkedin_url, 'pid': public_id},
        )
        row = result.fetchone()

        if row:
            profile_id = row[0]
            session.execute(
                text(
                    "UPDATE crawled_profile "
                    "SET public_identifier = :pid, "
                    "    linkedin_url = :url, "
                    "    data_source = 'setup' "
                    "WHERE id = :id"
                ),
                {'pid': public_id, 'url': linkedin_url, 'id': profile_id},
            )
            session.commit()
            log.info("Updated existing owner profile: {}", profile_id)
        else:
            # Generate a prefixed ID matching the entity convention
            from shared.common.nanoids import Nanoid
            profile_id = Nanoid.make_nanoid_with_prefix('cp')
            session.execute(
                text(
                    "INSERT INTO crawled_profile (id, linkedin_url, public_identifier, data_source) "
                    "VALUES (:id, :url, :pid, 'setup')"
                ),
                {'id': profile_id, 'url': linkedin_url, 'pid': public_id},
            )
            session.commit()
            log.info("Created owner profile: {}", profile_id)

    engine.dispose()
    return profile_id


def setup_user_profile(data_dir: Path, db_url: str) -> OperationReport:
    """Full user profile setup orchestration.

    Steps:
    1. Check for existing owner profile
    2. Prompt for LinkedIn URL
    3. Create/update profile record
    4. Explain affinity scoring

    Args:
        data_dir: Root data directory (e.g., ``~/linkedout-data``).
        db_url: PostgreSQL connection string.

    Returns:
        OperationReport summarizing what was done.
    """
    start = time.monotonic()
    succeeded = 0
    skipped = 0
    next_steps: list[str] = []

    # Check for existing owner profile
    existing_id = _find_existing_owner_profile(db_url)
    if existing_id:
        change = input(
            f"  An owner profile already exists (ID: {existing_id}).\n"
            "  Update it? [y/N] "
        ).strip().lower()
        if change not in ('y', 'yes'):
            print("  Keeping existing profile.")
            skipped += 1
            duration_ms = (time.monotonic() - start) * 1000
            return OperationReport(
                operation='user-profile-setup',
                duration_ms=duration_ms,
                counts=OperationCounts(total=1, skipped=1),
            )

    # Prompt for LinkedIn URL
    url = prompt_linkedin_url()
    # prompt_linkedin_url already validates — public_id is guaranteed non-None
    public_id = validate_linkedin_url(url)
    assert public_id is not None  # validated by prompt_linkedin_url loop

    # Create/update profile
    profile_id = create_user_profile(public_id, url, db_url)
    succeeded += 1

    # Explain affinity scoring
    print(
        f"\n  \u2713 Profile created: {profile_id}\n"
        f"    LinkedIn: {url}\n\n"
        "  Your profile is now the anchor for affinity scoring.\n"
        "  After importing connections and generating embeddings,\n"
        "  LinkedOut will rank everyone by how closely they relate\n"
        "  to your career, education, and professional signals."
    )

    # Check for Apify enrichment option
    from linkedout.setup.api_keys import _read_existing_secrets
    secrets = _read_existing_secrets(data_dir)
    if secrets.get('apify_api_key'):
        print(
            "\n  Apify key detected \u2014 you can enrich your profile later\n"
            "  with detailed work history via the Chrome extension."
        )
    else:
        print(
            "\n  Profile enrichment (detailed work history, education) will\n"
            "  come from LinkedIn CSV import or manual data entry."
        )

    duration_ms = (time.monotonic() - start) * 1000

    return OperationReport(
        operation='user-profile-setup',
        duration_ms=duration_ms,
        counts=OperationCounts(
            total=succeeded + skipped,
            succeeded=succeeded,
            skipped=skipped,
        ),
        next_steps=next_steps,
    )


def _find_existing_owner_profile(db_url: str) -> str | None:
    """Check if an owner profile already exists in the database.

    Returns the profile ID if found, otherwise None.
    """
    try:
        engine = create_engine(db_url)
        with Session(engine) as session:
            result = session.execute(
                text("SELECT id FROM crawled_profile WHERE data_source = 'setup' LIMIT 1")
            )
            row = result.fetchone()
            engine.dispose()
            return row[0] if row else None
    except Exception:
        return None
