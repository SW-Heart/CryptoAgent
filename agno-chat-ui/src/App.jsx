import React, { useCallback, useState, useEffect } from 'react';
import { 
  ChevronRight, Cpu
} from 'lucide-react';
import { useAuth, AuthProvider } from './context/AuthContext';
import { useTranslation } from 'react-i18next';
import AuthModal from './components/AuthModal';
import UserMenu from './components/UserMenu';
import SettingsModal from './components/SettingsModal';
import ExecutionPage from './pages/ExecutionPage';
import { getJson } from './services/apiClient';
import './i18n';

import InteractiveBackground from './components/InteractiveBackground';
import Sidebar from './components/sidebar/Sidebar';
import LandingPage from './pages/LandingPage';
import StrategiesPage from './pages/StrategiesPage';
import SettingsPage from './pages/SettingsPage';
import MarketPage from './pages/MarketPage';

function AppContent() {
  const { user, signOut } = useAuth();
  const { t } = useTranslation();
  
  const [activeTab, setActiveTab] = useState('dashboard');
  const [collapsed, setCollapsed] = useState(false);
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [llmConfig, setLlmConfig] = useState(null);
  
  const userId = user?.id;

  const refreshWorkspaceStatus = useCallback(async () => {
    if (!userId) {
      setLlmConfig(null);
      return;
    }
    try {
      const nextLlmConfig = await getJson(`/api/strategy/llm-config?user_id=${userId}`);
      setLlmConfig(nextLlmConfig);
    } catch (error) {
      console.error('Workspace status fetch error:', error);
    }
  }, [userId]);

  useEffect(() => {
    if (userId) refreshWorkspaceStatus();
  }, [refreshWorkspaceStatus, userId]);

  const [visitedTabs, setVisitedTabs] = useState({ [activeTab]: true });

  useEffect(() => {
    setVisitedTabs(prev => ({ ...prev, [activeTab]: true }));
  }, [activeTab]);

  // Render proper page based on activeTab, using "keep-alive" via display:none to prevent iframe/state destruction
  const renderActivePage = () => {
    if (!user) return <LandingPage onStart={() => setShowAuthModal(true)} />;
    
    return (
      <div className="h-full w-full relative">
        <div className="absolute inset-0" style={{ display: activeTab === 'dashboard' ? 'block' : 'none' }}>
          <ExecutionPage userId={userId} onOpenSettings={(tab) => setActiveTab(tab === 'strategies' ? 'strategies' : 'settings')} />
        </div>
        
        {visitedTabs['strategies'] && (
          <div className="absolute inset-0" style={{ display: activeTab === 'strategies' ? 'block' : 'none' }}>
            <StrategiesPage profiles={[]} userId={userId} onRefresh={refreshWorkspaceStatus} />
          </div>
        )}

        {visitedTabs['market'] && (
          <div className="absolute inset-0" style={{ display: activeTab === 'market' ? 'block' : 'none' }}>
            <MarketPage />
          </div>
        )}

        {visitedTabs['settings'] && (
          <div className="absolute inset-0" style={{ display: activeTab === 'settings' ? 'block' : 'none' }}>
            <SettingsPage userId={userId} onConfigUpdated={refreshWorkspaceStatus} />
          </div>
        )}
      </div>
    );
  };

    return (
    <div className={`flex h-screen overflow-hidden font-sans relative selection:bg-emerald-500/30 text-slate-100 ${
      !user ? 'bg-transparent' : 'bg-gradient-to-br from-[#050709] via-[#070b0e] to-[#0a1015]'
    }`}>
      {/* 仅在首页/未登录态启动极其猛烈的 3D 量子粒子内核阵列 */}
      {!user && <InteractiveBackground />}
      
      {user && (
        <Sidebar 
          activeTab={activeTab}
          onTabChange={setActiveTab}
          user={user}
          onSignOut={signOut}
          llmConfig={llmConfig}
          collapsed={collapsed}
          setCollapsed={setCollapsed}
        />
      )}

      <div className="flex-1 flex flex-col min-w-0 relative">
        <main className={`flex-1 overflow-hidden relative transition-all duration-300 ${user ? 'p-6' : ''}`}>
           {renderActivePage()}
        </main>
      </div>

      <AuthModal isOpen={showAuthModal} onClose={() => setShowAuthModal(false)} />
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
