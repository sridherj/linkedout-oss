# SPDX-License-Identifier: Apache-2.0
"""Demo offer and demo setup flow for the LinkedOut setup orchestrator.

After the first 4 infrastructure steps complete, the orchestrator calls
``offer_demo()`` to present a decision gate. If accepted,
``run_demo_setup()`` executes steps D1-D5 with demo-specific labels.

This module is the ONLY place that knows the demo step sequence. The
orchestrator delegates to it and receives a pass/fail result.
"""
from __future__ import annotations

import os
from pathlib import Path

from linkedout.setup.logging_integration import get_setup_logger


# ── Demo offer prompt ─────────────────────────────────────────────


def offer_demo() -> bool:
    """Present the demo offer prompt and return the user's choice.

    Returns:
        ``True`` if the user accepted the demo, ``False`` otherwise.
    """
    log = get_setup_logger("demo_offer")

    prompt = """
+--------------------------------------------------+
|  How would you like to get started?               |
|                                                   |
|  [Y] Quick start with demo data (recommended)    |
|      2,000 sample profiles, ready in ~2 minutes   |
|      No API keys needed — everything runs locally  |
|      ~375 MB download (demo data + search model)  |
|                                                   |
|  [n] Full setup with your own LinkedIn data       |
|      Import your connections and profile           |
|      Requires an OpenAI API key for embeddings    |
|      You can always switch later                   |
|                                                   |
+--------------------------------------------------+"""
    print(prompt)

    try:
        choice = input("\n  Your choice [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        log.info("Demo offer interrupted, continuing with full setup")
        return False

    accepted = choice in ("", "y", "yes")
    log.info("Demo offer {}", "accepted" if accepted else "declined")
    return accepted


# ── Demo step execution ───────────────────────────────────────────


def run_demo_setup(data_dir: Path, repo_root: Path, db_url: str) -> bool:
    """Execute demo steps D1-D5.

    Runs the demo setup flow: download demo data, download embedding
    model, restore database, install skills, and run readiness check.

    On failure of D1-D3, returns False so the orchestrator can offer
    to continue with full setup instead.

    Args:
        data_dir: Root data directory.
        repo_root: Repository root directory.
        db_url: Database connection URL (for the real ``linkedout`` DB).

    Returns:
        ``True`` if all demo steps succeeded, ``False`` on failure.
    """
    log = get_setup_logger("demo_offer")
    data_dir = Path(data_dir).expanduser()

    # ── D1: Download demo data ────────────────────────────────────
    print("\n  D1: Downloading demo data (100 MB)...")
    try:
        if not _run_demo_download(data_dir):
            return False
        print("      \u2713 Done")
    except Exception as exc:
        log.error("D1 failed: {}", exc)
        print(f"      \u2717 Download failed: {exc}")
        _print_download_retry_hint()
        return False

    # ── D2: Download search model ─────────────────────────────────
    print("  D2: Downloading search model (275 MB)...")
    try:
        if not _run_model_download():
            # Model download failure is not fatal — it may already be cached
            print("      \u26a0 Model download skipped (may already be cached)")
        else:
            print("      \u2713 Done")
    except Exception as exc:
        log.warning("D2 failed (non-fatal): {}", exc)
        print(f"      \u26a0 Model download failed: {exc}")

    # ── D3: Restore demo database ─────────────────────────────────
    print("  D3: Restoring demo database...")
    try:
        demo_db_url = _run_demo_restore(data_dir, db_url)
        if not demo_db_url:
            return False
        print("      \u2713 Done")
    except Exception as exc:
        log.error("D3 failed: {}", exc)
        print(f"      \u2717 Restore failed: {exc}")
        return False

    # ── D4: Install skills (auto-accept) ──────────────────────────
    print("  D4: Installing skills for Claude Code, Codex...")
    try:
        _run_skill_install(repo_root, data_dir)
        print("      \u2713 Done")
    except Exception as exc:
        log.warning("D4 failed (non-fatal): {}", exc)
        print(f"      \u26a0 Skill install failed: {exc}")

    # ── D5: Readiness check ───────────────────────────────────────
    print("  D5: Readiness check...")
    try:
        _run_readiness_check(demo_db_url, data_dir)
        print("      \u2713 Done")
    except Exception as exc:
        log.warning("D5 failed (non-fatal): {}", exc)
        print(f"      \u26a0 Readiness check failed: {exc}")

    # ── Success ───────────────────────────────────────────────────
    print("\n  \u2713 Demo ready!")
    _print_demo_welcome()
    return True


# ── Transition prompt ─────────────────────────────────────────────


def offer_transition() -> bool:
    """Present the transition prompt for users already in demo mode.

    Returns:
        ``True`` if the user wants to transition to real setup.
    """
    log = get_setup_logger("demo_offer")

    print("\n  You're using demo data. Ready to set up with your own connections? [Y/n]")
    print("  Your network, your profile \u2014 affinity scores will be personalized to you.")

    try:
        choice = input("\n> ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        log.info("Transition prompt interrupted, keeping demo mode")
        return False

    accepted = choice in ("", "y", "yes")
    log.info("Transition {}", "accepted" if accepted else "declined")
    return accepted


# ── Demo welcome message ──────────────────────────────────────────


def _print_demo_welcome() -> None:
    """Print the demo welcome message with sample queries."""
    from linkedout.demo.sample_queries import format_demo_profile, format_sample_queries

    print()
    print(format_demo_profile())
    print(format_sample_queries())
    print()
    print("  Demo mode \u00b7 linkedout setup to use your own data")


# ── Internal helpers ──────────────────────────────────────────────


def _run_demo_download(data_dir: Path) -> bool:
    """Download the demo dump file using the download_demo internals."""
    from linkedout.commands.download_demo import (
        _download_file,
        _fetch_manifest,
        _get_release_url,
    )
    from linkedout.demo import DEMO_DUMP_FILENAME
    from shared.utils.checksum import verify_checksum

    cache_dir = data_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    release_url, _tag = _get_release_url()
    manifest = _fetch_manifest(release_url)

    filename = manifest["name"]
    expected_sha256 = manifest["sha256"]
    expected_size = manifest["size_bytes"]
    dest = cache_dir / DEMO_DUMP_FILENAME

    # Skip if already cached with valid checksum
    if dest.exists() and verify_checksum(dest, expected_sha256):
        print("      Already cached (checksum OK)")
        return True

    download_url = f"{release_url}/{filename}"
    _download_file(download_url, dest, expected_size)

    if not verify_checksum(dest, expected_sha256):
        dest.unlink(missing_ok=True)
        print("      Checksum verification failed")
        return False

    return True


def _run_model_download() -> bool:
    """Download the local embedding model."""
    from linkedout.setup.python_env import pre_download_model

    return pre_download_model("local")


def _run_demo_restore(data_dir: Path, db_url: str) -> str | None:
    """Restore the demo database and update config.

    Returns the demo database URL on success, None on failure.
    """
    from linkedout.demo import DEMO_CACHE_DIR, DEMO_DUMP_FILENAME, set_demo_mode
    from linkedout.demo.db_utils import create_demo_database, restore_demo_dump
    from linkedout.setup.database import generate_agent_context_env

    dump_path = data_dir / DEMO_CACHE_DIR / DEMO_DUMP_FILENAME
    if not dump_path.exists():
        print("      Demo dump not found — download may have failed")
        return None

    demo_db_url = create_demo_database(db_url)
    if not restore_demo_dump(demo_db_url, dump_path):
        return None

    # Update config to demo mode
    set_demo_mode(data_dir, enabled=True)

    # Set embedding_provider to local for demo
    _set_embedding_provider(data_dir, "local")

    # Regenerate agent-context.env
    try:
        generate_agent_context_env(demo_db_url, data_dir)
    except Exception as exc:
        get_setup_logger("demo_offer").warning(
            "Could not regenerate agent-context.env: {}", exc
        )

    return demo_db_url


def _set_embedding_provider(data_dir: Path, provider: str) -> None:
    """Set the embedding_provider in config.yaml."""
    import yaml

    config_path = data_dir / "config" / "config.yaml"
    config: dict = {}
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

    config["embedding_provider"] = provider

    import tempfile

    config_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=config_path.parent, suffix=".yaml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)
        os.replace(tmp_path, str(config_path))
    except BaseException:
        import contextlib

        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def _run_skill_install(repo_root: Path, data_dir: Path) -> None:
    """Install skills with auto_accept=True for demo mode."""
    from linkedout.setup.skill_install import setup_skills

    print("      (skip with Ctrl+C)")
    setup_skills(repo_root=repo_root, data_dir=data_dir, auto_accept=True)


def _run_readiness_check(demo_db_url: str, data_dir: Path) -> None:
    """Run the readiness check against the demo database."""
    from linkedout.setup.readiness import generate_readiness_report

    generate_readiness_report(db_url=demo_db_url, data_dir=data_dir)


def _print_download_retry_hint() -> None:
    """Print a hint for retrying the download."""
    print("      Retry with: linkedout download-demo --force")
    print("      Then: linkedout restore-demo")
