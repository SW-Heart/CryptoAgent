import React, { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import {
    Activity,
    ChevronDown,
    Clock,
    DollarSign,
    RefreshCw,
    Play,
    Square,
    Loader2,
    TrendingUp,
    Zap,
    ShieldCheck,
    Wallet,
    CheckCircle2,
    AlertCircle,
    Cpu,
    Target,
    BarChart3,
    Plus,
    Globe,
    Trash2,
} from 'lucide-react';
import { getJson, postJson, putJson, deleteJson } from '../services/apiClient';
import Button from '../components/common/Button';
import Toast from '../components/common/Toast';
import OnboardingWizard from './OnboardingWizard';
import ConnectLLMModal from '../components/modals/ConnectLLMModal';
import ConfirmModal from '../components/modals/ConfirmModal';

// Extracted sub-components
import StatCard from './execution/StatCard';
import { CustomDropdown, MiniDropdown } from './execution/Dropdowns';
import DecisionCard from './execution/DecisionCard';
import { EXCHANGE_LOGOS, LLM_LOGOS } from './execution/constants';

// --- Main Page Component ---

export default function ExecutionPage({ userId }) {
    const [initialLoading, setInitialLoading] = useState(true);
    const [dataLoading, setDataLoading] = useState(false);
    const [acting, setActing] = useState(false);
    const [saving, setSaving] = useState(false);
    const [feedback, setFeedback] = useState(null);
    const [wallet, setWallet] = useState(null);
    const [positions, setPositions] = useState([]);
    const [orders, setOrders] = useState([]);
    const [tradeHistory, setTradeHistory] = useState([]);
    const [positionHistory, setPositionHistory] = useState([]);
    const [incomeHistory, setIncomeHistory] = useState([]);
    const [activeTab, setActiveTab] = useState('positions');
    const [statsPeriod, setStatsPeriod] = useState('all');
    const [strategies, setStrategies] = useState([]);
    const [accounts, setAccounts] = useState([]);
    const [llmConfigs, setLlmConfigs] = useState([]);
    const [logs, setLogs] = useState([]);
    const [activeTrader, setActiveTrader] = useState(null);
    const [traderInstances, setTraderInstances] = useState([]);
    const [isConnectingLLM, setIsConnectingLLM] = useState(false);
    const [showOnboarding, setShowOnboarding] = useState(false);
    const [showClearConfirm, setShowClearConfirm] = useState(false);
    const [clearing, setClearing] = useState(false);
    const [showClearLogsConfirm, setShowClearLogsConfirm] = useState(false);
    const [clearingLogs, setClearingLogs] = useState(false);
    const [pendingChanges, setPendingChanges] = useState({
        strategy_profile_id: '',
        exchange_account_id: '',
        llm_config_id: ''
    });
    const [hideBalance, setHideBalance] = useState(false);
    const [hidePnl, setHidePnl] = useState(false);
    const [hideWinRate, setHideWinRate] = useState(false);

    const isRunning = activeTrader?.status === 'RUNNING';

    const showFeedback = (msg, type) => {
        setFeedback({ msg, type });
        setTimeout(() => setFeedback(null), 3000);
    };

    const initializedRef = useRef(false);

    const fetchData = useCallback(async () => {
        if (!userId) return;
        try {
            const [traderRes, stratRes, accountRes, llmRes, logsRes] = await Promise.all([
                getJson(`/api/workspace/trader-instances?user_id=${userId}`),
                getJson(`/api/workspace/strategy-profiles?user_id=${userId}`),
                getJson(`/api/workspace/exchange-accounts?user_id=${userId}`),
                getJson(`/api/workspace/llm-configs?user_id=${userId}`),
                getJson(`/api/strategy/logs?user_id=${userId}&limit=20&_t=${Date.now()}`)
            ]);

            setStrategies(stratRes.profiles || []);
            setAccounts(accountRes.accounts || []);
            setLlmConfigs(llmRes.configs || []);
            setLogs(logsRes.logs || []);
            setTraderInstances(traderRes.traders || []);

            if (accountRes.accounts?.length === 0 || stratRes.profiles?.length === 0 || llmRes.configs?.length === 0) {
                setShowOnboarding(true);
            } else {
                setShowOnboarding(false);
            }

            if (traderRes.traders?.length > 0) {
                const primary = traderRes.traders[0];
                setActiveTrader(primary);

                // Only sync pendingChanges from the backend on FIRST load.
                // Subsequent polling should never overwrite local user edits.
                if (!initializedRef.current) {
                    initializedRef.current = true;
                    setPendingChanges({
                        strategy_profile_id: primary.strategy_profile_id || '',
                        exchange_account_id: primary.exchange_account_id || '',
                        llm_config_id: primary.llm_config_id || ''
                    });
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            setInitialLoading(false);
        }
    }, [userId]);

    const prevTraderIdRef = useRef(null);
    useEffect(() => {
        if (!activeTrader) return;
        const currentId = activeTrader.id;
        if (prevTraderIdRef.current !== currentId) {
            setDataLoading(true);
            
            // 如果是切换实例，清空旧数据
            if (prevTraderIdRef.current !== null) {
                setWallet(null);
                setPositions([]);
                setOrders([]);
                setTradeHistory([]);
                setPositionHistory([]);
                setIncomeHistory([]);
                setLogs([]);
            }
            
            // 由于 refreshMarket 已经包含了所有业务数据的抓取，包括 logs，
            // 首次选中或是切换都会在这里强制刷一次。
            // 使用 setTimeout 避开 react 严格模式下的连续调用冲突
            setTimeout(() => {
                refreshMarketRef.current();
            }, 0);
        }
        prevTraderIdRef.current = currentId;
    }, [activeTrader]);

    const refreshMarket = useCallback(async () => {
        if (!userId || showOnboarding) return;

        // 让前端不管是否属于 RUNNING 状态都持续同步一次底层交易所的状态和数据库的日志
        // 这样可以确保即使暂停，用户也能看到最新的余额与历史。
        if (!activeTrader) return;

        try {
            const [walletRes, posRes, ordersRes, historyRes, posHistRes, incomeRes, logsRes] = await Promise.all([
                getJson(`/api/strategy/wallet?user_id=${userId}&_t=${Date.now()}`),
                getJson(`/api/strategy/positions?status=OPEN&user_id=${userId}&_t=${Date.now()}`),
                getJson(`/api/strategy/orders?user_id=${userId}&status=OPEN&_t=${Date.now()}`),
                getJson(`/api/strategy/trade-history?user_id=${userId}&limit=50&_t=${Date.now()}`),
                getJson(`/api/strategy/position-history?user_id=${userId}&limit=100&_t=${Date.now()}`).catch(() => ({ positions: [] })),
                getJson(`/api/strategy/income-history?user_id=${userId}&limit=100&_t=${Date.now()}`).catch(() => ({ records: [] })),
                getJson(`/api/strategy/logs?user_id=${userId}&trader_instance_id=${activeTrader.id}&limit=20&_t=${Date.now()}`).catch(() => ({ logs: [] }))
            ]);
            if (!walletRes?.source?.includes('error')) {
                setWallet(walletRes || { current_balance: 0, total_pnl: 0, total_trades: 0, win_trades: 0 });
            }
            setPositions(posRes.positions || []);
            setOrders(ordersRes.orders || []);
            setTradeHistory(historyRes.trades || []);
            setPositionHistory(posHistRes.positions || []);
            setIncomeHistory(incomeRes.records || []);
            if (logsRes.logs && logsRes.logs.length > 0) {
                setLogs(logsRes.logs);
            }
        } catch (err) {
            console.error(err);
        } finally {
            setDataLoading(false);
        }
    }, [userId, showOnboarding, activeTrader]);

    const refreshMarketRef = useRef(refreshMarket);
    const fetchDataRef = useRef(fetchData);

    useEffect(() => {
        refreshMarketRef.current = refreshMarket;
        fetchDataRef.current = fetchData;
    }, [refreshMarket, fetchData]);

    useEffect(() => {
        if (!userId) return;
        fetchDataRef.current();
        refreshMarketRef.current();
        const timer = setInterval(() => {
            fetchDataRef.current();
            refreshMarketRef.current();
        }, 15000);
        return () => clearInterval(timer);
    }, [userId]);

    const handleAction = async (action) => {
        if (!activeTrader || acting) return;
        const lowerAction = action.toLowerCase();
        setActing(true);

        // 启动时立即清空旧数据，进入加载态，防止显示上一个交易所的残留数据
        if (lowerAction === 'start') {
            setDataLoading(true);
            setWallet(null);
            setPositions([]);
            setOrders([]);
            setTradeHistory([]);
            setPositionHistory([]);
            setIncomeHistory([]);
            setLogs([]);
        }

        try {
            await postJson(`/api/workspace/trader-instances/${activeTrader.id}/runtime-action?user_id=${userId}`, { action: lowerAction });
            if (lowerAction === 'start') {
                // 启动后并行拉取配置数据和市场数据，避免串行等待
                await Promise.all([fetchData(), refreshMarketRef.current()]);
            } else {
                await fetchData();
            }
            showFeedback(`${lowerAction === 'start' ? '已成功启动' : '已成功停止'}`, "success");
        } catch (err) {
            showFeedback(err.message || "操作失败，请重试", "error");
        } finally {
            setActing(false);
        }
    };

    const handleSaveInstance = async () => {
        if (!activeTrader || isRunning || saving) return;
        setSaving(true);
        try {
            await putJson(`/api/workspace/trader-instances/${activeTrader.id}?user_id=${userId}`, pendingChanges);
            await fetchData();
            showFeedback("配置已应用", "success");
        } catch (err) {
            showFeedback("应用失败", "error");
        } finally {
            setSaving(false);
        }
    };

    // 合并"保存配置 + 启动"的优化流程，避免冗余 fetchData
    const handleStartTrading = async () => {
        if (!activeTrader || acting || saving) return;
        setActing(true);
        setDataLoading(true);
        setWallet(null);
        setPositions([]);
        setOrders([]);
        setTradeHistory([]);
        setPositionHistory([]);
        setIncomeHistory([]);
        setLogs([]);

        // 乐观更新：立即切换到运行态面板，无需等待后端返回
        setActiveTrader(prev => ({ ...prev, status: 'RUNNING' }));

        try {
            // 1. 保存配置（不再调用 fetchData，因为马上就要启动了）
            await putJson(`/api/workspace/trader-instances/${activeTrader.id}?user_id=${userId}`, pendingChanges);
            // 2. 启动 Agent
            await postJson(`/api/workspace/trader-instances/${activeTrader.id}/runtime-action?user_id=${userId}`, { action: 'start' });
            // 3. 并行拉取配置状态 + 市场数据
            await Promise.all([fetchData(), refreshMarketRef.current()]);
            showFeedback("已成功启动", "success");
        } catch (err) {
            // 启动失败，回滚乐观更新
            setActiveTrader(prev => ({ ...prev, status: 'STOPPED' }));
            showFeedback(err.message || "启动失败，请重试", "error");
        } finally {
            setActing(false);
        }
    };

    const handleManualTrigger = async () => {
        if (!activeTrader || !isRunning || acting) return;
        setActing(true);
        try {
            await postJson(`/api/workspace/trader-instances/${activeTrader.id}/trigger?user_id=${userId}`);
            showFeedback("已触发独立策略分析，请稍候查看日志", "success");
            // Optionally wait a bit then refresh to see the pending status if backend handles it asynchronously
            setTimeout(() => refreshMarketRef.current(), 3000);
        } catch (err) {
            showFeedback(err.message || "触发失败请重试", "error");
        } finally {
            setActing(false);
        }
    };

    const handleClearConfig = () => {
        setShowClearConfirm(true);
    };

    const executeClearConfig = async () => {
        setClearing(true);
        try {
            await postJson(`/api/workspace/trader-instances/${activeTrader.id}/clear?user_id=${userId}`);
            await fetchData();
            showFeedback("已成功清除配置", "success");
        } catch (err) {
            showFeedback("清除失败", "error");
        } finally {
            setClearing(false);
            setShowClearConfirm(false);
        }
    };

    const executeClearLogs = async () => {
        setClearingLogs(true);
        try {
            await deleteJson(`/api/strategy/logs?user_id=${userId}`);
            await fetchData();
            showFeedback("决策日志已清空", "success");
        } catch (err) {
            console.error(err);
            showFeedback("清空失败", "error");
        } finally {
            setClearingLogs(false);
            setShowClearLogsConfirm(false);
        }
    };

    const handleDeleteInstance = () => {
        setPendingChanges({ strategy_profile_id: '', exchange_account_id: '', llm_config_id: '' });
        setIsConfirmingDelete(false);
        showFeedback("配置已清除", "success");
    };

    // 按时间维度筛选仓位历史，实时计算盈亏和胜率
    const periodOptions = [
        { key: 'all', label: '全部' },
        { key: 'year', label: '近一年' },
        { key: 'month', label: '近一月' },
        { key: 'week', label: '近一周' },
        { key: '3days', label: '近3天' },
        { key: 'today', label: '今日' },
    ];

    const filteredStats = useMemo(() => {
        const now = Date.now();
        const periodMs = {
            all: Infinity,
            year: 365 * 24 * 60 * 60 * 1000,
            month: 30 * 24 * 60 * 60 * 1000,
            week: 7 * 24 * 60 * 60 * 1000,
            '3days': 3 * 24 * 60 * 60 * 1000,
            today: 24 * 60 * 60 * 1000,
        };
        const cutoff = statsPeriod === 'all' ? 0 : now - (periodMs[statsPeriod] || Infinity);

        const filtered = positionHistory.filter(p => {
            const closeTime = p.close_time || 0;
            return closeTime >= cutoff;
        });

        const totalPnl = filtered.reduce((sum, p) => sum + Number(p.realized_pnl || 0), 0);
        const totalCount = filtered.length;
        const winCount = filtered.filter(p => Number(p.realized_pnl || 0) > 0).length;
        const winRate = totalCount > 0 ? (winCount / totalCount) * 100 : 0;

        return { totalPnl, totalCount, winCount, winRate };
    }, [positionHistory, statsPeriod]);

    const totalPnL = filteredStats.totalPnl;
    const winRate = filteredStats.winRate;

    const PeriodSelector = () => (
        <MiniDropdown options={periodOptions} value={statsPeriod} onChange={setStatsPeriod} />
    );

    if (initialLoading) {
        return (
            <div className="h-full flex flex-col gap-6 p-6 max-w-[1600px] mx-auto min-h-0 w-full animate-pulse">
                {/* Header Skeleton */}
                <div className="h-20 bg-[#0e1215]/50 border border-white/5 rounded-3xl flex-shrink-0" />

                {/* Stats Cards Skeleton */}
                <div className="grid grid-cols-4 gap-6 flex-shrink-0">
                    {[1, 2, 3, 4].map(i => (
                        <div key={i} className="h-32 bg-[#0e1215]/50 border border-white/5 rounded-2xl" />
                    ))}
                </div>

                {/* Body Skeleton */}
                <div className="flex-1 flex gap-8 min-h-0">
                    <div className="flex-[7] bg-[#0e1215]/50 border border-white/5 rounded-3xl" />
                    <div className="flex-[3] bg-[#0e1215]/50 border border-white/5 rounded-3xl min-w-[340px]" />
                </div>
            </div>
        );
    }

    if (showOnboarding) {
        return (
            <div className="h-full flex items-center justify-center p-4">
                <OnboardingWizard
                    userId={userId}
                    status={{ hasExchange: accounts.length > 0, hasLLM: llmConfigs.length > 0, hasStrategy: strategies.length > 0 }}
                    onStepComplete={() => fetchData()}
                />
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col gap-6 p-6 max-w-[1600px] mx-auto min-h-0">
            <Toast feedback={feedback} />

            {/* Top Row: Instance Config */}
            <header className="bg-[#0e1215]/40 border border-white/5 rounded-3xl p-4 flex items-center justify-between shadow-2xl backdrop-blur-md flex-shrink-0 animate-in fade-in duration-700 z-50 relative">
                <div className="flex items-center gap-6">
                    <div className="flex items-center gap-3 pr-6 border-r border-white/5">
                        <div className={`w-10 h-10 rounded-2xl flex items-center justify-center border transition-all ${isRunning ? 'bg-emerald-500/10 border-emerald-500/20' : 'bg-slate-700/10 border-white/10'}`}>
                            {isRunning ? <Activity className="w-5 h-5 text-emerald-400 animate-pulse" /> : <Zap className="w-5 h-5 text-slate-500" />}
                        </div>
                        <div>
                            <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest leading-none mb-1">运行状态</div>
                            <div className={`text-sm font-bold ${isRunning ? 'text-emerald-400' : 'text-white'}`}>{isRunning ? '正在运行' : '已停止'}</div>
                        </div>
                    </div>
                    <div className="flex items-center gap-4">
                        <div className="w-44"><CustomDropdown label="交易账户" options={accounts.map(a => ({ id: a.id, name: a.display_name, logo: EXCHANGE_LOGOS[a.exchange?.toLowerCase()] }))} value={pendingChanges.exchange_account_id} onChange={id => setPendingChanges(p => ({ ...p, exchange_account_id: id }))} icon={Globe} disabled={isRunning} /></div>
                        <div className="w-40"><CustomDropdown label="执行模型" options={llmConfigs.map(c => ({ id: c.id, name: c.name, logo: LLM_LOGOS[c.provider?.toLowerCase()] }))} value={pendingChanges.llm_config_id} onChange={id => setPendingChanges(p => ({ ...p, llm_config_id: id }))} icon={Cpu} disabled={isRunning} /></div>
                        <div className="w-44"><CustomDropdown label="策略配置" options={strategies.map(s => ({ id: s.id, name: s.name }))} value={pendingChanges.strategy_profile_id} onChange={id => setPendingChanges(p => ({ ...p, strategy_profile_id: id }))} icon={Target} disabled={isRunning} /></div>
                    </div>
                </div>
                <div className="flex items-center gap-3 pl-6 border-l border-white/5">
                    {isRunning && (
                        <Button variant="outline" size="sm" icon={RefreshCw} onClick={handleManualTrigger} disabled={acting} className="h-9 px-6 font-black uppercase text-[10px] text-slate-300 border-white/10 hover:bg-white/5">立刻分析</Button>
                    )}
                    {isRunning ? (
                        <Button variant="danger" size="sm" icon={Square} onClick={() => handleAction('STOP')} disabled={acting} className="h-9 px-6 font-black uppercase text-[10px]">停止运行</Button>
                    ) : (
                        <Button variant="primary" size="sm" icon={Play} onClick={handleStartTrading} disabled={acting || saving} className="h-9 px-6 font-black uppercase text-[10px]">开始运行</Button>
                    )}
                </div>
            </header>

            {/* Dashboard Stats */}
            {isRunning && (
                <div className="grid grid-cols-4 gap-6 flex-shrink-0 relative z-40">
                    <StatCard
                        icon={Wallet}
                        label="账户总权益"
                        value={wallet ? `${Number(wallet.equity || wallet.current_balance || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USDT` : <Loader2 className="w-4 h-4 text-slate-500 animate-spin" />}
                        tone="emerald"
                        hidden={hideBalance}
                        onToggleHidden={() => setHideBalance(h => !h)}
                    />
                    <StatCard
                        icon={DollarSign}
                        label="可用余额"
                        value={wallet ? `${Number(wallet.available_balance || ((wallet.current_balance || 0) - (wallet.margin_in_use || 0))).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USDT` : <Loader2 className="w-4 h-4 text-slate-500 animate-spin" />}
                        tone="amber"
                        hidden={hideBalance}
                        onToggleHidden={() => setHideBalance(h => !h)}
                    />
                    <StatCard
                        icon={BarChart3}
                        label="已实现盈亏"
                        headerRight={<PeriodSelector />}
                        value={filteredStats.totalCount > 0 ? (
                            <div className="flex items-baseline gap-2">
                                <span>{`${totalPnL >= 0 ? '+' : ''}${totalPnL.toFixed(2)} USDT`}</span>
                                {wallet && <span className={`text-sm font-bold ${totalPnL >= 0 ? 'text-emerald-500' : 'text-rose-500'} opacity-90`}>
                                    ({totalPnL >= 0 ? '+' : ''}{((totalPnL / Math.max(1, Number(wallet.current_balance || 1))) * 100).toFixed(1)}%)
                                </span>}
                            </div>
                        ) : (wallet ? '0.00 USDT' : <Loader2 className="w-4 h-4 text-slate-500 animate-spin" />)}
                        subValue={filteredStats.totalCount > 0 ? `${filteredStats.totalCount} 笔已平仓` : (wallet ? '0 笔已平仓' : undefined)}
                        tone={totalPnL >= 0 ? 'emerald' : 'rose'}
                        hidden={hidePnl}
                        onToggleHidden={() => setHidePnl(h => !h)}
                    />
                    <StatCard
                        icon={Target}
                        label="胜率"
                        headerRight={<PeriodSelector />}
                        value={filteredStats.totalCount > 0 ? `${winRate.toFixed(1)}%` : (wallet ? '0.0%' : <Loader2 className="w-4 h-4 text-slate-500 animate-spin" />)}
                        subValue={filteredStats.totalCount > 0 ? `${filteredStats.winCount} 盈 / ${filteredStats.totalCount - filteredStats.winCount} 亏  共 ${filteredStats.totalCount} 笔` : (wallet ? '0 笔交易' : undefined)}
                        tone={winRate >= 50 ? 'emerald' : 'rose'}
                        hidden={hideWinRate}
                        onToggleHidden={() => setHideWinRate(h => !h)}
                    />
                </div>
            )}

            {/* Split Workspace */}
            {isRunning ? (
                <div className="flex-1 flex gap-8 min-h-0 outline-none focus:outline-none ring-0">
                    <main className="flex-[7] flex flex-col bg-[#0e1215]/50 border border-white/5 rounded-3xl overflow-hidden shadow-2xl relative outline-none focus:outline-none ring-0 focus:ring-0 hover:outline-none transform-gpu">
                        <div className="flex border-b border-white/5 bg-black/10 px-4 overflow-x-auto outline-none focus:outline-none ring-0">
                            {['positions', 'orders', 'history', 'posHistory', 'income'].map(tab => (
                                <button key={tab} onClick={() => setActiveTab(tab)} className={`px-5 py-4 text-[10px] font-black uppercase tracking-widest relative transition-all whitespace-nowrap focus:outline-none ${activeTab === tab ? 'text-emerald-400' : 'text-slate-200'}`}>
                                    {{ 'positions': '当前仓位', 'orders': '待成交委托', 'history': '历史成交', 'posHistory': '仓位历史', 'income': '资金流水' }[tab]}
                                    {activeTab === tab && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-500 shadow-[0_0_10px_#6366f1]" />}
                                </button>
                            ))}
                        </div>
                        <div className="flex-1 p-0 overflow-y-auto custom-scrollbar">
                            {activeTab === 'positions' && (
                                <table className="w-full text-left">
                                    <thead className="sticky top-0 bg-[#0B0E11] z-10 border-b border-white/5 text-[9px] font-black text-slate-500 uppercase tracking-widest">
                                        <tr><th className="py-4 px-6">合约</th><th className="py-4 px-6 text-right">数量</th><th className="py-4 px-6 text-right">开仓价格</th><th className="py-4 px-6 text-right">标记价格</th><th className="py-4 px-6 text-right">未实现盈亏 (回报率)</th><th className="py-4 px-6 text-right">止盈/止损</th></tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/5">
                                        {positions.length > 0 ? positions.map((pos, i) => {
                                            const expectedCloseDir = pos.direction === 'LONG' ? 'CLOSE_LONG' : 'CLOSE_SHORT';
                                            const condOrders = orders.filter(o => o.symbol === pos.symbol && o.status === 'NEW' && o.direction === expectedCloseDir && (o.type?.includes('TAKE_PROFIT') || o.type?.includes('STOP')));
                                            
                                            // Find the TP and SL that are closest to the entry price to display on the outside
                                            const entryPrice = Number(pos.entry_price || 0);
                                            const getPrice = o => Number(o.stop_price || o.price || 0);

                                            const tpOrders = condOrders.filter(o => o.type?.includes('TAKE_PROFIT'))
                                                .sort((a, b) => Math.abs(getPrice(a) - entryPrice) - Math.abs(getPrice(b) - entryPrice));
                                            
                                            const slOrders = condOrders.filter(o => o.type?.includes('STOP') && !o.type?.includes('TAKE_PROFIT'))
                                                .sort((a, b) => Math.abs(getPrice(a) - entryPrice) - Math.abs(getPrice(b) - entryPrice));
                                            
                                            const tpOrder = tpOrders[0];
                                            const slOrder = slOrders[0];
                                            
                                            return (
                                                <tr key={i} className="hover:bg-white/[0.02] transition-colors group relative hover:z-50">
                                                    <td className="py-4 px-6">
                                                        <div className="flex items-center gap-2">
                                                            <div className={`w-1 h-4 rounded-sm ${pos.direction === 'LONG' ? 'bg-emerald-500' : 'bg-rose-500'}`}></div>
                                                            <div className="flex flex-col">
                                                                <span className="font-bold text-sm text-slate-100">{pos.symbol}</span>
                                                                <span className="text-[10px] text-slate-500 font-medium mt-0.5">永续</span>
                                                            </div>
                                                        </div>
                                                    </td>
                                                    <td className="py-4 px-6 text-right font-mono text-xs text-slate-300">{pos.quantity} {(pos.symbol || '').replace('USDT', '')}</td>
                                                    <td className="py-4 px-6 text-right font-mono text-xs text-slate-300">{Number(pos.entry_price).toLocaleString(undefined, { minimumFractionDigits: 1 })}</td>
                                                    <td className="py-4 px-6 text-right font-mono text-xs text-slate-300">{Number(pos.current_price || pos.mark_price || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                                                    <td className={`py-4 px-6 text-right font-mono text-xs ${Number(pos.unrealized_pnl) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                                        {Number(pos.unrealized_pnl).toFixed(2)} ({Number(pos.unrealized_pnl) >= 0 ? '+' : ''}{Number(pos.roi_percent || 0).toFixed(2)}%)
                                                    </td>
                                                    <td className="py-4 px-6 whitespace-nowrap relative group/tooltip">
                                                        <div className="flex items-center justify-end gap-3 cursor-pointer">
                                                            <div className="flex flex-col items-end gap-1 font-mono text-[11px]">
                                                                <div className="flex items-center gap-1.5 border-b border-dashed border-white/20 pb-0.5">
                                                                    {tpOrder ? <span className="text-emerald-400">{Number(tpOrder.stop_price || tpOrder.price).toLocaleString(undefined, { minimumFractionDigits: 1 })}</span> : <span className="text-slate-500">--</span>}
                                                                </div>
                                                                <div className="flex items-center gap-1.5 pt-0.5">
                                                                    {slOrder ? <span className="text-rose-400">{Number(slOrder.stop_price || slOrder.price).toLocaleString(undefined, { minimumFractionDigits: 1 })}</span> : <span className="text-slate-500">--</span>}
                                                                </div>
                                                            </div>
                                                            {condOrders.length > 1 && (
                                                                <span className="text-[10px] text-slate-400 bg-white/5 px-1.5 py-0.5 rounded">({condOrders.length})</span>
                                                            )}
                                                        </div>
                                                        
                                                        {/* Hover Tooltip for multiple orders */}
                                                        {condOrders.length > 1 && (
                                                            <div className="absolute right-full top-2 mr-3 opacity-0 pointer-events-none group-hover/tooltip:opacity-100 group-hover/tooltip:pointer-events-auto transition-all bg-[#1E2329] border border-white/10 rounded shadow-[0_8px_30px_rgb(0,0,0,0.8)] p-2 min-w-[200px] z-[9999]">
                                                                {/* Arrow pointing right */}
                                                                <div className="absolute top-[12px] -right-[4px] w-0 h-0 border-y-[4px] border-y-transparent border-l-[4px] border-l-[#1E2329]"></div>
                                                                
                                                                {/* OKX style tooltip content */}
                                                                <table className="w-full text-left text-[10px] relative z-10 m-0 border-collapse bg-transparent">
                                                                    <thead className="text-slate-500 font-medium tracking-wide">
                                                                        <tr>
                                                                            <th className="pb-1.5 px-1 font-normal border-b border-white/5 w-1/3">止盈</th>
                                                                            <th className="pb-1.5 px-1 font-normal border-b border-white/5 w-1/3">止损</th>
                                                                            <th className="pb-1.5 px-1 font-normal text-right border-b border-white/5 w-1/3">数量</th>
                                                                        </tr>
                                                                    </thead>
                                                                    <tbody className="font-mono divide-y divide-white/5">
                                                                        {condOrders.map((o, idx) => {
                                                                            const isTp = o.type?.includes('TAKE_PROFIT');
                                                                            const price = Number(o.stop_price || o.price).toLocaleString(undefined, { minimumFractionDigits: 1 });
                                                                            return (
                                                                                <tr key={idx} className="hover:bg-white/5">
                                                                                    <td className="py-2 px-1 leading-none">
                                                                                        {isTp ? <span className="text-emerald-400">{price}</span> : <span className="text-slate-500">--</span>}
                                                                                    </td>
                                                                                    <td className="py-2 px-1 leading-none">
                                                                                        {!isTp ? <span className="text-rose-400">{price}</span> : <span className="text-slate-500">--</span>}
                                                                                    </td>
                                                                                    <td className="py-2 px-1 text-right text-slate-300 leading-none">
                                                                                        {o.quantity}
                                                                                    </td>
                                                                                </tr>
                                                                            );
                                                                        })}
                                                                    </tbody>
                                                                </table>
                                                            </div>
                                                        )}
                                                    </td>
                                                </tr>
                                            );
                                        }) : (
                                            <tr>
                                                <td colSpan="6" className="py-12 text-center">
                                                    {dataLoading ? (
                                                        <div className="flex flex-col items-center justify-center gap-3 opacity-50">
                                                            <Loader2 className="w-5 h-5 text-emerald-400 animate-spin" />
                                                            <span className="text-slate-500 text-[10px] uppercase tracking-widest font-black">正在同步数据...</span>
                                                        </div>
                                                    ) : (
                                                        <span className="text-slate-600 text-[10px] font-bold tracking-[0.2em] opacity-40">暂无活跃持仓</span>
                                                    )}
                                                </td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            )}
                            {activeTab === 'orders' && (
                                <div className="w-full overflow-x-auto custom-scrollbar md:overflow-x-visible">
                                <table className="w-full min-w-max text-left whitespace-nowrap">
                                    <thead className="sticky top-0 bg-[#0B0E11] z-10 border-b border-white/5 text-[9px] font-black text-slate-500 uppercase tracking-widest">
                                        <tr><th className="py-4 px-6 w-32">委托时间</th><th className="py-4 px-6">合约</th><th className="py-4 px-6">方向</th><th className="py-4 px-6 text-right">数量</th><th className="py-4 px-6 text-right">触发价格</th><th className="py-4 px-6 text-right">委托类型</th><th className="py-4 px-6 text-right">状态</th></tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/5">
                                        {orders.length > 0 ? orders.map((order, i) => (
                                            <tr key={i} className="hover:bg-white/[0.02] transition-colors group">
                                                <td className="py-4 px-6 whitespace-nowrap">
                                                    <span className="text-xs font-mono text-slate-400">
                                                        {order.time ? `${new Date(order.time).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })} ${new Date(order.time).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}` : '--/-- --:--:--'}
                                                    </span>
                                                </td>
                                                <td className="py-4 px-6 whitespace-nowrap">
                                                    <div className="flex items-center gap-2">
                                                        <div className={`w-1 h-4 rounded-sm ${order.direction?.includes('LONG') ? 'bg-emerald-500' : 'bg-rose-500'}`}></div>
                                                        <div className="flex items-center gap-2">
                                                            <span className="font-bold text-sm text-slate-100">{order.symbol}</span>
                                                            <span className="text-[9px] px-1 py-0.5 rounded bg-white/5 text-slate-400 font-medium">永续</span>
                                                        </div>
                                                    </div>
                                                </td>
                                                <td className="py-4 px-6 whitespace-nowrap">
                                                    <span className={`text-xs tracking-wide ${(order.direction === 'LONG' || order.direction === 'CLOSE_SHORT') ? 'text-emerald-400' : 'text-rose-400'}`}>
                                                        {order.direction === 'LONG' ? '买入开多' : order.direction === 'SHORT' ? '卖出开空' : order.direction === 'CLOSE_LONG' ? '卖出平多' : order.direction === 'CLOSE_SHORT' ? '买入平空' : order.direction}
                                                    </span>
                                                </td>
                                                <td className="py-4 px-6 text-right font-mono text-xs text-slate-300 whitespace-nowrap">
                                                    {order.close_position ? (
                                                        <span className="text-slate-500">全部平仓</span>
                                                    ) : (
                                                        <div className="flex items-center justify-end gap-1">
                                                            <span>{(order.quantity || 0).toLocaleString()}</span>
                                                            <span className="text-[10px] text-slate-500">{order.symbol?.replace('USDT', '')}</span>
                                                        </div>
                                                    )}
                                                </td>
                                                <td className="py-4 px-6 text-right whitespace-nowrap">
                                                    {order.stop_price > 0 ? (
                                                        <span className={`font-mono text-xs ${order.type?.includes("TAKE_PROFIT") ? 'text-emerald-400' : 'text-rose-400'}`}>
                                                            {order.stop_price.toLocaleString(undefined, { minimumFractionDigits: 1 })}
                                                        </span>
                                                    ) : order.activation_price > 0 ? (
                                                        <span className="font-mono text-xs text-amber-400">
                                                            {order.activation_price.toLocaleString(undefined, { minimumFractionDigits: 1 })}
                                                        </span>
                                                    ) : (
                                                        <span className="text-slate-600 text-xs font-mono">--</span>
                                                    )}
                                                </td>
                                                <td className="py-4 px-6 text-right whitespace-nowrap">
                                                    <span className="text-xs text-slate-300">
                                                        {order.type === 'STOP_MARKET' ? '市价止损' : order.type === 'TAKE_PROFIT_MARKET' ? '市价止盈' : order.type === 'TRAILING_STOP_MARKET' ? '跟踪挂单' : order.type === 'LIMIT' ? '限价单' : order.type === 'MARKET' ? '市价单' : order.type}
                                                    </span>
                                                </td>
                                                <td className="py-4 px-6 text-right whitespace-nowrap">
                                                    <span className={`text-[11px] font-bold px-2 py-0.5 rounded ${order.status === 'NEW' ? 'text-amber-400' : 'text-slate-500'}`}>
                                                        {order.status === 'NEW' ? '等待成交' : order.status}
                                                    </span>
                                                </td>

                                            </tr>
                                        )) : (
                                            <tr><td colSpan="7" className="py-20 text-center"><div className="flex flex-col items-center justify-center gap-2"><div className="w-12 h-12 rounded-full border border-dashed border-white/10 flex items-center justify-center mb-2"><div className="w-2 h-2 rounded-full bg-emerald-500/50"></div></div><span className="text-slate-600 text-[11px] font-bold tracking-[0.2em] opacity-40">当前暂无任何挂单</span></div></td></tr>
                                        )}
                                    </tbody>
                                </table>
                                </div>
                            )}
                            {activeTab === 'history' && (
                                <table className="w-full text-left">
                                    <thead className="sticky top-0 bg-[#0B0E11] z-10 border-b border-white/5 text-[9px] font-black text-slate-500 uppercase tracking-widest">
                                        <tr><th className="py-4 px-6">时间</th><th className="py-4 px-6">交易对</th><th className="py-4 px-6">方向</th><th className="py-4 px-6 text-right">价格</th><th className="py-4 px-6 text-right">数量</th><th className="py-4 px-6 text-right">手续费</th><th className="py-4 px-6 text-right">已实现盈亏</th></tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/5">
                                        {tradeHistory.length > 0 ? tradeHistory.map((trade, i) => {
                                            const tradeTime = trade.time ? new Date(trade.time) : null;
                                            const timeStr = tradeTime ? `${tradeTime.getMonth() + 1}/${tradeTime.getDate()} ${String(tradeTime.getHours()).padStart(2, '0')}:${String(tradeTime.getMinutes()).padStart(2, '0')}:${String(tradeTime.getSeconds()).padStart(2, '0')}` : '--';
                                            const side = trade.side;
                                            const posSide = (trade.position_side || '').toUpperCase();
                                            // 通过 side + positionSide 判断精确方向
                                            let dirLabel = '';
                                            let isGreen = false;
                                            if (side === 'BUY' && posSide === 'LONG') { dirLabel = '买入/开多'; isGreen = true; }
                                            else if (side === 'SELL' && posSide === 'LONG') { dirLabel = '卖出/平多'; isGreen = false; }
                                            else if (side === 'SELL' && posSide === 'SHORT') { dirLabel = '卖出/开空'; isGreen = false; }
                                            else if (side === 'BUY' && posSide === 'SHORT') { dirLabel = '买入/平空'; isGreen = true; }
                                            else { dirLabel = side === 'BUY' ? '买入/做多' : '卖出/做空'; isGreen = side === 'BUY'; }
                                            const pnl = Number(trade.realized_pnl || 0);
                                            return (
                                                <tr key={i} className="hover:bg-white/[0.02] transition-colors">
                                                    <td className="py-4 px-6 text-xs font-mono text-slate-400">{timeStr}</td>
                                                    <td className="py-4 px-6 font-bold text-sm">{(trade.symbol || '').replace('USDT', '')}</td>
                                                    <td className={`py-4 px-6 text-xs font-bold ${isGreen ? 'text-emerald-400' : 'text-rose-400'}`}>{dirLabel}</td>
                                                    <td className="py-4 px-6 text-right font-mono text-xs text-slate-300">{Number(trade.price).toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                                                    <td className="py-4 px-6 text-right font-mono text-xs text-slate-300">{parseFloat(Number(trade.quantity || 0).toFixed(8))}</td>
                                                    <td className="py-4 px-6 text-right font-mono text-xs text-slate-500">{Number(trade.commission || 0).toFixed(4)}</td>
                                                    <td className={`py-4 px-6 text-right font-mono text-xs ${pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{pnl !== 0 ? `${pnl >= 0 ? '+' : ''}${pnl.toFixed(4)}` : '--'}</td>
                                                </tr>
                                            );
                                        }) : (
                                            <tr><td colSpan="7" className="py-12 text-center text-slate-600 text-[10px] font-bold tracking-[0.2em] opacity-40">暂无历史成交</td></tr>
                                        )}
                                    </tbody>
                                </table>
                            )}
                            {activeTab === 'posHistory' && (
                                <div className="divide-y divide-white/5">
                                    {positionHistory.length > 0 ? positionHistory.map((pos, i) => {
                                        const pnl = Number(pos.realized_pnl || 0);
                                        const roi = Number(pos.roi_percent || 0);
                                        const isPnlPositive = pnl >= 0;
                                        const fmtTime = (ts) => {
                                            if (!ts) return '--';
                                            const d = new Date(ts);
                                            return `${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}/${d.getFullYear()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`;
                                        };
                                        const unit = pos.symbol || '';
                                        return (
                                            <div key={i} className="px-6 py-5 hover:bg-white/[0.02] transition-colors">
                                                {/* Row 1: Symbol + Tags + Times */}
                                                <div className="flex items-center justify-between mb-4">
                                                    <div className="flex items-center gap-2.5 flex-wrap">
                                                        <span className="text-white font-black text-sm">{pos.symbol_full || `${unit}USDT`}</span>
                                                        <span className="text-[9px] font-bold text-slate-500 bg-slate-800/50 px-1.5 py-0.5 rounded">永续</span>
                                                        <span className="text-[9px] font-bold text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded">{pos.leverage || 10}x</span>
                                                        <span className="text-[9px] font-bold text-slate-400 bg-slate-700/30 px-1.5 py-0.5 rounded">{pos.margin_mode || '全仓'}</span>
                                                        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${pos.direction === 'LONG' ? 'text-emerald-400 bg-emerald-500/10' : 'text-rose-400 bg-rose-500/10'}`}>{pos.direction === 'LONG' ? '做多' : '做空'}</span>
                                                        <span className="text-[9px] font-bold text-slate-500">{pos.close_type || '全部平仓'}</span>
                                                    </div>
                                                    <div className="flex items-center gap-4 text-[10px] text-slate-500 font-mono">
                                                        <span>{fmtTime(pos.open_time)} 开仓时间</span>
                                                        <span className="text-slate-700">|</span>
                                                        <span>{fmtTime(pos.close_time)} 最后平仓时间</span>
                                                    </div>
                                                </div>
                                                {/* Row 2: Stats Grid */}
                                                <div className="grid grid-cols-6 gap-4">
                                                    <div>
                                                        <div className="text-[9px] text-slate-600 font-bold mb-1">已实现盈亏 (USDT)</div>
                                                        <div className={`text-sm font-black font-mono ${isPnlPositive ? 'text-emerald-400' : 'text-rose-400'}`}>{isPnlPositive ? '+' : ''}{pnl.toFixed(2)} USDT</div>
                                                    </div>
                                                    <div>
                                                        <div className="text-[9px] text-slate-600 font-bold mb-1">收益率</div>
                                                        <div className={`text-sm font-black font-mono ${isPnlPositive ? 'text-emerald-400' : 'text-rose-400'}`}>{isPnlPositive ? '+' : ''}{roi.toFixed(2)}%</div>
                                                    </div>
                                                    <div>
                                                        <div className="text-[9px] text-slate-600 font-bold mb-1">已平仓量 ({unit})</div>
                                                        <div className="text-sm font-mono text-white">{pos.closed_quantity}</div>
                                                    </div>
                                                    <div>
                                                        <div className="text-[9px] text-slate-600 font-bold mb-1">开仓价格</div>
                                                        <div className="text-sm font-mono text-white">{Number(pos.entry_price).toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
                                                    </div>
                                                    <div>
                                                        <div className="text-[9px] text-slate-600 font-bold mb-1">平仓均价</div>
                                                        <div className="text-sm font-mono text-white">{Number(pos.close_price).toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
                                                    </div>
                                                    <div>
                                                        <div className="text-[9px] text-slate-600 font-bold mb-1">最大未平仓合约量 ({unit})</div>
                                                        <div className="text-sm font-mono text-white">{pos.max_quantity}</div>
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    }) : (
                                        <div className="py-16 text-center text-slate-600 text-[10px] font-bold tracking-[0.2em] opacity-40">暂无仓位历史</div>
                                    )}
                                </div>
                            )}
                            {activeTab === 'income' && (
                                <table className="w-full text-left">
                                    <thead className="sticky top-0 bg-[#0B0E11] z-10 border-b border-white/5 text-[9px] font-black text-slate-500 uppercase tracking-widest">
                                        <tr><th className="py-4 px-5">时间</th><th className="py-4 px-5">交易对</th><th className="py-4 px-5">类型</th><th className="py-4 px-5 text-right">金额</th><th className="py-4 px-5 text-right">资产</th></tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/5">
                                        {incomeHistory.length > 0 ? [...incomeHistory].sort((a, b) => (b.time || 0) - (a.time || 0)).map((item, i) => {
                                            const t = item.time ? new Date(item.time) : null;
                                            const timeStr = t ? `${t.getMonth() + 1}/${t.getDate()} ${String(t.getHours()).padStart(2, '0')}:${String(t.getMinutes()).padStart(2, '0')}:${String(t.getSeconds()).padStart(2, '0')}` : '--';
                                            const amount = Number(item.amount || 0);
                                            const typeMap = { 'REALIZED_PNL': '已实现盈亏', 'FUNDING_FEE': '资金费率', 'COMMISSION': '手续费', 'TRANSFER': '转账', 'WELCOME_BONUS': '奖励', 'INSURANCE_CLEAR': '保险基金', 'DELIVERED_SETTELMENT': '交割', 'COIN_SWAP_DEPOSIT': '兑换充值', 'COIN_SWAP_WITHDRAW': '兑换提现' };
                                            const typeLabel = typeMap[item.type] || item.type;
                                            const typeColor = item.type === 'REALIZED_PNL' ? (amount >= 0 ? 'text-emerald-400' : 'text-rose-400') : item.type === 'FUNDING_FEE' ? 'text-sky-400' : item.type === 'COMMISSION' ? 'text-orange-400' : item.type === 'TRANSFER' ? 'text-violet-400' : 'text-slate-400';
                                            return (
                                                <tr key={i} className="hover:bg-white/[0.02] transition-colors">
                                                    <td className="py-3.5 px-5 text-xs font-mono text-slate-400">{timeStr}</td>
                                                    <td className="py-3.5 px-5 font-bold text-sm">{(item.symbol || '--').replace('USDT', '')}</td>
                                                    <td className={`py-3.5 px-5 text-xs font-bold ${typeColor}`}>{typeLabel}</td>
                                                    <td className={`py-3.5 px-5 text-right font-mono text-xs ${amount >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{amount >= 0 ? '+' : ''}{amount.toFixed(4)}</td>
                                                    <td className="py-3.5 px-5 text-right text-xs text-slate-400">{item.asset || 'USDT'}</td>
                                                </tr>
                                            );
                                        }) : (
                                            <tr><td colSpan="5" className="py-12 text-center text-slate-600 text-[10px] font-bold tracking-[0.2em] opacity-40">暂无资金流水</td></tr>
                                        )}
                                    </tbody>
                                </table>
                            )}
                            {!isRunning && positions.length === 0 && activeTab === 'positions' && <div className="h-full flex items-center justify-center opacity-30 italic text-[10px] uppercase tracking-[0.2em] font-black">待机模式 - 扫描未启动</div>}
                        </div>
                    </main>
                    <aside className="flex-[3] flex flex-col bg-[#0e1215]/50 border border-white/5 rounded-3xl overflow-hidden shadow-2xl relative min-w-[340px] outline-none focus:outline-none ring-0 focus:ring-0 hover:outline-none transform-gpu">
                        <div className="flex items-center justify-between border-b border-white/5 bg-black/10 px-6 h-[49px] outline-none focus:outline-none ring-0">
                            <div className="flex items-center gap-2"><Clock className="w-4 h-4 text-emerald-400" /><h3 className="text-[10px] font-black text-white uppercase tracking-widest">Agent决策日志</h3></div>
                            <button onClick={() => setShowClearLogsConfirm(true)} className="p-1 hover:bg-white/5 hover:text-rose-400 rounded-lg text-slate-500 transition-all cursor-pointer" title="清空日志">
                                <Trash2 className="w-4 h-4" />
                            </button>
                        </div>
                        <div className="flex-1 overflow-y-auto custom-scrollbar flex flex-col gap-3 p-4">
                            {logs.length > 0 ? logs.map((log, idx) => <DecisionCard key={idx} log={log} traderInstances={traderInstances} accounts={accounts} llmConfigs={llmConfigs} />) : (
                                dataLoading ? (
                                    <div className="h-full flex flex-col items-center justify-center gap-3 opacity-50">
                                        <Loader2 className="w-5 h-5 text-emerald-400 animate-spin" />
                                        <span className="text-slate-500 text-[10px] uppercase tracking-widest font-black">正在拉取日志...</span>
                                    </div>
                                ) : (
                                    <div className="h-full flex items-center justify-center text-slate-600 text-[10px] font-black opacity-30 uppercase tracking-[0.2em] italic">
                                        等待首份研究报告...
                                    </div>
                                )
                            )}
                        </div>
                    </aside>
                </div>
            ) : (
                <div className="flex-1 flex items-center justify-center rounded-[32px] mt-2 outline-none focus:outline-none ring-0 focus:ring-0 hover:outline-none transform-gpu relative overflow-hidden" style={{ background: 'radial-gradient(ellipse at 50% 40%, rgba(16,185,129,0.04) 0%, rgba(14,18,21,0.5) 70%)' }}>
                    {/* Subtle animated grid background */}
                    <div className="absolute inset-0 opacity-[0.03]" style={{ backgroundImage: 'linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)', backgroundSize: '48px 48px' }} />
                    
                    <div className="text-center relative z-10">
                        {/* Animated pulse rings */}
                        <div className="relative inline-flex items-center justify-center mb-6">
                            <div className="absolute w-24 h-24 rounded-full border border-emerald-500/5 animate-ping" style={{ animationDuration: '3s' }} />
                            <div className="absolute w-16 h-16 rounded-full border border-emerald-500/10" />
                            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-emerald-500/10 to-emerald-500/5 border border-emerald-500/20 flex items-center justify-center backdrop-blur-sm">
                                <Zap className="w-5 h-5 text-emerald-500/60" />
                            </div>
                        </div>
                        <p className="text-sm font-bold text-slate-300 tracking-wide">交易引擎待命中</p>
                        <p className="text-[11px] mt-2 text-slate-500 font-medium max-w-[280px] leading-relaxed">
                            选择好交易账户、模型和策略后，点击<span className="text-emerald-400/80 font-bold">「开始运行」</span>即可启动
                        </p>
                        <div className="flex items-center justify-center gap-1.5 mt-4">
                            <div className="w-1 h-1 rounded-full bg-emerald-500/40 animate-pulse" />
                            <div className="w-1 h-1 rounded-full bg-emerald-500/30 animate-pulse" style={{ animationDelay: '0.5s' }} />
                            <div className="w-1 h-1 rounded-full bg-emerald-500/20 animate-pulse" style={{ animationDelay: '1s' }} />
                        </div>
                    </div>
                </div>
            )}
            <ConnectLLMModal userId={userId} isOpen={isConnectingLLM} onClose={() => setIsConnectingLLM(false)} onConnected={() => fetchData()} />

            <ConfirmModal
                isOpen={showClearConfirm}
                onClose={() => setShowClearConfirm(false)}
                onConfirm={executeClearConfig}
                loading={clearing}
                title="清除实例配置"
                message="确定要清除当前交易实例的所有配置吗？这将立即停止相关策略的自动化分析与交易运行。此动作无法撤销。"
                confirmText="彻底清除"
                type="danger"
            />

            <ConfirmModal
                isOpen={showClearLogsConfirm}
                onClose={() => setShowClearLogsConfirm(false)}
                onConfirm={executeClearLogs}
                loading={clearingLogs}
                title="清空决策日志"
                message="确定要清空所有决策日志吗？此动作无法撤销。"
                confirmText="清空"
                type="danger"
            />
        </div>
    );
}

