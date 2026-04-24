import React, { useState, useMemo } from 'react';
import { ChevronDown, ChevronRight, Target } from 'lucide-react';
import { EXCHANGE_LOGOS, LLM_LOGOS } from './constants';

/**
 * 将 raw_response 按 Step / 步骤 分段解析
 * 支持 "### Step N:" / "## Step N" / "**Step N**" 等常见格式
 */
function parseAnalysisSteps(rawResponse) {
    if (!rawResponse || typeof rawResponse !== 'string') return [];
    // Split by step-like headings
    const stepRegex = /(?:^|\n)(?:#{1,4}\s*)?(?:\*{0,2})?\s*(?:Step\s*\d+[\.\:：]?|步骤\s*\d+[\.\:：]?)/gi;
    const matches = [...rawResponse.matchAll(stepRegex)];
    if (matches.length === 0) return [];

    const steps = [];
    for (let i = 0; i < matches.length; i++) {
        const start = matches[i].index;
        const end = i + 1 < matches.length ? matches[i + 1].index : rawResponse.length;
        const chunk = rawResponse.slice(start, end).trim();
        // Extract title (first line) and body (rest)
        const firstNewline = chunk.indexOf('\n');
        const title = firstNewline > 0 ? chunk.slice(0, firstNewline).replace(/^[#*\s]+/, '').trim() : chunk.replace(/^[#*\s]+/, '').trim();
        const body = firstNewline > 0 ? chunk.slice(firstNewline + 1).trim() : '';
        steps.push({ title, body });
    }
    return steps;
}

function StepItem({ step, index }) {
    const [expanded, setExpanded] = useState(false);
    return (
        <div className="border border-white/5 rounded-lg overflow-hidden">
            <button
                onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
                className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-white/[0.03] transition-colors"
            >
                {expanded
                    ? <ChevronDown className="w-3 h-3 text-emerald-400 flex-shrink-0" />
                    : <ChevronRight className="w-3 h-3 text-slate-500 flex-shrink-0" />
                }
                <span className="text-[10px] font-black text-emerald-400/80 flex-shrink-0 w-5">{index + 1}</span>
                <span className="text-[10px] font-bold text-slate-300 truncate">{step.title}</span>
            </button>
            {expanded && step.body && (
                <div className="px-3 pb-3 pt-1 border-t border-white/5">
                    <pre className="text-[10px] text-slate-400 font-mono whitespace-pre-wrap leading-relaxed break-words">{step.body}</pre>
                </div>
            )}
        </div>
    );
}

export default function DecisionCard({ log, traderInstances, accounts, llmConfigs }) {
    const [open, setOpen] = useState(false);

    const dateObj = useMemo(() => {
        if (!log.timestamp) return null;
        let tsStr = log.timestamp.replace(' ', 'T');
        // Handle postgres +00 output making it standard ISO 8601
        if (tsStr.endsWith('+00')) {
            tsStr = tsStr.replace(/\+00$/, 'Z');
        } else if (!tsStr.endsWith('Z') && !tsStr.includes('+')) {
            tsStr += 'Z';
        }

        // Safari bugs out on 6-digit microseconds (e.g. .123456Z). Truncate to 3 digits.
        tsStr = tsStr.replace(/\.(\d{3})\d+(Z|[+-][0-9:]+)$/, '.$1$2');

        const d = new Date(tsStr);
        if (isNaN(d.getTime())) return null;

        // Output UTC+8 regardless of browser local time
        const utc8Time = d.getTime() + (8 * 60 * 60 * 1000);
        return new Date(utc8Time);
    }, [log.timestamp]);

    if (!dateObj) return null; // Don't render a card with fake time

    const formattedDate = `${dateObj.getUTCFullYear()}/${dateObj.getUTCMonth() + 1}/${dateObj.getUTCDate()} ${String(dateObj.getUTCHours()).padStart(2, '0')}:${String(dateObj.getUTCMinutes()).padStart(2, '0')}:${String(dateObj.getUTCSeconds()).padStart(2, '0')}`;

    // Logic: '执行' if decision actually executed market orders, otherwise '等待'
    let isExecution = false;
    let activeActions = [];
    try {
        if (log.actions_taken && log.actions_taken !== '[]') {
            const actions = JSON.parse(log.actions_taken);
            if (Array.isArray(actions)) {
                activeActions = actions.filter(a => typeof a === 'string' && !a.toUpperCase().startsWith('HOLD'));
            } else if (typeof actions === 'string' && !actions.toUpperCase().startsWith('HOLD')) {
                activeActions = [actions];
            }
        }
    } catch {
        if (log.actions_taken && !log.actions_taken.toUpperCase().includes('HOLD') && log.actions_taken !== '[]') {
            activeActions = [log.actions_taken];
        }
    }

    // Fallback: If no action parsed from actions_taken, try extracting from the strategy decision markdown.
    // E.g. looking for keywords: OPEN_LONG, ADJUST_SL, SET_TP, BUY, SELL, ADJUST_TP, CLOSE_LONG
    if (activeActions.length === 0 && log.strategy_decision) {
        const keywords = ['OPEN_LONG', 'OPEN_SHORT', 'CLOSE_LONG', 'CLOSE_SHORT', 'ADJUST_SL', 'ADJUST_TP', 'SET_SL', 'SET_TP', 'ADD_POSITION', 'REDUCE_POSITION', 'REVERSE'];
        const decisionText = log.strategy_decision.toUpperCase();
        
        for (const kw of keywords) {
            if (decisionText.includes(kw)) {
                activeActions.push(kw);
            }
        }
        // Deduplicate
        activeActions = [...new Set(activeActions)];
    }

    if (activeActions.length > 0) {
        isExecution = true;
    }

    const trader = traderInstances?.find(t => String(t.id) === String(log.trader_instance_id));
    const account = accounts?.find(a => String(a.id) === String(trader?.exchange_account_id));
    const llm = llmConfigs?.find(l => String(l.id) === String(trader?.llm_config_id));

    const exchangeName = account ? account.exchange : null;
    const modelName = log.llm_provider || (llm ? llm.provider : null);

    const renderProviderLogo = (name, type) => {
        const lowerName = name?.toLowerCase() || '';
        
        let logoUrl = null;
        if (type === 'exchange') {
            logoUrl = EXCHANGE_LOGOS[lowerName];
        } else {
            logoUrl = LLM_LOGOS[lowerName] || (lowerName.includes('claude') ? LLM_LOGOS['anthropic'] : null);
        }

        if (logoUrl) {
            return (
                <div className="flex items-center justify-center p-0.5" title={name}>
                    <img src={logoUrl} alt={name} className="w-3.5 h-3.5 object-contain" />
                </div>
            );
        }

        // No recognized provider — don't render anything
        return null;
    };

    // 解析带有 symbol（如 ADJUST_SL_BTC）和参数（如 PARTIAL_CLOSE_LONG_BTC_50%）的复杂动作标签
    const translateAction = (act) => {
        const upper = typeof act === 'string' ? act.toUpperCase() : '';
        if (!upper) return act;
        
        const prefixMap = [
            { match: 'PARTIAL_CLOSE_LONG_', label: '部分平多' },
            { match: 'PARTIAL_CLOSE_SHORT_', label: '部分平空' },
            { match: 'OPEN_LONG_', label: '开多' },
            { match: 'OPEN_SHORT_', label: '开空' },
            { match: 'CLOSE_LONG_', label: '平多' },
            { match: 'CLOSE_SHORT_', label: '平空' },
            { match: 'ADJUST_SL_', label: '调整止损' },
            { match: 'ADJUST_TP_', label: '调整止盈' },
            { match: 'MODIFY_ORDER_', label: '修改挂单' },
            { match: 'CANCEL_ORDER_', label: '撤销挂单' },
            { match: 'REVERSE_', label: '反手' },
            { match: 'SET_SL_', label: '设置止损' },
            { match: 'SET_TP_', label: '设置止盈' },
        ];

        for (const { match, label } of prefixMap) {
            if (upper.startsWith(match)) {
                return label;
            }
        }
        
        const exactMap = {
            'HOLD': '持仓观望',
            'ADD_POSITION': '加仓',
            'REDUCE_POSITION': '减仓',
            'OPEN_LONG': '开多',
            'OPEN_SHORT': '开空',
            'CLOSE_LONG': '平多',
            'CLOSE_SHORT': '平空',
            'ADJUST_SL': '调整止损',
            'ADJUST_TP': '调整止盈',
            'MODIFY_ORDER': '修改挂单',
            'CANCEL_ORDER': '撤销挂单',
            'REVERSE': '反手',
            'SET_SL': '设置止损',
            'SET_TP': '设置止盈',
        };
        
        return exactMap[upper] || act;
    };

    // 获取去重后的简化中文标签
    let displayActions = isExecution 
        ? Array.from(new Set(activeActions.map(act => translateAction(act)))) 
        : [];
        
    // 极致UI压缩：智能合并同时操作的盈损标签
    if (displayActions.includes('调整止损') && displayActions.includes('调整止盈')) {
        displayActions = displayActions.filter(a => a !== '调整止损' && a !== '调整止盈');
        displayActions.unshift('调整盈损');
    }
    if (displayActions.includes('设置止损') && displayActions.includes('设置止盈')) {
        displayActions = displayActions.filter(a => a !== '设置止损' && a !== '设置止盈');
        displayActions.unshift('设置盈损');
    }

    // 解析分析步骤
    const analysisSteps = useMemo(() => parseAnalysisSteps(log.raw_response), [log.raw_response]);

    return (
        <div onClick={() => setOpen(!open)} className={`p-4 rounded-2xl border transition-all cursor-pointer flex-shrink-0 min-w-0 ${open ? 'bg-[#0a0d0f] border-emerald-500/30' : 'bg-[#0e1215]/40 border-white/5 hover:border-white/10'}`}>
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-[9px] font-mono text-slate-500 font-bold">{formattedDate}</span>
                    {exchangeName && renderProviderLogo(exchangeName, 'exchange')}
                    {modelName && renderProviderLogo(modelName, 'llm')}
                </div>
                <div className="flex items-center gap-1.5 flex-nowrap justify-end overflow-hidden">
                    <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest whitespace-nowrap flex-shrink-0">本轮决策：</span>
                    {!isExecution && (
                        <div className="px-2 py-0.5 rounded-[4px] text-[8px] font-black bg-amber-500/10 text-amber-500 border border-amber-500/20 whitespace-nowrap">
                            持仓观望
                        </div>
                    )}
                    {isExecution && displayActions.map((label, i) => (
                        <div key={i} className="px-2 py-0.5 rounded-[4px] text-[8px] font-black bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 whitespace-nowrap overflow-hidden text-ellipsis">
                            {label}
                        </div>
                    ))}
                </div>
            </div>
            <div className="flex items-center justify-between gap-4 py-1">
                <div className="flex items-center gap-2">
                    <Target className="w-3.5 h-3.5 text-emerald-400" />
                    <div className="text-xs font-black text-slate-100 uppercase">{log.symbols}</div>
                </div>
                <div className="p-1 rounded-lg text-slate-500 transition-all">
                    <ChevronDown className={`w-4 h-4 transition-transform ${open ? 'rotate-180' : ''}`} />
                </div>
            </div>
            {open && (
                <div className="mt-3 pt-3 border-t border-white/5 space-y-3 animate-in slide-in-from-top-1 duration-300">
                    <div>
                        <div className="text-[8px] font-black text-slate-500 uppercase tracking-widest mb-1">市场分析 (Market Analysis)</div>
                        <p className="text-[10px] text-slate-400 leading-relaxed font-bold opacity-80">{log.market_analysis || '暂无分析数据'}</p>
                    </div>
                    {/* 分析过程步骤展示 */}
                    {analysisSteps.length > 0 && (
                        <div>
                            <div className="text-[8px] font-black text-slate-500 uppercase tracking-widest mb-2">分析过程 (Analysis Steps)</div>
                            <div className="space-y-1" onClick={(e) => e.stopPropagation()}>
                                {analysisSteps.map((step, idx) => (
                                    <StepItem key={idx} step={step} index={idx} />
                                ))}
                            </div>
                        </div>
                    )}
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
