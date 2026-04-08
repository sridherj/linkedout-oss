// SPDX-License-Identifier: Apache-2.0
interface RateLimitBarProps {
  hourly: { used: number; limit: number };
  daily: { used: number; limit: number };
}

function getColor(used: number, limit: number): { fill: string; text: string } {
  const pct = limit > 0 ? used / limit : 0;
  if (pct >= 0.8) return { fill: '#DC2626', text: '#DC2626' };
  if (pct >= 0.5) return { fill: '#D97706', text: '#D97706' };
  return { fill: '#16A34A', text: '#16A34A' };
}

function RateItem({ label, used, limit }: { label: string; used: number; limit: number }) {
  const pct = limit > 0 ? Math.min((used / limit) * 100, 100) : 0;
  const color = getColor(used, limit);

  return (
    <div style={{ flex: 1 }}>
      <div style={styles.labelRow}>
        <span style={styles.label}>{label}</span>
        <span style={{ ...styles.count, color: color.text }}>{used}/{limit}</span>
      </div>
      <div style={styles.bar}>
        <div style={{ ...styles.fill, width: `${pct}%`, background: color.fill }} />
      </div>
    </div>
  );
}

export default function RateLimitBar({ hourly, daily }: RateLimitBarProps) {
  return (
    <div style={styles.section}>
      <div style={styles.row}>
        <RateItem label="Hourly" used={hourly.used} limit={hourly.limit} />
        <RateItem label="Daily" used={daily.used} limit={daily.limit} />
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  section: { padding: '10px 16px 12px' },
  row: { display: 'flex', gap: 16 },
  labelRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    marginBottom: 4,
  },
  label: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: 10,
    color: '#9C9C93',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.04em',
  },
  count: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: 11,
    fontWeight: 500,
  },
  bar: {
    height: 4,
    borderRadius: 2,
    background: '#F6F2F8',
    overflow: 'hidden',
  },
  fill: {
    height: '100%',
    borderRadius: 2,
    transition: 'width 300ms ease-out',
  },
};
