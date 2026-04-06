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

  // Render proper page based on activeTab
  const renderActivePage = () => {
    if (!user) return <LandingPage onStart={() => setShowAuthModal(true)} />;
    
    switch (activeTab) {
      case 'dashboard':
        return <ExecutionPage userId={userId} onOpenSettings={(tab) => setActiveTab(tab === 'strategies' ? 'strategies' : 'settings')} />;
      case 'strategies':
        return <StrategiesPage profiles={[]} userId={userId} onRefresh={refreshWorkspaceStatus} />;
      case 'settings':
        return <SettingsPage userId={userId} onConfigUpdated={refreshWorkspaceStatus} />;
      default:
        return <ExecutionPage userId={userId} onOpenSettings={setActiveTab} />;
    }
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
