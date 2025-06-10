import { ReactNode, useState, useEffect } from 'react';

export interface Tab {
  id: string;
  label: string;
  icon?: string;
  content: ReactNode;
  disabled?: boolean;
  badge?: string | number;
}

interface TabSystemProps {
  tabs: Tab[];
  activeTabId?: string;
  onTabChange?: (tabId: string) => void;
  className?: string;
}

export function TabSystem({
  tabs,
  activeTabId,
  onTabChange,
  className = '',
}: TabSystemProps) {
  const [internalActiveTab, setInternalActiveTab] = useState<string>(
    activeTabId || tabs[0]?.id || ''
  );

  const currentActiveTab = activeTabId || internalActiveTab;

  useEffect(() => {
    if (activeTabId && activeTabId !== internalActiveTab) {
      setInternalActiveTab(activeTabId);
    }
  }, [activeTabId, internalActiveTab]);

  const handleTabClick = (tabId: string) => {
    const tab = tabs.find(t => t.id === tabId);
    if (tab && !tab.disabled) {
      setInternalActiveTab(tabId);
      onTabChange?.(tabId);
    }
  };

  const activeTab = tabs.find(tab => tab.id === currentActiveTab);

  return (
    <div className={`tab-system ${className}`}>
      {/* Tab Navigation */}
      <div className="tab-navigation">
        <div className="tab-list">
          {tabs.map(tab => (
            <button
              key={tab.id}
              type="button"
              className={`tab-button ${
                tab.id === currentActiveTab ? 'active' : ''
              } ${tab.disabled ? 'disabled' : ''}`}
              onClick={() => handleTabClick(tab.id)}
              disabled={tab.disabled}
              aria-selected={tab.id === currentActiveTab}
              role="tab"
            >
              {tab.icon && (
                <span className="tab-icon" aria-hidden="true">
                  {tab.icon}
                </span>
              )}
              <span className="tab-label">{tab.label}</span>
              {tab.badge && (
                <span className="tab-badge" aria-label={`${tab.badge} items`}>
                  {tab.badge}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="tab-content">
        {activeTab && (
          <div
            className="tab-panel"
            role="tabpanel"
            aria-labelledby={`tab-${activeTab.id}`}
          >
            {activeTab.content}
          </div>
        )}
      </div>
    </div>
  );
}
