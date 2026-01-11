import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
    X, User, BarChart2, LogOut, Zap, Settings, Globe,
    ChevronLeft, ChevronRight, Key, Eye, EyeOff, RefreshCw,
    CheckCircle, XCircle, AlertCircle
} from 'lucide-react';

export default function SettingsModal({
    isOpen,
    onClose,
    user,
    credits,
    onSignOut,
    creditsHistory = [],
    defaultTab = 'general'
}) {
    const { t, i18n } = useTranslation();
    const [activeTab, setActiveTab] = useState(defaultTab);
    const [currentPage, setCurrentPage] = useState(1);
    const itemsPerPage = 10;

    // Update activeTab when defaultTab changes or modal opens
    useEffect(() => {
        if (isOpen && defaultTab) {
            setActiveTab(defaultTab);
        }
    }, [isOpen, defaultTab]);

    if (!isOpen) return null;

    // Get initials for avatar fallback
    const getInitials = () => {
        if (user?.displayName) {
            return user.displayName.charAt(0).toUpperCase();
        }
        if (user?.email) {
            return user.email.charAt(0).toUpperCase();
        }
        return 'U';
    };

    // Pagination logic
    const totalPages = Math.ceil(creditsHistory.length / itemsPerPage);
    const paginatedHistory = creditsHistory.slice(
        (currentPage - 1) * itemsPerPage,
        currentPage * itemsPerPage
    );

    const handleBackdropClick = (e) => {
        if (e.target === e.currentTarget) {
            onClose();
        }
    };

    const changeLanguage = (lang) => {
        i18n.changeLanguage(lang);
        localStorage.setItem('language', lang);
    };

    const getTabTitle = () => {
        switch (activeTab) {
            case 'general': return t('settings.tabs.general');
            case 'account': return t('settings.tabs.account');
            case 'usage': return t('settings.tabs.usage');
            case 'exchange': return t('settings.tabs.exchange');
            default: return '';
        }
    };

    return (
        <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
            onClick={handleBackdropClick}
            onKeyDown={(e) => e.key === 'Escape' && onClose()}
            tabIndex={-1}
        >
            <div className="bg-[#1a1f2e] rounded-2xl w-full max-w-3xl h-[500px] flex shadow-2xl border border-slate-700/50">
                {/* Left Sidebar */}
                <div className="w-56 bg-[#131722] border-r border-slate-700/50 p-4 flex flex-col rounded-l-2xl">
                    {/* Logo only */}
                    <div className="flex items-center justify-center mb-6">
                        <img
                            src="https://ai-shot.oss-cn-hangzhou.aliyuncs.com/logo/ailogo.png"
                            alt="logo"
                            className="w-10 h-10 rounded-lg object-contain"
                        />
                    </div>

                    <nav className="flex-1 space-y-1">
                        <button
                            onClick={() => setActiveTab('general')}
                            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${activeTab === 'general'
                                ? 'bg-slate-700/50 text-white'
                                : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                                }`}
                        >
                            <Settings className="w-4 h-4" />
                            {t('settings.tabs.general')}
                        </button>
                        <button
                            onClick={() => setActiveTab('account')}
                            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${activeTab === 'account'
                                ? 'bg-slate-700/50 text-white'
                                : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                                }`}
                        >
                            <User className="w-4 h-4" />
                            {t('settings.tabs.account')}
                        </button>
                        <button
                            onClick={() => setActiveTab('usage')}
                            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${activeTab === 'usage'
                                ? 'bg-slate-700/50 text-white'
                                : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                                }`}
                        >
                            <BarChart2 className="w-4 h-4" />
                            {t('settings.tabs.usage')}
                        </button>
                        <button
                            onClick={() => setActiveTab('exchange')}
                            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${activeTab === 'exchange'
                                ? 'bg-slate-700/50 text-white'
                                : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                                }`}
                        >
                            <Key className="w-4 h-4" />
                            {t('settings.tabs.exchange')}
                        </button>
                    </nav>
                </div>

                {/* Right Content */}
                <div className="flex-1 flex flex-col overflow-hidden rounded-r-2xl">
                    {/* Header */}
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

                    {/* Content - scrollable */}
                    <div className="flex-1 p-6 overflow-y-auto">
                        {activeTab === 'general' ? (
                            <GeneralContent
                                currentLanguage={i18n.language}
                                onChangeLanguage={changeLanguage}
                                t={t}
                            />
                        ) : activeTab === 'account' ? (
                            <AccountContent
                                user={user}
                                credits={credits}
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
                            <UsageContent
                                credits={credits}
                                history={paginatedHistory}
                                currentPage={currentPage}
                                totalPages={totalPages}
                                onPageChange={setCurrentPage}
                                t={t}
                            />
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

function GeneralContent({ currentLanguage, onChangeLanguage, t }) {
    return (
        <div className="space-y-6">
            {/* Language Setting */}
            <div>
                {/* Label outside the box */}
                <label className="block text-sm text-slate-500 mb-2">
                    {t('settings.general.language')}
                </label>

                {/* Language switch box */}
                <div className="bg-[#131722] rounded-xl p-4 border border-slate-700/50">
                    <div className="flex gap-2">
                        <button
                            onClick={() => onChangeLanguage('en')}
                            className={`flex-1 py-3 rounded-xl font-medium transition-colors ${currentLanguage === 'en' || currentLanguage?.startsWith('en')
                                ? 'bg-indigo-600 text-white'
                                : 'bg-slate-800/50 text-slate-400 hover:text-white border border-slate-600'
                                }`}
                        >
                            {t('settings.general.english')}
                        </button>
                        <button
                            onClick={() => onChangeLanguage('zh')}
                            className={`flex-1 py-3 rounded-xl font-medium transition-colors ${currentLanguage === 'zh' || currentLanguage?.startsWith('zh')
                                ? 'bg-indigo-600 text-white'
                                : 'bg-slate-800/50 text-slate-400 hover:text-white border border-slate-600'
                                }`}
                        >
                            {t('settings.general.chinese')}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

function AccountContent({ user, credits, getInitials, onSignOut, onClose, t }) {
    return (
        <div className="space-y-6">
            {/* User Info */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    {/* Real avatar or fallback */}
                    {user?.avatarUrl ? (
                        <img
                            src={user.avatarUrl}
                            alt="avatar"
                            className="w-14 h-14 rounded-full object-cover"
                            referrerPolicy="no-referrer"
                        />
                    ) : (
                        <div className="w-14 h-14 rounded-full bg-gradient-to-br from-indigo-500 to-violet-500 flex items-center justify-center text-white text-xl font-bold">
                            {getInitials()}
                        </div>
                    )}
                    <div>
                        <h3 className="text-white font-semibold text-lg">
                            {user?.displayName || 'User'}
                        </h3>
                        <p className="text-slate-400 text-sm">{user?.email || ''}</p>
                    </div>
                </div>
                {/* Only Sign Out button, no Edit */}
                <button
                    onClick={() => {
                        onSignOut();
                        onClose();
                    }}
                    className="p-2 rounded-lg bg-slate-700/50 hover:bg-red-500/20 text-slate-300 hover:text-red-400 transition-colors"
                    title={t('common.signOut')}
                >
                    <LogOut className="w-4 h-4" />
                </button>
            </div>

            {/* Subscription */}
            <div className="bg-[#131722] rounded-xl p-4 border border-slate-700/50">
                <div className="flex items-center justify-between mb-4">
                    <span className="text-white font-medium">Free</span>
                    <button
                        className="px-4 py-1.5 rounded-lg border border-slate-600 text-slate-300 text-sm hover:bg-slate-700/50 transition-colors cursor-not-allowed"
                        title="Coming soon"
                    >
                        Upgrade
                    </button>
                </div>

                <div className="space-y-3">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-slate-400 text-sm">
                            <Zap className="w-4 h-4" />
                            <span>{t('settings.account.credits')}</span>
                        </div>
                        <span className="text-white font-medium">{credits}</span>
                    </div>
                    <p className="text-slate-500 text-xs">{t('settings.account.freeCredits')}</p>
                </div>
            </div>
        </div>
    );
}

function UsageContent({ credits, history, currentPage, totalPages, onPageChange, t }) {
    return (
        <div className="space-y-6 h-full flex flex-col">
            {/* Credits Overview */}
            <div className="bg-[#131722] rounded-xl p-4 border border-slate-700/50 flex-shrink-0">
                <div className="flex items-center justify-between mb-4">
                    <span className="text-white font-medium">Free</span>
                    <button
                        className="px-4 py-1.5 rounded-lg border border-slate-600 text-slate-300 text-sm hover:bg-slate-700/50 transition-colors cursor-not-allowed"
                        title="Coming soon"
                    >
                        Upgrade
                    </button>
                </div>

                <div className="space-y-2">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-slate-400 text-sm">
                            <Zap className="w-4 h-4" />
                            <span>{t('settings.usage.credits')}</span>
                        </div>
                        <span className="text-white font-medium">{credits}</span>
                    </div>
                </div>
            </div>

            {/* Usage History Table - scrollable */}
            <div className="bg-[#131722] rounded-xl border border-slate-700/50 flex flex-col flex-1 min-h-0">
                <div className="overflow-x-auto overflow-y-auto flex-1">
                    <table className="w-full">
                        <thead className="sticky top-0 bg-[#131722]">
                            <tr className="border-b border-slate-700/50">
                                <th className="text-left text-slate-400 text-sm font-medium px-4 py-3">{t('settings.usage.action')}</th>
                                <th className="text-left text-slate-400 text-sm font-medium px-4 py-3">{t('settings.usage.date')}</th>
                                <th className="text-right text-slate-400 text-sm font-medium px-4 py-3">{t('settings.usage.creditsChange')}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {history.length > 0 ? (
                                history.map((item, idx) => (
                                    <tr key={idx} className="border-b border-slate-700/30 last:border-0">
                                        <td className="px-4 py-3 text-white text-sm max-w-[200px] truncate">
                                            {item.details}
                                        </td>
                                        <td className="px-4 py-3 text-slate-400 text-sm whitespace-nowrap">
                                            {item.date}
                                        </td>
                                        <td className="px-4 py-3 text-right text-red-400 text-sm font-medium">
                                            {item.credits_change}
                                        </td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan={3} className="px-4 py-8 text-center text-slate-500 text-sm">
                                        {t('settings.usage.noHistory')}
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>

                {/* Pagination - fixed at bottom */}
                {totalPages > 1 && (
                    <div className="flex items-center justify-center gap-2 px-4 py-3 border-t border-slate-700/50 flex-shrink-0">
                        <button
                            onClick={() => onPageChange(Math.max(1, currentPage - 1))}
                            disabled={currentPage === 1}
                            className="flex items-center gap-1 text-slate-400 hover:text-white text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            <ChevronLeft className="w-4 h-4" />
                            Previous
                        </button>

                        <div className="flex items-center gap-1 mx-4">
                            {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                                let page;
                                if (totalPages <= 5) {
                                    page = i + 1;
                                } else if (currentPage <= 3) {
                                    page = i + 1;
                                } else if (currentPage >= totalPages - 2) {
                                    page = totalPages - 4 + i;
                                } else {
                                    page = currentPage - 2 + i;
                                }
                                return (
                                    <button
                                        key={page}
                                        onClick={() => onPageChange(page)}
                                        className={`w-8 h-8 rounded-lg text-sm ${currentPage === page
                                            ? 'bg-indigo-500 text-white'
                                            : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
                                            }`}
                                    >
                                        {page}
                                    </button>
                                );
                            })}
                        </div>

                        <button
                            onClick={() => onPageChange(Math.min(totalPages, currentPage + 1))}
                            disabled={currentPage === totalPages}
                            className="flex items-center gap-1 text-slate-400 hover:text-white text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            Next
                            <ChevronRight className="w-4 h-4" />
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function ExchangeContent({ userId, t }) {
    const [apiKey, setApiKey] = useState('');
    const [apiSecret, setApiSecret] = useState('');
    const [isTestnet, setIsTestnet] = useState(true);
    const [showSecret, setShowSecret] = useState(false);
    const [status, setStatus] = useState(null);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    // Fetch status on mount
    useEffect(() => {
        if (userId) {
            fetchStatus();
        }
    }, [userId]);

    const fetchStatus = async () => {
        setLoading(true);
        try {
            const response = await fetch(`${BASE_URL}/api/strategy/binance/status?user_id=${userId}`);
            const data = await response.json();
            setStatus(data);
            setError('');
        } catch (err) {
            setError(t('settings.exchange.fetchError'));
        } finally {
            setLoading(false);
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
            const response = await fetch(`${BASE_URL}/api/strategy/binance/keys?user_id=${userId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    api_key: apiKey,
                    api_secret: apiSecret,
                    is_testnet: isTestnet
                })
            });
            const data = await response.json();

            if (data.success) {
                setApiKey('');
                setApiSecret('');
                await fetchStatus();
                // 通知 StrategyNexus 刷新状态
                window.dispatchEvent(new CustomEvent('binanceStatusChanged'));
            } else {
                setError(data.detail || t('settings.exchange.saveError'));
            }
        } catch (err) {
            setError(t('settings.exchange.saveError'));
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async () => {
        if (!window.confirm(t('settings.exchange.deleteConfirm'))) return;

        setLoading(true);
        try {
            const response = await fetch(`${BASE_URL}/api/strategy/binance/keys?user_id=${userId}`, {
                method: 'DELETE'
            });
            const data = await response.json();

            if (data.success) {
                await fetchStatus();
                // 通知 StrategyNexus 刷新状态
                window.dispatchEvent(new CustomEvent('binanceStatusChanged'));
            }
        } catch (err) {
            setError(t('settings.exchange.deleteError'));
        } finally {
            setLoading(false);
        }
    };

    const getStatusIcon = () => {
        if (loading) return <RefreshCw className="w-5 h-5 text-slate-400 animate-spin" />;
        if (!status?.is_configured) return <AlertCircle className="w-5 h-5 text-yellow-500" />;
        if (status?.connection_ok) return <CheckCircle className="w-5 h-5 text-green-500" />;
        return <XCircle className="w-5 h-5 text-red-500" />;
    };

    const getStatusText = () => {
        if (loading) return t('settings.exchange.checking');
        if (!status?.is_configured) return t('settings.exchange.notConfigured');
        if (status?.connection_ok) return t('settings.exchange.connected');
        return status?.connection_error || t('settings.exchange.connectionFailed');
    };

    return (
        <div className="space-y-6">
            {/* Connection Status */}
            <div className="bg-[#131722] rounded-xl p-4 border border-slate-700/50">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        {getStatusIcon()}
                        <div>
                            <h3 className="text-white font-medium">Binance Futures</h3>
                            <p className="text-slate-400 text-sm">{getStatusText()}</p>
                        </div>
                    </div>
                    <button
                        onClick={fetchStatus}
                        disabled={loading}
                        className="p-2 rounded-lg hover:bg-slate-700/50 text-slate-400 hover:text-white transition-colors disabled:opacity-50"
                    >
                        <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                    </button>
                </div>

                {/* Balance display if connected */}
                {status?.connection_ok && status?.balance && (
                    <div className="mt-4 pt-4 border-t border-slate-700/50">
                        <div className="flex items-center justify-between text-sm">
                            <span className="text-slate-400">{t('settings.exchange.balance')}</span>
                            <span className="text-white font-medium">
                                ${status.balance.available_balance?.toFixed(2)}
                            </span>
                            {status.balance.assets && status.balance.assets.length > 1 && (
                                <span className="text-slate-500 text-xs ml-2">
                                    ({status.balance.assets.map(a => `${a.available_balance?.toFixed(0)} ${a.asset}`).join(' + ')})
                                </span>
                            )}
                        </div>
                    </div>
                )}
            </div>

            {/* API Key Configuration */}
            {!status?.is_configured ? (
                <div className="bg-[#131722] rounded-xl p-4 border border-slate-700/50 space-y-4">
                    <h3 className="text-white font-medium">{t('settings.exchange.configureKeys')}</h3>

                    {/* Network Toggle */}
                    <div className="flex items-center justify-between">
                        <span className="text-slate-400 text-sm">{t('settings.exchange.network')}</span>
                        <div className="flex gap-2">
                            <button
                                onClick={() => setIsTestnet(true)}
                                className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${isTestnet
                                    ? 'bg-indigo-600 text-white'
                                    : 'bg-slate-800/50 text-slate-400 hover:text-white'
                                    }`}
                            >
                                {t('settings.exchange.testnet')}
                            </button>
                            <button
                                onClick={() => setIsTestnet(false)}
                                className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${!isTestnet
                                    ? 'bg-indigo-600 text-white'
                                    : 'bg-slate-800/50 text-slate-400 hover:text-white'
                                    }`}
                            >
                                {t('settings.exchange.mainnet')}
                            </button>
                        </div>
                    </div>

                    {/* API Key Input */}
                    <div>
                        <label className="block text-sm text-slate-500 mb-1.5">API Key</label>
                        <input
                            type="text"
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value)}
                            placeholder={t('settings.exchange.apiKeyPlaceholder')}
                            className="w-full bg-slate-800/50 border border-slate-600 rounded-lg px-3 py-2.5 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-indigo-500"
                        />
                    </div>

                    {/* API Secret Input */}
                    <div>
                        <label className="block text-sm text-slate-500 mb-1.5">API Secret</label>
                        <div className="relative">
                            <input
                                type={showSecret ? 'text' : 'password'}
                                value={apiSecret}
                                onChange={(e) => setApiSecret(e.target.value)}
                                placeholder={t('settings.exchange.apiSecretPlaceholder')}
                                className="w-full bg-slate-800/50 border border-slate-600 rounded-lg px-3 py-2.5 pr-10 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:border-indigo-500"
                            />
                            <button
                                type="button"
                                onClick={() => setShowSecret(!showSecret)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
                            >
                                {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                            </button>
                        </div>
                    </div>

                    {/* Error Message */}
                    {error && (
                        <p className="text-red-400 text-sm">{error}</p>
                    )}

                    {/* Save Button */}
                    <button
                        onClick={handleSave}
                        disabled={saving || !apiKey || !apiSecret}
                        className="w-full py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {saving ? t('settings.exchange.saving') : t('settings.exchange.save')}
                    </button>

                    {/* Testnet Instructions */}
                    {isTestnet && (
                        <p className="text-slate-500 text-xs">
                            {t('settings.exchange.testnetHint')}
                        </p>
                    )}
                </div>
            ) : (
                /* Keys Configured - Show Delete Option */
                <div className="bg-[#131722] rounded-xl p-4 border border-slate-700/50 space-y-4">
                    <div className="flex items-center justify-between">
                        <div>
                            <h3 className="text-white font-medium">{t('settings.exchange.keysConfigured')}</h3>
                            <p className="text-slate-400 text-sm">
                                {status?.is_trading_enabled
                                    ? t('settings.exchange.tradingEnabled')
                                    : t('settings.exchange.tradingDisabled')
                                }
                            </p>
                        </div>
                        <button
                            onClick={handleDelete}
                            className="px-4 py-2 rounded-lg border border-red-500/50 text-red-400 text-sm hover:bg-red-500/10 transition-colors"
                        >
                            {t('settings.exchange.delete')}
                        </button>
                    </div>
                </div>
            )}

            {/* Security Notice */}
            <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4">
                <p className="text-yellow-500 text-sm">
                    ⚠️ {t('settings.exchange.securityNotice')}
                </p>
            </div>
        </div>
    );
}
