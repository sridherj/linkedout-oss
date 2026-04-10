# Sub-phase 03: Skill Rewrite + Non-TTY Handling

## Metadata
- **Depends on:** nothing (but should run after 02b for cleaner diffs on shared files)
- **Blocks:** 04-spec-updates, 05-tests
- **Estimated scope:** 11 files modified (9 setup modules + 2 skill files)
- **Plan sections:** Phase 3a, Phase 3b (Issues 4, 5, 6, 7, 8, 9)

## Context

Read `_shared_context.md` for the EOFError pattern and skill template paths.

All six issues stem from one design flaw: the skill sources `agent-context.env` (which
doesn't exist yet) and fires `linkedout setup --full` without pre-configuring inputs.
The orchestrator's interactive prompts (`input()`, `getpass()`) block in Claude Code's
non-TTY Bash tool, causing EOFError.

## Task 3a: Add EOFError handling to all `input()` calls

Every `input()` call in setup modules should follow the `demo_offer.py` pattern:
```python
try:
    choice = input("Replace it? [y/N] ").strip().lower()
except (EOFError, KeyboardInterrupt):
    choice = ""  # default to "no" / keep existing
```

Default behavior on EOFError (safe/conservative):
- "Replace key?" -> No (keep existing)
- "Change provider?" -> No (keep existing)
- "Install skills?" -> Yes (skills are needed)
- "Enrich profiles?" -> Yes (if key exists)
- "Enter path:" -> skip (can't provide a path non-interactively)

**Files to update (every `input()` / `getpass()` call):**

| File | Approx lines | Count |
|------|-------------|-------|
| `backend/src/linkedout/setup/api_keys.py` | 98, 113, 125, 171, 331, 353, 381 | 6 |
| `backend/src/linkedout/setup/user_profile.py` | 56, 58, 175 | 3 |
| `backend/src/linkedout/setup/csv_import.py` | 111, 122, 129, 134 | 4 |
| `backend/src/linkedout/setup/contacts_import.py` | 68, 79, 221 | 3 |
| `backend/src/linkedout/setup/seed_data.py` | 220 | 1 |
| `backend/src/linkedout/setup/embeddings.py` | 265 | 1 |
| `backend/src/linkedout/setup/enrichment.py` | 278 | 1 |
| `backend/src/linkedout/setup/skill_install.py` | 339 | 1 |
| `backend/src/linkedout/setup/auto_repair.py` | 134 | 1 |

**Note:** `demo_offer.py` already has correct handling — do not modify.

## Task 3b: Rewrite the skill template

**Files:**
- `skills/linkedout-setup/SKILL.md.tmpl` (source template)
- `skills/claude-code/linkedout-setup/SKILL.md` (rendered output — regenerate after)

### New Flow

**Step 1: Ask demo vs full** (same as current — wait for answer before proceeding)

**Step 2: Demo path** — no config collection needed:
```bash
cd $(git rev-parse --show-toplevel)/backend && \
  uv venv .venv && source .venv/bin/activate && \
  uv pip install -r requirements.txt && \
  linkedout setup --demo
```
- NO `source agent-context.env` before setup — it doesn't exist yet
- Demo path needs no API keys

**Step 3: Full setup path — collect ALL inputs FIRST**

Before running any setup commands, conversationally collect:
1. Embedding provider — openai (recommended) or local (free, 275 MB)
2. OpenAI API key — if they chose openai
3. Apify API key — optional, for profile enrichment
4. LinkedIn profile URL — their own profile
5. Connections.csv path — or skip if not exported yet

Then write config files:
```bash
mkdir -p ~/linkedout-data/config
cat > ~/linkedout-data/config/secrets.yaml << 'EOF'
openai_api_key: "sk-..."
apify_api_key: "apify_api_..."  # omit if not provided
EOF
chmod 600 ~/linkedout-data/config/secrets.yaml
```

Then run setup:
```bash
cd $(git rev-parse --show-toplevel)/backend && \
  source .venv/bin/activate && \
  linkedout setup --full
```

**Step 4: After setup** — run data steps with collected inputs:
```bash
linkedout setup-user-profile --url "https://linkedin.com/in/..."
linkedout import-connections ~/Downloads/Connections.csv
```

**Step 5: Verify** — source `agent-context.env` and check status:
```bash
source ~/linkedout-data/config/agent-context.env && linkedout status
```

### Critical instructions to include in skill:
- NEVER use raw SQL to insert data
- NEVER source `agent-context.env` before setup completes
- If setup hangs on a prompt, it's a bug — report it

## Verification
- `/linkedout-setup` in Claude Code collects inputs, writes config, runs orchestrator
- No EOFError, no raw SQL
- All `input()` calls in setup modules have try/except

## Completion Criteria
- [ ] All `input()`/`getpass()` calls in 9 files wrapped with EOFError handling
- [ ] Safe defaults chosen for each prompt type
- [ ] Skill template rewritten with collect-then-run flow
- [ ] Rendered skill output regenerated
- [ ] No lint errors
