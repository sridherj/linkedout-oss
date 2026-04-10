# SP-A: Sandbox Infrastructure Enhancements

**Phase:** Integration Test for Installation
**Plan tasks:** A1 (settings.json), A2 (--dev flag), A3 (--detach flag), A4 (session log mount)
**Dependencies:** None (first sub-phase)
**Blocks:** SP-B, SP-C, SP-D, SP-E, SP-F
**Can run in parallel with:** —

## Objective

Make the existing sandbox container work headlessly with Claude Code and support dev-mode volume mounting. All four tasks modify existing files — no new files created. These are small, contained changes that enable all downstream sub-phases.

## Context

- Read shared context: `docs/execution/integration-test/_shared_context.md`
- Read plan (Sub-phase A section): `docs/plan/integration-test-installation.md`
- Read existing Dockerfile: `Dockerfile.sandbox`
- Read existing sandbox CLI: `backend/src/dev_tools/sandbox.py`

## Deliverables

### A1. Bake `settings.json` into Dockerfile

**File to modify:** `Dockerfile.sandbox`

After the Claude credentials block, add a `RUN` step that creates `/root/.claude/settings.json`:

```json
{
  "skipDangerousModePermissionPrompt": true,
  "effortLevel": "medium",
  "permissions": {
    "allow": ["Bash(*)", "Read", "Edit", "Write", "Glob", "Grep"],
    "defaultMode": "bypassPermissions"
  }
}
```

This enables headless Claude Code execution without interactive permission prompts. These are standard `settings.json` keys already used in SJ's own config.

**Implementation:**
```dockerfile
# -- Claude Code headless config --
RUN mkdir -p /root/.claude && \
    echo '{ \
      "skipDangerousModePermissionPrompt": true, \
      "effortLevel": "medium", \
      "permissions": { \
        "allow": ["Bash(*)", "Read", "Edit", "Write", "Glob", "Grep"], \
        "defaultMode": "bypassPermissions" \
      } \
    }' > /root/.claude/settings.json
```

### A2. Add `--dev` flag to `sandbox.py`

**File to modify:** `backend/src/dev_tools/sandbox.py`

Add a `--dev` click option that volume-mounts the local repo into the container:

```python
@click.option('--dev', is_flag=True, help='Volume-mount local repo for live editing.')
```

When `--dev` is active:
- Add `-v {REPO_ROOT}:/linkedout-oss` to the `docker run` command
- Skip the `git clone` step (the mount overlays `/linkedout-oss`)
- Log: `"Dev mode: local repo mounted at /linkedout-oss (changes appear instantly)"`

This enables burnish mode — code changes by the parent appear instantly inside the container without rebuilding.

### A3. Add `--detach` flag to `sandbox.py`

**File to modify:** `backend/src/dev_tools/sandbox.py`

Add a `--detach` flag that starts the container in detached mode and prints the container ID:

```python
@click.option('--detach', is_flag=True, help='Start container detached, print container ID.')
```

When `--detach` is active:
- Use `docker run -d --rm <image> sleep infinity` (with `-v` flag if `--dev`)
- Capture and print the container ID to stdout
- Do NOT exec into the container (the parent harness will `docker exec` into it via tmux)

### A4. Session log volume mount

**File to modify:** `backend/src/dev_tools/sandbox.py`

Always mount `/tmp/linkedout-oss` for session log access from the host:

```python
'-v', '/tmp/linkedout-oss:/tmp/linkedout-oss'
```

Add this volume mount to the `docker run` command unconditionally (both interactive and detached modes). This allows the parent harness to read session logs even when the container is running detached.

## Verification

1. **A1:** `docker run --rm linkedout-sandbox cat /root/.claude/settings.json` returns valid JSON with `bypassPermissions`
2. **A2:** `linkedout-sandbox --dev` — inside container, `ls /linkedout-oss/setup` shows the host file; modify a file on host -> visible inside container
3. **A3:** `linkedout-sandbox --detach` prints a container ID; `docker exec -it <id> bash` drops into the container
4. **A4:** Session logs written inside the container at `/tmp/linkedout-oss/` are readable on the host
5. **All flags combine:** `linkedout-sandbox --dev --detach` starts detached with volume mount and prints container ID

## Notes

- Read the existing `sandbox.py` carefully before modifying — it already handles `--no-build` and `--no-claude` flags. Follow the same patterns.
- The `--dev` and `--detach` flags must compose with each other and with existing flags (`--no-build`, `--no-claude`).
- Container runs as root — acceptable for an ephemeral throwaway sandbox.
- The Dockerfile change must be placed after the Claude credentials block to ensure `/root/.claude/` directory exists.
