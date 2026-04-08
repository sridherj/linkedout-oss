// SPDX-License-Identifier: Apache-2.0
import { useState, useMemo } from 'react';
import type { LogEntry, LogAction } from '../../../lib/log';

type FilterType = 'all' | 'saved' | 'skipped' | 'errors';

interface ActivityLogProps {
  entries: LogEntry[];
}

const FILTER_ACTIONS: Record<FilterType, LogAction[] | null> = {
  all: null,
  saved: ['saved', 'updated'],
  skipped: ['skipped'],
  errors: ['error', 'rate_limited'],
};

const ICON_CONFIG: Record<string, { icon: string; bg: string; color: string }> = {
  saved:        { icon: '\u2705', bg: '#E8F5E9', color: '#16A34A' },
  updated:      { icon: '\uD83D\uDD04', bg: '#E0F2FE', color: '#2563EB' },
  skipped:      { icon: '\u23ED', bg: '#F6F2F8', color: '#9C9C93' },
  rate_limited: { icon: '\u23F8', bg: '#FFF3E0', color: '#D97706' },
  error:        { icon: '\u26A0', bg: '#FEE2E2', color: '#DC2626' },
  best_hop:     { icon: '\uD83D\uDD0D', bg: '#EDE0F2', color: '#8558AC' },
  fetched:      { icon: '\u2705', bg: '#E8F5E9', color: '#16A34A' },
};

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

function countByCategory(entries: LogEntry[]) {
  let saved = 0, skipped = 0, errors = 0;
  for (const e of entries) {
    if (e.action === 'saved' || e.action === 'updated') saved++;
    else if (e.action === 'skipped') skipped++;
    else if (e.action === 'error' || e.action === 'rate_limited') errors++;
  }
  return { saved, skipped, errors };
}

export default function ActivityLog({ entries }: ActivityLogProps) {
  const [filter, setFilter] = useState<FilterType>('all');

  const filtered = useMemo(() => {
    const actions = FILTER_ACTIONS[filter];
    if (!actions) return entries;
    return entries.filter((e) => actions.includes(e.action));
  }, [entries, filter]);

  const counts = useMemo(() => countByCategory(entries), [entries]);

  const handleEntryClick = (url?: string) => {
    if (url) {
      window.open(url, '_blank', 'noopener,noreferrer');
    }
  };

  return (
    <>
      {/* Summary bar */}
      <div style={styles.summary}>
        <span style={styles.stat}>
          <span style={{ ...styles.statNum, color: '#16A34A' }}>{counts.saved}</span>
          <span style={styles.statLabel}> saved</span>
        </span>
        <span style={styles.sep} />
        <span style={styles.stat}>
          <span style={{ ...styles.statNum, color: '#6B6B63' }}>{counts.skipped}</span>
          <span style={styles.statLabel}> skipped</span>
        </span>
        <span style={styles.sep} />
        <span style={styles.stat}>
          <span style={{ ...styles.statNum, color: '#DC2626' }}>{counts.errors}</span>
          <span style={styles.statLabel}> {counts.errors === 1 ? 'error' : 'errors'}</span>
        </span>
      </div>

      {/* Filter chips */}
      <div style={styles.chips}>
        {(['all', 'saved', 'skipped', 'errors'] as FilterType[]).map((f) => (
          <button
            key={f}
            style={{ ...styles.chip, ...(filter === f ? styles.chipActive : {}) }}
            onClick={() => setFilter(f)}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Entries */}
      {filtered.length === 0 ? (
        <div style={styles.empty}>
          <div style={styles.emptyText}>No activity yet</div>
        </div>
      ) : (
        filtered.map((entry, i) => {
          const cfg = ICON_CONFIG[entry.action] ?? ICON_CONFIG.saved;
          const who = entry.profileName
            ? entry.profileHeadline
              ? `${entry.profileName} \u00B7 ${entry.profileHeadline}`
              : entry.profileName
            : entry.linkedinUrl ?? 'Unknown';

          return (
            <div
              key={`${entry.timestamp}-${i}`}
              style={styles.entry}
              onClick={() => handleEntryClick(entry.linkedinUrl)}
            >
              <span style={styles.time}>{formatTime(entry.timestamp)}</span>
              <div style={{ ...styles.icon, background: cfg.bg, color: cfg.color }}>
                {cfg.icon}
              </div>
              <div style={styles.content}>
                <div style={styles.who}>{who}</div>
                {entry.reason && <div style={styles.reason}>{entry.reason}</div>}
              </div>
            </div>
          );
        })
      )}
    </>
  );
}

const styles: Record<string, React.CSSProperties> = {
  summary: {
    padding: '10px 16px',
    background: '#F6F2F8',
    display: 'flex',
    gap: 6,
    flexWrap: 'wrap',
    alignItems: 'center',
    position: 'sticky',
    top: 0,
    zIndex: 1,
  },
  stat: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: '10.5px',
    display: 'flex',
    alignItems: 'center',
    gap: 4,
  },
  statNum: {
    fontWeight: 500,
  },
  statLabel: {
    color: '#9C9C93',
  },
  sep: {
    width: 1,
    height: 12,
    background: '#E5E3DD',
  },
  chips: {
    display: 'flex',
    gap: 4,
    padding: '6px 16px 8px',
  },
  chip: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: '9.5px',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.04em',
    padding: '3px 10px',
    borderRadius: 9999,
    border: '1px solid #E5E3DD',
    background: '#FFFFFF',
    color: '#9C9C93',
    cursor: 'pointer',
    transition: 'all 75ms',
  },
  chipActive: {
    background: '#F5EFFC',
    borderColor: '#A87AD0',
    color: '#8558AC',
  },
  entry: {
    display: 'flex',
    gap: 10,
    padding: '8px 16px',
    alignItems: 'flex-start',
    cursor: 'pointer',
    transition: 'background 75ms',
  },
  time: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: 10,
    color: '#9C9C93',
    width: 52,
    flexShrink: 0,
    paddingTop: 1,
  },
  icon: {
    width: 20,
    height: 20,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 10,
    flexShrink: 0,
    marginTop: 1,
  },
  content: {
    flex: 1,
    minWidth: 0,
  },
  who: {
    fontSize: 12,
    fontWeight: 500,
    color: '#1B1B18',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  reason: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: 10,
    color: '#9C9C93',
    marginTop: 1,
  },
  empty: {
    padding: '32px 24px',
    textAlign: 'center' as const,
  },
  emptyText: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: 11,
    color: '#9C9C93',
  },
};
