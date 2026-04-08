// SPDX-License-Identifier: Apache-2.0
import { useState } from 'react';
import type { ProfileDisplayData, ProfileBadgeStatus } from '../../../lib/messages';

interface ProfileCardProps {
  profile: ProfileDisplayData;
  badgeStatus: ProfileBadgeStatus;
  staleDays?: number;
}

const LocationIcon = () => (
  <svg viewBox="0 0 16 16" fill="currentColor" style={{ width: 11, height: 11, opacity: 0.6 }}>
    <path d="M8 1a5 5 0 0 0-5 5v.5c0 2 1.5 4.5 5 8 3.5-3.5 5-6 5-8V6a5 5 0 0 0-5-5zm0 7a2 2 0 1 1 0-4 2 2 0 0 1 0 4z" />
  </svg>
);

const ConnectionsIcon = () => (
  <svg viewBox="0 0 16 16" fill="currentColor" style={{ width: 11, height: 11, opacity: 0.6 }}>
    <path d="M8 2a6 6 0 1 0 0 12A6 6 0 0 0 8 2zM6.5 5a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0zM8 12c-1.7 0-3.2-.8-4-2 .8-1 2.3-1.5 4-1.5s3.2.5 4 1.5c-.8 1.2-2.3 2-4 2z" />
  </svg>
);

const CopyIcon = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ width: 10, height: 10 }}>
    <rect x="5" y="5" width="8" height="8" rx="1.5" />
    <path d="M3 11V3.5A1.5 1.5 0 0 1 4.5 2H11" />
  </svg>
);

function getInitials(name: string): string {
  return name.split(' ').map(w => w[0]).filter(Boolean).slice(0, 2).join('').toUpperCase();
}

function getBadgeConfig(status: ProfileBadgeStatus, staleDays?: number): { label: string; bg: string; color: string; dotColor: string } {
  switch (status) {
    case 'saved_today':
      return { label: 'Saved today', bg: '#E8F5E9', color: '#1B7A2E', dotColor: '#16A34A' };
    case 'up_to_date':
      return { label: 'Up to date', bg: '#F5EFFC', color: '#8558AC', dotColor: '#A87AD0' };
    case 'stale':
      return { label: `Stale (${staleDays ?? '?'} days)`, bg: '#FFF3E0', color: '#92400E', dotColor: '#D97706' };
    case 'not_saved':
      return { label: 'Not saved', bg: '#F6F2F8', color: '#9C9C93', dotColor: '#9C9C93' };
    case 'rate_limited':
      return { label: 'Rate limited', bg: '#FFF3E0', color: '#92400E', dotColor: '#D97706' };
    case 'save_failed':
      return { label: 'Save failed', bg: '#FEE2E2', color: '#B91C1C', dotColor: '#DC2626' };
    case 'challenge_detected':
      return { label: 'Challenge detected', bg: '#FEE2E2', color: '#B91C1C', dotColor: '#DC2626' };
    default:
      return { label: 'Loading', bg: '#F6F2F8', color: '#9C9C93', dotColor: '#9C9C93' };
  }
}

export default function ProfileCard({ profile, badgeStatus, staleDays }: ProfileCardProps) {
  const [copied, setCopied] = useState(false);
  const badge = getBadgeConfig(badgeStatus, staleDays);

  const copyUrl = () => {
    navigator.clipboard.writeText(profile.linkedinUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const connectionsLabel = profile.connectionsCount != null
    ? (profile.connectionsCount >= 500 ? '500+' : String(profile.connectionsCount))
    : null;

  return (
    <div style={styles.card}>
      <div style={styles.row}>
        {profile.avatarUrl ? (
          <div style={{ position: 'relative' as const }}>
            <img src={profile.avatarUrl} alt="" style={styles.avatarImg} />
            {profile.openToWork && <div style={styles.otwRing} />}
          </div>
        ) : (
          <div style={{ ...styles.avatar, ...(profile.openToWork ? styles.avatarOtw : {}), position: 'relative' as const }}>
            {getInitials(profile.name)}
            {profile.openToWork && <div style={styles.otwRing} />}
          </div>
        )}
        <div style={styles.info}>
          <div style={styles.nameRow}>
            <span style={styles.name}>{profile.name}</span>
            {profile.openToWork && <span style={styles.otwBadge}>Open to work</span>}
          </div>
          {profile.headline && <div style={styles.headline}>{profile.headline}</div>}
          <div style={styles.meta}>
            {profile.location && (
              <span style={styles.metaPill}>
                <LocationIcon />
                {profile.location}
              </span>
            )}
            {profile.location && connectionsLabel && <span style={styles.metaDot} />}
            {connectionsLabel && (
              <span style={styles.metaPill}>
                <ConnectionsIcon />
                {connectionsLabel}
              </span>
            )}
          </div>
          <div style={styles.actions}>
            <span style={{ ...styles.badge, background: badge.bg, color: badge.color }}>
              <span style={{ ...styles.badgeDot, background: badge.dotColor }} />
              {badge.label}
            </span>
            <button style={styles.copyBtn} onClick={copyUrl}>
              <CopyIcon />
              {copied ? 'Copied' : 'URL'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  card: { padding: '14px 16px 12px' },
  row: { display: 'flex', gap: '12px', alignItems: 'flex-start' },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: '50%',
    flexShrink: 0,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: "'Fraunces', serif",
    fontWeight: 600,
    fontSize: 16,
    color: 'white',
    background: '#A87AD0',
  },
  avatarOtw: {},
  avatarImg: {
    width: 48,
    height: 48,
    borderRadius: '50%',
    flexShrink: 0,
    objectFit: 'cover' as const,
  },
  otwRing: {
    position: 'absolute' as const,
    inset: -3,
    borderRadius: '50%',
    border: '2px solid #16A34A',
    pointerEvents: 'none' as const,
  },
  info: { flex: 1, minWidth: 0 },
  nameRow: { display: 'flex', alignItems: 'center', gap: 6 },
  name: { fontWeight: 600, fontSize: 15, lineHeight: 1.3 },
  otwBadge: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: '8.5px',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
    padding: '1px 6px',
    borderRadius: '9999px',
    background: '#E8F5E9',
    color: '#15803D',
    flexShrink: 0,
  },
  headline: {
    fontWeight: 400,
    fontSize: '12.5px',
    lineHeight: 1.4,
    color: '#6B6B63',
    marginTop: 1,
  },
  meta: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginTop: 5,
    flexWrap: 'wrap' as const,
  },
  metaPill: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: 10,
    color: '#9C9C93',
    display: 'flex',
    alignItems: 'center',
    gap: 3,
  },
  metaDot: {
    width: 2,
    height: 2,
    borderRadius: '50%',
    background: '#9C9C93',
  },
  actions: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    marginTop: 8,
  },
  badge: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 5,
    padding: '3px 10px',
    borderRadius: '9999px',
    fontFamily: "'Fragment Mono', monospace",
    fontSize: 10,
    letterSpacing: '0.02em',
  },
  badgeDot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
  },
  copyBtn: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: 10,
    color: '#A87AD0',
    background: 'none',
    border: '1px solid #E5E3DD',
    borderRadius: 6,
    padding: '3px 8px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: 4,
  },
};
