import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    Play, Square, Clock, Activity, Calendar, Settings2, Wallet,
    LineChart as LineChartIcon, Sliders, CheckCircle2, ChevronDown, ArrowRight
} from 'lucide-react';
import {
    LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
    CartesianGrid, ReferenceLine, AreaChart, Area, ComposedChart, Bar
} from 'recharts';
import Toast from '../components/common/Toast';
import { getJson, postJson } from '../services/apiClient';

// =============================================
// 高级统计卡片
// =============================================
const StatCard = ({ label, value, suffix = '', icon: Icon, tone = 'slate', subtitle }) => {
    const tones = {
        green: 'text-emerald-400 bg-emerald-500/5 border-emerald-500/20',
        red: 'text-rose-400 bg-rose-500/5 border-rose-500/20',
        amber: 'text-amber-400 bg-amber-500/5 border-amber-500/20',
        blue: 'text-sky-400 bg-sky-500/5 border-sky-500/20',
        slate: 'text-slate-200 bg-white/5 border-white/10',
    };
    return (
        <div className={`relative rounded-2xl border px-5 py-4 backdrop-blur-xl overflow-hidden ${tones[tone]}`}>
            <div className="relative z-10 flex items-center justify-between mb-2">
                <span className="text-xs uppercase tracking-widest opacity-70 font-bold">{label}</span>
                {Icon && <Icon className="w-4 h-4 opacity-50" />}
            </div>
            <div className="relative z-10 flex items-baseline gap-1">
                <div className="text-2xl font-extrabold tabular-nums tracking-tight">{value}</div>
                {suffix && <span className="text-sm opacity-60 font-medium">{suffix}</span>}
            </div>
            {subtitle && (
                <div className="relative z-10 mt-1.5 text-[11px] font-medium opacity-50 tracking-wider">
                    {subtitle}
                </div>
            )}
        </div>
    );
};

const FormField = ({ label, icon: Icon, children, zIndex = 1 }) => (
    <div className="flex flex-col gap-2 relative w-full" style={{ zIndex }}>
        <label className="flex items-center gap-2 text-[10px] font-bold text-slate-400 uppercase tracking-widest pl-1">
            {Icon && <Icon className="w-3.5 h-3.5 text-emerald-500/70" />}
            {label}
        </label>
        <div className="relative w-full">{children}</div>
    </div>
);

const CustomSelect = ({ value, onChange, options, disabled, placeholder = "请选择" }) => {
    const [isOpen, setIsOpen] = useState(false);
    const selectRef = useRef(null);

    useEffect(() => {
        const handleClickOutside = (e) => {
            if (selectRef.current && !selectRef.current.contains(e.target)) setIsOpen(false);
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const selectedOption = options.find(o => o.value == value) || null;

    return (
        <div ref={selectRef} className={`relative w-full ${disabled ? 'opacity-50 pointer-events-none' : ''}`}>
            <div
                onClick={() => setIsOpen(!isOpen)}
                className="w-full h-[46px] bg-black/40 border border-white/10 rounded-xl px-4 text-sm text-white shadow-inner cursor-pointer hover:border-emerald-500/50 transition-all flex items-center justify-between group"
            >
                <span className={selectedOption ? "text-white truncate pr-4" : "text-slate-500 truncate pr-4"}>
                    {selectedOption ? selectedOption.label : placeholder}
                </span>
                <ChevronDown className={`w-4 h-4 text-slate-500 transition-transform duration-300 flex-shrink-0 ${isOpen ? 'rotate-180 text-emerald-400' : 'group-hover:text-emerald-400'}`} />
            </div>

            {isOpen && (
                <div className="absolute z-50 top-[calc(100%+8px)] left-0 right-0 bg-[#0a0d0f]/95 backdrop-blur-2xl border border-emerald-500/20 rounded-xl shadow-[0_10px_40px_rgba(0,0,0,0.8)] overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
                    <div className="max-h-60 overflow-y-auto custom-scrollbar p-1.5 flex flex-col gap-1">
                        {options.map((opt) => (
                            <div
                                key={opt.value}
                                onClick={() => { onChange(opt.value); setIsOpen(false); }}
                                className={`px-4 py-3 rounded-lg text-sm cursor-pointer transition-colors flex items-center justify-between ${value == opt.value
                                    ? 'bg-emerald-500/10 text-emerald-400 font-bold'
                                    : 'text-slate-300 hover:bg-white/10 hover:text-white'
                                    }`}
                            >
                                <span className="truncate">{opt.label}</span>
                                {value == opt.value && <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

const TimeRangePicker = ({ startTime, endTime, onStartChange, onEndChange, disabled }) => {
    const [isOpen, setIsOpen] = useState(false);
    const containerRef = useRef(null);

    useEffect(() => {
        const handleClickOutside = (e) => {
            if (containerRef.current && !containerRef.current.contains(e.target)) setIsOpen(false);
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const formatDt = (d) => {
        const pad = (n) => n.toString().padStart(2, '0');
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    };

    const applyRange = (days) => {
        const end = new Date();
        end.setMinutes(0, 0, 0);
        const start = new Date(end);
        start.setDate(start.getDate() - days);
        onEndChange(formatDt(end));
        onStartChange(formatDt(start));
        setIsOpen(false);
    };

    return (
        <div ref={containerRef} className="relative w-full">
            <div
                className={`w-full h-[46px] bg-black/40 border border-white/10 rounded-xl px-4 text-sm text-white shadow-inner flex items-center justify-between cursor-pointer group hover:border-emerald-500/50 transition-all ${disabled ? 'opacity-50 pointer-events-none' : ''}`}
                onClick={() => setIsOpen(!isOpen)}
            >
                <span className="truncate flex items-center gap-2 text-slate-300 font-mono text-[13px]">
                    {startTime.replace('T', ' ')} <ArrowRight className="w-3.5 h-3.5 text-emerald-500" /> {endTime.replace('T', ' ')}
                </span>
                <Calendar className={`w-4 h-4 transition-transform duration-300 flex-shrink-0 ${isOpen ? 'text-emerald-400 scale-110' : 'text-slate-500 group-hover:text-emerald-400'}`} />
            </div>

            {isOpen && (
                <div className="absolute z-50 top-[calc(100%+8px)] left-0 w-[420px] bg-[#0a0d0f]/95 backdrop-blur-2xl border border-emerald-500/20 rounded-xl shadow-[0_10px_50px_rgba(0,0,0,0.8)] p-4 flex gap-5 animate-in fade-in slide-in-from-top-2 duration-200">
                    <div className="w-[120px] flex flex-col gap-1 border-r border-white/10 pr-5">
                        <div className="text-[10px] text-slate-500 font-bold uppercase mb-2 tracking-widest">快捷选择</div>
                        {[{ l: '最近 1 天', v: 1 }, { l: '最近 7 天', v: 7 }, { l: '最近 30 天', v: 30 }, { l: '最近 90 天', v: 90 }, { l: '最近 1 年', v: 365 }].map(opt => (
                            <button key={opt.v} onClick={() => applyRange(opt.v)} className="text-left px-3 py-2.5 text-xs text-slate-300 font-medium hover:text-white hover:bg-emerald-500/10 hover:text-emerald-400 rounded-lg transition-colors border border-transparent hover:border-emerald-500/20">
                                {opt.l}
                            </button>
                        ))}
                    </div>
                    <div className="flex-1 flex flex-col justify-between py-1">
                        <div className="flex flex-col gap-4">
                            <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">精确日期区间</div>
                            <div>
                                <label className="text-[11px] text-slate-400 font-bold mb-1.5 block">起始点 (START)</label>
                                <input type="datetime-local" value={startTime} onChange={e => onStartChange(e.target.value)} className="w-full h-10 bg-black/60 border border-white/10 rounded-xl px-3 text-sm text-white font-mono focus:border-emerald-500/50 outline-none" />
                            </div>
                            <div>
                                <label className="text-[11px] text-slate-400 font-bold mb-1.5 block">结算点 (END)</label>
                                <input type="datetime-local" value={endTime} onChange={e => onEndChange(e.target.value)} className="w-full h-10 bg-black/60 border border-white/10 rounded-xl px-3 text-sm text-white font-mono focus:border-emerald-500/50 outline-none" />
                            </div>
                        </div>
                        <div className="mt-4 text-right">
                            <button onClick={() => setIsOpen(false)} className="px-5 py-2 bg-emerald-500 text-white text-xs font-bold rounded-xl hover:bg-emerald-400 transition-colors shadow-[0_0_15px_rgba(16,185,129,0.2)]">
                                确 认
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

const DualCurveChart = ({ equity, drawdown, initialCapital }) => (
    <div className="w-full h-[360px]">
        <ResponsiveContainer width="100%" height="100%">
            <ComposedChart margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                    <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorMd" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2} />
                        <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                    </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
                <XAxis dataKey="time" xAxisId={0} tick={{ fill: '#64748b', fontSize: 11 }} tickFormatter={v => v?.slice(5, 10) || ''} axisLine={{ stroke: 'rgba(255,255,255,0.05)' }} allowDuplicatedCategory={false} />
                
                <YAxis yAxisId="left" tick={{ fill: '#64748b', fontSize: 11 }} tickFormatter={v => `$${v >= 1000 ? (v / 1000).toFixed(1) + 'K' : v}`} domain={['auto', 'auto']} axisLine={false} />
                <YAxis yAxisId="right" orientation="right" tick={{ fill: '#ef4444', fontSize: 11 }} tickFormatter={v => `${v}%`} domain={[0, 'auto']} reversed axisLine={false} />
                
                <Tooltip
                    contentStyle={{ backgroundColor: 'rgba(10, 13, 15, 0.95)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12, fontSize: 12 }}
                    itemStyle={{ color: '#10b981' }}
                    labelStyle={{ color: '#94a3b8', fontSize: 11 }}
                />
                
                <ReferenceLine y={initialCapital} yAxisId="left" stroke="rgba(255,255,255,0.15)" strokeDasharray="4 4" />
                
                {/* 权益曲线 */}
                <Area data={equity} xAxisId={0} type="monotone" dataKey="equity" stroke="#10b981" strokeWidth={2} fill="url(#colorEquity)" yAxisId="left" name="总权益" isAnimationActive={true} />
                
                {/* 回撤曲线 */}
                <Area data={drawdown} xAxisId={0} type="monotone" dataKey="drawdown_pct" stroke="#ef4444" strokeWidth={1} fill="url(#colorMd)" yAxisId="right" name="回撤%" isAnimationActive={true} />
            </ComposedChart>
        </ResponsiveContainer>
    </div>
);

const TradeStreamTable = ({ trades }) => {
    if (!trades || trades.length === 0) return (
        <div className="flex items-center justify-center h-32 text-slate-500 font-mono text-sm border border-white/5 rounded-2xl bg-black/20">
            暂无交易发生...
        </div>
    );
    const recentTrades = [...trades].reverse();

    return (
        <div className="overflow-auto custom-scrollbar border border-white/[0.05] rounded-2xl bg-black/30 h-[360px]">
             <table className="w-full text-left border-collapse min-w-[600px]">
                <thead className="sticky top-0 bg-[#0a0d0f]/95 backdrop-blur z-10 shadow-sm border-b border-white/5">
                    <tr>
                        <th className="py-3 px-4 text-[10px] font-extrabold text-slate-500 uppercase tracking-widest">进出场时机</th>
                        <th className="py-3 px-4 text-[10px] font-extrabold text-slate-500 uppercase tracking-widest">方向</th>
                        <th className="py-3 px-4 text-[10px] font-extrabold text-slate-500 uppercase tracking-widest text-right">进场/出场价</th>
                        <th className="py-3 px-4 text-[10px] font-extrabold text-slate-500 uppercase tracking-widest text-right">利润</th>
                    </tr>
                </thead>
                <tbody className="text-sm">
                    {recentTrades.map((t, i) => (
                        <tr key={i} className="border-b border-white/[0.02] hover:bg-white/[0.03] transition-colors">
                            <td className="py-2.5 px-4 text-slate-400 font-mono text-xs">
                                <div className="text-white">{t.entry_time?.slice(5)}</div>
                                <div className="opacity-50 mt-0.5">{t.exit_time?.slice(5)}</div>
                            </td>
                            <td className="py-2.5 px-4">
                                <span className={`px-2 py-1 rounded text-[10px] font-bold border ${t.direction === 'LONG' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                                    }`}>
                                    {t.direction === 'LONG' ? '做多' : '做空'}
                                </span>
                                <div className="text-[10px] text-slate-500 mt-1 pl-1 line-clamp-1">{t.exit_reason}</div>
                            </td>
                            <td className="py-2.5 px-4 text-right font-mono text-slate-200">
                                <div>${t.entry_price?.toFixed(2)}</div>
                                <div className="text-slate-500 mt-0.5">${t.exit_price?.toFixed(2)}</div>
                            </td>
                            <td className={`py-2.5 px-4 text-right font-bold tabular-nums font-mono ${t.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                {t.pnl >= 0 ? '+' : ''}{t.pnl?.toFixed(2)}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};


const BacktestPage = ({ userId }) => {
    // 基础数据
    const [strategies, setStrategies] = useState([]);
    
    // 当前配置
    const [selectedStrategyName, setSelectedStrategyName] = useState('');
    const [strategyParams, setStrategyParams] = useState({});
    
    const [symbol, setSymbol] = useState('BTC');
    const [interval, setInterval_] = useState('4h');
    const [startTime, setStartTime] = useState('');
    const [endTime, setEndTime] = useState('');
    const [initialCapital, setInitialCapital] = useState(10000);
    const [leverage, setLeverage] = useState(10);
    const [riskPerTrade, setRiskPerTrade] = useState(0.02);

    const symbolOptions = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP'];
    const intervalOptions = ['5m', '15m', '30m', '1h', '4h', '1d'];

    // 状态
    const [jobId, setJobId] = useState(null);
    const [jobStatus, setJobStatus] = useState(null);
    const [result, setResult] = useState(null);
    const [loading, setLoading] = useState(false);
    const [feedback, setFeedback] = useState(null);
    const pollRef = useRef(null);

    const showFeedback = (msg, type) => {
        setFeedback({ msg, type });
        setTimeout(() => setFeedback(null), 4000);
    };

    // 初始化时间 (默认选取最近 6 个月)
    useEffect(() => {
        const end = new Date();
        end.setMinutes(0, 0, 0);
        const start = new Date(end);
        start.setMonth(start.getMonth() - 6);
        const formatDt = (d) => {
            const pad = (n) => n.toString().padStart(2, '0');
            return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
        };
        setEndTime(formatDt(end));
        setStartTime(formatDt(start));
    }, []);

    // 拉取可用策略库
    useEffect(() => {
        getJson(`/api/backtest/strategies`).then(res => {
            if (res.strategies && res.strategies.length > 0) {
                setStrategies(res.strategies);
                setSelectedStrategyName(res.strategies[0].name);
            }
        }).catch(err => {
            console.error("加载策略失败:", err);
            showFeedback("无法加载量化策略库", "error");
        });
    }, []);

    // 策略切换时，用默认参数填充表单
    useEffect(() => {
        if (!selectedStrategyName || strategies.length === 0) return;
        const s = strategies.find(s => s.name === selectedStrategyName);
        if (s) {
            const defParams = {};
            s.params.forEach(p => {
                defParams[p.name] = p.default;
            });
            setStrategyParams(defParams);
        }
    }, [selectedStrategyName, strategies]);

    const handleParamChange = (name, value) => {
        setStrategyParams(prev => ({ ...prev, [name]: value }));
    };

    const handleRun = async () => {
        try {
            setLoading(true);
            setResult(null);
            setJobStatus(null);
            
            // 确保参数转换为数值
            const parsedParams = {};
            Object.entries(strategyParams).forEach(([k, v]) => {
                parsedParams[k] = Number(v);
            });

            const res = await postJson('/api/backtest/run', {
                symbol, interval,
                start_date: startTime.replace('T', ' '),
                end_date: endTime.replace('T', ' '),
                user_id: userId,
                initial_capital: initialCapital,
                leverage: leverage,
                risk_per_trade: riskPerTrade,
                strategy_type: selectedStrategyName,
                strategy_params: parsedParams,
            });
            
            setJobId(res.job_id);
            showFeedback('量化回测引擎已启动', 'success');
            startPolling(res.job_id);
        } catch (e) {
            setLoading(false);
            showFeedback(e.message || '启动失败', 'error');
        }
    };

    const startPolling = useCallback((id) => {
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = setInterval(async () => {
            try {
                const status = await getJson(`/api/backtest/status/${id}?user_id=${userId}`);
                setJobStatus(status);

                if (status.status === 'COMPLETED') {
                    clearInterval(pollRef.current);
                    const res = await getJson(`/api/backtest/result/${id}?user_id=${userId}`);
                    setResult(res);
                    setLoading(false);
                    showFeedback(`回测完成！耗时: ${res.elapsed_ms || '? '}ms`, 'success');
                } else if (['FAILED', 'CANCELLED'].includes(status.status)) {
                    clearInterval(pollRef.current);
                    setLoading(false);
                    showFeedback(`回测终止: ${status.status}`, 'error');
                }
            } catch (e) {
                console.error('Poll error:', e);
            }
        }, 1000); 
    }, [userId]);

    useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

    const inputClass = "w-full h-[46px] bg-black/40 border border-white/10 rounded-xl px-4 text-sm text-white shadow-inner focus:outline-none focus:border-emerald-500/50 appearance-none font-mono";

    const currentStrategy = strategies.find(s => s.name === selectedStrategyName);

    return (
        <div className="h-full overflow-y-auto custom-scrollbar flex flex-col pt-8 px-6 pb-32 animate-in fade-in duration-500 w-full mx-auto max-w-[1400px]">
            <Toast feedback={feedback} />

            <header className="mb-8 flex justify-between items-end">
                <div>
                    <h1 className="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-sky-400 tracking-tight mb-2">专业量化回测引擎</h1>
                    <p className="text-slate-400 text-sm">纯计算极速执行 · 参数完美映射 · 盈亏精确度量</p>
                </div>
                {result && result.benchmark && (
                    <div className="flex items-center gap-4 bg-white/5 border border-white/10 px-4 py-2 rounded-xl backdrop-blur-md">
                        <span className="text-xs text-slate-400 uppercase tracking-wider font-bold">Buy & Hold 基准收益率</span>
                        <span className={`text-lg font-bold font-mono ${result.benchmark.buy_hold_return_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                            {result.benchmark.buy_hold_return_pct >= 0 ? '+' : ''}{result.benchmark.buy_hold_return_pct}%
                        </span>
                    </div>
                )}
            </header>

            <div className="grid grid-cols-1 xl:grid-cols-12 gap-8 relative z-10 w-full">
                
                {/* 左侧：参数配置套件 */}
                <div className="xl:col-span-4 flex flex-col gap-6">
                    {/* 策略选取面板 */}
                    <div className="bg-[#0a0d0f]/80 backdrop-blur-2xl border border-white/10 rounded-[28px] p-6 shadow-xl">
                        <div className="flex items-center gap-2 mb-6 border-b border-white/5 pb-4">
                            <Settings2 className="w-5 h-5 text-emerald-400" />
                            <h2 className="text-sm font-extrabold text-white tracking-widest uppercase">策略配置</h2>
                        </div>
                        
                        <div className="flex flex-col gap-5">
                            <FormField label="选择量化策略" zIndex={50}>
                                <CustomSelect
                                    value={selectedStrategyName}
                                    onChange={setSelectedStrategyName}
                                    options={strategies.map(s => ({ value: s.name, label: `${s.icon} ${s.label}` }))}
                                    disabled={loading}
                                />
                            </FormField>
                            
                            {currentStrategy && (
                                <div className="relative z-[49] text-xs text-slate-400 leading-relaxed bg-black/30 p-3 rounded-lg border border-white/5">
                                    {currentStrategy.description}
                                </div>
                            )}

                            {/* 动态参数输入 */}
                            {currentStrategy && currentStrategy.params.map((p, idx) => (
                                <FormField key={p.name} label={p.label} zIndex={48 - idx}>
                                    <div className="relative">
                                        <input 
                                            type="number" 
                                            value={strategyParams[p.name] !== undefined ? strategyParams[p.name] : p.default}
                                            onChange={e => handleParamChange(p.name, e.target.value)}
                                            step={p.step || "any"}
                                            disabled={loading}
                                            className={`${inputClass} !text-right pr-16`}
                                        />
                                        <div className="absolute top-0 right-0 h-full flex items-center px-4 text-xs font-bold text-slate-500 bg-white/5 rounded-r-xl border-l border-white/5">
                                            数值
                                        </div>
                                    </div>
                                    {p.description && <span className="text-[10px] text-slate-500 font-medium pl-1">{p.description}</span>}
                                </FormField>
                            ))}
                        </div>
                    </div>

                    {/* 标的与资金面板 */}
                    <div className="bg-[#0a0d0f]/80 backdrop-blur-2xl border border-white/10 rounded-[28px] p-6 shadow-xl relative z-0">
                        <div className="flex items-center gap-2 mb-6 border-b border-white/5 pb-4">
                            <Sliders className="w-5 h-5 text-sky-400" />
                            <h2 className="text-sm font-extrabold text-white tracking-widest uppercase">环境设定</h2>
                        </div>

                        <div className="grid grid-cols-2 gap-5 mb-5">
                            <FormField label="交易对" icon={Activity} zIndex={40}>
                                <CustomSelect value={symbol} onChange={setSymbol} options={symbolOptions.map(s=>({value:s,label:`${s}/USDT`}))} disabled={loading} />
                            </FormField>

                            <FormField label="数据周期" icon={Clock} zIndex={30}>
                                <CustomSelect value={interval} onChange={setInterval_} options={intervalOptions.map(t=>({value:t,label:t}))} disabled={loading} />
                            </FormField>
                        </div>

                        <div className="mb-5">
                            <FormField label="回测区间" icon={Calendar} zIndex={20}>
                                <TimeRangePicker startTime={startTime} endTime={endTime} onStartChange={setStartTime} onEndChange={setEndTime} disabled={loading} />
                            </FormField>
                        </div>

                        <div className="grid grid-cols-2 gap-5 mb-6">
                            <FormField label="初始资金" icon={Wallet}>
                                <input type="number" value={initialCapital} onChange={e=>setInitialCapital(Number(e.target.value))} className={inputClass} disabled={loading} />
                            </FormField>
                            
                            <FormField label="杠杆倍数">
                                <input type="number" value={leverage} onChange={e=>setLeverage(Number(e.target.value))} className={inputClass} disabled={loading} />
                            </FormField>
                        </div>

                        <button 
                            onClick={handleRun} 
                            disabled={loading || !selectedStrategyName} 
                            className={`w-full h-12 rounded-xl text-sm font-extrabold transition-all shadow-lg flex items-center justify-center gap-2
                                ${loading 
                                    ? 'bg-emerald-500/50 cursor-wait text-white' 
                                    : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-500/20'}`}
                        >
                            {loading ? <><div className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin"></div> 极速演算中...</> : <><Play className="w-4 h-4 fill-current"/> 启动向量化引擎</>}
                        </button>
                    </div>
                </div>

                {/* 右侧：结果展示 */}
                <div className="xl:col-span-8 flex flex-col gap-6">
                    {/* 加载骨架屏 */}
                    {loading && !result && (
                        <div className="h-full flex-1 flex flex-col items-center justify-center bg-black/20 rounded-[32px] border border-white/5 border-dashed min-h-[500px]">
                            <div className="relative">
                                <div className="absolute inset-0 bg-emerald-500 blur-xl opacity-20 animate-pulse"></div>
                                <Activity className="w-16 h-16 text-emerald-400 animate-bounce relative z-10" />
                            </div>
                            <div className="mt-6 text-xl font-extrabold text-white tracking-wider animate-pulse">正在穿梭历史维度...</div>
                            <div className="mt-2 text-sm text-slate-500 font-mono">执行中 耗时极速</div>
                        </div>
                    )}

                    {/* 结果可视化 */}
                    {!loading && result && result.summary && (
                        <div className="flex flex-col gap-6 animate-in slide-in-from-right-8 fade-in duration-500">
                            
                            {/* 核心指标墙 */}
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                <StatCard label="总收益率" value={result.summary.total_return_pct + '%'} tone={result.summary.total_return_pct > 0 ? 'green' : 'red'} subtitle={`年化: ${result.summary.annualized_return_pct}%`} />
                                <StatCard label="最大回撤" value={result.summary.max_drawdown_pct + '%'} tone={result.summary.max_drawdown_pct < 15 ? 'green' : 'red'} subtitle={`净值缩水: $${result.summary.max_drawdown_usd}`} />
                                <StatCard label="夏普比率" value={result.summary.sharpe_ratio} tone={result.summary.sharpe_ratio >= 1.5 ? 'green' : (result.summary.sharpe_ratio > 0 ? 'slate' : 'red')} subtitle={`Calmar: ${result.summary.calmar_ratio}`} />
                                <StatCard label="策略胜率" value={result.summary.win_rate + '%'} tone={result.summary.win_rate > 50 ? 'green' : 'slate'} subtitle={`${result.summary.win_count} 胜 / ${result.summary.lose_count} 负`} />
                            </div>
                            
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-4 flex flex-col justify-center">
                                    <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-1">盈亏比 / 利润因子</div>
                                    <div className="text-xl font-bold font-mono text-white">{result.summary.risk_reward} <span className="text-slate-500 text-sm font-sans mx-1">/</span> {result.summary.profit_factor}</div>
                                </div>
                                <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-4 flex flex-col justify-center">
                                    <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-1">连赢 / 连亏 (最大)</div>
                                    <div className="text-xl font-bold font-mono text-white">{result.summary.max_consecutive_wins} <span className="text-slate-500 text-sm font-sans">局</span> <span className="text-slate-500 font-sans mx-1">-</span> {result.summary.max_consecutive_losses} <span className="text-slate-500 text-sm font-sans">局</span></div>
                                </div>
                                <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-4 flex flex-col justify-center">
                                    <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-1">总交易次数</div>
                                    <div className="text-xl font-bold font-mono text-white">{result.summary.total_trades} <span className="text-slate-500 text-sm font-sans ml-1">笔</span></div>
                                </div>
                                <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-4 flex flex-col justify-center">
                                    <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-1">平均持仓时间</div>
                                    <div className="text-xl font-bold font-mono text-white">{result.summary.avg_hold_hours} <span className="text-slate-500 text-sm font-sans ml-1">小时</span></div>
                                </div>
                            </div>

                            {/* 图表展示 */}
                            <div className="bg-[#0a0d0f]/60 border border-white/10 rounded-[28px] p-6 shadow-xl">
                                <div className="flex items-center justify-between mb-6">
                                    <h3 className="text-sm font-bold text-slate-300 uppercase tracking-widest flex items-center gap-2">
                                        <LineChartIcon className="w-5 h-5 text-emerald-500" />
                                        权益与回撤分析
                                    </h3>
                                </div>
                                <DualCurveChart 
                                    equity={result.equity_curve} 
                                    drawdown={result.drawdown_curve} 
                                    initialCapital={initialCapital} 
                                />
                            </div>

                            {/* 交易表现拆解 & 列表 */}
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                <div className="bg-white/[0.02] border border-white/5 rounded-[24px] p-6">
                                    <h3 className="text-sm font-bold text-slate-300 uppercase tracking-widest mb-6">多空表现拆解</h3>
                                    <div className="flex flex-col gap-6">
                                        <div>
                                            <div className="flex justify-between text-xs text-slate-400 mb-2"><span>做多 (Long)</span> <span>{result.summary.long_trades}笔</span></div>
                                            <div className="w-full bg-black/40 h-2 rounded-full overflow-hidden">
                                                <div className="h-full bg-emerald-500" style={{width: `${result.summary.long_win_rate}%`}}></div>
                                            </div>
                                            <div className="flex justify-between text-[11px] mt-1 font-mono"><span className="text-emerald-400">胜率 {result.summary.long_win_rate}%</span> <span className="text-white">PnL: {result.summary.long_pnl > 0 ? '+' : ''}{result.summary.long_pnl}</span></div>
                                        </div>
                                        <div>
                                            <div className="flex justify-between text-xs text-slate-400 mb-2"><span>做空 (Short)</span> <span>{result.summary.short_trades}笔</span></div>
                                            <div className="w-full bg-black/40 h-2 rounded-full overflow-hidden">
                                                <div className="h-full bg-rose-500" style={{width: `${result.summary.short_win_rate}%`}}></div>
                                            </div>
                                            <div className="flex justify-between text-[11px] mt-1 font-mono"><span className="text-rose-400">胜率 {result.summary.short_win_rate}%</span> <span className="text-white">PnL: {result.summary.short_pnl > 0 ? '+' : ''}{result.summary.short_pnl}</span></div>
                                        </div>
                                    </div>
                                </div>

                                <div className="md:col-span-2">
                                     <TradeStreamTable trades={result.trades} />
                                </div>
                            </div>

                        </div>
                    )}

                    {!loading && !result && (
                        <div className="flex-1 flex flex-col items-center justify-center opacity-40">
                            <Activity className="w-24 h-24 mb-6 stroke-[1]" />
                            <p className="text-lg tracking-widest font-bold uppercase">建立参数并启动模拟</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default BacktestPage;
