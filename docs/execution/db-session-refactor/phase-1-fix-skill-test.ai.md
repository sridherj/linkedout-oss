# Phase 1: Fix Stale Skill Install Test Assertion

## RCA

RCA #3 — `test_platform_info_has_correct_paths` expects `.claude/skills/linkedout` but the code was intentionally changed to `.claude/skills` (the directory **where** skills get installed, not a specific skill subdirectory).

## Scope

1 file, 1 line change.

## Dependencies

None. This phase is independent and can run in parallel with Phases 2 and 3.

## Changes

### File: `tests/linkedout/setup/test_skill_install.py`

**Line 56** — change the assertion from:
```python
assert claude.skill_install_dir == tmp_path / ".claude" / "skills" / "linkedout"
```

To:
```python
assert claude.skill_install_dir == tmp_path / ".claude" / "skills"
```

**Why:** The code at `src/linkedout/setup/skill_install.py:30` defines `skill_install_dir` as `.claude/skills`. The `install_skills_for_platform()` function (line 177) copies skill subdirectories **into** this directory. The test expectation was stale — it included `/linkedout` which is a subdirectory created during installation, not the install directory itself.

## Verification

```bash
cd ./backend && uv run pytest tests/linkedout/setup/test_skill_install.py -x -v 2>&1 | tail -20
```

**Expected:** All tests in `test_skill_install.py` pass, including `test_platform_info_has_correct_paths`.
