import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
    X, User, Cpu, LogOut, Settings, Globe,
    ChevronLeft, ChevronRight, Key, Eye, EyeOff, RefreshCw,
    CheckCircle, XCircle, AlertCircle, Save, Activity
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function SettingsModal({
    isOpen,
    onClose,
    user,
    onSignOut,
    onConfigUpdated,
    defaultTab = 'account'
}) {
    const { t, i18n } = useTranslation();
    const [activeTab, setActiveTab] = useState(defaultTab);

    useEffect(() => {
        if (isOpen && defaultTab) {
            const timer = window.setTimeout(() => {
                setActiveTab(defaultTab);
            }, 0);
            return () => window.clearTimeout(timer);
        }
        return undefined;
    }, [isOpen, defaultTab]);

    if (!isOpen) return null;

    const getInitials = () => {
        if (user?.displayName) return user.displayName.charAt(0).toUpperCase();
        if (user?.email) return user.email.charAt(0).toUpperCase();
        return 'U';
    };

    const handleBackdropClick = (e) => {
        if (e.target === e.currentTarget) onClose();
    };

    const changeLanguage = (lang) => {
        i18n.changeLanguage(lang);
        localStorage.setItem('language', lang);
    };

    const getTabTitle = () => {
        switch (activeTab) {
            case 'account': return t('settings.tabs.account');
            case 'llm': return t('settings.tabs.llm');
            case 'exchange': return t('settings.tabs.exchange');
            default: return '';
        }
    };

    return (
        <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 px-4"
            onClick={handleBackdropClick}
            onKeyDown={(e) => e.key === 'Escape' && onClose()}
            tabIndex={-1}
        >
            <div className="bg-[#0a0d0f] rounded-2xl w-full max-w-3xl h-[550px] flex shadow-2xl border border-slate-700/50 overflow-hidden">
                {/* Left Sidebar */}
                <div className="w-16 sm:w-48 bg-[#0e1215] border-r border-slate-700/50 p-3 sm:p-4 flex flex-col flex-shrink-0">
                    <div className="flex items-center justify-center mb-8">
                        <img
                            src="https://ai-shot.oss-cn-hangzhou.aliyuncs.com/logo/ailogo.png"
                            alt="OG AI"
                            className="w-10 h-10 object-contain drop-shadow-md"
                        />
                    </div>

                    <nav className="flex-1 space-y-1">
                        <TabButton 
                            active={activeTab === 'account'} 
                            onClick={() => setActiveTab('account')}
                            icon={<User className="w-4 h-4" />}
                            label={t('settings.tabs.account')}
                        />
                        <TabButton 
                            active={activeTab === 'llm'} 
                            onClick={() => setActiveTab('llm')}
                            icon={<Cpu className="w-4 h-4" />}
                            label={t('settings.tabs.llm')}
                        />
                        <TabButton 
                            active={activeTab === 'exchange'} 
                            onClick={() => setActiveTab('exchange')}
                            icon={<Key className="w-4 h-4" />}
                            label={t('settings.tabs.exchange')}
                        />
                    </nav>
                </div>

                {/* Right Content */}
                <div className="flex-1 flex flex-col overflow-hidden">
                    <div className="flex items-center justify-between p-4 border-b border-slate-700/50 flex-shrink-0">
                        <h2 className="text-lg font-semibold text-white">
                            {getTabTitle()}
                        </h2>
                        <button
                            onClick={onClose}
                            className="p-1.5 rounded-lg hover:bg-slate-700/50 text-slate-400 hover:text-white transition-colors"
                        >
                            <X className="w-5 h-5" />
                        </button>
                    </div>

                    <div className="flex-1 p-6 overflow-y-auto custom-scrollbar bg-[#0d1117]">
                        <div key={activeTab} className="animate-in fade-in slide-in-from-bottom-1 duration-200 min-h-full">
                            {activeTab === 'account' ? (
                                <AccountContent
                                    user={user}
                                    getInitials={getInitials}
                                    onSignOut={onSignOut}
                                    onClose={onClose}
                                    t={t}
                                />
                            ) : activeTab === 'exchange' ? (
                                <ExchangeContent
                                    userId={user?.id}
                                    t={t}
                                />
                            ) : (
                                <LLMContent
                                    userId={user?.id}
                                    t={t}
                                    onConfigUpdated={onConfigUpdated}
                                />
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

function TabButton({ active, onClick, icon, label }) {
    return (
        <button
            onClick={onClick}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-200 border outline-none ${active
                ? 'bg-gradient-to-r from-white/10 to-transparent text-white font-medium border-white/10 shadow-lg'
                : 'text-slate-400 hover:text-white hover:bg-white/5 border-transparent'
                }`}
        >
            {icon}
            <span className="hidden sm:inline">{label}</span>
        </button>
    );
}


function AccountContent({ user, getInitials, onSignOut, onClose, t }) {
    return (
        <div className="space-y-6">
            <div className="p-4 rounded-2xl bg-white/5 border border-white/5 flex items-center justify-between">
                <div className="flex items-center gap-4">
                    {user?.avatarUrl ? (
                        <img
                            src={user.avatarUrl}
                            alt="avatar"
                            className="w-16 h-16 rounded-full object-cover border-2 border-emerald-500/20"
                            referrerPolicy="no-referrer"
                        />
                    ) : (
                        <div className="w-16 h-16 rounded-full bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center text-white text-2xl font-bold">
                            {getInitials()}
                        </div>
                    )}
                    <div>
                        <h3 className="text-white font-bold text-lg">
                            {user?.displayName || 'User'}
                        </h3>
                        <p className="text-slate-400 text-sm">{user?.email || ''}</p>
                    </div>
                </div>
                <button
                    onClick={() => {
                        onSignOut();
                        onClose();
                    }}
                    className="p-2.5 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-400 transition-all group"
                    title={t('auth.signOut')}
                >
                    <LogOut className="w-5 h-5 group-hover:scale-110 transition-transform" />
                </button>
            </div>

            <div className="p-4 rounded-2xl bg-emerald-500/5 border border-emerald-500/10">
                <div className="flex items-center gap-3 mb-2">
                    <Activity className="w-4 h-4 text-emerald-400" />
                    <span className="text-sm font-semibold text-emerald-300 uppercase tracking-wider">Trading Status</span>
                </div>
                <p className="text-slate-400 text-xs">Your account is currently active for automated strategy trading.</p>
            </div>
        </div>
    );
}

const LLM_PROVIDERS = [
    { id: 'deepseek', name: 'DeepSeek', models: ['deepseek-chat', 'deepseek-reasoner'] },
    { id: 'openai', name: 'OpenAI', models: ['gpt-4o', 'gpt-4o-mini', 'o1-preview', 'o1-mini'] },
    { id: 'anthropic', name: 'Anthropic', models: ['claude-3-5-sonnet-latest', 'claude-3-opus-latest', 'claude-3-haiku-latest'] },
    { id: 'google', name: 'Google Gemini', models: ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-2.0-flash-exp'] }
];

function LLMContent({ userId, t, onConfigUpdated }) {
    const [config, setConfig] = useState({
        llm_provider: 'deepseek',
        llm_model: 'deepseek-chat',
        api_key: ''
    });
    const [hasKey, setHasKey] = useState(false);
    const [saving, setSaving] = useState(false);
    const [showKey, setShowKey] = useState(false);
    const [message, setMessage] = useState(null);

    const normalizeErrorDetail = (detail, fallback) => {
        if (!detail) return fallback;
        if (typeof detail === 'string') return detail;
        if (Array.isArray(detail)) {
            const first = detail[0];
            if (typeof first === 'string') return first;
            if (first && typeof first === 'object') {
                if (typeof first.msg === 'string') return first.msg;
                try {
                    return JSON.stringify(first);
                } catch {
                    return fallback;
                }
            }
            return fallback;
        }
        if (typeof detail === 'object') {
            if (typeof detail.msg === 'string') return detail.msg;
            try {
                return JSON.stringify(detail);
            } catch {
                return fallback;
            }
        }
        return fallback;
    };

    useEffect(() => {
        if (userId) {
            fetch(`${API_BASE_URL}/api/strategy/llm-config?user_id=${userId}`)
                .then(res => res.json())
                .then(data => {
                    setConfig({
                        llm_provider: data.llm_provider || 'deepseek',
                        llm_model: data.llm_model || 'deepseek-chat',
                        api_key: data.has_api_key ? '********' : ''
                    });
                    setHasKey(data.has_api_key);
                })
                .catch(err => console.error(err));
        }
    }, [userId]);

    const handleSave = async () => {
        setSaving(true);
        setMessage(null);
        try {
            const params = new URLSearchParams();
            params.append('user_id', userId);
            params.append('llm_provider', config.llm_provider);
            params.append('llm_model', config.llm_model);
            if (config.api_key && config.api_key !== '********') {
                params.append('llm_api_key', config.api_key);
            }

            const res = await fetch(`${API_BASE_URL}/api/strategy/llm-config?${params.toString()}`, {
                method: 'POST'
            });
            const data = await res.json();

            if (!res.ok) {
                setMessage({
                    type: 'error',
                    text: normalizeErrorDetail(data?.detail, t('settings.llm.error'))
                });
                return;
            }

            if (data?.success) {
                setMessage({ type: 'success', text: t('settings.llm.success') });
                if (onConfigUpdated) onConfigUpdated();
                if (config.api_key && config.api_key !== '********') setHasKey(true);
            } else {
                setMessage({
                    type: 'error',
                    text: normalizeErrorDetail(data?.detail, t('settings.llm.error'))
                });
            }
        } catch {
            setMessage({ type: 'error', text: t('settings.llm.error') });
        } finally {
            setSaving(false);
        }
    };

    const currentProvider = LLM_PROVIDERS.find(p => p.id === config.llm_provider) || LLM_PROVIDERS[0];

    return (
        <div className="space-y-6">
            <p className="text-slate-400 text-sm bg-emerald-500/5 p-3 rounded-xl border border-emerald-500/10 leading-relaxed">
                {t('settings.llm.desc')}
            </p>

            <div className="space-y-4">
                {/* Provider Select */}
                <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">{t('settings.llm.provider')}</label>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                        {LLM_PROVIDERS.map(p => (
                            <button
                                key={p.id}
                                onClick={() => setConfig({ ...config, llm_provider: p.id, llm_model: p.models[0] })}
                                className={`px-2 py-2.5 rounded-xl text-xs font-medium transition-all border ${config.llm_provider === p.id
                                    ? 'bg-emerald-600 border-emerald-500 text-white shadow-lg shadow-emerald-500/20'
                                    : 'bg-slate-800/50 border-slate-700 text-slate-400 hover:text-white'
                                    }`}
                            >
                                {p.name}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Model Input with datalist */}
                <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">{t('settings.llm.model')}</label>
                    <div className="relative">
                        <input
                            type="text"
                            list="model-suggestions"
                            value={config.llm_model}
                            onChange={(e) => setConfig({ ...config, llm_model: e.target.value })}
                            placeholder="Enter or select model name"
                            autoComplete="off"
                            className="w-full bg-slate-800/50 border border-slate-700 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-emerald-500 shadow-inner hide-datalist-arrow"
                        />
                        <datalist id="model-suggestions">
                            {currentProvider.models.map(m => (
                                <option key={m} value={m} />
                            ))}
                        </datalist>
                    </div>
                </div>

                {/* API Key */}
                <div>
                    <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">{t('settings.llm.apiKey')}</label>
                    <div className="relative">
                        <input
                            type={showKey ? 'text' : 'password'}
                            value={config.api_key}
                            onChange={(e) => setConfig({ ...config, api_key: e.target.value })}
                            placeholder={hasKey ? '********' : t('settings.exchange.apiKeyPlaceholder')}
                            className="w-full bg-slate-800/50 border border-slate-700 rounded-xl px-4 py-3 pr-12 text-white text-sm placeholder:text-slate-600 focus:outline-none focus:border-emerald-500 shadow-inner"
                        />
                        <button
                            type="button"
                            onClick={() => setShowKey(!showKey)}
                            className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white transition-colors"
                        >
                            {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                    </div>
                </div>
            </div>

            {message && (
                <div className={`p-3 rounded-xl text-sm flex items-center gap-2 animate-in fade-in slide-in-from-top-1 ${
                    message.type === 'success' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'
                }`}>
                    {message.type === 'success' ? <CheckCircle className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
                    <span className="flex-1">{message.text}</span>
                </div>
            )}

            <button
                onClick={handleSave}
                disabled={saving}
                className="w-full flex items-center justify-center gap-2 py-4 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white font-bold transition-all shadow-xl shadow-emerald-500/20 disabled:opacity-50 active:scale-95"
            >
                {saving ? (
                    <>
                        <RefreshCw className="w-5 h-5 animate-spin" />
                        <span>连通性检测中（最多 10 秒）...</span>
                    </>
                ) : (
                    <>
                        <Save className="w-5 h-5" />
                        <span>{t('settings.llm.save')}</span>
                    </>
                )}
            </button>
        </div>
    );
}

function ExchangeContent({ userId, t }) {
    const [apiKey, setApiKey] = useState('');
    const [apiSecret, setApiSecret] = useState('');
    const [showSecret, setShowSecret] = useState(false);
    const [status, setStatus] = useState(null);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    const normalizeErrorDetail = (detail, fallback) => {
        if (!detail) return fallback;
        if (typeof detail === 'string') return detail;
        if (Array.isArray(detail)) {
            const first = detail[0];
            if (typeof first === 'string') return first;
            if (first && typeof first === 'object') {
                if (typeof first.msg === 'string') return first.msg;
                try {
                    return JSON.stringify(first);
                } catch {
                    return fallback;
                }
            }
            return fallback;
        }
        if (typeof detail === 'object') {
            if (typeof detail.msg === 'string') return detail.msg;
            try {
                return JSON.stringify(detail);
            } catch {
                return fallback;
            }
        }
        return fallback;
    };

    useEffect(() => {
        if (userId) fetchStatus();
    }, [userId]);

    const fetchStatus = async () => {
        setLoading(true);
        try {
            const response = await fetch(`${API_BASE_URL}/api/strategy/binance/status?user_id=${userId}`);
            const data = await response.json();
            setStatus(data);
            setError('');
        } catch {
            setError(t('settings.exchange.fetchError'));
        } finally {
            // 我们稍微延迟结束 loading 状态，确保 UI 渲染已完成
            setTimeout(() => setLoading(false), 50);
        }
    };

    const handleSave = async () => {
        if (!apiKey || !apiSecret) {
            setError(t('settings.exchange.keysRequired'));
            return;
        }

        setSaving(true);
        setError('');
        try {
            const response = await fetch(`${API_BASE_URL}/api/strategy/binance/keys?user_id=${userId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ api_key: apiKey, api_secret: apiSecret, is_testnet: false })
            });
            const data = await response.json();
            if (data.success) {
                setApiKey('');
                setApiSecret('');
                await fetchStatus();
                window.dispatchEvent(new CustomEvent('binanceStatusChanged'));
            } else {
                setError(normalizeErrorDetail(data?.detail, t('settings.exchange.saveError')));
            }
        } catch {
            setError(t('settings.exchange.saveError'));
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="space-y-6">
            <div className="bg-[#0e1215] rounded-2xl p-5 border border-slate-700/50">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                            status?.connection_ok ? 'bg-emerald-500/10 text-emerald-400' : 'bg-yellow-500/10 text-yellow-500'
                        }`}>
                            {status?.connection_ok ? <CheckCircle className="w-6 h-6" /> : <AlertCircle className="w-6 h-6" />}
                        </div>
                        <div>
                            <h3 className="text-white font-bold">Binance Futures</h3>
                            <p className="text-slate-400 text-sm">
                                {loading ? t('settings.exchange.checking') : status?.is_configured ? (status.connection_ok ? t('settings.exchange.connected') : t('settings.exchange.connectionFailed')) : t('settings.exchange.notConfigured')}
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            {!status?.is_configured && (
                <div className="space-y-4 p-5 bg-[#0e1215] rounded-2xl border border-slate-700/50">
                    <div>
                        <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">API Key</label>
                        <input
                            type="text"
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value)}
                            className="w-full bg-slate-800/50 border border-slate-700 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-emerald-500"
                        />
                    </div>
                    <div>
                        <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">API Secret</label>
                        <div className="relative">
                            <input
                                type={showSecret ? 'text' : 'password'}
                                value={apiSecret}
                                onChange={(e) => setApiSecret(e.target.value)}
                                className="w-full bg-slate-800/50 border border-slate-700 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-emerald-500"
                            />
                            <button onClick={() => setShowSecret(!showSecret)} className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500">
                                {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                            </button>
                        </div>
                    </div>
                    
                    {error && <p className="text-red-400 text-xs">{error}</p>}

                    <button
                        onClick={handleSave}
                        disabled={saving}
                        className="w-full py-4 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white font-bold shadow-xl shadow-emerald-500/20 transition-all"
                    >
                        {saving ? t('settings.exchange.saving') : t('settings.exchange.save')}
                    </button>
                </div>
            )}
        </div>
    );
}
