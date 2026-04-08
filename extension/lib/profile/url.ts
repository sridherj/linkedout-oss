// SPDX-License-Identifier: Apache-2.0
/**
 * LinkedIn URL utilities — port of Python logic at
 * src/shared/utils/linkedin_url.py
 *
 * Canonical form: https://www.linkedin.com/in/<slug>
 */

/**
 * Normalize a LinkedIn profile URL to canonical form.
 * Strips query params, trailing slashes, country prefixes, forces lowercase slug.
 * Returns null for empty/invalid URLs.
 */
export function normalizeLinkedinUrl(url: string): string | null {
  if (!url || !url.trim()) return null;

  url = url.trim();

  // Must contain linkedin.com/in/
  if (!url.toLowerCase().includes('linkedin.com/in/')) return null;

  // Ensure protocol
  if (!url.includes('://')) url = `https://${url}`;

  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }

  // Strip trailing slashes from path
  const path = parsed.pathname.replace(/\/+$/, '');

  // Find the /in/<slug> portion
  const match = path.match(/\/in\/([^/]+)/);
  if (!match) return null;

  const slug = match[1].toLowerCase();
  if (!slug) return null;

  return `https://www.linkedin.com/in/${slug}`;
}

/** Extract the profile ID (slug) from a LinkedIn URL. */
export function extractProfileId(url: string): string | null {
  const normalized = normalizeLinkedinUrl(url);
  if (!normalized) return null;
  const match = normalized.match(/\/in\/([^/]+)$/);
  return match ? match[1] : null;
}

/** Check if a URL is a LinkedIn profile page. */
export function isLinkedInProfilePage(url: string): boolean {
  return normalizeLinkedinUrl(url) !== null;
}
