// SPDX-License-Identifier: Apache-2.0
import { describe, it, expect } from 'vitest';
import { normalizeLinkedinUrl, extractProfileId, isLinkedInProfilePage } from '../url';

describe('normalizeLinkedinUrl', () => {
  it('strips query params', () => {
    expect(normalizeLinkedinUrl('https://www.linkedin.com/in/johndoe?ref=search'))
      .toBe('https://www.linkedin.com/in/johndoe');
  });

  it('strips trailing slashes', () => {
    expect(normalizeLinkedinUrl('https://www.linkedin.com/in/johndoe/'))
      .toBe('https://www.linkedin.com/in/johndoe');
  });

  it('lowercases slug', () => {
    expect(normalizeLinkedinUrl('https://www.linkedin.com/in/JohnDoe'))
      .toBe('https://www.linkedin.com/in/johndoe');
  });

  it('handles country prefixes (de., uk.)', () => {
    expect(normalizeLinkedinUrl('https://de.linkedin.com/in/johndoe'))
      .toBe('https://www.linkedin.com/in/johndoe');
    expect(normalizeLinkedinUrl('https://uk.linkedin.com/in/johndoe'))
      .toBe('https://www.linkedin.com/in/johndoe');
  });

  it('adds missing protocol', () => {
    expect(normalizeLinkedinUrl('linkedin.com/in/johndoe'))
      .toBe('https://www.linkedin.com/in/johndoe');
  });

  it('returns null for empty/whitespace', () => {
    expect(normalizeLinkedinUrl('')).toBeNull();
    expect(normalizeLinkedinUrl('   ')).toBeNull();
  });

  it('returns null for non-LinkedIn URLs', () => {
    expect(normalizeLinkedinUrl('https://twitter.com/johndoe')).toBeNull();
  });

  it('returns null for missing /in/', () => {
    expect(normalizeLinkedinUrl('https://www.linkedin.com/company/acme')).toBeNull();
  });

  it('returns null for empty slug /in/', () => {
    // /in/ with nothing after it — the regex won't match
    expect(normalizeLinkedinUrl('https://www.linkedin.com/in/')).toBeNull();
  });
});

describe('extractProfileId', () => {
  it('returns slug from valid URL', () => {
    expect(extractProfileId('https://www.linkedin.com/in/johndoe')).toBe('johndoe');
  });

  it('returns null for invalid URL', () => {
    expect(extractProfileId('https://twitter.com/johndoe')).toBeNull();
  });
});

describe('isLinkedInProfilePage', () => {
  it('returns true for valid LinkedIn profile URLs', () => {
    expect(isLinkedInProfilePage('https://www.linkedin.com/in/johndoe')).toBe(true);
  });

  it('returns false for non-profile URLs', () => {
    expect(isLinkedInProfilePage('https://www.linkedin.com/company/acme')).toBe(false);
    expect(isLinkedInProfilePage('https://twitter.com/johndoe')).toBe(false);
  });
});
