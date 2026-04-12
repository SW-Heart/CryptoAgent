import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
    TrendingUp, TrendingDown, DollarSign, Target,
    ChevronDown, ChevronRight, Activity, Wallet,
    ArrowUpCircle, ArrowDownCircle, Clock, Percent,
    Award, Power, Key, Play, Square, AlertCircle, Settings,
    ListFilter, History, Layers, RefreshCw, CheckCircle, XCircle, X, Cpu
} from 'lucide-react';
import CryptoLoader from './CryptoLoader';
import BetaGate from './BetaGate';
import StrategySettingsModal from './StrategySettingsModal';

import { BASE_URL } from '../services/config';

// Main Component
export default function StrategyNexus({ userId, onOpenSettings }) {
    const { t } = useTranslation();
    const [wallet, setWallet] = useState(null);
    const [positions, setPositions] = useState([]);
    const [tradeHistory, setTradeHistory] = useState([]); // Renamed from closedPositions for clarity
    const [openOrders, setOpenOrders] = useState([]);
    const [historyOrders, setHistoryOrders] = useState([]); // New state for order history

    // Logs state
    const [logs, setLogs] = useState([]);
    const [expandedLog, setExpandedLog] = useState(null);
    const [logsHasMore, setLogsHasMore] = useState(true);
    const [logsLoading, setLogsLoading] = useState(false);
    const logsContainerRef = useRef(null);

    // UI state
    const [activeTab, setActiveTab] = useState('positions');
    const [isSettingsOpen, setIsSettingsOpen] = useState(false);
    const [orderFilter, setOrderFilter] = useState('OPEN'); // 'OPEN' or 'HISTORY'
    const [loading, setLoading] = useState(true);
    const [initialLoadComplete, setInitialLoadComplete] = useState(false);

    // Binance Status
    const [binanceStatus, setBinanceStatus] = useState(null);
    const [binanceLoading, setBinanceLoading] = useState(true);
    const [analysisLoading, setAnalysisLoading] = useState(false);

    // Beta Access State
    const [betaChecking, setBetaChecking] = useState(true);
    const [hasBetaAccess, setHasBetaAccess] = useState(false);

    // Validation State
    const [validationData, setValidationData] = useState(null);
    const [showValidationModal, setShowValidationModal] = useState(false);

    // Check Beta Access on mount
    useEffect(() => {
        if (userId) {
            checkBetaAccess();
        }
    }, [userId]);

    const checkBetaAccess = async () => {
        setBetaChecking(true);
        try {
            const res = await fetch(`${BASE_URL}/api/strategy/beta/status?user_id=${userId}`);
            const data = await res.json();
            setHasBetaAccess(data.has_beta_access || false);
        } catch (e) {
            console.error('[StrategyNexus] Beta check error:', e);
            setHasBetaAccess(false);
        } finally {
            setBetaChecking(false);
        }
    };

    const handleBetaAccessGranted = () => {
        setHasBetaAccess(true);
    };

    // Initial Status Check
    useEffect(() => {
        fetchBinanceStatus();
        // Listener for setting changes
        const handleStatusChanged = () => {
            console.log('[StrategyNexus] Binance status changed, refreshing...');
            fetchBinanceStatus();
        };
        window.addEventListener('binanceStatusChanged', handleStatusChanged);
        return () => window.removeEventListener('binanceStatusChanged', handleStatusChanged);
    }, [userId]);

    // Data Polling
    useEffect(() => {
        if (binanceStatus?.is_configured && binanceStatus?.is_trading_enabled) {
            fetchData();
            const interval = setInterval(fetchData, 10000);
            return () => clearInterval(interval);
        }
    }, [binanceStatus?.is_configured, binanceStatus?.is_trading_enabled, orderFilter]); // Rerun if orderFilter changes


    const fetchBinanceStatus = async () => {
        if (!userId) return;
        setBinanceLoading(true);
        try {
            const res = await fetch(`${BASE_URL}/api/strategy/binance/status?user_id=${userId}`);
            setBinanceStatus(await res.json());
        } catch (e) {
            console.error('Binance status error:', e);
        } finally {
            setBinanceLoading(false);
        }
    };

    const toggleTrading = async () => {
        if (binanceLoading) return;
        
        // 如果是要 开启 (从 disable 变 enable)，先做 ready-check
        if (!binanceStatus?.is_trading_enabled) {
            try {
                const res = await fetch(`${BASE_URL}/api/strategy/ready-check?user_id=${userId}`);
                const data = await res.json();
                if (!data.ready) {
                    setValidationData(data);
                    setShowValidationModal(true);
                    return; // 拦截，不执行开启操作
                }
            } catch (e) {
                console.error('[Strategy] Ready check failed:', e);
            }
        }

        setBinanceLoading(true);
        try {
            const endpoint = binanceStatus.is_trading_enabled ? 'disable' : 'enable';
            const res = await fetch(`${BASE_URL}/api/strategy/binance/trading/${endpoint}?user_id=${userId}`, { method: 'POST' });
            const data = await res.json();
            if (data.success) fetchBinanceStatus();
        } catch (e) {
            console.error('Trading toggle error:', e);
        } finally {
            setBinanceLoading(false);
        }
    };

    const runAnalysis = async () => {
        if (analysisLoading) return;
        setAnalysisLoading(true);
        try {
            const res = await fetch(`${BASE_URL}/api/strategy/analysis/run`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ symbols: 'BTC,ETH,SOL' })
            });
            const data = await res.json();
            if (data.status === 'success') {
                // Show success feedback (could use toast if available, or just console)
                console.log('Analysis started:', data.message);
                // Refresh logs after a short delay to likely see the start of analysis
                setTimeout(fetchData, 2000);
            }
        } catch (e) {
            console.error('Analysis trigger error:', e);
        } finally {
            setAnalysisLoading(false);
        }
    };

    const fetchData = async () => {
        try {
            const userParam = userId ? `?user_id=${userId}` : '';
            const userParamWithStatus = userId ? `&user_id=${userId}` : '';

            // Construct promises array
            const promises = [
                fetch(`${BASE_URL}/api/strategy/wallet${userParam}`).then(r => r.json()),
                fetch(`${BASE_URL}/api/strategy/positions?status=OPEN${userParamWithStatus}`).then(r => r.json()),
                fetch(`${BASE_URL}/api/strategy/trade-history${userParam}&limit=100`).then(r => r.json()),
                fetch(`${BASE_URL}/api/strategy/orders?status=OPEN${userParamWithStatus}`).then(r => r.json()),
                fetch(`${BASE_URL}/api/strategy/logs?limit=20&offset=0`).then(r => r.json())
            ];

            // Conditionally fetch order history if filtering for it
            // (Or fetch eagerly, but user requested separation. Order history can be heavy, so fetching on demand or separate call might be better. 
            // For now, let's just fetch history if needed or if first load)
            const [walletRes, posRes, historyRes, openOrdersRes, logsRes] = await Promise.all(promises);

            // Separate call for order history if needed (to keep main fetch fast)
            let historyOrdersRes = { orders: [] };
            if (activeTab === 'orders' && orderFilter === 'HISTORY') {
                historyOrdersRes = await fetch(`${BASE_URL}/api/strategy/orders?status=HISTORY${userParamWithStatus}&limit=50`).then(r => r.json());
                setHistoryOrders(historyOrdersRes.orders || []);
            }

            // 如果后端返回 binance_error（交易所临时不可用），保持上次有效数据
            if (!walletRes?.source?.includes('error')) {
                setWallet(walletRes);
            }
            setPositions(posRes.positions || []);
            setTradeHistory(Array.isArray(historyRes) ? historyRes : (historyRes.trades || []));
            setOpenOrders(openOrdersRes.orders || []);

            // Use existing logs logic
            if (logs.length === 0) setLogs(logsRes.logs || []); // Only set initial logs if empty to prevent jitter? No, this is polling.
            // Better to prepend or update? Simple set for now.
            setLogs(logsRes.logs || []);
            setLogsHasMore(logsRes.has_more || false);

            setLoading(false);
        } catch (e) {
            console.error('Strategy data fetch error:', e);
            setLoading(false);
        }
    };

    // Load more logs
    const loadMoreLogs = useCallback(async () => {
        if (logsLoading || !logsHasMore) return;
        setLogsLoading(true);
        try {
            const offset = logs.length;
            const res = await fetch(`${BASE_URL}/api/strategy/logs?limit=20&offset=${offset}`);
            const data = await res.json();
            if (data.logs?.length > 0) {
                setLogs(prev => [...prev, ...data.logs]);
                setLogsHasMore(data.has_more || false);
            } else {
                setLogsHasMore(false);
            }
        } catch (e) { console.error(e); } finally { setLogsLoading(false); }
    }, [logs.length, logsLoading, logsHasMore]);

    // Handle logs scroll
    const handleLogsScroll = useCallback((e) => {
        if (e.target.scrollHeight - e.target.scrollTop - e.target.clientHeight < 50 && logsHasMore && !logsLoading) {
            loadMoreLogs();
        }
    }, [loadMoreLogs, logsHasMore, logsLoading]);

    // 加载状态：binanceLoading 期间或数据加载期间都显示加载动画
    // 条件1: binanceLoading 还在加载状态
    // 条件2: binance 已配置且启用交易，但数据还没加载完
    const showCryptoLoader = binanceLoading ||
        (loading && binanceStatus?.is_configured && binanceStatus?.is_trading_enabled && !initialLoadComplete);

    // Beta Access Check - Show BetaGate if user doesn't have access
    if (betaChecking) {
        return <CryptoLoader isReady={false} onComplete={() => { }} />;
    }

    if (!hasBetaAccess) {
        return <BetaGate userId={userId} onAccessGranted={handleBetaAccessGranted} />;
    }

    if (showCryptoLoader) {
        return <CryptoLoader isReady={!loading && !binanceLoading} onComplete={() => setInitialLoadComplete(true)} />;
    }

    // Not Configured View
    if (!binanceStatus?.is_configured && !binanceLoading) {
        return (
            <div className="flex-1 flex flex-col items-center justify-center bg-[#0d1117] p-8">
                <div className="bg-[#131722] rounded-2xl p-8 max-w-md w-full border border-slate-700/50 text-center">
                    <div className="w-16 h-16 rounded-full bg-indigo-500/20 flex items-center justify-center mx-auto mb-6">
                        <Key className="w-8 h-8 text-indigo-400" />
                    </div>
                    <h2 className="text-xl font-semibold text-white mb-2">{t('strategy.binance.setupTitle')}</h2>
                    <p className="text-slate-400 text-sm mb-6">{t('strategy.binance.setupDesc')}</p>
                    <button onClick={() => window.dispatchEvent(new CustomEvent('openSettings', { detail: 'exchange' }))}
                        className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-medium flex items-center justify-center gap-2">
                        <Settings className="w-5 h-5" /> {t('strategy.binance.goToSettings')}
                    </button>
                </div>
            </div>
        );
    }


    return (
        <div className="flex-1 flex flex-col bg-[#0d1117] overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-slate-700/50">
                <div className="flex items-center gap-3">
                    <Activity className="w-6 h-6 text-indigo-400" />
                    <h1 className="text-xl font-semibold text-white">{t('strategy.title')}</h1>
                </div>
                <div className="flex items-center gap-3">
                    {/* Strategy Settings Button */}
                    <button
                        onClick={() => setIsSettingsOpen(true)}
                        className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all bg-indigo-500/10 text-indigo-400 hover:bg-indigo-500/20 border border-indigo-500/20"
                    >
                        <Settings className="w-3.5 h-3.5" />
                        {t('strategy.settings.title', '交易设置')}
                    </button>

                    {/* Manual Trigger Button (Debug) */}
                    <button 
                        onClick={runAnalysis} 
                        disabled={analysisLoading}
                        className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all bg-slate-800/50 text-slate-400 hover:text-white border border-slate-700/50"
                    >
                        <Settings className={`w-3.5 h-3.5 ${analysisLoading ? 'animate-spin' : ''}`} />
                        {analysisLoading ? '分析中...' : '调试分析'}
                    </button>

                    {/* Main Trading Toggle */}
                    <button onClick={toggleTrading} disabled={binanceLoading}
                        className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-all shadow-lg hover:scale-[1.02] active:scale-95 ${binanceStatus?.is_trading_enabled
                            ? 'bg-red-500 hover:bg-red-600 text-white shadow-red-500/20'
                            : 'bg-green-600 hover:bg-green-700 text-white shadow-green-500/20'
                            }`}>
                        {binanceStatus?.is_trading_enabled
                            ? <><Square className="w-4 h-4 fill-current" /> {t('strategy.binance.stopTrading')}</>
                            : <><Play className="w-4 h-4 fill-current" /> {t('strategy.binance.startTrading')}</>}
                    </button>
                </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-4 gap-4 p-4">
                <StatCard icon={<Wallet className="w-5 h-5" />} label={t('strategy.equity')}
                    value={`$${(wallet?.equity || 0).toFixed(2)}`} color="indigo" />
                <StatCard icon={<DollarSign className="w-5 h-5" />} label={t('strategy.realizedPnL')}
                    value={`${(wallet?.total_pnl || 0) >= 0 ? '+' : ''}$${(wallet?.total_pnl || 0).toFixed(2)}`}
                    subtext={(() => {
                        // 计算投入本金：权益 - 已实现盈亏 - 未实现盈亏
                        const equity = wallet?.equity || 0;
                        const realizedPnl = wallet?.total_pnl || 0;
                        const unrealizedPnl = wallet?.unrealized_pnl || 0;
                        const principal = equity - realizedPnl - unrealizedPnl;
                        // 避免除零，且本金必须为正数才有意义
                        const returnRate = principal > 0 ? (realizedPnl / principal * 100) : 0;
                        return `${returnRate.toFixed(1)}% 回报`;
                    })()}
                    color={(wallet?.total_pnl || 0) >= 0 ? "green" : "red"} />
                <StatCard icon={(wallet?.unrealized_pnl || 0) >= 0 ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
                    label={t('strategy.unrealizedPnL')}
                    value={`${(wallet?.unrealized_pnl || 0) >= 0 ? '+' : ''}$${(wallet?.unrealized_pnl || 0).toFixed(2)}`}
                    color={(wallet?.unrealized_pnl || 0) >= 0 ? "green" : "red"} />
                <StatCard icon={<Award className="w-5 h-5" />} label={t('strategy.winRate')}
                    value={`${wallet?.win_rate || 0}%`}
                    subtext={`${wallet?.win_trades || 0}/${wallet?.total_trades || 0} 笔`} color="amber" />
            </div>

            {/* Main Content */}
            <div className="flex-1 flex flex-col md:flex-row gap-4 p-4 pt-0 overflow-hidden">
                {/* Left: Lists */}
                <div className="flex-1 flex flex-col gap-4 overflow-hidden">
                    {/* Tabs */}
                    <div className="flex gap-2 flex-shrink-0">
                        <button onClick={() => setActiveTab('positions')}
                            className={`px-4 py-2 rounded-lg text-sm flex items-center gap-2 transition-colors ${activeTab === 'positions' ? 'bg-indigo-500 text-white' : 'bg-slate-800/50 text-slate-400 hover:text-white'}`}>
                            <Layers className="w-4 h-4" /> {t('strategy.tabs.positions')}
                        </button>
                        <button onClick={() => setActiveTab('history')}
                            className={`px-4 py-2 rounded-lg text-sm flex items-center gap-2 transition-colors ${activeTab === 'history' ? 'bg-indigo-500 text-white' : 'bg-slate-800/50 text-slate-400 hover:text-white'}`}>
                            <History className="w-4 h-4" /> {t('strategy.tabs.history')}
                        </button>
                        <button onClick={() => setActiveTab('orders')}
                            className={`px-4 py-2 rounded-lg text-sm flex items-center gap-2 transition-colors ${activeTab === 'orders' ? 'bg-indigo-500 text-white' : 'bg-slate-800/50 text-slate-400 hover:text-white'}`}>
                            <ListFilter className="w-4 h-4" /> {t('strategy.tabs.orders')}
                        </button>
                    </div>

                    {/* Content Area */}
                    <div className="flex-1 bg-[#131722] rounded-xl border border-slate-700/50 overflow-hidden flex flex-col">
                        {activeTab === 'positions' && <PositionsTable positions={positions} t={t} />}

                        {activeTab === 'history' && <HistoryTable trades={tradeHistory} t={t} />}

                        {activeTab === 'orders' && (
                            <div className="flex flex-col h-full">
                                {/* Order Sub-Filter */}
                                <div className="flex border-b border-slate-700/50 px-4">
                                    <button onClick={() => setOrderFilter('OPEN')}
                                        className={`px-3 py-2 text-xs font-medium border-b-2 transition-colors ${orderFilter === 'OPEN' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-slate-500 hover:text-white'}`}>
                                        {t('strategy.orders.current', '当前委托')}
                                    </button>
                                    <button onClick={() => setOrderFilter('HISTORY')}
                                        className={`px-3 py-2 text-xs font-medium border-b-2 transition-colors ${orderFilter === 'HISTORY' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-slate-500 hover:text-white'}`}>
                                        {t('strategy.orders.history', '历史委托')}
                                    </button>
                                </div>
                                <OrdersTable orders={orderFilter === 'OPEN' ? openOrders : historyOrders} isHistory={orderFilter === 'HISTORY'} t={t} />
                            </div>
                        )}
                    </div>
                </div>

                {/* Right: Logs */}
                <div className="w-full md:w-96 flex flex-col min-h-0 bg-[#131722] rounded-xl border border-slate-700/50 overflow-hidden">
                    <div className="p-3 border-b border-slate-700/50 flex-shrink-0">
                        <h3 className="text-sm font-medium text-white flex items-center gap-2">
                            <Clock className="w-4 h-4 text-slate-400" /> {t('strategy.logs.title')}
                        </h3>
                    </div>
                    <div ref={logsContainerRef} onScroll={handleLogsScroll} className="flex-1 min-h-0 overflow-y-auto p-2 space-y-2">
                        {logs.length > 0 ? (
                            logs.map((log, idx) => (
                                <LogEntry key={log.id || idx} log={log}
                                    isExpanded={expandedLog === (log.id || idx)}
                                    onToggle={() => setExpandedLog(expandedLog === (log.id || idx) ? null : (log.id || idx))} />
                            ))
                        ) : (
                            <div className="text-center text-slate-500 py-8 text-sm">{t('strategy.logs.noLogs')}</div>
                        )}
                        {logsLoading && <div className="text-center text-slate-500 py-2 text-xs">加载中...</div>}
                    </div>
                </div>
            </div>

            {/* Settings Modal */}
            <StrategySettingsModal 
                isOpen={isSettingsOpen} 
                onClose={() => setIsSettingsOpen(false)} 
                userId={userId} 
            />

            {/* Validation Modal */}
            <ValidationModal 
                isOpen={showValidationModal} 
                onClose={() => setShowValidationModal(false)} 
                data={validationData}
                onGoToSettings={onOpenSettings}
                onOpenQuickSettings={() => setIsSettingsOpen(true)}
            />
        </div>
    );
}

// --- Sub Components ---

function StatCard({ icon, label, value, subtext, color }) {
    const colors = {
        indigo: 'text-indigo-400 bg-indigo-500/10',
        green: 'text-green-400 bg-green-500/10',
        red: 'text-red-400 bg-red-500/10',
        amber: 'text-amber-400 bg-amber-500/10'
    };
    return (
        <div className="bg-[#131722] rounded-xl p-4 border border-slate-700/50">
            <div className="flex items-center gap-2 mb-2">
                <div className={`p-1.5 rounded-lg ${colors[color]}`}>{icon}</div>
                <span className="text-slate-400 text-sm">{label}</span>
            </div>
            <div className={`text-xl font-semibold ${colors[color].split(' ')[0]}`}>{value}</div>
            {subtext && <div className="text-xs text-slate-500 mt-1">{subtext}</div>}
        </div>
    );
}

function PositionsTable({ positions, t }) {
    if (!positions?.length) return <EmptyState text={t('strategy.positions.noPositions')} />;

    return (
        <div className="overflow-auto h-full">
            <table className="w-full text-sm">
                <thead className="sticky top-0 bg-[#131722] z-10">
                    <tr className="text-left text-slate-400 text-xs border-b border-slate-700/50">
                        <th className="p-3 bg-[#131722]">{t('strategy.positions.symbol')}</th>
                        <th className="p-3 bg-[#131722]">{t('strategy.positions.size')}</th>
                        <th className="p-3 bg-[#131722] text-right">{t('strategy.positions.entry')}</th>
                        <th className="p-3 bg-[#131722] text-right">{t('strategy.positions.mark')}</th>
                        <th className="p-3 bg-[#131722] text-right">{t('strategy.positions.pnl')}</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/30">
                    {positions.map((pos, idx) => {
                        const pnl = pos.unrealized_pnl || 0;
                        const roe = pos.margin > 0 ? (pnl / pos.margin * 100) : 0;
                        const notional = pos.notional_value || (pos.margin * pos.leverage);

                        return (
                            <tr key={idx} className="hover:bg-slate-800/30">
                                <td className="p-3">
                                    <div className="flex items-center gap-2">
                                        <span className="font-semibold text-white">{pos.symbol}</span>
                                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${pos.direction === 'LONG' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                                            {pos.leverage}x {pos.direction}
                                        </span>
                                    </div>
                                </td>
                                <td className="p-3">
                                    <div className="text-white">${notional?.toFixed(0)}</div>
                                    <div className="text-[10px] text-slate-500">Margin: ${pos.margin?.toFixed(2)}</div>
                                </td>
                                <td className="p-3 text-right font-mono text-slate-300">${pos.entry_price?.toFixed(2)}</td>
                                <td className="p-3 text-right font-mono text-slate-300">${pos.current_price?.toFixed(2)}</td>
                                <td className="p-3 text-right">
                                    <div className={`font-medium ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                        {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
                                    </div>
                                    <div className={`text-xs ${roe >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                        {roe.toFixed(2)}%
                                    </div>
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}

function HistoryTable({ trades, t }) {
    if (!trades?.length) return <EmptyState text={t('strategy.history.noHistory')} />;

    const formatTime = (ts) => {
        const d = new Date(ts);
        return `${(d.getMonth() + 1).toString().padStart(2, '0')}-${d.getDate().toString().padStart(2, '0')} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;
    };

    return (
        <div className="overflow-auto h-full">
            <table className="w-full text-sm">
                <thead className="sticky top-0 bg-[#131722] z-10">
                    <tr className="text-left text-slate-400 text-xs border-b border-slate-700/50">
                        <th className="p-3 bg-[#131722] whitespace-nowrap">{t('strategy.orders.time')}</th>
                        <th className="p-3 bg-[#131722]">{t('strategy.orders.symbol')}</th>
                        <th className="p-3 bg-[#131722]">{t('strategy.orders.direction')}</th>
                        <th className="p-3 bg-[#131722] text-right">{t('strategy.orders.price')}</th>
                        <th className="p-3 bg-[#131722] text-right">{t('strategy.orders.quantity')}</th>
                        <th className="p-3 bg-[#131722] text-right">{t('strategy.orders.fee')}</th>
                        <th className="p-3 bg-[#131722] text-right">{t('strategy.realizedPnL')}</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/30">
                    {trades.map((trade, idx) => {
                        const isBuy = trade.side === 'BUY';
                        // FIX: Use correct keys from Backend (realized_pnl, quantity, commission_asset)
                        const pnl = parseFloat(trade.realized_pnl || 0);
                        const fee = parseFloat(trade.commission || 0);
                        const qty = parseFloat(trade.quantity || trade.qty || 0);

                        return (
                            <tr key={trade.id || idx} className="hover:bg-slate-800/30">
                                <td className="p-3 text-slate-400 whitespace-nowrap text-xs font-mono">{formatTime(trade.time)}</td>
                                <td className="p-3 font-semibold text-white">{trade.symbol}</td>
                                <td className="p-3">
                                    <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${isBuy ? 'text-green-400 bg-green-500/10' : 'text-red-400 bg-red-500/10'}`}>
                                        {isBuy ? '买入' : '卖出'} {trade.position_side && trade.position_side !== 'BOTH' ? trade.position_side : ''}
                                    </span>
                                </td>
                                <td className="p-3 text-right font-mono text-slate-300">{parseFloat(trade.price).toFixed(2)}</td>
                                <td className="p-3 text-right font-mono text-slate-300">{qty.toFixed(3)}</td>
                                <td className="p-3 text-right font-mono text-slate-500 text-xs">
                                    {fee > 0 ? `${fee.toFixed(4)} ${trade.commission_asset || ''}` : '-'}
                                </td>
                                <td className={`p-3 text-right font-mono font-medium ${pnl > 0 ? 'text-green-400' : (pnl < 0 ? 'text-red-400' : 'text-slate-500')}`}>
                                    {pnl !== 0 ? (<span>{pnl > 0 ? '+' : ''}{pnl.toFixed(2)}</span>) : '-'}
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}

function OrdersTable({ orders, isHistory, t }) {
    if (!orders?.length) return <EmptyState text={t('strategy.orders.noOrders')} />;

    const formatTime = (ts) => {
        const d = new Date(ts);
        return `${(d.getMonth() + 1).toString().padStart(2, '0')}-${d.getDate().toString().padStart(2, '0')} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
    };

    return (
        <div className="overflow-auto h-full">
            <table className="w-full text-sm">
                <thead className="sticky top-0 bg-[#131722] z-10">
                    <tr className="text-left text-slate-400 text-xs border-b border-slate-700/50">
                        <th className="p-3 bg-[#131722] min-w-[120px]">{t('strategy.orders.time')}</th>
                        <th className="p-3 bg-[#131722]">{t('strategy.orders.symbol')}</th>
                        <th className="p-3 bg-[#131722]">{t('strategy.orders.type')}</th>
                        <th className="p-3 bg-[#131722]">{t('strategy.orders.direction')}</th>
                        <th className="p-3 bg-[#131722] text-right">{t('strategy.orders.price')}</th>
                        <th className="p-3 bg-[#131722] text-right">{t('strategy.orders.quantity')}</th>
                        <th className="p-3 bg-[#131722] text-right">{isHistory ? '已成交' : '成交/总量'}</th>
                        <th className="p-3 bg-[#131722] text-right">{t('strategy.history.status')}</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/30">
                    {orders.map((order, idx) => {
                        const isBuy = order.side === 'BUY';
                        const filled = order.filled_quantity || order.executedQty || 0;
                        const total = order.quantity || order.origQty || 0;

                        return (
                            <tr key={order.id || idx} className="hover:bg-slate-800/30">
                                <td className="p-3 text-slate-400 whitespace-nowrap text-xs font-mono">{formatTime(order.created_at)}</td>
                                <td className="p-3 font-semibold text-white">{order.symbol}</td>
                                <td className="p-3 text-xs text-slate-300">{order.type?.replace('_', ' ')}</td>
                                <td className="p-3">
                                    <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${isBuy ? 'text-green-400 bg-green-500/10' : 'text-red-400 bg-red-500/10'}`}>
                                        {isBuy ? '买入' : '卖出'}
                                    </span>
                                </td>
                                <td className="p-3 text-right font-mono text-white">{order.price > 0 ? parseFloat(order.price).toFixed(2) : '市价'}</td>
                                <td className="p-3 text-right font-mono text-slate-300">{parseFloat(total).toFixed(3)}</td>
                                <td className="p-3 text-right font-mono text-slate-400 text-xs">
                                    {isHistory ? filled.toFixed(3) : `${filled.toFixed(3)} / ${total.toFixed(3)}`}
                                </td>
                                <td className="p-3 text-right">
                                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${order.status === 'FILLED' ? 'bg-green-500/20 text-green-400' :
                                        order.status === 'CANCELED' ? 'bg-slate-500/20 text-slate-400' :
                                            'bg-amber-500/20 text-amber-400'
                                        }`}>
                                        {order.status}
                                    </span>
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}

function LogEntry({ log, isExpanded, onToggle }) {
    return (
        <div className="bg-slate-800/30 rounded-lg overflow-hidden border border-slate-700/30">
            <button onClick={onToggle} className="w-full p-3 flex items-start gap-2 text-left hover:bg-slate-700/30 transition-colors">
                {isExpanded ? <ChevronDown className="w-4 h-4 text-slate-400 mt-0.5" /> : <ChevronRight className="w-4 h-4 text-slate-400 mt-0.5" />}
                <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                        <span className="text-xs text-slate-500 font-mono">{log.round_id}</span>
                        {log.strategy_decision && <span className="text-[10px] bg-indigo-500/20 text-indigo-300 px-1 rounded">Decision</span>}
                    </div>
                    <div className="text-xs text-slate-300 mt-1 truncate">{log.market_analysis?.substring(0, 50)}...</div>
                </div>
            </button>
            {isExpanded && (
                <div className="px-3 pb-3 space-y-2 border-t border-slate-700/30 pt-2 bg-slate-800/20">
                    {['market_analysis', 'position_check', 'strategy_decision'].map(field => log[field] && (
                        <div key={field}>
                            <div className="text-[10px] text-slate-500 uppercase mb-0.5">{field.replace('_', ' ')}</div>
                            <div className="text-xs text-slate-300 whitespace-pre-wrap font-mono bg-[#0d1117] p-2 rounded border border-slate-700/30">{log[field]}</div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

function EmptyState({ text }) {
    return (
        <div className="flex flex-col items-center justify-center h-full text-slate-500 gap-2">
            <div className="w-12 h-12 rounded-full bg-slate-800/50 flex items-center justify-center">
                <ListFilter className="w-6 h-6 text-slate-600" />
            </div>
            <span className="text-sm">{text}</span>
        </div>
    );
}
function ValidationModal({ isOpen, onClose, data, onGoToSettings, onOpenQuickSettings }) {
    if (!isOpen) return null;


    const checks = [
        { key: 'binance', label: '交易所接口（Binance）', icon: <Key className="w-4 h-4" />, tab: 'exchange' },
        { key: 'llm', label: '大模型配置（API Key）', icon: <Cpu className="w-4 h-4" />, tab: 'llm' },
        { key: 'strategy', label: '策略参数配置', icon: <Target className="w-4 h-4" />, 
          tab: 'quick-settings' // 特殊处理，用于打开组件内部的配置弹窗
        }
    ];

    const details = data?.details || {};

    return (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/80 backdrop-blur-md px-4 py-8 animate-in fade-in duration-300">
            <div className="bg-[#1a1f2e] border border-white/10 w-full max-w-md rounded-2xl overflow-hidden shadow-2xl">
                <div className="p-6">
                    <div className="flex items-center justify-between mb-6 text-left">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-red-500/10 flex items-center justify-center">
                                <AlertCircle className="w-6 h-6 text-red-400" />
                            </div>
                            <h2 className="text-xl font-bold text-white">启动限制</h2>
                        </div>
                        <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors p-1 rounded-lg hover:bg-white/5">
                            <X className="w-5 h-5" />
                        </button>
                    </div>

                    <p className="text-slate-400 text-sm mb-6 leading-relaxed text-left">
                        在开启系统自动执行前，我们需要确保以下所有前置条件已正确配置：
                    </p>

                    <div className="space-y-3 mb-8">
                        {checks.map(check => {
                            const status = details[check.key];
                            return (
                                <div key={check.key} className="flex items-center justify-between p-4 bg-white/5 rounded-xl border border-white/5 group hover:bg-white/10 transition-colors">
                                    <div className="flex items-center gap-3 text-left">
                                        <div className={`p-2 rounded-lg ${status?.ok ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                                            {check.icon}
                                        </div>
                                        <div>
                                            <span className="text-xs text-slate-500 block uppercase font-bold tracking-wider">{check.label}</span>
                                            <span className={`text-sm font-medium ${status?.ok ? 'text-emerald-300' : 'text-red-300'}`}>
                                                {status?.message || '未知状态'}
                                            </span>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        {status?.ok ? (
                                            <CheckCircle className="w-5 h-5 text-emerald-500" />
                                        ) : (
                                            <button 
                                                onClick={() => {
                                                    onClose();
                                                    if (check.tab === 'quick-settings') {
                                                        onOpenQuickSettings?.();
                                                    } else {
                                                        onGoToSettings(check.tab);
                                                    }
                                                }}
                                                className="text-[10px] bg-red-500/20 hover:bg-red-500/40 text-red-300 px-2 py-1 rounded transition-all border border-red-500/20"
                                            >
                                                去配置
                                            </button>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>

                    <button 
                        onClick={onClose}
                        className="w-full py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-bold transition-all border border-slate-700 active:scale-95"
                    >
                        知道了
                    </button>
                </div>
            </div>
        </div>
    );
}
