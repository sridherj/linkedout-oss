# SP4: Backend Server Management

**Phase:** 12 — Chrome Extension Add-on
**Sub-phase:** 4 of 7
**Dependencies:** SP1 (UX Design Doc approved by SJ)
**Estimated effort:** ~75 minutes
**Shared context:** `_shared_context.md`
**Phase plan tasks:** 12E

---

## Scope

Implement the `linkedout start-backend` and `linkedout stop-backend` CLI commands for reliable backend server lifecycle management. Integrate backend status reporting into `linkedout status`.

---

## Task 12E: Backend Server Management

### Files to Create

#### `backend/src/linkedout/cli/commands/start_backend.py`

Implement `linkedout start-backend` CLI command per `docs/decision/cli-surface.md`:

```
linkedout start-backend [OPTIONS]

Options:
  --port PORT           Bind port (default: 8001, from LINKEDOUT_BACKEND_PORT)
  --host HOST           Bind host (default: 127.0.0.1, from LINKEDOUT_BACKEND_HOST)
  --background          Run as background daemon (write PID to ~/linkedout-data/state/backend.pid)
```

**Foreground mode (default):**
- Runs uvicorn directly
- Logs to stdout + `~/linkedout-data/logs/backend.log`

**Background mode (`--background`):**
1. Check if port is in use → kill existing process if found (idempotent — resolved decision)
2. Fork process via `subprocess.Popen` with stdout/stderr redirected to `~/linkedout-data/logs/backend.log`
3. Write PID to `~/linkedout-data/state/backend.pid`
4. Wait up to 10s for health check (`GET /health`) to succeed
5. Print: `Backend started on http://localhost:8001 (PID: 12345)`
6. If health check fails: print error, kill process, exit 1

**Idempotency:** Before starting, check if a process is already running on the target port. If so, kill it first. `start-backend` is always safe to re-run.

#### `backend/src/linkedout/cli/commands/stop_backend.py`

Implement `linkedout stop-backend`:
1. Read PID from `~/linkedout-data/state/backend.pid`
2. Send SIGTERM, wait up to 10s, then SIGKILL if still running
3. Remove PID file
4. Confirm: `Backend stopped.`
5. If no PID file or process not running: `Backend is not running.`

**Note:** `stop-backend` is user-facing in `--help` as a convenience command. Not part of the 13-command contract (resolved decision Q5).

### Files to Modify

#### `backend/src/linkedout/cli/cli.py`
- Register `start-backend` command
- Register `stop-backend` command

#### `backend/src/linkedout/cli/commands/status.py`
Add backend status check:
- Check if `~/linkedout-data/state/backend.pid` exists AND process is running
- Check if port is reachable: `GET http://localhost:{port}/health`
- Report: `backend: running (PID 12345, port 8001)` or `backend: not running`

### Decision Docs to Read

Before implementing, read:
- `docs/decision/cli-surface.md` — `start-backend` command spec, CLI naming conventions
- `docs/decision/env-config-design.md` — `LINKEDOUT_BACKEND_PORT` (8001), `LINKEDOUT_BACKEND_HOST` (127.0.0.1), config YAML loading
- `docs/decision/2026-04-07-data-directory-convention.md` — PID file at `~/linkedout-data/state/backend.pid`, logs at `~/linkedout-data/logs/backend.log`
- Read current `backend/src/linkedout/cli/cli.py` to understand command registration pattern
- Read current `backend/src/linkedout/cli/commands/status.py` to understand existing status output format

### Implementation Notes

- Port and host defaults should come from config YAML (via the config loading established in Phase 2), with env var overrides (`LINKEDOUT_BACKEND_PORT`, `LINKEDOUT_BACKEND_HOST`), and CLI flags as final override
- Ensure `~/linkedout-data/state/` and `~/linkedout-data/logs/` directories are created if they don't exist
- The health check endpoint is `GET /health` on the backend API — verify this endpoint exists
- Process cleanup on SIGTERM must be clean (no zombie processes)
- Error messages for port conflicts must be actionable: suggest specific alternative port or command

### Verification

- [ ] `linkedout start-backend` starts uvicorn, serves API on configured port
- [ ] `linkedout start-backend --background` daemonizes correctly, PID file written to `~/linkedout-data/state/backend.pid`
- [ ] `linkedout start-backend --background` on already-running backend kills old process first (idempotent)
- [ ] `linkedout stop-backend` cleanly stops the backend, removes PID file
- [ ] `linkedout status` reports backend running/not running with PID and port
- [ ] Health check endpoint (`/health`) returns 200 with version info
- [ ] Port conflict produces clear error message with suggested resolution
- [ ] Logs are written to `~/linkedout-data/logs/backend.log`
- [ ] All error messages are actionable (reference specific commands)
