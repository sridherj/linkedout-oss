# SP08: Polish `/linkedout-upgrade`

## Context

Read `_shared_context.md` first for skill template conventions.

The upgrade skill works but doesn't check for dirty git state before pulling or show what changed.

## Depends On

None (independent).

## Tasks

### 8a. Add dirty-state check before pull

**File:** `skills/linkedout-upgrade/SKILL.md.tmpl`

Add before the `git pull` step:

```markdown
Before pulling, check for uncommitted changes:
\```bash
git status --porcelain
\```
If there are uncommitted changes, warn the user:
> You have uncommitted changes. Stash or commit them before upgrading: `git stash`
```

### 8b. Show what changed after pull

After `git pull`, show the user what was updated:

```markdown
\```bash
git log --oneline HEAD@{1}..HEAD
\```
If no commits were pulled: "Already up to date."
```

## Verification

```bash
bin/generate-skills

# Check generated skill contains dirty-state check
grep "porcelain" skills/claude-code/linkedout-upgrade/SKILL.md

# Check changelog display
grep "HEAD@{1}" skills/claude-code/linkedout-upgrade/SKILL.md
```
