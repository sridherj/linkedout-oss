# SP6: Extension Constants Extraction

**Sub-phase:** 6 of 7
**Plan task:** 4G (Extension Constants Extraction)
**Dependencies:** SP1 (extension audit completed — reference `docs/audit/extension-constants-audit.md`)
**Independent of:** SP2–SP5 (can run in parallel — different codebase)
**Estimated complexity:** M
**Changes code:** Yes

---

## Objective

Create `extension/lib/config.ts` with a typed `ExtensionConfig` interface backed by `browser.storage.local`. Move all user-configurable extension values from `constants.ts` and other files to this config system. Document fragile constants that stay hardcoded.

---

## Steps

### 1. Create `extension/lib/config.ts`

Create a new config module with:

```typescript
export interface ExtensionConfig {
  backendUrl: string;
  stalenessDays: number;
  hourlyLimit: number;
  dailyLimit: number;
  minFetchDelayMs: number;
  maxFetchDelayMs: number;
  maxLogEntries: number;
  mutualPageSize: number;
  mutualMaxPages: number;
  urlDebounceMs: number;
}

const DEFAULTS: ExtensionConfig = {
  backendUrl: import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001',
  stalenessDays: 30,
  hourlyLimit: 30,
  dailyLimit: 150,
  minFetchDelayMs: 2000,
  maxFetchDelayMs: 5000,
  maxLogEntries: 200,
  mutualPageSize: 10,
  mutualMaxPages: 10,
  urlDebounceMs: 500,
};

export async function getConfig(): Promise<ExtensionConfig> {
  const stored = await browser.storage.local.get('linkedout_config');
  return { ...DEFAULTS, ...stored.linkedout_config };
}
```

**Note:** The exact field names and values above are from the plan. Verify against the actual code in `constants.ts` and other files before implementing.

### 2. Refactor `extension/lib/constants.ts`

Reduce `constants.ts` to only true constants that are NOT user-configurable:

**Keep in `constants.ts`:**
- Voyager decoration IDs (fragile LinkedIn internals — add clear documentation)
- Tenant/BU/User IDs (`tenant_sys_001`, `bu_sys_001`, `usr_sys_001`) — single-user OSS defaults
- Custom event names (`linkedout:*`) — internal protocol
- LinkedIn API query params (`q=memberIdentity`, etc.) — API contract
- HTTP status codes (`403`, `409`, `429`) — protocol constants

**Move to `config.ts`:**
- Backend URL
- Staleness days
- Rate limits (hourly, daily)
- Fetch delays (min, max)
- Max log entries
- Mutual connections pagination (page size, max pages)
- URL debounce timer

Add clear documentation comments to `constants.ts`:
```typescript
// ── Voyager Decoration IDs ──────────────────────────────
// WARNING: These are LinkedIn internal API identifiers.
// They are FRAGILE and may break with LinkedIn updates.
// Do NOT make these configurable — they must match LinkedIn's current API.
export const VOYAGER_FULL_PROFILE_DECORATION = '...FullProfileWithEntities-93';
export const VOYAGER_SEARCH_DECORATION = '...SearchClusterCollection-186';
```

### 3. Update all callers

Update these files to use `getConfig()` instead of importing from `constants.ts`:

- **`extension/lib/rate-limiter.ts`** — read `hourlyLimit`, `dailyLimit`, `minFetchDelayMs`, `maxFetchDelayMs` from config
- **`extension/lib/log.ts`** — read `maxLogEntries` from config
- **`extension/entrypoints/voyager.content.ts`** — read `urlDebounceMs` from config
- **`extension/lib/mutual/extractor.ts`** — read `mutualPageSize`, `mutualMaxPages` from config
- **`extension/lib/backend/client.ts`** — read `backendUrl` from config
- **Any other files** that import configurable values from `constants.ts`

**Important considerations:**
- `getConfig()` is async (reads from `browser.storage.local`). Callers that are currently synchronous will need to handle the async pattern.
- Consider caching: load config once at extension startup and pass it around, rather than calling `getConfig()` on every use. A singleton pattern with lazy initialization works well.
- For content scripts that need config synchronously at module load time, use the build-time `VITE_BACKEND_URL` as immediate fallback, then update from storage when available.

### 4. Verify extension builds

```bash
cd extension && npm run build  # or equivalent build command
```

---

## Verification

- [ ] `extension/lib/config.ts` exists with typed `ExtensionConfig` interface and `getConfig()` function
- [ ] `extension/lib/constants.ts` contains only true constants (Voyager IDs, event names, system IDs, API params, HTTP codes)
- [ ] All configurable values flow through `getConfig()`, not direct imports from `constants.ts`
- [ ] Voyager decoration IDs in `constants.ts` have fragility documentation
- [ ] `getConfig()` returns defaults when `browser.storage.local` is empty
- [ ] `getConfig()` merges stored values over defaults
- [ ] Extension builds without errors
- [ ] Run: `grep -rn "STALENESS_DAYS\|HOURLY_LIMIT\|DAILY_LIMIT" extension/lib/ --include="*.ts" | grep -v config.ts | grep -v constants.ts` — zero results for direct hardcoded references

---

## Notes

- Read all extension files listed in SP1's audit before making changes.
- The async nature of `getConfig()` is the main implementation challenge. Plan the caching strategy before updating callers.
- The options page (where users would edit these values in a UI) is Phase 12 work. For now, power users can edit via DevTools: `chrome.storage.local.set({ linkedout_config: { hourlyLimit: 50 } })`.
- Tenant/BU/User IDs (`tenant_sys_001` etc.) are intentionally NOT configurable — they're system defaults for single-user OSS.
