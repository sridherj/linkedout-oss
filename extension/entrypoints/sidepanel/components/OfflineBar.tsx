// SPDX-License-Identifier: Apache-2.0
interface OfflineBarProps {
  visible: boolean;
}

export default function OfflineBar({ visible }: OfflineBarProps) {
  if (!visible) return null;

  return (
    <div style={styles.bar}>
      <span style={styles.icon}>⚡</span>
      <span>Backend unreachable — actions will retry on next attempt</span>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  bar: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '8px 16px',
    background: '#DC2626',
    color: '#fff',
    fontSize: 11,
    fontWeight: 500,
    lineHeight: 1.4,
  },
  icon: {
    flexShrink: 0,
  },
};
