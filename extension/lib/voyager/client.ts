// SPDX-License-Identifier: Apache-2.0
/** Voyager API caller — runs in MAIN world content script. */

import { VOYAGER_DECORATION_ID } from '../constants';
import type { VoyagerRawResponse } from './types';

export class VoyagerCsrfError extends Error {
  constructor() {
    super('CSRF token not found or expired — re-login to LinkedIn');
    this.name = 'VoyagerCsrfError';
  }
}

export class VoyagerRateLimitError extends Error {
  constructor() {
    super('LinkedIn rate limited this request (429)');
    this.name = 'VoyagerRateLimitError';
  }
}

export class VoyagerChallengePage extends Error {
  constructor() {
    super('LinkedIn returned a challenge page — solve CAPTCHA and retry');
    this.name = 'VoyagerChallengePage';
  }
}

function extractCsrf(): string {
  const match = document.cookie.match(/JSESSIONID="?([^";]+)"?/);
  if (!match) throw new VoyagerCsrfError();
  return match[1];
}

/**
 * Fetch a full profile from LinkedIn's Voyager API using session cookies.
 * @param profileId - The LinkedIn public identifier (slug).
 * @returns Raw Voyager JSON response.
 */
export async function fetchVoyagerProfile(
  profileId: string,
): Promise<VoyagerRawResponse> {
  const csrf = extractCsrf();
  const url =
    `https://www.linkedin.com/voyager/api/identity/dash/profiles` +
    `?q=memberIdentity&memberIdentity=${encodeURIComponent(profileId)}` +
    `&decorationId=${encodeURIComponent(VOYAGER_DECORATION_ID)}`;

  const res = await fetch(url, {
    headers: {
      'csrf-token': csrf,
      accept: 'application/vnd.linkedin.normalized+json+2.1',
    },
    credentials: 'include',
  });

  if (res.status === 403) throw new VoyagerCsrfError();
  if (res.status === 429) throw new VoyagerRateLimitError();

  const contentType = res.headers.get('content-type') ?? '';
  if (!contentType.includes('json')) throw new VoyagerChallengePage();

  return (await res.json()) as VoyagerRawResponse;
}
