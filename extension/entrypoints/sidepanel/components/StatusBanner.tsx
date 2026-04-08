// SPDX-License-Identifier: Apache-2.0
interface StatusBannerProps {
  message: string;
  variant: 'error' | 'warning';
  onDismiss: () => void;
}

export default function StatusBanner({ message, variant, onDismiss }: StatusBannerProps) {
  const isError = variant === 'error';

  return (
    <div style={{
      ...styles.banner,
      background: isError ? '#FEE2E2' : '#FFF3E0',
      borderColor: isError ? '#DC2626' : '#D97706',
      color: isError ? '#991B1B' : '#92400E',
    }}>
      <div style={styles.content}>
        <span>{message}</span>
        <button style={styles.dismiss} onClick={onDismiss}>&times;</button>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  banner: {
    margin: '8px 16px',
    padding: '10px 12px',
    borderRadius: 6,
    fontSize: 12,
    lineHeight: 1.4,
    borderLeft: '3px solid',
  },
  content: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 8,
  },
  dismiss: {
    background: 'none',
    border: 'none',
    fontSize: 16,
    cursor: 'pointer',
    color: 'inherit',
    padding: 0,
    lineHeight: 1,
    flexShrink: 0,
    opacity: 0.7,
  },
};
