# SP4: Backend Startup Refactor (`main.py`)

**Sub-phase:** 4 of 7
**Tasks covered:** 2G
**Size:** M
**Dependencies:** SP2 (config module must exist)
**Estimated effort:** 30-45 minutes

---

## Objective

Replace the current env-file loading in `backend/main.py` with the new config system. Remove all references to `.env.local/.env.test/.env.prod` and the `ENVIRONMENT`-based file selection.

---

## Steps

### 1. Read Current `backend/main.py`

Understand the existing startup code:
- `_get_env_file()` function — selects `.env.local`/`.env.test`/`.env.prod` based on `ENVIRONMENT`
- `dotenv.load_dotenv()` call
- uvicorn configuration (host, port)
- CORS middleware setup
- Lifespan context (Procrastinate worker, Firebase auth)

### 2. Remove Old Config Loading

**Remove:**
- `_get_env_file()` function entirely
- `dotenv.load_dotenv(_get_env_file())` call
- `import dotenv` / `from dotenv import load_dotenv`
- Any reference to `ENVIRONMENT` env var for file selection

**Replace with:**
```python
from shared.config import get_config

settings = get_config()
```

### 3. Update Uvicorn Configuration

Replace hardcoded or env-var-based host/port with settings:

```python
uvicorn.run(
    app,
    host=settings.backend_host,
    port=settings.backend_port,
)
```

### 4. Update CORS Middleware

Current: `allow_origins=['*']`

Keep `['*']` as the default for local dev (per architecture decision — CORS tightening is Phase 6):

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(',') if settings.cors_origins else ['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
```

### 5. Update Log Level Configuration

If `main.py` sets up logging, use `settings.log_level`. The actual logging refactor is Phase 3, but wire the config value through.

### 6. Preserve Existing Functionality

**Keep unchanged (Phase 6 removes these):**
- Procrastinate worker startup in lifespan
- Firebase auth initialization
- Any other middleware or startup hooks

The goal is ONLY to change how config is loaded, not to change what the app does.

### 7. Remove Old Env Files (Optional Cleanup)

If `.env.local`, `.env.test`, `.env.prod` exist in the backend directory, note them but do NOT delete — they may be in the user's working copy. The `.gitignore` will exclude them.

---

## Verification

```bash
# Backend starts with DATABASE_URL env var only
DATABASE_URL=postgresql://linkedout:test@localhost:5432/linkedout \
  python -c "
from backend.main import app
print('PASS: app created successfully')
"

# No references to old env file pattern
grep -rn "\.env\.local\|\.env\.test\|\.env\.prod\|_get_env_file" backend/main.py && echo "FAIL: old pattern found" || echo "PASS: no old pattern"

# No dotenv import in main.py
grep -n "import dotenv\|from dotenv" backend/main.py && echo "FAIL: dotenv still imported" || echo "PASS: dotenv removed"

# Settings values used for uvicorn config
grep -n "settings\.backend_host\|settings\.backend_port" backend/main.py && echo "PASS: settings used" || echo "FAIL: settings not used"
```

---

## Acceptance Criteria

- [ ] Backend starts with `DATABASE_URL` env var alone
- [ ] Backend starts with `config.yaml` alone (if `config.yaml` has `database_url`)
- [ ] No reference to `.env.local` / `.env.test` / `.env.prod` in `main.py`
- [ ] No reference to `_get_env_file()` in `main.py`
- [ ] `python-dotenv` import removed from `main.py`
- [ ] `settings.backend_host` and `settings.backend_port` used for uvicorn
- [ ] `settings.cors_origins` used for CORS (with `['*']` fallback)
- [ ] Procrastinate and Firebase code left untouched (Phase 6)
