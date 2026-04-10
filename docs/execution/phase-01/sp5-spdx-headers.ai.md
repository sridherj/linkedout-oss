# SP5: SPDX License Headers

**Phase:** 01 — OSS Repository Scaffolding
**Sub-phase:** 5 of 5
**Dependencies:** SP4 (CI should be green before mass-modifying source files)
**Estimated effort:** ~30 minutes
**Shared context:** `_shared_context.md`

---

## Scope

Add SPDX license identifiers to all source files for Apache 2.0 compliance. Create a reusable script for future files.

**Tasks from phase plan:** 1J

---

## Task 1J: SPDX Headers

### Header Formats

**Python files (`.py`):**
```python
# SPDX-License-Identifier: Apache-2.0
```
Added as the **first line** of every `.py` file (before any existing imports, docstrings, or comments).

**TypeScript files (`.ts`, `.tsx`):**
```typescript
// SPDX-License-Identifier: Apache-2.0
```
Added as the **first line** of every `.ts`/`.tsx` file.

### Files in Scope

- `backend/src/**/*.py` — All Python source files
- `extension/**/*.ts` and `extension/**/*.tsx` — All TypeScript source files

### Files to Exclude

- Empty `__init__.py` files (0 bytes) — don't need headers
- Generated files: anything in `.egg-info/`, `node_modules/`, `.output/`, `.wxt/`
- Config files: `pyproject.toml`, `package.json`, `tsconfig.json`, `wxt.config.ts`, etc.
- Non-source files: `.md`, `.yml`, `.yaml`, `.json`, `.txt`, `.toml`, `.ini`, `.cfg`
- `conftest.py` at the backend root level (test infrastructure)
- Files in `backend/tests/` — add headers but with lower priority (do add them if time permits, skip if they cause test issues)
- Files in `backend/migrations/` — Alembic auto-generated files, skip

### Implementation: Create a Script

**File to create:** `scripts/add-spdx-headers.py`

The script must:
1. Find all `.py`, `.ts`, `.tsx` files in scope
2. Check if SPDX header already exists (idempotent — skip files that already have it)
3. Prepend the appropriate header format based on file extension
4. Handle files that start with shebangs (`#!/...`) — insert header after the shebang line
5. Handle Python files that start with encoding declarations (`# -*- coding: ...`) — insert after encoding
6. Report: files modified, files skipped (already had header), files excluded
7. Exit 0 on success

### Script Usage

```bash
# Add headers to all source files
python scripts/add-spdx-headers.py

# Check without modifying (dry run)
python scripts/add-spdx-headers.py --check

# The --check mode exits non-zero if any files are missing headers
# (suitable for CI integration in later phases)
```

### Execution Steps

1. Create `scripts/add-spdx-headers.py`
2. Run the script: `python scripts/add-spdx-headers.py`
3. Review the output — verify file counts make sense
4. Run the script again — verify it reports 0 files modified (idempotent)
5. Verify a few files manually (spot check):
   - A Python file in `backend/src/linkedout/`
   - A Python file in `backend/src/shared/`
   - A TypeScript file in `extension/`

### Verification

- [ ] Script exists at `scripts/add-spdx-headers.py`
- [ ] Script is idempotent (running twice doesn't add duplicate headers)
- [ ] Every `.py` file in `backend/src/` has `# SPDX-License-Identifier: Apache-2.0` as first non-shebang line
- [ ] Every `.ts`/`.tsx` file in `extension/` (excluding `node_modules/`, `.output/`, `.wxt/`) has `// SPDX-License-Identifier: Apache-2.0`
- [ ] No non-source files were modified
- [ ] `--check` mode works for CI integration
- [ ] Script output reports counts: modified, skipped, excluded

---

## Output Artifacts

- `scripts/add-spdx-headers.py` (new file)
- All `.py` files in `backend/src/` (modified — header prepended)
- All `.ts`/`.tsx` files in `extension/` (modified — header prepended)

---

## Post-Completion Check

1. Run `grep -rL "SPDX-License-Identifier" backend/src/ --include="*.py"` — should return no results (all files have header)
2. Run `grep -rL "SPDX-License-Identifier" extension/ --include="*.ts" --include="*.tsx" --exclude-dir=node_modules --exclude-dir=.output --exclude-dir=.wxt` — should return no results
3. Run `python scripts/add-spdx-headers.py --check` — should exit 0
4. Verify no duplicate headers: `grep -c "SPDX-License-Identifier" backend/src/linkedout/cli.py` should return `1` (or whatever file exists — just one occurrence)
