// SPDX-License-Identifier: Apache-2.0
import { useState, useEffect, useCallback } from 'react';
import { browser } from 'wxt/browser';
import type {
  ExtensionMessage,
  FindBestHop,
  CancelBestHop,
  SetExtractionSpeed,
  BestHopResult as BestHopResultMsg,
  BestHopThinking,
  BestHopComplete,
  BestHopError,
  MutualExtractionProgress,
  ExtractionSpeedChanged,
} from '../../../lib/messages';

type Phase = 'idle' | 'extracting' | 'analyzing' | 'done' | 'error';

interface ResultItem {
  rank: number;
  name: string;
  role: string | null;
  affinityScore: number | null;
  reasoning: string | null;
  linkedinUrl: string | null;
}

interface BestHopPanelProps {
  disabled: boolean;
  entityUrn: string | null;
  linkedinUrl: string;
  profileName: string;
}

export default function BestHopPanel({ disabled, entityUrn, linkedinUrl, profileName }: BestHopPanelProps) {
  const [phase, setPhase] = useState<Phase>('idle');
  const [extractionPage, setExtractionPage] = useState(0);
  const [extractionTotal, setExtractionTotal] = useState<number | undefined>();
  const [results, setResults] = useState<ResultItem[]>([]);
  const [matchedCount, setMatchedCount] = useState(0);
  const [unmatchedCount, setUnmatchedCount] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [errorPhase, setErrorPhase] = useState<'extraction' | 'search' | null>(null);
  const [speed, setSpeed] = useState<1 | 2 | 4 | 8>(1);
  const [thinkingMessage, setThinkingMessage] = useState<string | null>(null);

  // Listen for Best Hop messages from service worker
  useEffect(() => {
    const handler = (message: ExtensionMessage) => {
      switch (message.type) {
        case 'MUTUAL_EXTRACTION_PROGRESS':
          setPhase('extracting');
          setExtractionPage(message.page);
          if (message.total != null) setExtractionTotal(message.total);
          break;

        case 'BEST_HOP_THINKING':
          setPhase('analyzing');
          setThinkingMessage(message.message);
          break;

        case 'BEST_HOP_RESULT':
          setPhase('analyzing');
          setResults((prev) => [...prev, {
            rank: message.rank,
            name: message.name,
            role: message.role,
            affinityScore: message.affinityScore,
            reasoning: message.reasoning,
            linkedinUrl: message.linkedinUrl,
          }]);
          break;

        case 'BEST_HOP_COMPLETE':
          setPhase('done');
          setMatchedCount(message.matched);
          setUnmatchedCount(message.unmatched);
          break;

        case 'BEST_HOP_ERROR':
          setPhase('error');
          setErrorMessage(message.message);
          setErrorPhase(message.phase);
          break;

        case 'EXTRACTION_SPEED_CHANGED':
          setSpeed(message.multiplier);
          break;
      }
    };

    browser.runtime.onMessage.addListener(handler);
    return () => browser.runtime.onMessage.removeListener(handler);
  }, []);

  const handleTrigger = useCallback(() => {
    if (disabled || !entityUrn) return;
    // Reset state
    setPhase('extracting');
    setExtractionPage(0);
    setExtractionTotal(undefined);
    setResults([]);
    setMatchedCount(0);
    setUnmatchedCount(0);
    setErrorMessage(null);
    setErrorPhase(null);
    setSpeed(1);
    setThinkingMessage(null);

    const msg: FindBestHop = {
      type: 'FIND_BEST_HOP',
      entityUrn,
      linkedinUrl,
      profileName,
    };
    browser.runtime.sendMessage(msg);
  }, [disabled, entityUrn, linkedinUrl, profileName]);

  const handleCancel = useCallback(() => {
    const msg: CancelBestHop = { type: 'CANCEL_BEST_HOP' };
    browser.runtime.sendMessage(msg);
    setPhase('done');
  }, []);

  const handleSpeedCycle = useCallback(() => {
    const next = { 1: 2, 2: 4, 4: 8, 8: 1 } as const;
    const newSpeed = next[speed];
    setSpeed(newSpeed);
    const msg: SetExtractionSpeed = { type: 'SET_EXTRACTION_SPEED', multiplier: newSpeed };
    browser.runtime.sendMessage(msg);
  }, [speed]);

  const handleRetry = useCallback(() => {
    handleTrigger();
  }, [handleTrigger]);

  const handleNewSearch = useCallback(() => {
    setPhase('idle');
    setResults([]);
    setMatchedCount(0);
    setUnmatchedCount(0);
    setErrorMessage(null);
    setErrorPhase(null);
    setThinkingMessage(null);
  }, []);

  // ── Render ──

  const isActive = phase === 'extracting' || phase === 'analyzing';

  return (
    <>
      <div style={styles.secHeader}>
        <span style={styles.secTitle}>
          {phase === 'done' && results.length > 0
            ? `Best Hop \u00B7 ${results.length} path${results.length !== 1 ? 's' : ''}`
            : 'Best Hop'}
        </span>
        {phase === 'done' && results.length > 0 && (
          <button style={styles.secAction} onClick={handleNewSearch}>New search</button>
        )}
      </div>

      {/* Idle: trigger card */}
      {phase === 'idle' && (
        <div
          style={{
            ...styles.trigger,
            ...(disabled ? styles.triggerDisabled : {}),
          }}
          onClick={handleTrigger}
        >
          <div>
            <div style={styles.triggerText}>Find intro path</div>
            <div style={styles.triggerSub}>via mutual connections</div>
          </div>
          <span style={styles.arrow}>&rarr;</span>
        </div>
      )}

      {/* Phase 1: Extracting mutual connections */}
      {phase === 'extracting' && (
        <div style={styles.progress}>
          <div style={styles.progressHeader}>
            <div style={styles.progressLabel}>
              Extracting mutuals{extractionPage > 0 ? ` \u00B7 page ${extractionPage}` : ''}
              {extractionTotal != null ? `/${extractionTotal}` : ''}
            </div>
            <button style={styles.speedChip} onClick={handleSpeedCycle} title="Cycle extraction speed">
              {speed}x
            </button>
          </div>
          <div style={styles.bar}>
            <div
              style={{
                ...styles.fill,
                width: extractionTotal
                  ? `${Math.min(100, (extractionPage / extractionTotal) * 100)}%`
                  : '60%',
              }}
            />
          </div>
          <button style={styles.cancel} onClick={handleCancel}>Cancel</button>
        </div>
      )}

      {/* Phase 2: Analyzing (SSE streaming) */}
      {phase === 'analyzing' && (
        <div style={styles.progress}>
          <div style={styles.progressLabel}>{thinkingMessage || 'Analyzing introduction paths...'}</div>
          <div style={styles.bar}>
            <div style={{ ...styles.fill, width: '100%' }} />
          </div>
          <button style={styles.cancel} onClick={handleCancel}>Cancel</button>
        </div>
      )}

      {/* Error state */}
      {phase === 'error' && (
        <div style={styles.errorBanner}>
          <div style={styles.errorText}>{errorMessage}</div>
          <button style={styles.retryBtn} onClick={handleRetry}>Retry</button>
        </div>
      )}

      {/* Matched/unmatched summary */}
      {phase === 'done' && results.length > 0 && (matchedCount > 0 || unmatchedCount > 0) && (
        <div style={styles.matchSummary}>
          {matchedCount} found{unmatchedCount > 0 ? `, ${unmatchedCount} not in network` : ''}
        </div>
      )}

      {/* Done with zero results */}
      {phase === 'done' && results.length === 0 && (
        <div style={styles.empty}>
          <div style={styles.emptyText}>No mutual connections found</div>
          <button style={styles.retryBtn} onClick={handleNewSearch}>Try again</button>
        </div>
      )}

      {/* Result cards (visible during analyzing + done) */}
      {results.map((r) => (
        <div key={r.rank} style={styles.result}>
          <div style={styles.resultHeader}>
            <span style={styles.rank}>{r.rank}</span>
            <div style={styles.resultInfo}>
              <div style={styles.resultName}>{r.name}</div>
              {r.role && <div style={styles.resultRole}>{r.role}</div>}
            </div>
            {r.affinityScore != null && (
              <span style={styles.affinity}>{r.affinityScore.toFixed(2)}</span>
            )}
          </div>
          {r.reasoning && (
            <div style={styles.reason}>
              <span style={styles.reasonLabel}>Why</span>
              {r.reasoning}
            </div>
          )}
          {r.linkedinUrl && (
            <a
              href={r.linkedinUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={styles.profileLink}
            >
              View profile &rarr;
            </a>
          )}
        </div>
      ))}
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
  matchSummary: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: 10,
    color: '#9C9C93',
    padding: '0 16px 8px',
  },
  secAction: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: 10,
    color: '#A87AD0',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    padding: 0,
  },
  trigger: {
    margin: '0 16px 12px',
    padding: '12px 14px',
    borderRadius: 10,
    background: '#EDE0F2',
    border: '1px solid #E2D8EE',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    cursor: 'pointer',
    transition: 'border-color 150ms, background 150ms',
  },
  triggerDisabled: {
    opacity: 0.5,
    cursor: 'not-allowed',
  },
  triggerText: {
    fontWeight: 500,
    fontSize: 13,
    color: '#8558AC',
  },
  triggerSub: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: 10,
    color: '#9C9C93',
    marginTop: 2,
  },
  arrow: {
    color: '#A87AD0',
    fontSize: 16,
  },
  progress: {
    margin: '0 16px 12px',
    padding: '12px 14px',
    borderRadius: 10,
    background: '#F5EFFC',
    border: '1px solid #E2D8EE',
  },
  progressHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 6,
  },
  progressLabel: {
    fontSize: 12.5,
    fontWeight: 500,
    color: '#8558AC',
  },
  speedChip: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: 10,
    fontWeight: 600,
    color: '#8558AC',
    background: '#EDE0F2',
    border: '1px solid #E2D8EE',
    borderRadius: 9999,
    padding: '2px 8px',
    cursor: 'pointer',
    flexShrink: 0,
    transition: 'background 150ms',
  },
  bar: {
    height: 3,
    borderRadius: 2,
    background: '#E2D8EE',
    overflow: 'hidden',
  },
  fill: {
    height: '100%',
    borderRadius: 2,
    background: '#A87AD0',
    animation: 'pulse 1.5s ease-in-out infinite',
  },
  cancel: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: 10,
    color: '#9C9C93',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    marginTop: 6,
    padding: 0,
  },
  errorBanner: {
    margin: '0 16px 12px',
    padding: '10px 14px',
    borderRadius: 10,
    background: '#FEE2E2',
    border: '1px solid #FECACA',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  errorText: {
    fontSize: 12,
    color: '#DC2626',
    flex: 1,
  },
  retryBtn: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: 10,
    color: '#A87AD0',
    background: 'none',
    border: '1px solid #E2D8EE',
    borderRadius: 6,
    padding: '4px 10px',
    cursor: 'pointer',
    flexShrink: 0,
  },
  empty: {
    margin: '0 16px 12px',
    padding: '16px',
    textAlign: 'center' as const,
  },
  emptyText: {
    fontSize: 12,
    color: '#9C9C93',
    marginBottom: 8,
  },
  result: {
    margin: '0 16px 8px',
    padding: 12,
    borderRadius: 10,
    background: '#FFFFFF',
    border: '1px solid #E5E3DD',
    transition: 'border-color 150ms',
  },
  resultHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  rank: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: 10,
    color: '#A87AD0',
    fontWeight: 500,
    width: 18,
    height: 18,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 9999,
    background: '#F5EFFC',
    flexShrink: 0,
  },
  resultInfo: {
    flex: 1,
    minWidth: 0,
  },
  resultName: {
    fontWeight: 600,
    fontSize: 13,
  },
  resultRole: {
    fontWeight: 400,
    fontSize: 11,
    color: '#6B6B63',
  },
  affinity: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: 10,
    padding: '2px 6px',
    borderRadius: 9999,
    background: '#EDE0F2',
    color: '#8558AC',
    marginLeft: 'auto',
    flexShrink: 0,
  },
  reason: {
    fontSize: 12,
    lineHeight: 1.55,
    color: '#1B1B18',
    marginTop: 8,
    padding: '8px 10px',
    borderRadius: 6,
    background: '#F5EFFC',
    border: '1px solid #E2D8EE',
  },
  reasonLabel: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: 9,
    fontWeight: 500,
    textTransform: 'uppercase' as const,
    letterSpacing: 0.5,
    color: '#8558AC',
    display: 'block',
    marginBottom: 3,
  },
  profileLink: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: 10,
    color: '#A87AD0',
    textDecoration: 'none',
    marginTop: 4,
    display: 'inline-block',
  },
};
