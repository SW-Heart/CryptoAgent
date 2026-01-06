import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
    TrendingUp, TrendingDown, DollarSign, Target,
    ChevronDown, ChevronRight, Activity, Wallet,
    ArrowUpCircle, ArrowDownCircle, Clock, Percent,
    Award, Power
} from 'lucide-react';
import TerminalLoader from './TerminalLoader';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Admin user ID - must match backend STRATEGY_ADMIN_USER_ID
const ADMIN_USER_ID = 'ee20fa53-5ac2-44bc-9237-41b308e291d8';

export default function StrategyNexus({ userId, onBack }) {
    const { t } = useTranslation();
    const [wallet, setWallet] = useState(null);
    const [positions, setPositions] = useState([]);
    const [closedPositions, setClosedPositions] = useState([]);
    const [orders, setOrders] = useState([]);
    const [logs, setLogs] = useState([]);
    const [equityCurve, setEquityCurve] = useState([]);
    const [expandedLog, setExpandedLog] = useState(null);
    const [activeTab, setActiveTab] = useState('positions');
    const [loading, setLoading] = useState(true);
    const [showLoader, setShowLoader] = useState(true);

    // Logs pagination state
    const [logsHasMore, setLogsHasMore] = useState(true);
    const [logsLoading, setLogsLoading] = useState(false);
    const logsContainerRef = useRef(null);

    // Scheduler control state
    const [schedulerRunning, setSchedulerRunning] = useState(false);
    const [schedulerLoading, setSchedulerLoading] = useState(false);
    const isAdmin = userId === ADMIN_USER_ID;

    useEffect(() => {
        fetchData();
        fetchSchedulerStatus();
        const interval = setInterval(fetchData, 10000); // Refresh every 10s
        return () => clearInterval(interval);
    }, []);

    // Fetch scheduler status
    const fetchSchedulerStatus = async () => {
        try {
            const res = await fetch(`${BASE_URL}/api/strategy/scheduler/status`);
            const data = await res.json();
            setSchedulerRunning(data.running || false);
        } catch (e) {
            console.error('Scheduler status fetch error:', e);
        }
    };

    // Toggle scheduler on/off (admin only)
    const toggleScheduler = async () => {
        if (!isAdmin || schedulerLoading) return;

        setSchedulerLoading(true);
        try {
            const endpoint = schedulerRunning ? 'stop' : 'start';
            const res = await fetch(`${BASE_URL}/api/strategy/scheduler/${endpoint}?user_id=${userId}`, {
                method: 'POST'
            });
            const data = await res.json();
            if (data.success) {
                setSchedulerRunning(!schedulerRunning);
            } else {
                console.error('Scheduler toggle failed:', data.message);
            }
        } catch (e) {
            console.error('Scheduler toggle error:', e);
        } finally {
            setSchedulerLoading(false);
        }
    };

    const fetchData = async () => {
        try {
            const [walletRes, posRes, closedRes, ordersRes, logsRes, curveRes] = await Promise.all([
                fetch(`${BASE_URL}/api/strategy/wallet`).then(r => r.json()),
                fetch(`${BASE_URL}/api/strategy/positions?status=OPEN`).then(r => r.json()),
                fetch(`${BASE_URL}/api/strategy/positions?status=CLOSED`).then(r => r.json()),
                fetch(`${BASE_URL}/api/strategy/orders?limit=50`).then(r => r.json()),
                fetch(`${BASE_URL}/api/strategy/logs?limit=20&offset=0`).then(r => r.json()),
                fetch(`${BASE_URL}/api/strategy/equity-curve`).then(r => r.json())
            ]);

            setWallet(walletRes);
            setPositions(posRes.positions || []);
            setClosedPositions(closedRes.positions || []);
            setOrders(ordersRes.orders || []);
            setLogs(logsRes.logs || []);
            setLogsHasMore(logsRes.has_more || false);
            setEquityCurve(curveRes.curve || []);
            setLoading(false);
        } catch (e) {
            console.error('Strategy data fetch error:', e);
            setLoading(false);
        }
    };

    // Load more logs (infinite scroll)
    const loadMoreLogs = useCallback(async () => {
        if (logsLoading || !logsHasMore) return;

        setLogsLoading(true);
        try {
            const offset = logs.length;
            const res = await fetch(`${BASE_URL}/api/strategy/logs?limit=20&offset=${offset}`);
            const data = await res.json();

            if (data.logs && data.logs.length > 0) {
                setLogs(prev => [...prev, ...data.logs]);
                setLogsHasMore(data.has_more || false);
            } else {
                setLogsHasMore(false);
            }
        } catch (e) {
            console.error('Load more logs error:', e);
        } finally {
            setLogsLoading(false);
        }
    }, [logs.length, logsLoading, logsHasMore]);

    // Handle logs scroll to detect reaching bottom
    const handleLogsScroll = useCallback((e) => {
        const { scrollTop, scrollHeight, clientHeight } = e.target;
        // Load more when scrolled to near bottom (within 50px)
        if (scrollHeight - scrollTop - clientHeight < 50 && logsHasMore && !logsLoading) {
            loadMoreLogs();
        }
    }, [loadMoreLogs, logsHasMore, logsLoading]);

    // Use backend-calculated values
    const totalUnrealizedPnL = wallet?.unrealized_pnl || 0;
    const equity = wallet?.equity || 0;

    // 显示加载器直到数据加载完成并完成动画
    if (showLoader) {
        return (
            <TerminalLoader
                fullScreen={false}
                isReady={!loading}
                onComplete={() => setShowLoader(false)}
            />
        );
    }

    const tabLabels = {
        positions: t('strategy.tabs.positions'),
        history: t('strategy.tabs.history'),
        orders: t('strategy.tabs.orders')
    };

    return (
        <div className="flex-1 flex flex-col bg-[#0d1117] overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-slate-700/50">
                <div className="flex items-center gap-3">
                    <Activity className="w-6 h-6 text-indigo-400" />
                    <h1 className="text-xl font-semibold text-white">{t('strategy.title')}</h1>
                    <span className={`px-2 py-0.5 text-xs rounded-full ${schedulerRunning ? 'bg-green-500/20 text-green-400' : 'bg-slate-500/20 text-slate-400'}`}>
                        {schedulerRunning ? t('strategy.scheduler.running') : t('strategy.scheduler.stopped')}
                    </span>
                </div>
                <div className="flex items-center gap-3">
                    {/* Scheduler Toggle (Admin Only) */}
                    {isAdmin && (
                        <button
                            onClick={toggleScheduler}
                            disabled={schedulerLoading}
                            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${schedulerRunning
                                ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                                : 'bg-green-500/20 text-green-400 hover:bg-green-500/30'
                                } ${schedulerLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
                            title={schedulerRunning ? t('strategy.scheduler.stop') : t('strategy.scheduler.start')}
                        >
                            <Power className={`w-4 h-4 ${schedulerLoading ? 'animate-pulse' : ''}`} />
                            {schedulerRunning ? t('strategy.scheduler.stop') : t('strategy.scheduler.start')}
                        </button>
                    )}
                    {/* Auto-refresh indicator */}
                    <span className="text-xs text-slate-500">{t('strategy.autoRefresh')}</span>
                </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-4 gap-4 p-4">
                <StatCard
                    icon={<Wallet className="w-5 h-5" />}
                    label={t('strategy.equity')}
                    value={`$${equity.toFixed(2)}`}
                    color="indigo"
                />
                <StatCard
                    icon={<DollarSign className="w-5 h-5" />}
                    label={t('strategy.available')}
                    value={`$${wallet?.current_balance?.toFixed(2) || '0.00'}`}
                    color="blue"
                />
                <StatCard
                    icon={totalUnrealizedPnL >= 0 ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
                    label={t('strategy.unrealizedPnL')}
                    value={`${totalUnrealizedPnL >= 0 ? '+' : ''}$${totalUnrealizedPnL.toFixed(2)}`}
                    color={totalUnrealizedPnL >= 0 ? "green" : "red"}
                />
                <StatCard
                    icon={<Award className="w-5 h-5" />}
                    label={t('strategy.winRate')}
                    value={`${wallet?.win_rate || 0}%`}
                    subtext={`${wallet?.win_trades || 0}/${wallet?.total_trades || 0} ${t('strategy.trades')}`}
                    color="amber"
                />
            </div>

            {/* Main Content */}
            <div className="flex-1 flex flex-col md:flex-row gap-4 p-4 pt-0 overflow-hidden">
                {/* Left: Positions & Orders */}
                <div className="flex-1 flex flex-col gap-4 overflow-hidden">
                    {/* Tabs */}
                    <div className="flex gap-2 flex-shrink-0">
                        {['positions', 'history', 'orders'].map(tab => (
                            <button
                                key={tab}
                                onClick={() => setActiveTab(tab)}
                                className={`px-4 py-2 rounded-lg text-sm capitalize transition-colors ${activeTab === tab
                                    ? 'bg-indigo-500 text-white'
                                    : 'bg-slate-800/50 text-slate-400 hover:text-white'
                                    }`}
                            >
                                {tabLabels[tab]}
                            </button>
                        ))}
                    </div>

                    {/* Content */}
                    <div className="flex-1 bg-[#131722] rounded-xl border border-slate-700/50 overflow-hidden">
                        {activeTab === 'positions' && (
                            <PositionsTable positions={positions} t={t} />
                        )}
                        {activeTab === 'history' && (
                            <PositionsTable positions={closedPositions} isClosed t={t} />
                        )}
                        {activeTab === 'orders' && (
                            <OrdersTable orders={orders} t={t} />
                        )}
                    </div>
                </div>

                {/* Right: Strategy Logs */}
                <div className="w-full md:w-96 flex flex-col min-h-0 bg-[#131722] rounded-xl border border-slate-700/50 overflow-hidden">
                    <div className="p-3 border-b border-slate-700/50 flex-shrink-0">
                        <h3 className="text-sm font-medium text-white flex items-center gap-2">
                            <Clock className="w-4 h-4 text-slate-400" />
                            {t('strategy.logs.title')}
                        </h3>
                    </div>
                    <div
                        ref={logsContainerRef}
                        onScroll={handleLogsScroll}
                        className="flex-1 min-h-0 overflow-y-auto p-2 space-y-2"
                    >
                        {logs.filter(log => log.market_analysis || log.position_check || log.strategy_decision).length > 0
                            ? (<>
                                {logs
                                    .filter(log => log.market_analysis || log.position_check || log.strategy_decision)
                                    .map((log, idx) => (
                                        <LogEntry
                                            key={log.id || idx}
                                            log={log}
                                            isExpanded={expandedLog === (log.id || idx)}
                                            onToggle={() => setExpandedLog(expandedLog === (log.id || idx) ? null : (log.id || idx))}
                                            t={t}
                                        />
                                    ))}
                                {/* Load More Button (Manual trigger if scroll ignores) */}
                                {logsHasMore && !logsLoading && (
                                    <button
                                        onClick={loadMoreLogs}
                                        className="w-full py-2 text-xs text-indigo-400 hover:text-indigo-300 hover:bg-slate-800/50 transition-colors border-t border-slate-700/30 mt-2"
                                    >
                                        {t('strategy.logs.loadMore', 'Load More')}
                                    </button>
                                )}
                                {/* Loading indicator */}
                                {logsLoading && (
                                    <div className="text-center text-slate-500 py-3 text-xs">
                                        {t('strategy.logs.loading', 'Loading...')}
                                    </div>
                                )}
                                {/* No more logs indicator */}
                                {!logsHasMore && !logsLoading && (
                                    <div className="text-center text-slate-600 py-3 text-xs border-t border-slate-700/30 mt-2">
                                        {t('strategy.logs.noMore', 'No more logs')}
                                    </div>
                                )}
                            </>) : (
                                <div className="text-center text-slate-500 py-8 text-sm">
                                    {t('strategy.logs.noLogs')}
                                </div>
                            )}
                    </div>
                </div>
            </div>
        </div>
    );
}

function StatCard({ icon, label, value, subtext, color }) {
    const colorClasses = {
        indigo: 'text-indigo-400 bg-indigo-500/10',
        blue: 'text-blue-400 bg-blue-500/10',
        green: 'text-green-400 bg-green-500/10',
        red: 'text-red-400 bg-red-500/10',
        amber: 'text-amber-400 bg-amber-500/10'
    };

    return (
        <div className="bg-[#131722] rounded-xl p-4 border border-slate-700/50">
            <div className="flex items-center gap-2 mb-2">
                <div className={`p-1.5 rounded-lg ${colorClasses[color]}`}>
                    {icon}
                </div>
                <span className="text-slate-400 text-sm">{label}</span>
            </div>
            <div className={`text-xl font-semibold ${colorClasses[color].split(' ')[0]}`}>
                {value}
            </div>
            {subtext && <div className="text-xs text-slate-500 mt-1">{subtext}</div>}
        </div>
    );
}

function PositionsTable({ positions, isClosed, t }) {
    if (positions.length === 0) {
        return (
            <div className="flex items-center justify-center h-full text-slate-500 text-sm">
                {isClosed ? t('strategy.history.noHistory') : t('strategy.positions.noPositions')}
            </div>
        );
    }

    return (
        <div className="overflow-auto h-full">
            <table className="w-full text-sm">
                <thead className="sticky top-0 bg-[#131722]">
                    <tr className="text-left text-slate-400 text-xs border-b border-slate-700/50">
                        <th className="p-2">{t('strategy.positions.symbol')}</th>
                        <th className="p-2">{t('strategy.positions.side')}</th>
                        <th className="p-2">{t('strategy.positions.size')}</th>
                        <th className="p-2">{t('strategy.positions.entry')}</th>
                        <th className="p-2">{isClosed ? t('strategy.history.closePrice') : t('strategy.positions.mark')}</th>
                        <th className="p-2 text-right">{t('strategy.positions.pnl')}</th>
                    </tr>
                </thead>
                <tbody>
                    {positions.map((pos, idx) => {
                        const unrealizedPnl = pos.unrealized_pnl || 0;
                        const realizedPnl = pos.realized_pnl || 0;
                        const pnl = isClosed ? realizedPnl : unrealizedPnl;
                        const leverage = pos.leverage || 10;
                        const margin = pos.margin || 0;
                        const notional = pos.notional_value || margin * leverage;
                        // ROE = (PnL / Margin) * 100% - this is the leveraged return
                        const roe = margin > 0 ? (pnl / margin * 100) : 0;

                        // 阶段性平仓状态
                        const hasPartialClose = (pos.closed_quantity || 0) > 0;
                        const closedQty = pos.closed_quantity || 0;
                        const remainingQty = pos.remaining_quantity || pos.quantity;

                        return (
                            <tr key={idx} className="border-b border-slate-700/30 hover:bg-slate-800/30">
                                {/* Symbol + Leverage badge + Partial close indicator */}
                                <td className="p-2">
                                    <div className="flex items-center gap-1">
                                        <span className="font-semibold text-white">{pos.symbol}</span>
                                        <span className="px-1.5 py-0.5 bg-amber-500/20 text-amber-400 text-[10px] rounded font-medium">
                                            {leverage}x
                                        </span>
                                        {hasPartialClose && !isClosed && (
                                            <span className="px-1.5 py-0.5 bg-cyan-500/20 text-cyan-400 text-[10px] rounded font-medium">
                                                部分平仓
                                            </span>
                                        )}
                                    </div>
                                </td>
                                {/* Direction */}
                                <td className="p-2">
                                    <span className={`flex items-center gap-1 font-medium ${pos.direction === 'LONG' ? 'text-green-400' : 'text-red-400'}`}>
                                        {pos.direction === 'LONG' ? <ArrowUpCircle className="w-3.5 h-3.5" /> : <ArrowDownCircle className="w-3.5 h-3.5" />}
                                        {pos.direction === 'LONG' ? t('strategy.positions.long') : t('strategy.positions.short')}
                                    </span>
                                </td>
                                {/* Size: 显示剩余仓位信息 */}
                                <td className="p-2">
                                    <div className="text-white">${notional.toFixed(0)}</div>
                                    <div className="text-[10px] text-slate-500">
                                        {t('strategy.positions.margin')} ${margin.toFixed(0)}
                                        {hasPartialClose && !isClosed && (
                                            <span className="text-cyan-400 ml-1">
                                                (剩 {((remainingQty / pos.quantity) * 100).toFixed(0)}%)
                                            </span>
                                        )}
                                    </div>
                                </td>
                                {/* Entry Price */}
                                <td className="p-2 text-slate-300">
                                    ${pos.entry_price?.toFixed(2)}
                                </td>
                                {/* Current/Close Price */}
                                <td className="p-2 text-slate-300">
                                    ${(isClosed ? pos.close_price : pos.current_price)?.toFixed(2)}
                                </td>
                                {/* PnL with ROE + 已实现盈亏 */}
                                <td className={`p-2 text-right font-semibold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                    <div>{pnl >= 0 ? '+' : ''}{pnl.toFixed(2)} USDT</div>
                                    <div className={`text-xs ${roe >= 0 ? 'text-green-400/70' : 'text-red-400/70'}`}>
                                        {roe >= 0 ? '+' : ''}{roe.toFixed(2)}%
                                    </div>
                                    {hasPartialClose && !isClosed && realizedPnl !== 0 && (
                                        <div className={`text-[10px] ${realizedPnl >= 0 ? 'text-cyan-400' : 'text-red-400/60'}`}>
                                            已实现: {realizedPnl >= 0 ? '+' : ''}{realizedPnl.toFixed(2)}
                                        </div>
                                    )}
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}

function OrdersTable({ orders, t }) {
    if (orders.length === 0) {
        return (
            <div className="flex items-center justify-center h-full text-slate-500 text-sm">
                {t('strategy.orders.noOrders')}
            </div>
        );
    }

    // Format time display
    const formatTime = (dateStr) => {
        if (!dateStr) return '-';
        const d = new Date(dateStr);
        return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
    };

    // Format action display with professional labels
    const formatAction = (action, direction) => {
        if (action?.includes('OPEN')) {
            return direction === 'LONG' ? '开多' : '开空';
        } else if (action?.includes('PARTIAL_CLOSE')) {
            // Extract percentage from action like "PARTIAL_CLOSE_50%"
            const match = action.match(/PARTIAL_CLOSE_(\d+)%/);
            const pct = match ? match[1] : '';
            return `部分止盈 ${pct}%`;
        } else if (action === 'CLOSE') {
            return '平仓';
        } else if (action?.includes('MODIFY')) {
            return '调整止盈止损';
        }
        return action;
    };

    return (
        <div className="overflow-x-auto h-full">
            <table className="w-max min-w-full text-sm">
                <thead className="sticky top-0 bg-[#131722]">
                    <tr className="text-left text-slate-400 text-xs border-b border-slate-700/50">
                        <th className="p-2 sticky left-0 bg-[#131722]">{t('strategy.orders.time')}</th>
                        <th className="p-2">{t('strategy.orders.symbol')}</th>
                        <th className="p-2">方向</th>
                        <th className="p-2">{t('strategy.orders.action')}</th>
                        <th className="p-2">数量</th>
                        <th className="p-2">{t('strategy.orders.price')}</th>
                        <th className="p-2">盈亏</th>
                        <th className="p-2">{t('strategy.orders.fee')}</th>
                        <th className="p-2">{t('strategy.history.status')}</th>
                    </tr>
                </thead>
                <tbody>
                    {orders.map((order, idx) => {
                        const isOpen = order.action?.includes('OPEN');
                        const isLong = order.direction === 'LONG';
                        const isPartialClose = order.action?.includes('PARTIAL_CLOSE');
                        const isClose = order.action === 'CLOSE';
                        const isModify = order.action?.includes('MODIFY');
                        const pnl = order.realized_pnl || 0;

                        // Color based on action
                        let actionColor = 'text-slate-300';
                        if (isOpen && isLong) actionColor = 'text-green-400';
                        else if (isOpen && !isLong) actionColor = 'text-red-400';
                        else if (isPartialClose) actionColor = 'text-cyan-400';
                        else if (isClose) actionColor = 'text-amber-400';
                        else if (isModify) actionColor = 'text-blue-400';

                        return (
                            <tr key={idx} className="border-b border-slate-700/30 hover:bg-slate-800/30">
                                <td className="p-2 text-slate-400 whitespace-nowrap sticky left-0 bg-[#131722]">
                                    {formatTime(order.created_at)}
                                </td>
                                <td className="p-2 font-medium text-white">{order.symbol}</td>
                                <td className="p-2">
                                    {order.direction && (
                                        <span className={`font-medium ${isLong ? 'text-green-400' : 'text-red-400'}`}>
                                            {isLong ? '多' : '空'}
                                        </span>
                                    )}
                                </td>
                                <td className={`p-2 font-medium ${actionColor}`}>
                                    {formatAction(order.action, order.direction)}
                                </td>
                                <td className="p-2 text-slate-300">
                                    {order.quantity ? order.quantity.toFixed(4) : '-'}
                                </td>
                                <td className="p-2 text-slate-300">
                                    {order.entry_price ? `$${order.entry_price.toFixed(2)}` : '-'}
                                </td>
                                <td className={`p-2 font-medium ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                    {pnl !== 0 ? `${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}` : '-'}
                                </td>
                                <td className="p-2 text-slate-500">
                                    {order.fee ? `$${order.fee.toFixed(2)}` : '-'}
                                </td>
                                <td className="p-2">
                                    <span className={`px-1.5 py-0.5 rounded text-[10px] ${order.status === 'FILLED' ? 'bg-green-500/20 text-green-400' : 'bg-slate-500/20 text-slate-400'
                                        }`}>
                                        {order.status || 'FILLED'}
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

function LogEntry({ log, isExpanded, onToggle, t }) {
    const hasAction = log.actions_taken && log.actions_taken !== '[]';

    return (
        <div className="bg-slate-800/30 rounded-lg overflow-hidden">
            <button
                onClick={onToggle}
                className="w-full p-3 flex items-start gap-2 text-left hover:bg-slate-700/30 transition-colors"
            >
                {isExpanded ? (
                    <ChevronDown className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
                ) : (
                    <ChevronRight className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-500">{log.round_id}</span>
                        {hasAction && (
                            <span className="px-1.5 py-0.5 bg-green-500/20 text-green-400 text-[10px] rounded">{t('strategy.logs.action')}</span>
                        )}
                    </div>
                    <div className="text-xs text-slate-400 mt-1">
                        {t('strategy.logs.symbols')}: {log.symbols || 'N/A'}
                    </div>
                </div>
            </button>

            {isExpanded && (
                <div className="px-3 pb-3 space-y-3 border-t border-slate-700/30 pt-3">
                    {log.market_analysis && (
                        <div>
                            <div className="text-[10px] text-slate-500 uppercase mb-1">Market Analysis</div>
                            <div className="text-xs text-slate-300 whitespace-pre-wrap">{log.market_analysis}</div>
                        </div>
                    )}
                    {log.position_check && (
                        <div>
                            <div className="text-[10px] text-slate-500 uppercase mb-1">Position Check</div>
                            <div className="text-xs text-slate-300 whitespace-pre-wrap">{log.position_check}</div>
                        </div>
                    )}
                    {log.strategy_decision && (
                        <div>
                            <div className="text-[10px] text-slate-500 uppercase mb-1">Strategy Decision</div>
                            <div className="text-xs text-slate-300 whitespace-pre-wrap">{log.strategy_decision}</div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
