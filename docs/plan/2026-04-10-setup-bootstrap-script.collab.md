# Plan: Add `./setup` bootstrap script (gstack-style)

## Context

After cloning LinkedOut, a new user can't run `/linkedout-setup` because Claude Code doesn't know about the skill yet — skills live in `skills/claude-code/` but aren't installed to `~/.claude/skills/linkedout/`. This is a chicken-and-egg problem. gstack solves this with a `./setup` script that symlinks skills into `~/.claude/skills/` before the user ever opens Claude Code.

**Goal:** Create a `./setup` script at the repo root so the user flow becomes:
```
git clone https://github.com/sridherj/linkedout-oss.git
cd linkedout-oss
./setup
claude    # /linkedout-setup now works
```

## Approach

Reuse the existing `bin/dev-setup` symlink logic. The new `./setup` is a thin wrapper that:
1. Checks prerequisites (Python 3.11+)
2. Symlinks generated skills to `~/.claude/skills/linkedout/` (via `bin/dev-setup`)
3. Prints next-step instructions

### Why reuse `bin/dev-setup`?
- Already handles host detection, symlink creation, routing file updates
- Works for Claude Code, Codex, and Copilot
- Idempotent (safe to re-run)

### Why NOT run `bin/generate-skills` during setup?
- Generated skills (`skills/claude-code/*.md`) are **already committed to git**
- Running generate-skills requires PyYAML which the user may not have yet
- The committed output is always in sync (CI can verify with `bin/generate-skills --check`)
- Keeps `./setup` dependency-free (no pip install needed before it runs)

## Issues found during review

### Issue 1: `skill_install.py` overwrites symlinks with copies

**Problem:** Step 12 of `/linkedout-setup` orchestrator runs `skill_install.py:setup_skills()`, which uses `shutil.copy2()` to copy skills into `~/.claude/skills/linkedout/`. This **replaces symlinks with file copies**, losing the auto-update-on-git-pull benefit.

**Fix:** Modify `skill_install.py:install_skills_for_platform()` to detect existing symlinks and skip if they point to the correct source. If symlinks are already in place (from `./setup`), the copy step becomes a no-op. This keeps both paths working:
- `./setup` → symlinks (dev/power-user flow)
- `/linkedout-setup` without prior `./setup` → copies (fallback)

**File:** `backend/src/linkedout/setup/skill_install.py` lines 149-204

### Issue 2: Upgrade flow

**Symlinks auto-update on `git pull`** — since `bin/dev-setup` symlinks entire skill directories (not individual files), any file changes inside `skills/claude-code/linkedout-setup/` are immediately visible through the symlink. User does NOT need to re-run `./setup` after pulling updates.

**But:** If new skills are added (new directories), user needs to re-run `./setup`. This is the same as gstack's behavior and is acceptable. The `./setup` banner should mention: "Re-run after pulling updates that add new skills."

### Issue 3: `./setup` should not require Python deps

The current `bin/dev-setup` imports from `skills.lib.config` which needs PyYAML. But `./setup` runs before any Python deps are installed. Two options:
- **Option A:** Rewrite the symlink logic in bash (simple — just symlink `skills/claude-code/*` to `~/.claude/skills/linkedout/`)
- **Option B:** Inline the minimal Python needed without PyYAML (read the install path from claude.yaml manually)

**Recommendation:** Option A. The bash version is ~15 lines and avoids the PyYAML dependency entirely. `bin/dev-setup` remains for developers who already have deps installed.

## Changes

### 1. Create `./setup` (repo root, bash script)

Simple bash script (~50 lines):
- Check Python 3.11+ exists (warn if not, but don't block — skills install doesn't need Python)
- Detect AI hosts by checking `~/.claude/`, `~/.agents/`, `~/.github/`
- For each detected host, symlink skill directories from `skills/claude-code/` (or codex/copilot equivalent)
- Symlink the routing CLAUDE.md to `~/.claude/skills/CLAUDE.md`
- Print success banner with next steps

No Python deps required. Pure bash.

### 2. Modify `skill_install.py` — respect existing symlinks

In `install_skills_for_platform()`, before `shutil.copy2()`, check if destination is a symlink pointing into the repo's `skills/` directory. If so, skip the copy.

**File:** `backend/src/linkedout/setup/skill_install.py:182-188`

### 3. Update `README.md` quickstart

Add `./setup` step between clone and opening Claude Code.

### 4. Update `docs/getting-started.md`

Add `./setup` step to both Quick Demo and Full Setup sections.

### 5. Update `Dockerfile.sandbox`

Replace any skill pre-install with running `./setup` inside the container. This tests the actual user flow.

## Files to modify

| File | Change |
|------|--------|
| `setup` (new, repo root) | Bootstrap bash script — symlinks skills, no Python deps |
| `backend/src/linkedout/setup/skill_install.py` | Skip copy when symlinks already point to correct source |
| `README.md` | Add `./setup` to quickstart |
| `docs/getting-started.md` | Add `./setup` to Quick Demo + Full Setup |
| `Dockerfile.sandbox` | Run `./setup` instead of manual skill copy |

## Not changing

- `bin/dev-setup` — remains as the developer-oriented Python version
- `bin/generate-skills` — not needed during `./setup` (output is committed)
- `backend/src/linkedout/setup/orchestrator.py` — step 12 still calls skill_install, which now respects symlinks
- `backend/src/dev_tools/sandbox.py` — keep as-is
- `backend/pyproject.toml` — keep `linkedout-sandbox` entry point as-is

## Verification

1. **Clean install:** Remove `~/.claude/skills/linkedout/`, run `./setup`, verify symlinks created
2. **Idempotent:** Re-run `./setup`, verify "already linked" messages, no errors
3. **Upgrade:** Modify a SKILL.md in the repo, verify the change is visible via the symlink without re-running setup
4. **New skill added:** Add a skill dir, verify `./setup` picks it up
5. **Orchestrator compat:** Run `/linkedout-setup` after `./setup` — step 12 should detect symlinks and skip copy
6. **Docker sandbox:** `linkedout-sandbox` builds, `./setup` runs, `/linkedout-setup` skill is available
7. **No-host graceful:** Run `./setup` without `~/.claude/` — should print helpful message, not crash
