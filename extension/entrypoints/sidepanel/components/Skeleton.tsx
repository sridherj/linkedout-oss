// SPDX-License-Identifier: Apache-2.0
export default function Skeleton() {
  return (
    <>
      <style>{`
        @keyframes shimmer {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>
      <div style={styles.card}>
        <div style={styles.row}>
          <div style={{ ...styles.skel, ...styles.skelAvatar }} />
          <div style={{ flex: 1 }}>
            <div style={{ ...styles.skel, ...styles.skelLine, width: '60%' }} />
            <div style={{ ...styles.skel, ...styles.skelLine, width: '80%' }} />
            <div style={{ ...styles.skel, ...styles.skelLine, width: '40%' }} />
          </div>
        </div>
      </div>
      <div style={styles.rateSection}>
        <div style={{ display: 'flex', gap: 16 }}>
          <div style={{ flex: 1 }}>
            <div style={{ ...styles.skel, ...styles.skelLine, width: '100%', height: 4 }} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ ...styles.skel, ...styles.skelLine, width: '100%', height: 4 }} />
          </div>
        </div>
      </div>
    </>
  );
}

const shimmerBg = 'linear-gradient(90deg, #F6F2F8 25%, #F5EFFC 50%, #F6F2F8 75%)';

const styles: Record<string, React.CSSProperties> = {
  card: { padding: '14px 16px 12px' },
  row: { display: 'flex', gap: 12, alignItems: 'flex-start' },
  rateSection: { padding: '10px 16px 12px' },
  skel: {
    background: shimmerBg,
    backgroundSize: '200% 100%',
    animation: 'shimmer 1.5s ease-in-out infinite',
    borderRadius: 6,
  },
  skelAvatar: {
    width: 48,
    height: 48,
    borderRadius: '50%',
    flexShrink: 0,
  },
  skelLine: {
    height: 12,
    marginBottom: 6,
  },
};
