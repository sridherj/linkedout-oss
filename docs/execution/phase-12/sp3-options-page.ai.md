# SP3: Options Page + Config Refactor

**Phase:** 12 — Chrome Extension Add-on
**Sub-phase:** 3 of 7
**Dependencies:** SP1 (UX Design Doc approved by SJ)
**Estimated effort:** ~90 minutes
**Shared context:** `_shared_context.md`
**Phase plan tasks:** 12C

---

## Scope

Create an extension options page for user-configurable settings and refactor the existing constants system to use async config loading from `browser.storage.local`. This is the most file-touching sub-phase — it touches the config layer that many extension files depend on.

---

## Task 12C: Extension Options Page

### Files to Create

#### `extension/entrypoints/options/index.html`
Minimal HTML shell for the React options page.

#### `extension/entrypoints/options/main.tsx`
React mount point — standard WXT options page entry.

#### `extension/entrypoints/options/App.tsx`
Settings form with the following fields:

| Setting | Default | Type | Notes |
|---------|---------|------|-------|
| Backend URL | `http://localhost:8001` | text input | From `VITE_BACKEND_URL` build-time default |
| Staleness threshold (days) | `30` | number input | Per `LINKEDOUT_STALENESS_DAYS` |
| Hourly rate limit | `30` | number input | Per `LINKEDOUT_RATE_LIMIT_HOURLY` |
| Daily rate limit | `150` | number input | Per `LINKEDOUT_RATE_LIMIT_DAILY` |
| Tenant ID | `tenant_sys_001` | text input | Advanced — collapsed by default |
| BU ID | `bu_sys_001` | text input | Advanced — collapsed by default |
| User ID | `usr_sys_001` | text input | Advanced — collapsed by default |
| Enrichment mode | `manual` | toggle | manual / auto |

Include a **"Connection Test" button** that:
- Calls `GET {backendUrl}/health`
- Shows green check + "Connected to LinkedOut backend v{version}" on success
- Shows red X + error message on failure
- Helps users validate their backend URL without leaving the options page

#### `extension/lib/config.ts`
Replace the hardcoded constants pattern with an async `getConfig()` function:

```typescript
export async function getConfig(): Promise<ExtensionConfig> {
  // Read from browser.storage.local
  // Fall back to hardcoded defaults for any missing values
  // Return typed config object
}
```

Pattern specified in `docs/decision/env-config-design.md`.

### Files to Modify

#### `extension/lib/constants.ts`
- Deprecate this file — re-export from `config.ts` for backward compatibility during this sub-phase
- All consumers should be migrated to use `getConfig()` directly

#### `extension/lib/backend/client.ts`
- Migrate from static `API_BASE_URL`, `APP_USER_ID`, `STALENESS_DAYS` imports to async `getConfig()` calls
- The `request()` helper must load config before making API calls

#### `extension/entrypoints/background.ts`
- Migrate `STALENESS_DAYS` usage to async `getConfig()`

#### `extension/lib/rate-limiter.ts`
- Migrate `HOURLY_LIMIT`, `DAILY_LIMIT` to async `getConfig()`

#### `extension/lib/settings.ts`
- May need to merge enrichment mode into the unified config if not already aligned

#### `extension/wxt.config.ts`
- Verify WXT auto-discovers `entrypoints/options/`. If not, add manual registration.

### Decision Docs to Read

Before implementing, read:
- `docs/decision/env-config-design.md` — the `getConfig()` pattern, `browser.storage.local` usage, all config keys and defaults
- Read the current `extension/lib/constants.ts` to understand what's being replaced
- Read all files that import from `constants.ts` to understand the migration scope

### Implementation Notes

- All config values must be typed — create an `ExtensionConfig` interface
- `getConfig()` should cache the config in memory with a short TTL or invalidate on storage change events
- Settings persist across extension reloads (browser.storage.local is durable)
- Changing backend URL takes effect on next API call (no extension reload needed)
- Default values MUST match `docs/decision/env-config-design.md`

### Verification

- [ ] Options page is accessible via chrome://extensions → LinkedOut → Details → Extension options
- [ ] All 8 settings are present with correct defaults
- [ ] Advanced settings (Tenant ID, BU ID, User ID) are collapsed by default
- [ ] Connection test button works (both success and failure states)
- [ ] Settings persist across extension reloads
- [ ] `getConfig()` returns correct defaults when storage is empty
- [ ] `getConfig()` merges stored values with defaults
- [ ] All consumers of `constants.ts` are migrated to `getConfig()`
- [ ] No import errors or runtime errors from the migration
- [ ] `extension/lib/config.ts` is the single source of truth for extension configuration
