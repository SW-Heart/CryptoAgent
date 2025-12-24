import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
    X, User, BarChart2, LogOut, Zap, Settings, Globe,
    ChevronLeft, ChevronRight
} from 'lucide-react';

export default function SettingsModal({
    isOpen,
    onClose,
    user,
    credits,
    onSignOut,
    creditsHistory = []
}) {
    const { t, i18n } = useTranslation();
    const [activeTab, setActiveTab] = useState('general');
    const [currentPage, setCurrentPage] = useState(1);
    const itemsPerPage = 10;

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
