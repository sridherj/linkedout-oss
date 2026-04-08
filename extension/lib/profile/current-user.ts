// SPDX-License-Identifier: Apache-2.0
/** Extract the logged-in user's profile slug from the LinkedIn page DOM. */

export function getCurrentUserSlug(): string | null {
  // LinkedIn puts the current user's profile link in the nav "Me" dropdown
  const meLink = document.querySelector<HTMLAnchorElement>(
    'a[href*="/in/"][data-control-name="identity_welcome_message"], ' +
    '.global-nav__me-content a[href*="/in/"], ' +
    'a.global-nav__primary-link[href*="/in/"]'
  );
  if (meLink) {
    const match = meLink.href.match(/\/in\/([^/?#]+)/);
    if (match) return match[1].toLowerCase();
  }

  // Fallback: look for the mini-profile slug in page metadata
  const meta = document.querySelector<HTMLMetaElement>('meta[name="currentUser"]');
  if (meta?.content) return meta.content.toLowerCase();

  return null;
}
