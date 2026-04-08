#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Add SPDX license headers to all source files in the LinkedOut project."""

import argparse
import os
import sys
from pathlib import Path

SPDX_PYTHON = "# SPDX-License-Identifier: Apache-2.0"
SPDX_TYPESCRIPT = "// SPDX-License-Identifier: Apache-2.0"

SPDX_MARKER = "SPDX-License-Identifier"

# Directories to exclude entirely
EXCLUDE_DIRS = {
    "node_modules",
    ".output",
    ".wxt",
    ".egg-info",
    "__pycache__",
    ".git",
    ".venv",
    "venv",
}

# Specific paths to exclude (relative to project root)
EXCLUDE_PATHS = {
    "backend/migrations",
}


def find_project_root() -> Path:
    """Find the project root (directory containing backend/ and extension/)."""
    script_dir = Path(__file__).resolve().parent
    return script_dir.parent


def should_exclude_dir(dirpath: str, root: Path) -> bool:
    """Check if a directory should be excluded."""
    dirname = os.path.basename(dirpath)
    if dirname in EXCLUDE_DIRS:
        return True
    rel = os.path.relpath(dirpath, root)
    for exc in EXCLUDE_PATHS:
        if rel == exc or rel.startswith(exc + os.sep):
            return True
    return False


def is_empty_init(filepath: Path) -> bool:
    """Check if a file is an empty __init__.py."""
    return filepath.name == "__init__.py" and filepath.stat().st_size == 0


def has_spdx_header(content: str) -> bool:
    """Check if file content already contains an SPDX header."""
    return SPDX_MARKER in content


def add_header_to_content(content: str, header: str) -> str:
    """Add SPDX header to file content, respecting shebangs and encoding lines."""
    lines = content.split("\n")
    insert_pos = 0

    # Skip shebang line
    if lines and lines[0].startswith("#!"):
        insert_pos = 1

    # Skip encoding declaration (e.g., # -*- coding: utf-8 -*-)
    if insert_pos < len(lines) and "coding" in lines[insert_pos] and lines[insert_pos].startswith("#"):
        insert_pos += 1

    # Insert header followed by a blank line (if next line isn't blank)
    if insert_pos < len(lines) and lines[insert_pos].strip():
        lines.insert(insert_pos, header)
    else:
        lines.insert(insert_pos, header)

    return "\n".join(lines)


def collect_files(root: Path) -> list[tuple[Path, str]]:
    """Collect all source files that need SPDX headers.

    Returns list of (filepath, header_text) tuples.
    """
    files = []

    # Python files in backend/src/
    backend_src = root / "backend" / "src"
    if backend_src.exists():
        for dirpath, dirnames, filenames in os.walk(backend_src):
            dirnames[:] = [d for d in dirnames if not should_exclude_dir(os.path.join(dirpath, d), root)]
            for f in filenames:
                if f.endswith(".py"):
                    files.append((Path(dirpath) / f, SPDX_PYTHON))

    # Python files in backend/tests/
    backend_tests = root / "backend" / "tests"
    if backend_tests.exists():
        for dirpath, dirnames, filenames in os.walk(backend_tests):
            dirnames[:] = [d for d in dirnames if not should_exclude_dir(os.path.join(dirpath, d), root)]
            for f in filenames:
                if f.endswith(".py"):
                    files.append((Path(dirpath) / f, SPDX_PYTHON))

    # TypeScript files in extension/
    extension_dir = root / "extension"
    if extension_dir.exists():
        for dirpath, dirnames, filenames in os.walk(extension_dir):
            dirnames[:] = [d for d in dirnames if not should_exclude_dir(os.path.join(dirpath, d), root)]
            for f in filenames:
                if f.endswith((".ts", ".tsx")):
                    files.append((Path(dirpath) / f, SPDX_TYPESCRIPT))

    return files


def process_files(root: Path, check_only: bool = False) -> tuple[int, int, int]:
    """Process all files and add SPDX headers.

    Returns (modified, skipped, excluded) counts.
    """
    files = collect_files(root)
    modified = 0
    skipped = 0
    excluded = 0
    missing = []

    for filepath, header in files:
        # Skip empty __init__.py files
        if is_empty_init(filepath):
            excluded += 1
            continue

        content = filepath.read_text(encoding="utf-8")

        if has_spdx_header(content):
            skipped += 1
            continue

        if check_only:
            missing.append(filepath)
            modified += 1
            continue

        new_content = add_header_to_content(content, header)
        filepath.write_text(new_content, encoding="utf-8")
        modified += 1

    if check_only and missing:
        print(f"\nFiles missing SPDX headers ({len(missing)}):")
        for f in missing:
            print(f"  {f.relative_to(root)}")

    return modified, skipped, excluded


def main() -> int:
    parser = argparse.ArgumentParser(description="Add SPDX license headers to source files")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check for missing headers without modifying files (exits non-zero if any missing)",
    )
    args = parser.parse_args()

    root = find_project_root()
    print(f"Project root: {root}")

    if args.check:
        print("Running in check mode (no files will be modified)\n")
    else:
        print("Adding SPDX headers to source files\n")

    modified, skipped, excluded = process_files(root, check_only=args.check)

    print(f"\nResults:")
    if args.check:
        print(f"  Missing headers: {modified}")
    else:
        print(f"  Files modified:  {modified}")
    print(f"  Already present: {skipped}")
    print(f"  Excluded:        {excluded}")

    if args.check and modified > 0:
        print(f"\nFAILED: {modified} file(s) missing SPDX headers")
        return 1

    if args.check:
        print("\nPASSED: All source files have SPDX headers")

    return 0


if __name__ == "__main__":
    sys.exit(main())
