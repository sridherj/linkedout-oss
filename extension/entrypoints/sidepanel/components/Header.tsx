// SPDX-License-Identifier: Apache-2.0
import { useState, useEffect } from 'react';
import { getEnrichmentMode, setEnrichmentMode, onEnrichmentModeChange, type EnrichmentMode } from '../../../lib/settings';

export default function Header() {
  const [mode, setMode] = useState<EnrichmentMode>('manual');

  useEffect(() => {
    getEnrichmentMode().then(setMode);
    return onEnrichmentModeChange(setMode);
  }, []);

  const toggleMode = () => {
    const next = mode === 'manual' ? 'auto' : 'manual';
    setEnrichmentMode(next);
  };

  const isAuto = mode === 'auto';

  return (
    <div style={styles.header}>
      <span style={styles.logo}>LinkedOut</span>
      <div style={styles.right}>
        <div style={styles.toggleGroup}>
          <span style={styles.toggleLabel}>Auto</span>
          <div
            style={{ ...styles.track, ...(isAuto ? styles.trackActive : {}) }}
            onClick={toggleMode}
          >
            <div style={{ ...styles.thumb, ...(isAuto ? styles.thumbActive : {}) }} />
          </div>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '10px 16px',
    borderBottom: '1px solid #E5E3DD',
    background: '#FFFFFF',
    flexShrink: 0,
  },
  logo: {
    fontFamily: "'Fraunces', serif",
    fontWeight: 700,
    fontSize: '15px',
    color: '#8558AC',
    letterSpacing: '-0.01em',
  },
  right: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  toggleGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  toggleLabel: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: '10px',
    color: '#9C9C93',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
  },
  track: {
    width: '32px',
    height: '18px',
    borderRadius: '9999px',
    background: '#E5E3DD',
    position: 'relative' as const,
    cursor: 'pointer',
    transition: 'background 150ms ease-out',
  },
  trackActive: {
    background: '#A87AD0',
  },
  thumb: {
    width: '14px',
    height: '14px',
    borderRadius: '50%',
    background: 'white',
    position: 'absolute' as const,
    top: '2px',
    left: '2px',
    transition: 'transform 150ms ease-out',
    boxShadow: '0 1px 2px rgba(0,0,0,0.15)',
  },
  thumbActive: {
    transform: 'translateX(14px)',
  },
};
