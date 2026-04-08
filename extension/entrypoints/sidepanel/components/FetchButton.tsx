// SPDX-License-Identifier: Apache-2.0
import type { ProfileBadgeStatus } from '../../../lib/messages';

interface FetchButtonProps {
  badgeStatus: ProfileBadgeStatus;
  isAutoMode: boolean;
  isFetching: boolean;
  onFetch: () => void;
}

const SaveIcon = () => (
  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
    <path d="M8 1v10M4 7l4 4 4-4" />
    <path d="M2 13h12" />
  </svg>
);

const Spinner = () => (
  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"
    style={{ animation: 'spin 1s linear infinite' }}>
    <path d="M8 1a7 7 0 0 1 7 7" />
    <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
  </svg>
);

export default function FetchButton({ badgeStatus, isAutoMode, isFetching, onFetch }: FetchButtonProps) {
  // Hidden in auto mode
  if (isAutoMode) return null;

  // Only show for actionable states
  const isNew = badgeStatus === 'not_saved';
  const isStale = badgeStatus === 'stale';
  const isError = badgeStatus === 'save_failed' || badgeStatus === 'challenge_detected';
  if (!isNew && !isStale && !isError) return null;

  const isSecondary = isStale || isError;
  const label = isNew ? 'Save to LinkedOut' : isStale ? 'Update Profile' : 'Retry Save';

  return (
    <button
      style={{
        ...styles.btn,
        ...(isSecondary ? styles.secondary : {}),
        ...(isFetching ? styles.disabled : {}),
      }}
      onClick={onFetch}
      disabled={isFetching}
    >
      {isFetching ? <Spinner /> : <SaveIcon />}
      {label}
    </button>
  );
}

const styles: Record<string, React.CSSProperties> = {
  btn: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    width: 'calc(100% - 32px)',
    margin: '4px 16px',
    padding: '10px 16px',
    border: 'none',
    borderRadius: 6,
    background: '#A87AD0',
    color: 'white',
    fontFamily: "'Fraunces', serif",
    fontWeight: 500,
    fontSize: 13,
    cursor: 'pointer',
    transition: 'background 150ms ease-out',
  },
  secondary: {
    background: 'none',
    border: '1px solid #A87AD0',
    color: '#A87AD0',
  },
  disabled: {
    background: '#E5E3DD',
    color: '#9C9C93',
    cursor: 'not-allowed',
    border: 'none',
  },
};
