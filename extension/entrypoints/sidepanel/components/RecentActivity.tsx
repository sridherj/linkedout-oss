// SPDX-License-Identifier: Apache-2.0
import type { LogEntry } from '../../../lib/log';

interface RecentActivityProps {
  entries: LogEntry[];
  onViewAll: () => void;
}

const AVATAR_COLORS = ['#FAEAEE', '#F0EAF5', '#F6EDE4', '#EDE0F2', '#E0F2FE'];

function getInitials(name: string): string {
  return name.split(' ').map(w => w[0]).filter(Boolean).slice(0, 2).join('').toUpperCase();
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'now';
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  const days = Math.floor(hrs / 24);
  return `${days}d`;
}

export default function RecentActivity({ entries, onViewAll }: RecentActivityProps) {
  const recent = entries.slice(0, 5).filter((e) => e.profileName);

  return (
    <>
      <div style={styles.secHeader}>
        <span style={styles.secTitle}>Recent</span>
        <button style={styles.secAction} onClick={onViewAll}>View all</button>
      </div>
      {recent.length === 0 ? (
        <div style={styles.empty}>
          <div style={styles.emptyText}>No activity yet</div>
        </div>
      ) : (
        recent.map((entry, i) => (
          <div
            key={`${entry.timestamp}-${i}`}
            style={styles.item}
            onClick={() => entry.linkedinUrl && window.open(entry.linkedinUrl, '_blank', 'noopener,noreferrer')}
          >
            <div style={{ ...styles.avatar, background: AVATAR_COLORS[i % AVATAR_COLORS.length] }}>
              {getInitials(entry.profileName!)}
            </div>
            <div style={styles.info}>
              <div style={styles.name}>{entry.profileName}</div>
              {entry.profileHeadline && (
                <div style={styles.headline}>{entry.profileHeadline}</div>
              )}
            </div>
            <span style={styles.time}>{relativeTime(entry.timestamp)}</span>
          </div>
        ))
      )}
    </>
  );
}

const styles: Record<string, React.CSSProperties> = {
  secHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 16px 8px',
  },
  secTitle: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: 10,
    color: '#9C9C93',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.08em',
  },
  secAction: {
    fontFamily: "'Fraunces', serif",
    fontSize: '11.5px',
    fontWeight: 500,
    color: '#A87AD0',
    cursor: 'pointer',
    border: 'none',
    background: 'none',
    padding: '2px 0',
  },
  item: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '8px 16px',
    transition: 'background 75ms',
    cursor: 'pointer',
  },
  avatar: {
    width: 28,
    height: 28,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 10,
    fontWeight: 600,
    color: '#6B6B63',
    flexShrink: 0,
  },
  info: {
    flex: 1,
    minWidth: 0,
  },
  name: {
    fontWeight: 500,
    fontSize: '12.5px',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  headline: {
    fontWeight: 400,
    fontSize: 11,
    color: '#9C9C93',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  time: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: 10,
    color: '#9C9C93',
    flexShrink: 0,
  },
  empty: {
    padding: '16px',
    textAlign: 'center' as const,
  },
  emptyText: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: 11,
    color: '#9C9C93',
  },
};
