import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
    TrendingUp, TrendingDown, DollarSign, Target,
    ChevronDown, ChevronRight, Activity, Wallet,
    ArrowUpCircle, ArrowDownCircle, Clock, Percent,
    Award
} from 'lucide-react';
import TerminalLoader from './TerminalLoader';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export default function StrategyNexus({ onBack }) {
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
    const [showLoader, setShowLoader] = useState(true); // 控制加载动画显示

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 10000); // Refresh every 10s
        return () => clearInterval(interval);
    }, []);

    const fetchData = async () => {
        try {
            const [walletRes, posRes, closedRes, ordersRes, logsRes, curveRes] = await Promise.all([
                fetch(`${BASE_URL}/api/strategy/wallet`).then(r => r.json()),
                fetch(`${BASE_URL}/api/strategy/positions?status=OPEN`).then(r => r.json()),
                fetch(`${BASE_URL}/api/strategy/positions?status=CLOSED`).then(r => r.json()),
                fetch(`${BASE_URL}/api/strategy/orders?limit=50`).then(r => r.json()),
                fetch(`${BASE_URL}/api/strategy/logs?limit=20`).then(r => r.json()),
                fetch(`${BASE_URL}/api/strategy/equity-curve`).then(r => r.json())
            ]);

            setWallet(walletRes);
            setPositions(posRes.positions || []);
            setClosedPositions(closedRes.positions || []);
            setOrders(ordersRes.orders || []);
            setLogs(logsRes.logs || []);
            setEquityCurve(curveRes.curve || []);
            setLoading(false);
        } catch (e) {
            console.error('Strategy data fetch error:', e);
            setLoading(false);
        }
    };

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
                    <span className="px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded-full">{t('strategy.live')}</span>
                </div>
                {/* Auto-refresh indicator */}
                <span className="text-xs text-slate-500">{t('strategy.autoRefresh')}</span>
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
                <div className="w-full md:w-96 flex flex-col bg-[#131722] rounded-xl border border-slate-700/50 overflow-hidden">
                    <div className="p-3 border-b border-slate-700/50 flex-shrink-0">
                        <h3 className="text-sm font-medium text-white flex items-center gap-2">
                            <Clock className="w-4 h-4 text-slate-400" />
                            {t('strategy.logs.title')}
                        </h3>
                    </div>
                    <div className="flex-1 overflow-y-auto p-2 space-y-2">
                        {logs.filter(log => log.market_analysis || log.position_check || log.strategy_decision).length > 0
                            ? logs
                                .filter(log => log.market_analysis || log.position_check || log.strategy_decision)
                                .map((log, idx) => (
                                    <LogEntry
                                        key={idx}
                                        log={log}
                                        isExpanded={expandedLog === idx}
                                        onToggle={() => setExpandedLog(expandedLog === idx ? null : idx)}
                                        t={t}
                                    />
                                )) : (
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
                        const pnl = isClosed ? (pos.realized_pnl || 0) : (pos.unrealized_pnl || 0);
                        const leverage = pos.leverage || 10;
                        const margin = pos.margin || 0;
                        const notional = pos.notional_value || margin * leverage;
                        // ROE = (PnL / Margin) * 100% - this is the leveraged return
                        const roe = margin > 0 ? (pnl / margin * 100) : 0;

                        return (
                            <tr key={idx} className="border-b border-slate-700/30 hover:bg-slate-800/30">
                                {/* Symbol + Leverage badge */}
                                <td className="p-2">
                                    <div className="flex items-center gap-1">
                                        <span className="font-semibold text-white">{pos.symbol}</span>
                                        <span className="px-1.5 py-0.5 bg-amber-500/20 text-amber-400 text-[10px] rounded font-medium">
                                            {leverage}x
                                        </span>
                                    </div>
                                </td>
                                {/* Direction */}
                                <td className="p-2">
                                    <span className={`flex items-center gap-1 font-medium ${pos.direction === 'LONG' ? 'text-green-400' : 'text-red-400'}`}>
                                        {pos.direction === 'LONG' ? <ArrowUpCircle className="w-3.5 h-3.5" /> : <ArrowDownCircle className="w-3.5 h-3.5" />}
                                        {pos.direction === 'LONG' ? t('strategy.positions.long') : t('strategy.positions.short')}
                                    </span>
                                </td>
                                {/* Size: Margin + Notional */}
                                <td className="p-2">
                                    <div className="text-white">${notional.toFixed(0)}</div>
                                    <div className="text-[10px] text-slate-500">{t('strategy.positions.margin')} ${margin.toFixed(0)}</div>
                                </td>
                                {/* Entry Price */}
                                <td className="p-2 text-slate-300">
                                    ${pos.entry_price?.toFixed(2)}
                                </td>
                                {/* Current/Close Price */}
                                <td className="p-2 text-slate-300">
                                    ${(isClosed ? pos.close_price : pos.current_price)?.toFixed(2)}
                                </td>
                                {/* PnL with ROE */}
                                <td className={`p-2 text-right font-semibold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                    <div>{pnl >= 0 ? '+' : ''}{pnl.toFixed(2)} USDT</div>
                                    <div className={`text-xs ${roe >= 0 ? 'text-green-400/70' : 'text-red-400/70'}`}>
                                        {roe >= 0 ? '+' : ''}{roe.toFixed(2)}%
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

    return (
        <div className="overflow-x-auto h-full">
            <table className="w-max min-w-full text-sm">
                <thead className="sticky top-0 bg-[#131722]">
                    <tr className="text-left text-slate-400 text-xs border-b border-slate-700/50">
                        <th className="p-2 sticky left-0 bg-[#131722]">{t('strategy.orders.time')}</th>
                        <th className="p-2">{t('strategy.orders.symbol')}</th>
                        <th className="p-2">{t('strategy.orders.action')}</th>
                        <th className="p-2">{t('strategy.orders.price')}</th>
                        <th className="p-2">{t('strategy.orders.margin')}</th>
                        <th className="p-2">SL</th>
                        <th className="p-2">TP</th>
                        <th className="p-2">{t('strategy.orders.fee')}</th>
                        <th className="p-2">{t('strategy.history.status')}</th>
                    </tr>
                </thead>
                <tbody>
                    {orders.map((order, idx) => {
                        const isOpen = order.action?.includes('OPEN');
                        const isLong = order.action?.includes('LONG');
                        const isShort = order.action?.includes('SHORT');
                        const isClose = order.action?.includes('CLOSE');
                        const isModify = order.action?.includes('MODIFY');

                        // Color based on action
                        let actionColor = 'text-slate-300';
                        if (isLong) actionColor = 'text-green-400';
                        else if (isShort) actionColor = 'text-red-400';
                        else if (isClose) actionColor = 'text-amber-400';
                        else if (isModify) actionColor = 'text-blue-400';

                        return (
                            <tr key={idx} className="border-b border-slate-700/30 hover:bg-slate-800/30">
                                <td className="p-2 text-slate-400 whitespace-nowrap sticky left-0 bg-[#131722]">
                                    {formatTime(order.created_at)}
                                </td>
                                <td className="p-2 font-medium text-white">{order.symbol}</td>
                                <td className={`p-2 font-medium ${actionColor}`}>
                                    {order.action}
                                </td>
                                <td className="p-2 text-slate-300">
                                    {order.entry_price ? `$${order.entry_price.toFixed(2)}` : '-'}
                                </td>
                                <td className="p-2 text-slate-300">
                                    {order.margin ? `$${order.margin.toFixed(0)}` : '-'}
                                </td>
                                <td className="p-2 text-red-400/80">
                                    {order.stop_loss ? `$${order.stop_loss.toFixed(2)}` : '-'}
                                </td>
                                <td className="p-2 text-green-400/80">
                                    {order.take_profit ? `$${order.take_profit.toFixed(2)}` : '-'}
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
