# Sub-Phase 3: CLI Wiring and End-to-End Verification

**Goal:** linkedin-ai-production
**Source plan:** 2026-03-28-classify-roles-port-and-wiring.md
**Type:** CLI integration + spec update
**Estimated effort:** ~1 hour
**Dependencies:** Sub-Phase 2
**Can parallelize with:** Nothing (sequential)

---

## Overview

Wire `rcv2 db classify-roles` as a CLI command. Update the CLI Commands spec. Verify the full pipeline runs and downstream commands are unblocked.

---

## Step 1: Add CLI Command

**What:** Add `db classify-roles` command to `src/dev_tools/cli.py`.

**Actions:**
1. Add the command following the exact pattern from `db_fix_none_names` / `db_backfill_seniority`:
   ```python
   @db.command(name='classify-roles')
   @click.option('--dry-run', is_flag=True, help='Classify and report only, do not write')
   def db_classify_roles(dry_run):
       """Classify titles into seniority/function, populate role_alias, update experience + crawled_profile."""
       from dev_tools.classify_roles import main as classify_main
       exit_code = classify_main(dry_run=dry_run)
       if exit_code != 0:
           sys.exit(exit_code)
   ```
2. Add backward-compatible alias: `classify_roles_command = db_classify_roles` at the bottom of cli.py with the other aliases

**Key constraint:** Lazy import pattern (`from dev_tools.classify_roles import main as classify_main`) — matches all other db commands.

**Verification:**
- [ ] `rcv2 db classify-roles --help` shows help text
- [ ] `rcv2 db classify-roles --dry-run` runs and prints stats
- [ ] `rcv2 db classify-roles` runs and populates data

---

## Step 2: Update CLI Commands Spec

**What:** Update `docs/specs/cli_commands.collab.md` with the new command.

**Actions:**
1. Delegate to `/taskos-update-spec` with changes:
   - Add `src/dev_tools/classify_roles.py` to `linked_files`
   - Add `db classify-roles` behavior entry under DB Group:
     ```
     - **db classify-roles**: Given experience and crawled_profile rows with position titles. Running the command classifies titles via regex into seniority_level and function_area, populates role_alias via upsert, and bulk updates experience and crawled_profile. Verify `--dry-run` reports classification stats without writing, and real run populates role_alias and updates downstream tables.
     ```
   - Bump version to 3
2. Review spec update output for accuracy

**Verification:**
- [ ] Spec updated with new command
- [ ] Version bumped

---

## Step 3: End-to-End Verification

**What:** Run the full verification suite.

**Actions:**
1. Run CLI help: `rcv2 db classify-roles --help`
2. Run dry run: `rcv2 db classify-roles --dry-run`
3. Run real run: `rcv2 db classify-roles`
4. Verify downstream unblocked:
   - `rcv2 db backfill-seniority --dry-run` — should show matches
   - `rcv2 db compute-affinity --dry-run` — should confirm ready
5. DB spot-check:
   ```bash
   psql $DATABASE_URL -c "SELECT COUNT(*) FROM role_alias;"
   psql $DATABASE_URL -c "SELECT seniority_level, COUNT(*) FROM role_alias WHERE seniority_level IS NOT NULL GROUP BY 1 ORDER BY 2 DESC;"
   ```
6. Run tests: `pytest tests/dev_tools/test_classify_roles.py -v`
7. Run `precommit-tests` to confirm nothing is broken

**Verification:**
- [ ] All CLI commands work
- [ ] Downstream commands show matches
- [ ] DB has expected data
- [ ] All tests pass

---

## Completion Criteria

- [ ] `rcv2 db classify-roles` is a working CLI command
- [ ] CLI spec updated with new command (version 3)
- [ ] `--dry-run` and real run both work correctly
- [ ] `precommit-tests` passes
- [ ] Downstream commands (`backfill-seniority`, `compute-affinity`) are unblocked
