// SPDX-License-Identifier: Apache-2.0
/**
 * Extension-wide truly-constant values (never change at runtime).
 *
 * Configurable values (backend URL, rate limits, system IDs, enrichment mode)
 * have moved to lib/config.ts. Use getConfigSync() or getConfig() instead.
 */

// ── Voyager Decoration IDs ─────────────────────────────────
// WARNING: These are LinkedIn internal API identifiers.
// They are FRAGILE and may break when LinkedIn updates their API.
// Do NOT make these configurable — they must match LinkedIn's current API.
// Symptom of breakage: Voyager API returns 400 or empty results.

/** Decoration ID for full profile data (used by fetchVoyagerProfile). */
export const VOYAGER_DECORATION_ID =
  'com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-93';

/** Decoration ID for search/clusters endpoint (used by mutual connection extractor). */
export const VOYAGER_SEARCH_DECORATION_ID =
  'com.linkedin.voyager.dash.deco.search.SearchClusterCollection-186';

// ── Mutual Connection Pagination ───────────────────────────
// Must match LinkedIn's Voyager search pagination size — not user-configurable.
export const MUTUAL_PAGE_SIZE = 10;
