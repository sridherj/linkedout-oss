// SPDX-License-Identifier: Apache-2.0
import { browser } from 'wxt/browser';

interface ChallengeBannerProps {
  visible: boolean;
  message?: string;
}

export default function ChallengeBanner({ visible, message }: ChallengeBannerProps) {
  if (!visible) return null;

  const handleRetry = () => {
    browser.runtime.sendMessage({ type: 'RETRY_AFTER_CHALLENGE' });
  };

  return (
    <div style={styles.banner}>
      <div style={styles.text}>
        {message || 'LinkedIn detected unusual activity. Please complete the challenge in your LinkedIn tab, then click Retry.'}
      </div>
      <button style={styles.retryBtn} onClick={handleRetry}>
        Retry
      </button>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  banner: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
    margin: '8px 16px',
    padding: '10px 12px',
    background: '#FEE2E2',
    borderLeft: '3px solid #DC2626',
    borderRadius: 6,
    fontSize: 12,
    lineHeight: 1.4,
    color: '#991B1B',
  },
  text: {
    flex: 1,
  },
  retryBtn: {
    flexShrink: 0,
    padding: '4px 12px',
    background: '#DC2626',
    color: '#fff',
    border: 'none',
    borderRadius: 4,
    fontSize: 11,
    fontWeight: 600,
    cursor: 'pointer',
  },
};
