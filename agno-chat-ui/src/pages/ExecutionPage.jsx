import React, { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import {
    Activity,
    ArrowUpRight,
    ArrowDownRight,
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
    Edit3,
    Cpu,
    Target,
    BarChart3,
    Plus,
    Globe
} from 'lucide-react';
import { getJson, postJson, putJson } from '../services/apiClient';
import Button from '../components/common/Button';
import OnboardingWizard from '../components/OnboardingWizard';
import ConnectLLMModal from '../components/ConnectLLMModal';
import ConfirmModal from '../components/ConfirmModal';

// --- Sub-components (StatCard, CustomDropdown, etc.) ---

function StatCard({ icon: Icon, label, value, subValue, trend, tone = 'emerald' }) {
    const tones = {
        emerald: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/10',
        amber: 'text-amber-400 bg-amber-500/10 border-amber-500/10',
        rose: 'text-rose-400 bg-rose-500/10 border-rose-500/10',
    };
    return (
        <div className="flex-1 min-w-[200px] p-5 rounded-2xl bg-[#0e1215]/50 border border-white/5 hover:border-emerald-500/20 transition-all group relative overflow-hidden">
            <div className={`absolute top-0 right-0 w-24 h-24 blur-[60px] opacity-20 -mr-12 -mt-12 transition-all group-hover:opacity-40 ${tones[tone].split(' ')[0].replace('text', 'bg')}`} />
            <div className="flex items-center justify-between mb-4">
                <div className={`p-2.5 rounded-xl border ${tones[tone]}`}><Icon className="w-5 h-5" /></div>
                {trend !== undefined && (
                    <div className={`flex items-center gap-1 text-xs font-bold ${trend >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {trend >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                        {Math.abs(trend).toFixed(1)}%
                    </div>
                )}
            </div>
            <div className="flex flex-col gap-1">
                <span className="text-xs font-bold text-slate-500 uppercase tracking-widest">{label}</span>
                <div className="text-2xl font-black text-white tracking-tight">{value}</div>
                {subValue && <div className="text-[10px] font-medium text-slate-500 tracking-wide uppercase opacity-60">{subValue}</div>}
            </div>
        </div>
    );
}

function CustomDropdown({ label, options, value, onChange, disabled, icon: Icon }) {
    const [isOpen, setIsOpen] = useState(false);
    const dropdownRef = useRef(null);
    const selectedOption = options.find(o => String(o.id) === String(value));

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target)) setIsOpen(false);
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    return (
        <div className="relative" ref={dropdownRef}>
            <div className="flex items-center justify-between mb-1.5 px-0.5">
                <label className="text-[9px] font-black text-slate-600 uppercase tracking-widest flex items-center gap-1.5">
                    {Icon && <Icon className="w-3 h-3 text-slate-500" />} {label}
                </label>
            </div>
            <button
                type="button"
                disabled={disabled}
                onClick={() => setIsOpen(!isOpen)}
                className={`w-full flex items-center justify-between gap-2 px-3 py-2.5 bg-[#0e1215]/60 border border-white/5 rounded-xl text-xs font-bold hover:border-white/10 transition-all ${disabled ? 'opacity-40 cursor-not-allowed' : 'text-slate-200'}`}
            >
                <span className="truncate">{selectedOption ? selectedOption.name : '未选择'}</span>
                <ChevronDown className={`w-3.5 h-3.5 text-slate-500 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
            </button>
            {isOpen && !disabled && (
                <div className="absolute top-[calc(100%+4px)] left-0 right-0 z-[100] bg-[#111516] border border-white/10 rounded-xl shadow-2xl overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200 border-t-emerald-500/50">
                    <div className="max-h-60 overflow-y-auto custom-scrollbar">
                        {options.map(opt => (
                            <button
                                key={opt.id}
                                onClick={() => { onChange(opt.id); setIsOpen(false); }}
                                className={`w-full text-left px-4 py-3 text-[11px] font-bold transition-colors ${String(opt.id) === String(value) ? 'bg-emerald-500 text-white' : 'text-slate-400 hover:bg-white/5 hover:text-white'}`}
                            >
                                {opt.name}
                            </button>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

// --- Main Page Component ---

export default function ExecutionPage({ userId }) {
    const [initialLoading, setInitialLoading] = useState(true);
    const [acting, setActing] = useState(false);
    const [saving, setSaving] = useState(false);
    const [feedback, setFeedback] = useState(null);
    const [wallet, setWallet] = useState(null);
    const [positions, setPositions] = useState([]);
    const [activeTab, setActiveTab] = useState('positions');
    const [strategies, setStrategies] = useState([]);
    const [accounts, setAccounts] = useState([]);
    const [llmConfigs, setLlmConfigs] = useState([]);
    const [logs, setLogs] = useState([]);
    const [activeTrader, setActiveTrader] = useState(null);
    const [isConnectingLLM, setIsConnectingLLM] = useState(false);
    const [showOnboarding, setShowOnboarding] = useState(false);
    const [showClearConfirm, setShowClearConfirm] = useState(false);
    const [clearing, setClearing] = useState(false);
    const [pendingChanges, setPendingChanges] = useState({
        strategy_profile_id: '',
        exchange_account_id: '',
        llm_config_id: ''
    });

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
                getJson(`/api/strategy/logs?user_id=${userId}&limit=20`)
            ]);
            
            setStrategies(stratRes.profiles || []);
            setAccounts(accountRes.accounts || []);
            setLlmConfigs(llmRes.configs || []);
            setLogs(logsRes.logs || []);
            
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

    const refreshMarket = useCallback(async () => {
        if (!userId || showOnboarding) return;
        try {
            const [walletRes, posRes] = await Promise.all([
                getJson(`/api/strategy/wallet?user_id=${userId}`),
                getJson(`/api/strategy/positions?status=OPEN&user_id=${userId}`),
            ]);
            // 如果后端返回 binance_error（交易所临时不可用），保持上次有效数据
            if (!walletRes?.source?.includes('error')) {
                setWallet(walletRes || { current_balance: 0, total_pnl: 0, total_trades: 0, win_trades: 0 });
            }
            setPositions(posRes.positions || []);
        } catch (err) {
            console.error(err);
        }
    }, [userId, showOnboarding]);

    useEffect(() => {
        fetchData();
        refreshMarket();
        const timer = setInterval(() => { refreshMarket(); fetchData(); }, 15000);
        return () => clearInterval(timer);
    }, [fetchData, refreshMarket, userId]);

    const handleAction = async (action) => {
        if (!activeTrader || acting) return;
        const lowerAction = action.toLowerCase();
        setActing(true);
        try {
            await postJson(`/api/workspace/trader-instances/${activeTrader.id}/runtime-action?user_id=${userId}`, { action: lowerAction });
            await fetchData();
            showFeedback(`${lowerAction === 'start' ? '已成功启动' : '已成功停止'}`, "success");
        } catch (err) {
            showFeedback("操作失败，请重试", "error");
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

    const handleDeleteInstance = () => {
        setPendingChanges({ strategy_profile_id: '', exchange_account_id: '', llm_config_id: '' });
        setIsConfirmingDelete(false);
        showFeedback("配置已清除", "success");
    };

    const totalPnL = useMemo(() => {
        return Number(wallet?.total_pnl || 0);
    }, [wallet]);

    const winRate = useMemo(() => {
        if (!wallet || !wallet.total_trades) return 0;
        return (wallet.win_trades / wallet.total_trades) * 100;
    }, [wallet]);

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
            {feedback && (
                <div className={`fixed top-6 right-6 z-[100] px-6 py-3 rounded-2xl shadow-2xl border animate-in slide-in-from-top-4 duration-300 ${feedback.type === 'success' ? 'bg-emerald-500 text-white border-emerald-400' : 'bg-rose-500 text-white border-rose-400'}`}>
                    <div className="flex items-center gap-3 font-bold text-sm">
                        {feedback.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
                        {feedback.msg}
                    </div>
                </div>
            )}

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
                        <div className="w-44"><CustomDropdown label="交易账户" options={accounts.map(a => ({ id: a.id, name: a.display_name }))} value={pendingChanges.exchange_account_id} onChange={id => setPendingChanges(p => ({ ...p, exchange_account_id: id }))} icon={Globe} disabled={isRunning} /></div>
                        <div className="w-40"><CustomDropdown label="执行模型" options={llmConfigs.map(c => ({ id: c.id, name: c.name }))} value={pendingChanges.llm_config_id} onChange={id => setPendingChanges(p => ({ ...p, llm_config_id: id }))} icon={Cpu} disabled={isRunning} /></div>
                        <div className="w-44"><CustomDropdown label="策略配置" options={strategies.map(s => ({ id: s.id, name: s.name }))} value={pendingChanges.strategy_profile_id} onChange={id => setPendingChanges(p => ({ ...p, strategy_profile_id: id }))} icon={Target} disabled={isRunning} /></div>
                    </div>
                </div>
                <div className="flex items-center gap-3 pl-6 border-l border-white/5">
                    <Button variant="outline" size="sm" onClick={() => window.location.hash = '/strategies'} className="text-[10px] font-black uppercase tracking-widest h-9 px-4">编辑策略</Button>
                    {isRunning ? (
                        <Button variant="danger" size="sm" icon={Square} onClick={() => handleAction('STOP')} disabled={acting} className="h-9 px-6 font-black uppercase text-[10px]">停止运行</Button>
                    ) : (
                        <Button variant="primary" size="sm" icon={Play} onClick={() => handleSaveInstance().then(() => handleAction('START'))} disabled={acting || saving} className="h-9 px-6 font-black uppercase text-[10px]">开始运行</Button>
                    )}
                    {!isRunning && (
                        <div className="flex items-center gap-1">
                            <Button 
                                variant="outline" 
                                size="sm" 
                                onClick={handleClearConfig} 
                                className="h-9 px-4 text-slate-500 border-white/5 hover:bg-rose-500/10 hover:text-rose-500 hover:border-rose-500/20 transition-all font-black text-[10px] uppercase tracking-widest"
                            >
                                清除配置
                            </Button>
                        </div>
                    )}
                </div>
            </header>

            {/* Dashboard Stats */}
            <div className="grid grid-cols-4 gap-6 flex-shrink-0 animate-in fade-in duration-700">
                <StatCard 
                    icon={Wallet} 
                    label="账户总余额" 
                    value={isRunning && wallet ? `${Number(wallet.current_balance || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USDT` : '--'} 
                    tone="emerald" 
                />
                <StatCard 
                    icon={DollarSign} 
                    label="可用余额" 
                    value={isRunning && wallet ? `${Number((wallet.current_balance || 0) - (wallet.margin_in_use || 0)).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USDT` : '--'} 
                    tone="amber" 
                />
                <StatCard 
                    icon={BarChart3} 
                    label="总盈亏" 
                    value={isRunning && wallet && (wallet.total_trades > 0 || positions.length > 0) ? (
                        <div className="flex items-baseline gap-2">
                            <span>{`${totalPnL >= 0 ? '+' : ''}${totalPnL.toFixed(2)} USDT`}</span>
                            <span className={`text-sm font-bold ${totalPnL >= 0 ? 'text-emerald-500' : 'text-rose-500'} opacity-90`}>
                                ({totalPnL >= 0 ? '+' : ''}{((totalPnL / Math.max(1, (Number(wallet.current_balance || 0) - totalPnL))) * 100).toFixed(1)}%)
                            </span>
                        </div>
                    ) : '--'} 
                    tone={totalPnL >= 0 ? 'emerald' : 'rose'} 
                />
                <StatCard 
                    icon={Target} 
                    label="胜率" 
                    value={isRunning && wallet && wallet.total_trades > 0 ? `${winRate.toFixed(1)}%` : '--'} 
                    tone="emerald" 
                />
            </div>

            {/* Split Workspace */}
            <div className="flex-1 flex gap-8 min-h-0 animate-in fade-in duration-1000">
                <main className="flex-[7] flex flex-col bg-[#0e1215]/50 border border-white/5 rounded-3xl overflow-hidden shadow-2xl backdrop-blur-sm relative">
                    <div className="flex border-b border-white/5 bg-black/10 px-4">
                        {['positions', 'orders', 'history'].map(tab => (
                            <button key={tab} onClick={() => setActiveTab(tab)} className={`px-6 py-4 text-[10px] font-black uppercase tracking-widest relative transition-all ${activeTab === tab ? 'text-emerald-400' : 'text-slate-200'}`}>
                                {tab === 'positions' ? '实盘持仓' : tab === 'orders' ? '待成交委托' : '历史成交流水'}
                                {activeTab === tab && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-500 shadow-[0_0_10px_#6366f1]" />}
                            </button>
                        ))}
                    </div>
                    <div className="flex-1 p-0 overflow-y-auto custom-scrollbar">
                        {activeTab === 'positions' && (
                            <table className="w-full text-left">
                                <thead className="sticky top-0 bg-[#0B0E11] z-10 border-b border-white/5 text-[9px] font-black text-slate-500 uppercase tracking-widest">
                                    <tr><th className="py-4 px-6">交易对</th><th className="py-4 px-6 text-right">持仓数量</th><th className="py-4 px-6 text-right">开仓均价</th><th className="py-4 px-6 text-right">未实现盈亏</th></tr>
                                </thead>
                                <tbody className="divide-y divide-white/5">
                                    {positions.length > 0 ? positions.map((pos, i) => (
                                        <tr key={i} className="hover:bg-white/[0.02] transition-colors">
                                            <td className="py-4 px-6 font-bold">{pos.symbol}</td>
                                            <td className="py-4 px-6 text-right font-mono text-sm">{pos.quantity}</td>
                                            <td className="py-4 px-6 text-right font-mono text-sm">{pos.entry_price}</td>
                                            <td className={`py-4 px-6 text-right font-mono font-bold ${Number(pos.unrealized_pnl) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{pos.unrealized_pnl}</td>
                                        </tr>
                                    )) : (
                                        <tr><td colSpan="4" className="py-12 text-center text-slate-600 text-[10px] font-bold tracking-[0.2em] opacity-40">暂无活跃持仓</td></tr>
                                    )}
                                </tbody>
                            </table>
                        )}
                        {activeTab === 'orders' && <div className="p-12 text-center text-slate-600 text-[10px] font-black opacity-40 uppercase tracking-widest">暂无记录</div>}
                        {activeTab === 'history' && <div className="p-12 text-center text-slate-600 text-[10px] font-black opacity-40 uppercase tracking-widest">暂无记录</div>}
                        {!isRunning && positions.length === 0 && activeTab === 'positions' && <div className="h-full flex items-center justify-center opacity-30 italic text-[10px] uppercase tracking-[0.2em] font-black">待机模式 - 扫描未启动</div>}
                    </div>
                </main>
                <aside className="flex-[3] flex flex-col bg-[#0e1215]/50 border border-white/5 rounded-3xl overflow-hidden shadow-2xl backdrop-blur-sm relative min-w-[340px]">
                    <div className="flex items-center justify-between border-b border-white/5 bg-black/10 px-6 h-[49px]">
                        <div className="flex items-center gap-2"><Clock className="w-4 h-4 text-emerald-400" /><h3 className="text-[10px] font-black text-white uppercase tracking-widest">实时智脑决策日志</h3></div>
                    </div>
                    <div className="flex-1 overflow-y-auto custom-scrollbar flex flex-col gap-3 p-4">
                        {logs.length > 0 ? logs.map((log, idx) => <DecisionCard key={idx} log={log} />) : (
                            <div className="h-full flex items-center justify-center text-slate-600 text-[10px] font-black opacity-30 uppercase tracking-[0.2em] italic">
                                等待首份研究报告...
                            </div>
                        )}
                    </div>
                </aside>
            </div>
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
        </div>
    );
}

// --- Internal Decision Card ---
function DecisionCard({ log }) {
    const [open, setOpen] = useState(false);
    
    // NO FALLBACKS to current date. If timestamp is missing, it should reflect the real missing state.
    const date = useMemo(() => {
        if (!log.timestamp) return null;
        const d = new Date(log.timestamp);
        return isNaN(d.getTime()) ? new Date(log.timestamp.replace(' ', 'T')) : d;
    }, [log.timestamp]);

    if (!date) return null; // Don't render a card with fake time

    const formattedDate = `${date.getFullYear()}/${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`;
    
    // Logic: '执行' if decision implies an action, otherwise '等待'
    const isExecution = log.strategy_decision?.toLowerCase().includes('open') || 
                        log.strategy_decision?.toLowerCase().includes('close') ||
                        (log.actions_taken && log.actions_taken !== '[]');

    return (
        <div className={`p-4 rounded-2xl border transition-all ${open ? 'bg-[#0a0d0f] border-emerald-500/30' : 'bg-[#0e1215]/40 border-white/5 hover:border-white/10'}`}>
            <div className="flex items-center justify-between mb-2">
                <div className="text-[9px] font-mono text-slate-500 font-bold">{formattedDate}</div>
                <div className={`px-2 py-0.5 rounded-[4px] text-[8px] font-black uppercase ${isExecution ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-amber-500/10 text-amber-500 border border-amber-500/20'}`}>
                    {isExecution ? '执行' : '等待'}
                </div>
            </div>
            <div className="flex items-center justify-between gap-4 py-1">
                <div className="flex items-center gap-2">
                    <Target className="w-3.5 h-3.5 text-emerald-400" />
                    <div className="text-xs font-black text-slate-100 uppercase">{log.symbols}</div>
                </div>
                <button onClick={() => setOpen(!open)} className="p-1 hover:bg-white/5 rounded-lg text-slate-500 transition-all">
                    <ChevronDown className={`w-4 h-4 transition-transform ${open ? 'rotate-180' : ''}`} />
                </button>
            </div>
            {open && (
                <div className="mt-3 pt-3 border-t border-white/5 space-y-3 animate-in slide-in-from-top-1 duration-300">
                    <div>
                        <div className="text-[8px] font-black text-slate-500 uppercase tracking-widest mb-1">市场分析 (Market Analysis)</div>
                        <p className="text-[10px] text-slate-400 leading-relaxed font-bold opacity-80">{log.market_analysis || '暂无分析数据'}</p>
                    </div>
                    <div>
                        <div className="text-[8px] font-black text-slate-500 uppercase tracking-widest mb-1">执行决策 (Decision)</div>
                        <div className="p-2.5 bg-black/40 rounded-xl text-[10px] text-emerald-300 font-mono border border-white/5 whitespace-pre-wrap leading-relaxed shadow-inner">
                            {log.strategy_decision || '正在同步中...'}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
