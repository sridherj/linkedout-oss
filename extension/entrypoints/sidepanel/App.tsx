// SPDX-License-Identifier: Apache-2.0
import { useState, useEffect, useCallback } from 'react';
import { browser } from 'wxt/browser';
import Header from './components/Header';
import TabBar from './components/TabBar';
import ProfileCard from './components/ProfileCard';
import RateLimitBar from './components/RateLimitBar';
import FetchButton from './components/FetchButton';
import StatusBanner from './components/StatusBanner';
import OfflineBar from './components/OfflineBar';
import ChallengeBanner from './components/ChallengeBanner';
import Skeleton from './components/Skeleton';
import BestHopPanel from './components/BestHopPanel';
import RecentActivity from './components/RecentActivity';
import ActivityLog from './components/ActivityLog';
import { getEnrichmentMode, onEnrichmentModeChange, type EnrichmentMode } from '../../lib/settings';
import { getLogs, type LogEntry } from '../../lib/log';
import type { ProfileStatusUpdate, ProfileDisplayData, ProfileBadgeStatus, RateLimitUpdate, ExtensionMessage } from '../../lib/messages';

type ActiveTab = 'profile' | 'activity';

interface BannerState {
  message: string;
  variant: 'error' | 'warning';
}

export default function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('profile');
  const [profileData, setProfileData] = useState<ProfileDisplayData | null>(null);
  const [badgeStatus, setBadgeStatus] = useState<ProfileBadgeStatus>('loading');
  const [staleDays, setStaleDays] = useState<number | undefined>();
  const [rateLimits, setRateLimits] = useState({ hourly: { used: 0, limit: 30 }, daily: { used: 0, limit: 150 } });
  const [isFetching, setIsFetching] = useState(false);
  const [isOnProfile, setIsOnProfile] = useState(false);
  const [enrichmentMode, setEnrichmentMode] = useState<EnrichmentMode>('manual');
  const [banner, setBanner] = useState<BannerState | null>(null);
  const [logEntries, setLogEntries] = useState<LogEntry[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isOffline, setIsOffline] = useState(false);
  const [challengeActive, setChallengeActive] = useState(false);
  const [challengeMessage, setChallengeMessage] = useState<string | undefined>();

  // Load initial logs from storage
  useEffect(() => {
    getLogs().then(setLogEntries);
  }, []);

  // Connect to service worker on mount (triggers "I'm looking" signal)
  useEffect(() => {
    const port = browser.runtime.connect({ name: 'sidepanel' });
    return () => port.disconnect();
  }, []);

  // Load initial enrichment mode and subscribe to changes
  useEffect(() => {
    getEnrichmentMode().then(setEnrichmentMode);
    return onEnrichmentModeChange(setEnrichmentMode);
  }, []);

  // Listen for push-based messages from service worker
  useEffect(() => {
    const handler = (message: ExtensionMessage) => {
      switch (message.type) {
        case 'PROFILE_STATUS_UPDATE':
          handleProfileStatus(message);
          break;
        case 'RATE_LIMIT_UPDATE':
          handleRateLimitUpdate(message);
          break;
        case 'LOG_UPDATED':
          handleLogUpdated(message.entry as LogEntry);
          break;
        case 'OFFLINE_STATUS_UPDATE':
          setIsOffline(message.isOffline);
          break;
        case 'CHALLENGE_STATUS_UPDATE':
          setChallengeActive(message.isActive);
          setChallengeMessage(message.message);
          break;
      }
    };
    browser.runtime.onMessage.addListener(handler);
    return () => browser.runtime.onMessage.removeListener(handler);
  }, []);

  const handleLogUpdated = useCallback((entry: LogEntry) => {
    setLogEntries((prev) => {
      // Upsert: remove existing entry for same profile, prepend new one
      const filtered = entry.linkedinUrl
        ? prev.filter((e) => e.linkedinUrl !== entry.linkedinUrl)
        : prev;
      return [entry, ...filtered];
    });
    // Increment unread if not currently on Activity tab
    setUnreadCount((prev) => prev + 1);
  }, []);

  const handleProfileStatus = useCallback((msg: ProfileStatusUpdate) => {
    const { status, badgeStatus: badge, profileData: data, staleDays: days, errorMessage, linkedinUrl } = msg;

    // Track whether we're on a profile page
    if (linkedinUrl) {
      setIsOnProfile(true);
    }

    // Update profile data if provided
    if (data) {
      setProfileData(data);
    }

    // Update staleness info
    if (days != null) {
      setStaleDays(days);
    }

    // When fetching starts for a new URL, clear old profile data to show skeleton
    if (status === 'fetching' && linkedinUrl && !data) {
      setProfileData(null);
      setStaleDays(undefined);
      setBanner(null);
    }

    // Map status to fetching state
    // 'ready' means Voyager data received, profile card shown — NOT fetching
    setIsFetching(status === 'fetching' || status === 'saving');

    // Map to badge status
    if (badge) {
      setBadgeStatus(badge);
    } else {
      // Fallback mapping for backwards compatibility
      switch (status) {
        case 'idle':
          if (!data && !linkedinUrl) {
            setIsOnProfile(false);
            setBadgeStatus('loading');
          }
          break;
        case 'ready':
          setBadgeStatus('not_saved');
          break;
        case 'fetching':
        case 'saving':
          setBadgeStatus('loading');
          break;
        case 'done':
          setBadgeStatus('saved_today');
          break;
        case 'skipped':
          setBadgeStatus('up_to_date');
          break;
        case 'error':
          setBadgeStatus('save_failed');
          break;
      }
    }

    // Show error/warning banners
    if (status === 'error' && errorMessage) {
      const isRateLimit = badge === 'rate_limited' || errorMessage.includes('Rate limit');
      setBanner({
        message: errorMessage,
        variant: isRateLimit ? 'warning' : 'error',
      });
    } else if (status !== 'error') {
      setBanner(null);
    }
  }, []);

  const handleRateLimitUpdate = useCallback((msg: RateLimitUpdate) => {
    setRateLimits({ hourly: msg.hourly, daily: msg.daily });
  }, []);

  const handleFetch = useCallback(() => {
    browser.runtime.sendMessage({ type: 'ENRICH_PROFILE' });
  }, []);

  const handleDismissBanner = useCallback(() => setBanner(null), []);

  const handleTabChange = useCallback((tab: ActiveTab) => {
    setActiveTab(tab);
    if (tab === 'activity') {
      setUnreadCount(0);
    }
  }, []);

  const handleViewAll = useCallback(() => {
    setActiveTab('activity');
    setUnreadCount(0);
  }, []);

  const isLoading = isFetching && !profileData;

  return (
    <div style={styles.container}>
      <Header />
      <TabBar activeTab={activeTab} onTabChange={handleTabChange} unreadCount={unreadCount} />
      <OfflineBar visible={isOffline} />
      <ChallengeBanner visible={challengeActive} message={challengeMessage} />

      <div style={styles.body}>
        {activeTab === 'profile' ? (
          isOnProfile || profileData ? (
            <>
              {isLoading ? (
                <Skeleton />
              ) : profileData ? (
                <>
                  <ProfileCard profile={profileData} badgeStatus={badgeStatus} staleDays={staleDays} />
                  <RateLimitBar hourly={rateLimits.hourly} daily={rateLimits.daily} />
                  {banner && (
                    <StatusBanner
                      message={banner.message}
                      variant={banner.variant}
                      onDismiss={handleDismissBanner}
                    />
                  )}
                  <FetchButton
                    badgeStatus={badgeStatus}
                    isAutoMode={enrichmentMode === 'auto'}
                    isFetching={isFetching}
                    onFetch={handleFetch}
                  />
                  <div style={styles.divider} />
                  <BestHopPanel
                    disabled={!profileData.entityUrn}
                    entityUrn={profileData.entityUrn}
                    linkedinUrl={profileData.linkedinUrl}
                    profileName={profileData.name}
                  />
                  <div style={styles.divider} />
                  <RecentActivity entries={logEntries} onViewAll={handleViewAll} />
                </>
              ) : (
                <Skeleton />
              )}
            </>
          ) : (
            <div style={styles.empty}>
              <div style={styles.emptyIcon}>&#x1F517;</div>
              <div style={styles.emptyTitle}>Navigate to a LinkedIn profile</div>
              <div style={styles.emptyDesc}>Open a LinkedIn profile page to get started</div>
            </div>
          )
        ) : (
          <ActivityLog entries={logEntries} />
        )}
      </div>

      <div style={styles.footer}>
        <span style={styles.footerText}>LinkedOut Extension v0.1</span>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column' as const,
    minHeight: '100vh',
    background: '#FDFBFE',
  },
  body: {
    flex: 1,
    overflowY: 'auto' as const,
    paddingBottom: 4,
  },
  divider: {
    height: 1,
    background: '#E5E3DD',
    margin: '0 16px',
  },
  empty: {
    padding: '32px 24px',
    textAlign: 'center' as const,
  },
  emptyIcon: {
    fontSize: 28,
    marginBottom: 10,
    opacity: 0.4,
  },
  emptyTitle: {
    fontWeight: 600,
    fontSize: 14,
    marginBottom: 4,
  },
  emptyDesc: {
    fontWeight: 400,
    fontSize: 12,
    color: '#9C9C93',
    lineHeight: 1.5,
  },
  footer: {
    padding: '8px 16px',
    borderTop: '1px solid #E5E3DD',
    textAlign: 'center' as const,
    flexShrink: 0,
  },
  footerText: {
    fontFamily: "'Fragment Mono', monospace",
    fontSize: 9,
    color: '#9C9C93',
    letterSpacing: '0.03em',
  },
};
