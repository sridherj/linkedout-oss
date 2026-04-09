# SPDX-License-Identifier: Apache-2.0
"""Skill detection and installation for LinkedOut setup.

Detects installed AI coding platforms (Claude Code, Codex, Copilot),
generates skills from templates using ``bin/generate-skills``, copies
or symlinks generated output to each platform's skill directory, and
updates the platform's dispatch file (CLAUDE.md / AGENTS.md) with
routing rules.

All operations are idempotent — re-running updates skills in place,
and missing platforms are skipped gracefully.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from linkedout.setup.logging_integration import get_setup_logger
from shared.utilities.operation_report import OperationCounts, OperationReport

# ── Platform detection config ──────────────────────────────────────

_PLATFORM_CONFIGS = {
    "Claude Code": {
        "detect_dir": ".claude",
        "skill_install_dir": ".claude/skills",
        "dispatch_file": ".claude/CLAUDE.md",
        "generated_dir": "skills/claude-code",
    },
    "Codex": {
        "detect_dir": ".agents",
        "skill_install_dir": ".agents/skills",
        "dispatch_file": ".agents/AGENTS.md",
        "generated_dir": "skills/codex",
    },
    "Copilot": {
        "detect_dir": ".github",
        "skill_install_dir": ".github/skills",
        "dispatch_file": ".copilot/COPILOT.md",
        "generated_dir": "skills/copilot",
    },
}


@dataclass
class PlatformInfo:
    """Detected AI platform information.

    Attributes:
        name: Human-readable platform name.
        config_dir: Path to the platform's config directory.
        skill_install_dir: Target path for skill files.
        dispatch_file: Path to the routing dispatch file.
        generated_dir: Source directory for generated skill files.
    """

    name: str
    config_dir: Path
    skill_install_dir: Path
    dispatch_file: Path
    generated_dir: Path


def detect_platforms() -> list[PlatformInfo]:
    """Detect installed AI coding platforms.

    Checks for platform config directories in the user's home
    directory. Only claims a platform is installed if the config
    directory actually exists.

    Returns:
        List of ``PlatformInfo`` for each detected platform.
    """
    log = get_setup_logger("skill_install")
    home = Path.home()
    detected: list[PlatformInfo] = []

    for name, cfg in _PLATFORM_CONFIGS.items():
        detect_path = home / cfg["detect_dir"]
        if detect_path.is_dir():
            log.info("Detected platform: {} ({})", name, detect_path)
            detected.append(
                PlatformInfo(
                    name=name,
                    config_dir=detect_path,
                    skill_install_dir=home / cfg["skill_install_dir"],
                    dispatch_file=home / cfg["dispatch_file"],
                    generated_dir=Path(cfg["generated_dir"]),
                )
            )
        else:
            log.debug("Platform not detected: {} (no {})", name, detect_path)

    return detected


def generate_skills(repo_root: Path) -> bool:
    """Run ``bin/generate-skills`` to render skill templates.

    If the generation script does not exist (Phase 8 not complete),
    prints an informational message and returns ``False``.

    Args:
        repo_root: Path to the repository root.

    Returns:
        ``True`` if generation succeeded, ``False`` otherwise.
    """
    log = get_setup_logger("skill_install")
    script = repo_root / "bin" / "generate-skills"

    if not script.exists():
        log.warning("bin/generate-skills not found — Phase 8 may not be complete")
        print(
            "  bin/generate-skills not found.\n"
            "  Skill generation requires Phase 8 artifacts.\n"
            "  Skipping skill generation."
        )
        return False

    print("  Generating skill files from templates...")

    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )

    if result.returncode != 0:
        error = result.stderr.strip() or result.stdout.strip()
        log.error("generate-skills failed: {}", error)
        print(f"  Skill generation failed: {error}")
        return False

    stdout = result.stdout.strip()
    if stdout:
        for line in stdout.splitlines():
            print(f"    {line}")

    log.info("Skill generation complete")
    return True


def install_skills_for_platform(
    platform: PlatformInfo,
    repo_root: Path,
) -> bool:
    """Copy generated skill files to a platform's skill directory.

    Creates the target directory if needed. Copies all files from
    the generated output directory to the platform's skill install
    path, preserving directory structure.

    Args:
        platform: The target platform.
        repo_root: Path to the repository root.

    Returns:
        ``True`` if installation succeeded, ``False`` otherwise.
    """
    log = get_setup_logger("skill_install")
    source = repo_root / platform.generated_dir

    if not source.exists():
        log.warning(
            "Generated skill dir not found: {} — run bin/generate-skills first",
            source,
        )
        print(f"  No generated skills found for {platform.name}")
        return False

    target = platform.skill_install_dir
    target.mkdir(parents=True, exist_ok=True)

    # Count files to copy (skip if symlinks already point to the source)
    files_copied = 0
    files_skipped = 0
    for src_file in source.rglob("*"):
        if src_file.is_file():
            rel = src_file.relative_to(source)
            dst = target / rel
            # If dst resolves to the same file (e.g. via directory symlink from ./setup),
            # skip the copy — the symlink already provides the content.
            if dst.exists() and dst.resolve() == src_file.resolve():
                files_skipped += 1
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src_file), str(dst))
            files_copied += 1

    if files_skipped > 0 and files_copied == 0:
        log.info(
            "Skills already symlinked for {} at {} ({} files)",
            platform.name,
            target,
            files_skipped,
        )
        print(f"    Already installed via symlinks at {_display_path(target)}")
    elif files_copied > 0:
        log.info(
            "Installed {} files for {} to {}",
            files_copied,
            platform.name,
            target,
        )
        print(f"    Installed to {_display_path(target)}")
    else:
        log.warning("No skill files found in {}", source)
        print(f"    No skill files found in generated output for {platform.name}")

    return files_copied > 0 or files_skipped > 0


def update_dispatch_file(
    platform: PlatformInfo,
    agent_context_path: Path,
) -> bool:
    """Add LinkedOut routing rules to the platform's dispatch file.

    Appends a routing section to the dispatch file (e.g., CLAUDE.md)
    that tells the platform how to route ``/linkedout`` commands to
    the installed skills. Includes the path to ``agent-context.env``
    so skills can find DB credentials.

    If the dispatch file already contains LinkedOut routing, it is
    updated in place.

    Args:
        platform: The target platform.
        agent_context_path: Path to ``agent-context.env``.

    Returns:
        ``True`` if the dispatch file was updated, ``False`` otherwise.
    """
    log = get_setup_logger("skill_install")

    dispatch = platform.dispatch_file
    marker = "# LinkedOut skill routing"
    skill_dir = _display_path(platform.skill_install_dir)

    routing_block = (
        f"\n{marker}\n"
        f"# Auto-generated by linkedout-setup — do not edit this section\n"
        f"# Skills: {skill_dir}\n"
        f"# Agent context: {_display_path(agent_context_path)}\n"
    )

    if dispatch.exists():
        content = dispatch.read_text(encoding="utf-8")
        if marker in content:
            # Replace existing block
            before = content.split(marker)[0].rstrip()
            # Find end of our block (next section or EOF)
            after_marker = content.split(marker, 1)[1]
            # Find next markdown heading or end
            remaining_lines = after_marker.splitlines()
            end_idx = len(remaining_lines)
            for i, line in enumerate(remaining_lines):
                if i > 0 and line.startswith("# ") and "LinkedOut" not in line:
                    end_idx = i
                    break
            remaining = "\n".join(remaining_lines[end_idx:])
            new_content = before + routing_block
            if remaining.strip():
                new_content += "\n" + remaining
            dispatch.write_text(new_content + "\n", encoding="utf-8")
            log.info("Updated routing in {}", dispatch)
        else:
            # Append
            with open(dispatch, "a", encoding="utf-8") as f:
                f.write(routing_block)
            log.info("Appended routing to {}", dispatch)
    else:
        # Create new dispatch file
        dispatch.parent.mkdir(parents=True, exist_ok=True)
        dispatch.write_text(routing_block.lstrip() + "\n", encoding="utf-8")
        log.info("Created dispatch file {}", dispatch)

    print(f"    Updated {_display_path(dispatch)} with routing rules")
    return True


def setup_skills(
    repo_root: Path,
    data_dir: Path,
    auto_accept: bool = False,
) -> OperationReport:
    """Full skill installation orchestration for the setup flow.

    Steps:
    1. Detect installed AI platforms
    2. Confirm with user (unless ``auto_accept=True``)
    3. Generate skills from templates
    4. Install to each detected platform
    5. Update dispatch files

    Args:
        repo_root: Path to the repository root.
        data_dir: Root data directory (e.g., ``~/linkedout-data``).
        auto_accept: When ``True`` (demo mode), skip the Y/n prompt.

    Returns:
        ``OperationReport`` summarizing what was done.
    """
    start = time.monotonic()
    data_dir = Path(data_dir).expanduser()
    agent_context = data_dir / "config" / "agent-context.env"

    if not auto_accept:
        print("Step 12 of 14: Skill Installation\n")

    # Detect platforms
    platforms = detect_platforms()

    if not platforms:
        print("  No AI coding platforms detected.")
        print("  Skills can be installed manually later.")
        duration_ms = (time.monotonic() - start) * 1000
        return OperationReport(
            operation="setup-skills",
            duration_ms=duration_ms,
            counts=OperationCounts(total=0, succeeded=0),
            next_steps=["Install an AI coding platform, then re-run /linkedout-setup"],
        )

    # Show detected platforms
    print("  Detected AI platforms:")
    for p in platforms:
        print(f"    \u2713 {p.name}  ({_display_path(p.config_dir)})")
    print()

    # Ask for confirmation (skip in demo/auto_accept mode)
    if not auto_accept:
        choice = input("  Install LinkedOut skills for these platforms? [Y/n] ").strip().lower()
        if choice in ("n", "no"):
            print("\n  Skipping skill installation.")
            duration_ms = (time.monotonic() - start) * 1000
            return OperationReport(
                operation="setup-skills",
                duration_ms=duration_ms,
                counts=OperationCounts(
                    total=len(platforms),
                    skipped=len(platforms),
                ),
                next_steps=["Re-run /linkedout-setup to install skills later"],
            )

    # Generate skills
    generated = generate_skills(repo_root)
    if not generated:
        duration_ms = (time.monotonic() - start) * 1000
        return OperationReport(
            operation="setup-skills",
            duration_ms=duration_ms,
            counts=OperationCounts(total=len(platforms), failed=len(platforms)),
            next_steps=["Run bin/generate-skills manually, then re-run /linkedout-setup"],
        )

    # Install per platform
    succeeded = 0
    failed = 0
    for p in platforms:
        print(f"\n  Installing skills for {p.name}...")
        installed = install_skills_for_platform(p, repo_root)
        if installed:
            update_dispatch_file(p, agent_context)
            print(f"  \u2713 {p.name} skills installed")
            succeeded += 1
        else:
            print(f"  \u2717 {p.name} skill installation failed")
            failed += 1

    print(f"\n  Skills installed for {succeeded} platform(s).")

    duration_ms = (time.monotonic() - start) * 1000
    return OperationReport(
        operation="setup-skills",
        duration_ms=duration_ms,
        counts=OperationCounts(
            total=len(platforms),
            succeeded=succeeded,
            failed=failed,
        ),
    )


# ── Internal helpers ──────────────────────────────────────────────


def _display_path(path: Path) -> str:
    """Format a path with ~ shorthand when under the home directory."""
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)
