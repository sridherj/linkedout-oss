// SPDX-License-Identifier: Apache-2.0
import { useState, useEffect, useCallback } from 'react';
import { getConfig, saveConfig, type ExtensionConfig, type EnrichmentMode } from '../../lib/config';

type ConnectionStatus = 'idle' | 'testing' | 'success' | 'error';

interface ConnectionResult {
  status: ConnectionStatus;
  message?: string;
}

export default function App() {
  const [config, setConfig] = useState<ExtensionConfig | null>(null);
  const [saved, setSaved] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [connection, setConnection] = useState<ConnectionResult>({ status: 'idle' });

  useEffect(() => {
    getConfig().then(setConfig);
  }, []);

  const handleSave = useCallback(async () => {
    if (!config) return;
    await saveConfig({
      backendUrl: config.backendUrl,
      stalenessDays: config.stalenessDays,
      hourlyLimit: config.hourlyLimit,
      dailyLimit: config.dailyLimit,
      tenantId: config.tenantId,
      buId: config.buId,
      userId: config.userId,
      enrichmentMode: config.enrichmentMode,
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }, [config]);

  const handleTestConnection = useCallback(async () => {
    if (!config) return;
    setConnection({ status: 'testing' });
    try {
      const res = await fetch(`${config.backendUrl}/health`, { signal: AbortSignal.timeout(5000) });
      if (!res.ok) {
        setConnection({ status: 'error', message: `Backend returned ${res.status}` });
        return;
      }
      const data = await res.json();
      const version = data.version ?? 'unknown';
      setConnection({ status: 'success', message: `Connected to LinkedOut backend v${version}` });
    } catch (err) {
      const message = err instanceof TypeError
        ? 'Cannot reach backend. Is it running? Start with: linkedout start-backend'
        : String(err);
      setConnection({ status: 'error', message });
    }
  }, [config]);

  const update = <K extends keyof ExtensionConfig>(key: K, value: ExtensionConfig[K]) => {
    setConfig((prev) => prev ? { ...prev, [key]: value } : prev);
    setSaved(false);
    setConnection({ status: 'idle' });
  };

  if (!config) return <div style={styles.container}><p>Loading...</p></div>;

  return (
    <div style={styles.container}>
      <h1 style={styles.title}>LinkedOut Settings</h1>

      <section style={styles.section}>
        <label style={styles.label}>
          Backend URL
          <input
            type="text"
            value={config.backendUrl}
            onChange={(e) => update('backendUrl', e.target.value)}
            style={styles.input}
            placeholder="http://localhost:8001"
          />
        </label>

        <button
          onClick={handleTestConnection}
          disabled={connection.status === 'testing'}
          style={styles.testButton}
        >
          {connection.status === 'testing' ? 'Testing...' : 'Test Connection'}
        </button>

        {connection.status === 'success' && (
          <div style={styles.connectionSuccess}>
            <span style={styles.checkMark}>&#10003;</span> {connection.message}
          </div>
        )}
        {connection.status === 'error' && (
          <div style={styles.connectionError}>
            <span style={styles.xMark}>&#10007;</span> {connection.message}
          </div>
        )}
      </section>

      <section style={styles.section}>
        <h2 style={styles.sectionTitle}>Rate Limits</h2>

        <label style={styles.label}>
          Staleness threshold (days)
          <input
            type="number"
            min={1}
            value={config.stalenessDays}
            onChange={(e) => update('stalenessDays', parseInt(e.target.value, 10) || 30)}
            style={styles.input}
          />
        </label>

        <label style={styles.label}>
          Hourly rate limit
          <input
            type="number"
            min={1}
            value={config.hourlyLimit}
            onChange={(e) => update('hourlyLimit', parseInt(e.target.value, 10) || 30)}
            style={styles.input}
          />
        </label>

        <label style={styles.label}>
          Daily rate limit
          <input
            type="number"
            min={1}
            value={config.dailyLimit}
            onChange={(e) => update('dailyLimit', parseInt(e.target.value, 10) || 150)}
            style={styles.input}
          />
        </label>
      </section>

      <section style={styles.section}>
        <h2 style={styles.sectionTitle}>Enrichment Mode</h2>
        <div style={styles.toggleRow}>
          <span style={styles.toggleLabel}>
            {config.enrichmentMode === 'auto' ? 'Auto' : 'Manual'}
          </span>
          <button
            onClick={() => update('enrichmentMode', config.enrichmentMode === 'manual' ? 'auto' : 'manual')}
            style={{
              ...styles.toggle,
              backgroundColor: config.enrichmentMode === 'auto' ? '#4A7C59' : '#ccc',
            }}
            role="switch"
            aria-checked={config.enrichmentMode === 'auto'}
          >
            <span
              style={{
                ...styles.toggleKnob,
                transform: config.enrichmentMode === 'auto' ? 'translateX(20px)' : 'translateX(0)',
              }}
            />
          </button>
        </div>
        <p style={styles.hint}>
          Manual: click Fetch on each profile. Auto: profiles are saved automatically when you visit them.
        </p>
      </section>

      <section style={styles.section}>
        <button
          onClick={() => setAdvancedOpen(!advancedOpen)}
          style={styles.advancedToggle}
        >
          {advancedOpen ? '▾' : '▸'} Advanced Settings
        </button>

        {advancedOpen && (
          <div style={styles.advancedContent}>
            <label style={styles.label}>
              Tenant ID
              <input
                type="text"
                value={config.tenantId}
                onChange={(e) => update('tenantId', e.target.value)}
                style={styles.input}
              />
            </label>

            <label style={styles.label}>
              BU ID
              <input
                type="text"
                value={config.buId}
                onChange={(e) => update('buId', e.target.value)}
                style={styles.input}
              />
            </label>

            <label style={styles.label}>
              User ID
              <input
                type="text"
                value={config.userId}
                onChange={(e) => update('userId', e.target.value)}
                style={styles.input}
              />
            </label>
          </div>
        )}
      </section>

      <div style={styles.footer}>
        <button onClick={handleSave} style={styles.saveButton}>
          {saved ? 'Saved!' : 'Save Settings'}
        </button>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: 520,
    margin: '0 auto',
    padding: '32px 24px',
  },
  title: {
    fontSize: 24,
    fontWeight: 600,
    marginBottom: 24,
  },
  section: {
    marginBottom: 24,
    paddingBottom: 24,
    borderBottom: '1px solid #E8E5E0',
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: 600,
    marginBottom: 12,
  },
  label: {
    display: 'block',
    fontSize: 14,
    fontWeight: 500,
    marginBottom: 12,
    color: '#1B1B18',
  },
  input: {
    display: 'block',
    width: '100%',
    marginTop: 4,
    padding: '8px 10px',
    fontSize: 14,
    fontFamily: "'Fragment Mono', monospace",
    border: '1px solid #D1CCC4',
    borderRadius: 6,
    backgroundColor: '#fff',
    color: '#1B1B18',
  },
  testButton: {
    marginTop: 8,
    padding: '8px 16px',
    fontSize: 13,
    fontFamily: "'Fraunces', Georgia, serif",
    fontWeight: 500,
    border: '1px solid #D1CCC4',
    borderRadius: 6,
    backgroundColor: '#fff',
    color: '#1B1B18',
    cursor: 'pointer',
  },
  connectionSuccess: {
    marginTop: 8,
    padding: '8px 12px',
    fontSize: 13,
    borderRadius: 6,
    backgroundColor: '#E8F5E9',
    color: '#2E7D32',
  },
  connectionError: {
    marginTop: 8,
    padding: '8px 12px',
    fontSize: 13,
    borderRadius: 6,
    backgroundColor: '#FFEBEE',
    color: '#C62828',
  },
  checkMark: {
    fontWeight: 700,
    marginRight: 6,
  },
  xMark: {
    fontWeight: 700,
    marginRight: 6,
  },
  toggleRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
  },
  toggleLabel: {
    fontSize: 14,
    fontWeight: 500,
    minWidth: 60,
  },
  toggle: {
    position: 'relative' as const,
    width: 44,
    height: 24,
    borderRadius: 12,
    border: 'none',
    cursor: 'pointer',
    transition: 'background-color 0.2s',
    padding: 0,
  },
  toggleKnob: {
    display: 'block',
    width: 20,
    height: 20,
    borderRadius: '50%',
    backgroundColor: '#fff',
    position: 'absolute' as const,
    top: 2,
    left: 2,
    transition: 'transform 0.2s',
    boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
  },
  hint: {
    marginTop: 8,
    fontSize: 12,
    color: '#6B6760',
    lineHeight: 1.4,
  },
  advancedToggle: {
    background: 'none',
    border: 'none',
    padding: 0,
    fontSize: 14,
    fontWeight: 500,
    fontFamily: "'Fraunces', Georgia, serif",
    color: '#6B6760',
    cursor: 'pointer',
  },
  advancedContent: {
    marginTop: 12,
    paddingLeft: 16,
    borderLeft: '2px solid #E8E5E0',
  },
  footer: {
    paddingTop: 8,
  },
  saveButton: {
    padding: '10px 24px',
    fontSize: 14,
    fontFamily: "'Fraunces', Georgia, serif",
    fontWeight: 600,
    border: 'none',
    borderRadius: 8,
    backgroundColor: '#1B1B18',
    color: '#FDFBFE',
    cursor: 'pointer',
  },
};
