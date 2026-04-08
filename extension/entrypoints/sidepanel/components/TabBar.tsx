// SPDX-License-Identifier: Apache-2.0
interface TabBarProps {
  activeTab: 'profile' | 'activity';
  onTabChange: (tab: 'profile' | 'activity') => void;
  unreadCount: number;
}

export default function TabBar({ activeTab, onTabChange, unreadCount }: TabBarProps) {
  return (
    <div style={styles.tabs}>
      <button
        style={{ ...styles.tab, ...(activeTab === 'profile' ? styles.tabActive : {}) }}
        onClick={() => onTabChange('profile')}
      >
        Profile
      </button>
      <button
        style={{ ...styles.tab, ...(activeTab === 'activity' ? styles.tabActive : {}) }}
        onClick={() => onTabChange('activity')}
      >
        Activity
        {unreadCount > 0 && <span style={styles.badge}>{unreadCount}</span>}
      </button>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  tabs: {
    display: 'flex',
    borderBottom: '1px solid #E5E3DD',
    background: '#FFFFFF',
    flexShrink: 0,
  },
  tab: {
    flex: 1,
    padding: '8px 0',
    fontFamily: "'Fragment Mono', monospace",
    fontSize: '10.5px',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.06em',
    color: '#9C9C93',
    textAlign: 'center' as const,
    border: 'none',
    background: 'none',
    cursor: 'pointer',
    borderBottom: '2px solid transparent',
    transition: 'color 150ms, border-color 150ms',
  },
  tabActive: {
    color: '#8558AC',
    borderBottomColor: '#A87AD0',
  },
  badge: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: '16px',
    height: '16px',
    padding: '0 4px',
    borderRadius: '9999px',
    background: '#F5EFFC',
    color: '#8558AC',
    fontSize: '9px',
    fontWeight: 500,
    marginLeft: '4px',
  },
};
