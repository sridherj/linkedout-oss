#!/usr/bin/env python3
"""Verify seed data file checksums against seed-manifest.json."""

import hashlib
import json
import sys
from pathlib import Path

SEED_DIR = Path("seed-data")
MANIFEST_PATH = SEED_DIR / "seed-manifest.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if not MANIFEST_PATH.exists():
        print(f"ERROR: {MANIFEST_PATH} not found")
        return 1

    manifest = json.loads(MANIFEST_PATH.read_text())
    files = manifest.get("files", [])
    if not files:
        print("WARNING: No files listed in seed-manifest.json")
        return 0

    errors = []
    for entry in files:
        name = entry["name"]
        expected_sha = entry.get("sha256", "")
        path = SEED_DIR / name

        if not path.exists():
            print(f"SKIP: {name} not present (released separately)")
            continue

        actual_sha = sha256_file(path)
        if expected_sha and actual_sha != expected_sha:
            errors.append(f"MISMATCH: {name} expected={expected_sha[:16]}... actual={actual_sha[:16]}...")
        else:
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"OK: {name} ({size_mb:.1f} MB)")

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1

    print("All seed checksums verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
