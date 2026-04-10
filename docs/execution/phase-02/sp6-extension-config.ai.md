# SP6: Extension Config Refactor

**Sub-phase:** 6 of 7
**Tasks covered:** 2I
**Size:** M
**Dependencies:** None (independent of backend work — can run in parallel with SP4/SP5)
**Estimated effort:** 30-45 minutes

---

## Objective

Replace hardcoded values in `extension/lib/constants.ts` with a config module that reads from `browser.storage.local` with fallbacks to build-time env vars and hardcoded defaults.

---

## Steps

### 1. Read Current Extension Code

Understand the current state:
- `extension/lib/constants.ts` — all hardcoded values
- `extension/wxt.config.ts` — WXT build configuration
- Find all files importing from `constants.ts`:
  ```bash
  grep -rn "from.*constants\|import.*constants" extension/ --include="*.ts" --include="*.tsx"
  ```

### 2. Create `extension/lib/config.ts`

```typescript
import { browser } from 'wxt/browser';

export interface ExtensionConfig {
  backendUrl: string;
  stalenessDays: number;
  hourlyLimit: number;
  dailyLimit: number;
}

const DEFAULTS: ExtensionConfig = {
  backendUrl: import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001',
  stalenessDays: 30,
  hourlyLimit: 30,
  dailyLimit: 150,
};

// Cached config — loaded once at startup
let _cachedConfig: ExtensionConfig | null = null;

export async function getConfig(): Promise<ExtensionConfig> {
  if (_cachedConfig) return _cachedConfig;
  
  const stored = await browser.storage.local.get('linkedout_config');
  _cachedConfig = { ...DEFAULTS, ...(stored.linkedout_config || {}) };
  return _cachedConfig;
}

// Synchronous access after initial load (returns defaults if not yet loaded)
export function getConfigSync(): ExtensionConfig {
  return _cachedConfig || DEFAULTS;
}

// Call once at extension startup (e.g., in background script)
export async function initConfig(): Promise<ExtensionConfig> {
  _cachedConfig = null; // force reload
  return getConfig();
}
```

**Design decision (from shared context):** Cache at startup, not per-call async. This simplifies consumer code.

### 3. Refactor `extension/lib/constants.ts`

**Keep in `constants.ts`** (truly constant, never change):
- `TENANT_ID` — `'tenant_sys_001'`
- `BU_ID` — `'bu_sys_001'`
- `APP_USER_ID` — `'usr_sys_001'`
- Voyager decoration ID (LinkedIn API constant)
- `PAGE_DELAY_MIN_MS`, `PAGE_DELAY_MAX_MS` — internal timing
- Any other truly-constant values not configurable by users

**Remove from `constants.ts`** (moved to `config.ts`):
- `API_BASE_URL` → `config.backendUrl`
- `STALENESS_DAYS` → `config.stalenessDays`
- `HOURLY_LIMIT` → `config.hourlyLimit`
- `DAILY_LIMIT` → `config.dailyLimit`

### 4. Update `extension/wxt.config.ts`

Ensure `VITE_BACKEND_URL` is recognized as a build-time env var. WXT uses Vite under the hood, so `import.meta.env.VITE_*` vars work automatically. Verify:

```typescript
// wxt.config.ts
export default defineConfig({
  // ... existing config ...
  // Vite env vars (VITE_* prefix) are automatically available
  // No explicit configuration needed for VITE_BACKEND_URL
});
```

If WXT has a `vite` config section, check that it doesn't filter out `VITE_BACKEND_URL`.

### 5. Update All Consumer Files

For each file that imports `API_BASE_URL`, `STALENESS_DAYS`, `HOURLY_LIMIT`, or `DAILY_LIMIT` from `constants.ts`:

**Option A (preferred — using cached sync access):**
```typescript
// Before:
import { API_BASE_URL } from '~/lib/constants';
fetch(`${API_BASE_URL}/api/...`);

// After:
import { getConfigSync } from '~/lib/config';
fetch(`${getConfigSync().backendUrl}/api/...`);
```

**Option B (if in async context):**
```typescript
import { getConfig } from '~/lib/config';
const config = await getConfig();
fetch(`${config.backendUrl}/api/...`);
```

**Key consideration:** If the extension has a background script or startup point, call `initConfig()` there first so `getConfigSync()` works everywhere else.

### 6. Initialize Config at Startup

Find the extension's main entry point (likely `extension/entrypoints/background.ts` or similar) and add:

```typescript
import { initConfig } from '~/lib/config';

// At startup
await initConfig();
```

### 7. Verify Extension Builds

```bash
cd extension && npm run build
```

Fix any TypeScript errors from the refactor.

---

## Verification

```bash
# Extension builds successfully
cd extension && npm run build && echo "PASS: build succeeded" || echo "FAIL: build failed"

# New config module exists
test -f extension/lib/config.ts && echo "PASS" || echo "FAIL"

# API_BASE_URL no longer in constants.ts
grep "API_BASE_URL" extension/lib/constants.ts && echo "FAIL: still hardcoded" || echo "PASS: removed"

# No direct imports of removed constants
grep -rn "API_BASE_URL\|STALENESS_DAYS\|HOURLY_LIMIT\|DAILY_LIMIT" extension/ --include="*.ts" --include="*.tsx" | grep "constants" && echo "FAIL: old imports remain" || echo "PASS"

# Config module exports getConfig
grep "export.*getConfig" extension/lib/config.ts && echo "PASS" || echo "FAIL"

# VITE_BACKEND_URL referenced in config
grep "VITE_BACKEND_URL" extension/lib/config.ts && echo "PASS" || echo "FAIL"

# Truly-constant values still in constants.ts
grep "TENANT_ID\|BU_ID\|APP_USER_ID" extension/lib/constants.ts && echo "PASS: constants preserved" || echo "FAIL"

# TypeScript type check
cd extension && npx tsc --noEmit && echo "PASS: type check" || echo "FAIL: type errors"
```

---

## Acceptance Criteria

- [ ] `extension/lib/config.ts` exists with `getConfig()`, `getConfigSync()`, and `initConfig()`
- [ ] `API_BASE_URL` no longer hardcoded in `constants.ts` — reads from config
- [ ] `VITE_BACKEND_URL` env var works at build time
- [ ] Extension builds successfully (`npm run build`)
- [ ] Extension still connects to backend on `localhost:8001` by default
- [ ] Truly-constant values (`TENANT_ID`, `BU_ID`, `APP_USER_ID`, Voyager IDs) remain in `constants.ts`
- [ ] Config cached at startup — `getConfigSync()` works in synchronous contexts
- [ ] All consumer files updated to use config instead of old constants
