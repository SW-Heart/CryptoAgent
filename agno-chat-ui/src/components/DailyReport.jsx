import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Newspaper, Mail, ChevronLeft, ChevronRight, Loader2, Check, X, Bell, BellOff } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { BASE_URL } from '../services/config';

export default function DailyReport() {
    const { t, i18n } = useTranslation();
    const [report, setReport] = useState(null);
    const [loading, setLoading] = useState(true);
    // Report language follows app language
    const [reportLanguage, setReportLanguage] = useState(() => {
        const lang = i18n.language;
        return lang?.startsWith('zh') ? 'zh' : 'en';
    });
    const [availableDates, setAvailableDates] = useState([]);
    const [currentDateIndex, setCurrentDateIndex] = useState(0);

    // Subscription state
    const [showSubscribeModal, setShowSubscribeModal] = useState(false);
    const [email, setEmail] = useState('');
    const [subscribing, setSubscribing] = useState(false);
    const [subscribeStatus, setSubscribeStatus] = useState(null);

    // Subscribed user state (stored in localStorage)
    const [subscribedEmail, setSubscribedEmail] = useState(() => {
        return localStorage.getItem('dailyReportEmail') || null;
    });
    const [unsubscribeToken, setUnsubscribeToken] = useState(() => {
        return localStorage.getItem('dailyReportToken') || null;
    });

    // Sync report language with app language
    useEffect(() => {
        const lang = i18n.language;
        setReportLanguage(lang?.startsWith('zh') ? 'zh' : 'en');
    }, [i18n.language]);

    // Fetch available dates
    useEffect(() => {
        fetch(`${BASE_URL}/api/daily-report/dates?language=${reportLanguage}&limit=30`)
            .then(res => res.json())
            .then(data => setAvailableDates(data.dates || []))
            .catch(err => console.error('Failed to fetch dates:', err));
    }, [reportLanguage]);

    // Fetch report
    useEffect(() => {
        setLoading(true);
        const dateParam = availableDates[currentDateIndex];
        const url = dateParam
            ? `${BASE_URL}/api/daily-report/${dateParam}?language=${reportLanguage}`
            : `${BASE_URL}/api/daily-report?language=${reportLanguage}`;

        fetch(url)
            .then(res => res.json())
            .then(data => {
                setReport(data);
                setLoading(false);
            })
            .catch(err => {
                console.error('Failed to fetch report:', err);
                setLoading(false);
            });
    }, [reportLanguage, currentDateIndex, availableDates]);

    const handleSubscribe = async (e) => {
        e.preventDefault();
        if (!email.trim()) return;

        setSubscribing(true);
        setSubscribeStatus(null);

        try {
            const res = await fetch(`${BASE_URL}/api/subscribe`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, language: reportLanguage })
            });

            const data = await res.json();

            if (res.ok) {
                setSubscribeStatus('success');
                setSubscribedEmail(email);
                // Store token if returned (for unsubscribe)
                if (data.token) {
                    setUnsubscribeToken(data.token);
                    localStorage.setItem('dailyReportToken', data.token);
                }
                localStorage.setItem('dailyReportEmail', email);
                localStorage.setItem('dailyReportLanguage', reportLanguage);
                setTimeout(() => {
                    setShowSubscribeModal(false);
                    setEmail('');
                    setSubscribeStatus(null);
                }, 1500);
            } else {
                setSubscribeStatus('error');
            }
        } catch (err) {
            setSubscribeStatus('error');
        } finally {
            setSubscribing(false);
        }
    };

    const handleUnsubscribe = async () => {
        if (!unsubscribeToken && !subscribedEmail) return;

        try {
            // Try unsubscribe by token first, then by email
            if (unsubscribeToken) {
                await fetch(`${BASE_URL}/api/unsubscribe/${unsubscribeToken}`);
            } else {
                await fetch(`${BASE_URL}/api/unsubscribe-email?email=${encodeURIComponent(subscribedEmail)}`, {
                    method: 'DELETE'
                });
            }

            // Clear local storage
            localStorage.removeItem('dailyReportEmail');
            localStorage.removeItem('dailyReportToken');
            localStorage.removeItem('dailyReportLanguage');
            setSubscribedEmail(null);
            setUnsubscribeToken(null);
            setShowSubscribeModal(false);
        } catch (err) {
            console.error('Unsubscribe failed:', err);
        }
    };

    const formatDate = (dateStr) => {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        const locale = reportLanguage === 'zh' ? 'zh-CN' : 'en-US';
        return d.toLocaleDateString(locale, {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
    };

    return (
        <div className="flex flex-col h-full w-full flex-1 bg-black">
            {/* Header */}
            <header className="h-16 flex items-center justify-between px-6 border-b border-slate-800 flex-shrink-0">
                <div className="flex items-center gap-2">
                    <Newspaper className="w-5 h-5 text-indigo-400" />
                    <h1 className="text-lg font-semibold text-white">
                        {t('dailyReport.title')}
                    </h1>
                </div>

                {/* Subscribe Button */}
                <button
                    onClick={() => setShowSubscribeModal(true)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${subscribedEmail
                        ? 'bg-green-600/20 text-green-400 border border-green-500/30 hover:bg-green-600/30'
                        : 'bg-indigo-600 hover:bg-indigo-500 text-white'
                        }`}
                >
                    {subscribedEmail ? (
                        <>
                            <Bell className="w-4 h-4" />
                            <span className="text-sm">{t('dailyReport.subscribed')}</span>
                        </>
                    ) : (
                        <>
                            <Mail className="w-4 h-4" />
                            <span className="text-sm">{t('dailyReport.subscribe')}</span>
                        </>
                    )}
                </button>
            </header>

            {/* Main Content */}
            <div className="flex-1 overflow-y-auto p-6">
                <div className="max-w-3xl mx-auto">
                    {/* Date Navigation */}
                    <div className="flex items-center justify-between mb-6">
                        <button
                            onClick={() => setCurrentDateIndex(i => Math.min(i + 1, availableDates.length - 1))}
                            disabled={currentDateIndex >= availableDates.length - 1}
                            className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors disabled:opacity-30"
                        >
                            <ChevronLeft className="w-5 h-5" />
                        </button>

                        <div className="text-center">
                            <div className="text-2xl font-bold text-white">
                                {formatDate(report?.report_date)}
                            </div>
                            <div className="text-sm text-slate-500">
                                {t('dailyReport.updatedAt')}
                            </div>
                        </div>

                        <button
                            onClick={() => setCurrentDateIndex(i => Math.max(i - 1, 0))}
                            disabled={currentDateIndex <= 0}
                            className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors disabled:opacity-30"
                        >
                            <ChevronRight className="w-5 h-5" />
                        </button>
                    </div>

                    {/* Report Content */}
                    <div className="bg-[#131722] rounded-xl border border-slate-800 p-6">
                        {loading ? (
                            <div className="flex items-center justify-center py-20">
                                <Loader2 className="w-8 h-8 text-indigo-400 animate-spin" />
                            </div>
                        ) : (
                            <div className="prose prose-invert prose-sm max-w-none">
                                <ReactMarkdown
                                    remarkPlugins={[remarkGfm]}
                                    components={{
                                        h1: ({ children }) => <h1 className="text-2xl font-bold text-white mb-4">{children}</h1>,
                                        h2: ({ children }) => <h2 className="text-xl font-semibold text-indigo-400 mt-6 mb-3">{children}</h2>,
                                        h3: ({ children }) => <h3 className="text-lg font-medium text-slate-300 mt-4 mb-2">{children}</h3>,
                                        p: ({ children }) => <p className="text-slate-300 leading-relaxed mb-3">{children}</p>,
                                        ul: ({ children }) => <ul className="list-disc list-inside text-slate-300 space-y-1 mb-4">{children}</ul>,
                                        ol: ({ children }) => <ol className="list-decimal list-inside text-slate-300 space-y-1 mb-4">{children}</ol>,
                                        li: ({ children }) => <li className="text-slate-300">{children}</li>,
                                        strong: ({ children }) => <strong className="text-white font-semibold">{children}</strong>,
                                        hr: () => <hr className="border-slate-700 my-6" />,
                                        table: ({ children }) => (
                                            <div className="overflow-x-auto my-4">
                                                <table className="w-full border-collapse">{children}</table>
                                            </div>
                                        ),
                                        thead: ({ children }) => <thead className="bg-slate-800">{children}</thead>,
                                        tbody: ({ children }) => <tbody>{children}</tbody>,
                                        tr: ({ children }) => <tr className="border-b border-slate-700">{children}</tr>,
                                        th: ({ children }) => <th className="px-4 py-2 text-left text-sm font-semibold text-indigo-300">{children}</th>,
                                        td: ({ children }) => <td className="px-4 py-2 text-sm text-slate-300">{children}</td>,
                                    }}
                                >
                                    {report?.content || t('dailyReport.noReport')}
                                </ReactMarkdown>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Subscribe Modal */}
            {showSubscribeModal && (
                <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
                    <div className="bg-gradient-to-br from-[#1e293b] to-[#0f172a] rounded-2xl border border-slate-700 p-6 w-full max-w-md mx-4 shadow-2xl">
                        {/* Modal Header */}
                        <div className="flex items-center justify-between mb-6">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-indigo-500/20 rounded-lg">
                                    <Mail className="w-5 h-5 text-indigo-400" />
                                </div>
                                <h2 className="text-xl font-semibold text-white">
                                    {subscribedEmail ? t('dailyReport.modal.settingsTitle') : t('dailyReport.modal.title')}
                                </h2>
                            </div>
                            <button
                                onClick={() => setShowSubscribeModal(false)}
                                className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        {subscribedEmail ? (
                            /* Already Subscribed View */
                            <div className="space-y-4">
                                <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4">
                                    <div className="flex items-center gap-2 mb-2">
                                        <Check className="w-5 h-5 text-green-400" />
                                        <span className="text-green-400 font-medium">{t('dailyReport.subscribed')}</span>
                                    </div>
                                    <p className="text-slate-300 text-sm break-all">
                                        {subscribedEmail}
                                    </p>
                                </div>

                                <p className="text-slate-400 text-sm">
                                    {t('dailyReport.modal.subscribedMessage')}
                                </p>

                                <button
                                    onClick={handleUnsubscribe}
                                    className="w-full flex items-center justify-center gap-2 py-3 bg-red-600/20 hover:bg-red-600/30 text-red-400 border border-red-500/30 rounded-xl transition-colors"
                                >
                                    <BellOff className="w-4 h-4" />
                                    {t('dailyReport.modal.unsubscribe')}
                                </button>
                            </div>
                        ) : (
                            /* Subscribe Form */
                            <form onSubmit={handleSubscribe} className="space-y-4">
                                <p className="text-slate-400 text-sm">
                                    {t('dailyReport.modal.description')}
                                </p>

                                <div>
                                    <label className="block text-sm font-medium text-slate-400 mb-2">
                                        {t('dailyReport.modal.email')}
                                    </label>
                                    <input
                                        type="email"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        placeholder={t('dailyReport.modal.emailPlaceholder')}
                                        className="w-full px-4 py-3 bg-slate-800/50 border border-slate-600 rounded-xl text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                                        required
                                    />
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-slate-400 mb-2">
                                        {t('dailyReport.modal.language')}
                                    </label>
                                    <div className="flex gap-2">
                                        <button
                                            type="button"
                                            onClick={() => setReportLanguage('en')}
                                            className={`flex-1 py-3 rounded-xl font-medium transition-colors ${reportLanguage === 'en'
                                                ? 'bg-indigo-600 text-white'
                                                : 'bg-slate-800/50 text-slate-400 hover:text-white border border-slate-600'
                                                }`}
                                        >
                                            English
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => setReportLanguage('zh')}
                                            className={`flex-1 py-3 rounded-xl font-medium transition-colors ${reportLanguage === 'zh'
                                                ? 'bg-indigo-600 text-white'
                                                : 'bg-slate-800/50 text-slate-400 hover:text-white border border-slate-600'
                                                }`}
                                        >
                                            中文
                                        </button>
                                    </div>
                                </div>

                                <button
                                    type="submit"
                                    disabled={subscribing}
                                    className="w-full py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-medium rounded-xl transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                                >
                                    {subscribing ? (
                                        <Loader2 className="w-5 h-5 animate-spin" />
                                    ) : subscribeStatus === 'success' ? (
                                        <>
                                            <Check className="w-5 h-5" />
                                            {t('dailyReport.subscribed')}!
                                        </>
                                    ) : (
                                        <>
                                            <Bell className="w-5 h-5" />
                                            {t('dailyReport.modal.subscribeNow')}
                                        </>
                                    )}
                                </button>

                                {subscribeStatus === 'error' && (
                                    <p className="text-red-400 text-sm text-center">
                                        {t('dailyReport.modal.error')}
                                    </p>
                                )}
                            </form>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
