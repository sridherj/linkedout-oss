# Voyager Schema Mapping to CrawledProfile API

> Maps LinkedIn Voyager API response fields to the LinkedOut `CreateCrawledProfileRequestSchema`.
> Created during sp1d of the Chrome Extension spike (2026-04-04).

## 1. Voyager Endpoint Patterns Matched

The interceptor (`entrypoints/interceptor.content.ts`) matches:

| Pattern | When Fired |
|---------|------------|
| `*/voyager/api/identity/dash/profiles*` | Navigating to any LinkedIn profile page (`/in/<slug>`) |

The URL includes query params like `decorationId` and `memberIdentity` — these vary by LinkedIn's internal versioning and are **not** relevant to field extraction. The interceptor matches on the path substring only.

No additional Voyager endpoints are intercepted at this time. Future candidates:
- `/voyager/api/identity/dash/profiles?...&decorationId=...FULL_PROFILE...` — may return richer data (education, experience arrays) on some page loads
- `/voyager/api/graphql?...` — LinkedIn is gradually migrating to GraphQL; not observed in the spike

## 2. Response Structure

### Top-Level Shape

```json
{
  "data": { ... },
  "included": [ ... ]
}
```

- **`data`**: Contains the primary entity reference (URN pointer) and metadata. Not directly useful for field extraction.
- **`included`**: Flat array of entities, each tagged with a `$type` discriminator and an `entityUrn`. This is where all profile data lives.

### `included` Array Structure

Each element in `included` is an object with:

```json
{
  "$type": "com.linkedin.voyager.dash.identity.profile.Profile",
  "entityUrn": "urn:li:fsd_profile:ACoAAB...",
  "firstName": "...",
  ...
}
```

### `$type` Discriminators Observed

| `$type` (suffix) | Full `$type` Value | Contains |
|-------------------|--------------------|----------|
| `...Profile` | `com.linkedin.voyager.dash.identity.profile.Profile` | Core profile: name, headline, location, summary, connections |
| `...Position` | `com.linkedin.voyager.dash.identity.profile.Position` | Job positions: title, company, date range |
| `...Education` | `com.linkedin.voyager.dash.identity.profile.Education` | Education entries |
| `...Skill` | `com.linkedin.voyager.dash.identity.profile.Skill` | Skills |
| `...ProfilePhoto` | `com.linkedin.voyager.dash.identity.profile.PhotoFilterPicture` | Profile image reference |
| `...Industry` | `com.linkedin.voyager.dash.common.Industry` | Industry classification |
| `...GeoLocation` | `com.linkedin.voyager.dash.common.Geo` | Structured geo data |

**Note:** The exact `$type` strings may vary across LinkedIn deployments. The interceptor's background script filters using `.includes('Profile')` — this is intentionally broad for the spike. Phase 2 should use exact type matching.

## 3. Field-by-Field Mapping Table

### Legend
- **Required**: Must be provided in `CreateCrawledProfileRequestSchema`
- **Source**: Where in the Voyager response the data comes from
- **Confidence**: High = confirmed in spike logs, Medium = inferred from Voyager schema patterns, Low = may not be present

| # | CrawledProfile Field | Required | Voyager Source | `$type` | Path | Confidence | Notes |
|---|---------------------|----------|----------------|---------|------|------------|-------|
| 1 | `linkedin_url` | **Yes** | Constructed | — | `https://www.linkedin.com/in/{publicIdentifier}` | High | Must normalize (see §5) |
| 2 | `data_source` | **Yes** | Hardcoded | — | `'extension'` | High | Always `'extension'` for this source |
| 3 | `public_identifier` | No | Profile entity | `...Profile` | `.publicIdentifier` | High | Confirmed in spike |
| 4 | `first_name` | No | Profile entity | `...Profile` | `.firstName` | High | Confirmed in spike |
| 5 | `last_name` | No | Profile entity | `...Profile` | `.lastName` | High | Confirmed in spike |
| 6 | `full_name` | No | Derived | — | `${firstName} ${lastName}` | High | Concatenated client-side |
| 7 | `headline` | No | Profile entity | `...Profile` | `.headline` | High | Confirmed in spike |
| 8 | `about` | No | Profile entity | `...Profile` | `.summary` | Medium | Field name is `summary` in Voyager, not `about` |
| 9 | `location_city` | No | Profile / Geo | `...Profile` / `...Geo` | `.geoLocation` -> city | Medium | May need Geo entity lookup via URN |
| 10 | `location_state` | No | Profile / Geo | `...Profile` / `...Geo` | `.geoLocation` -> state | Medium | Same as above |
| 11 | `location_country` | No | Profile / Geo | `...Profile` / `...Geo` | `.geoLocation` -> country | Medium | Same as above |
| 12 | `location_country_code` | No | Profile / Geo | `...Profile` / `...Geo` | `.geoCountryCode` | Medium | May be directly on Profile entity |
| 13 | `location_raw` | No | Profile entity | `...Profile` | `.locationName` | High | Confirmed in spike; raw text like "San Francisco Bay Area" |
| 14 | `connections_count` | No | Profile entity | `...Profile` | `.connectionsCount` | Medium | May be capped at 500 for non-premium |
| 15 | `follower_count` | No | Profile entity | `...Profile` | `.followerCount` | Medium | Present on most profiles |
| 16 | `open_to_work` | No | Profile entity | `...Profile` | `.openToWork` or decoration | Low | May require separate API call or decoration flag |
| 17 | `premium` | No | Profile entity | `...Profile` | `.premium` | Low | May be in a separate decoration |
| 18 | `current_company_name` | No | Position entity | `...Position` | `.companyName` where `dateRange.end == null` | Medium | Filter positions for current (no end date) |
| 19 | `current_position` | No | Position entity | `...Position` | `.title` where `dateRange.end == null` | Medium | Same filter as above |
| 20 | `company_id` | No | Not mapped | — | — | — | Resolved server-side; do not send from extension |
| 21 | `seniority_level` | No | Not mapped | — | — | — | Enrichment/NLP; not in Voyager |
| 22 | `function_area` | No | Not mapped | — | — | — | Enrichment/NLP; not in Voyager |
| 23 | `source_app_user_id` | No | Not mapped | — | — | — | Set by backend based on auth |
| 24 | `has_enriched_data` | No | Hardcoded | — | `false` | High | Always false for fresh crawls |
| 25 | `last_crawled_at` | No | Generated | — | `new Date().toISOString()` | High | Timestamp at interception time |
| 26 | `profile_image_url` | No | Profile entity | `...Profile` | `.profilePicture.displayImageReference.vectorImage.rootUrl` + largest artifact | Medium | URL construction is multi-step (see §4) |
| 27 | `raw_profile` | No | Full response | — | `JSON.stringify(voyagerResponse)` | High | Store complete Voyager JSON as-is |

### Summary

| Category | Count |
|----------|-------|
| Fields with confirmed Voyager mapping | 15 |
| Fields with medium-confidence mapping | 8 |
| Fields not mappable (enrichment/server-side) | 4 |
| **Total CreateCrawledProfileRequestSchema fields** | **27** |

## 4. Profile Image URL Construction

Voyager profile images use a multi-part URL scheme:

```
profilePicture.displayImageReference.vectorImage:
  rootUrl: "https://media.licdn.com/dms/image/v2/..."
  artifacts: [
    { width: 100, height: 100, fileIdentifyingUrlPathSegment: "..._100_100/..." },
    { width: 200, height: 200, fileIdentifyingUrlPathSegment: "..._200_200/..." },
    { width: 400, height: 400, fileIdentifyingUrlPathSegment: "..._400_400/..." },
    { width: 800, height: 800, fileIdentifyingUrlPathSegment: "..._800_800/..." }
  ]
```

**Construction:** `rootUrl + largest artifact's fileIdentifyingUrlPathSegment`

**Caution:** These URLs are time-limited (contain an `e=<timestamp>` expiry param). The `profile_image_url` field should be treated as ephemeral — it may expire in ~30 days.

## 5. URL Normalization

The backend's canonical form (`src/shared/utils/linkedin_url.py`):
```
https://www.linkedin.com/in/<slug>
```

Rules:
- Lowercase slug
- No trailing slash
- No query params
- No country prefix (e.g., `/uk/` removed)

**Extension responsibility:** Before sending to the backend, construct the URL from `publicIdentifier`:
```typescript
const linkedinUrl = `https://www.linkedin.com/in/${publicIdentifier.toLowerCase()}`;
```

Do NOT use `window.location.href` as the source — it may contain query params, locale prefixes, or other noise. The `publicIdentifier` field from the Voyager response is the authoritative slug.

## 6. Comparison with Apify Format

### Fields present in Apify but NOT directly available in Voyager profile response

| Apify Field | Notes |
|-------------|-------|
| `location.parsed.city/state/country/countryCode` | Apify pre-parses location; Voyager provides raw `locationName` + separate Geo entity |
| `currentPosition[0].companyId` | Apify provides numeric company ID; Voyager uses URN-based references |
| `experience[]` (full array) | Voyager may include Position entities in `included`, but completeness varies by decoration |
| `education[]` (full array) | Same — depends on decoration requested by LinkedIn's frontend |
| `skills[]` (full array) | Same — may or may not be in the `included` array |
| `openToWork` | Apify reliably reports this; Voyager may require a specific decoration |
| `premium` | Same as above |

### Fields present in Voyager but NOT in Apify

| Voyager Field | Notes |
|---------------|-------|
| `industryName` | Direct industry string on Profile entity; Apify doesn't expose this |
| `entityUrn` | Internal LinkedIn URN — useful for deduplication |
| `$type` discriminators | Enables typed entity parsing; Apify flattens everything |
| `geoLocation` structured data | URN-referenced Geo entity with structured location data |

### Normalization Differences

| Aspect | Apify | Voyager |
|--------|-------|---------|
| **URL format** | `linkedinUrl` field, already canonical | Must construct from `publicIdentifier` |
| **Location** | Pre-parsed into `city`/`state`/`country` | Raw `locationName` string + separate Geo entity |
| **Date format** | `{ month: "Feb", year: 2025 }` (text month) | `{ month: 2, year: 2025 }` (numeric month) |
| **Company reference** | Numeric `companyId` string | URN like `urn:li:fsd_company:12345` |
| **Current position** | Separate `currentPosition` array | Position entities in `included` where `dateRange.end == null` |
| **Profile image** | Direct URL in `profilePicture.url` | Multi-part: `rootUrl` + artifact path segment |

## 7. Surprises and Unknowns

### Confirmed Surprises from Spike

1. **`locationName` vs `location`**: Voyager uses `locationName` (a flat string like "San Francisco Bay Area"), not a nested `location` object like Apify. Structured geo data is in a separate entity referenced by URN.

2. **`industryName` field**: Present directly on the Profile entity in Voyager. This is **bonus data** not available from Apify — could be useful for enrichment.

3. **`summary` vs `about`**: The Profile entity uses `summary` for the about/bio text. The CrawledProfile schema calls it `about`. Simple rename in the mapper.

4. **Variable response completeness**: The Voyager response's `included` array content depends on the `decorationId` query param. Some page loads return a minimal set (name, headline, location); others return the full profile with positions and education. The extension cannot control which decoration LinkedIn requests.

### Open Unknowns (Phase 2 Investigation)

1. **`openToWork` and `premium` availability**: These flags may not be in the standard profile decoration. May require observing additional Voyager endpoints or specific page interactions.

2. **Position/Education completeness**: The `included` array may not always contain all Position and Education entities. If the user hasn't scrolled to the Experience section, LinkedIn may not have fetched them yet. The extension may need to intercept multiple Voyager calls and merge.

3. **`connectionsCount` cap**: Non-premium users may see `500+` displayed, but the actual field value may be `500` or `null`. Need to verify with premium vs. non-premium profiles.

4. **Geo entity resolution**: Structured location (city, state, country) requires finding the Geo entity in `included` by matching URN references. The exact URN format and Geo entity structure need validation with more profile samples.

5. **Rate limiting / detection**: No throttling observed during the spike (intercepting is passive), but storing and forwarding data could trigger LinkedIn's client-side telemetry if done at scale.
