import React, { useState, useMemo } from 'react';
import { ChevronDown, Target } from 'lucide-react';
import { EXCHANGE_LOGOS, LLM_LOGOS } from './constants';

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
                if (activeActions.length > 0) isExecution = true;
            } else if (typeof actions === 'string' && !actions.toUpperCase().startsWith('HOLD')) {
                activeActions = [actions];
                isExecution = true;
            }
        }
    } catch {
        if (log.actions_taken && !log.actions_taken.toUpperCase().includes('HOLD') && log.actions_taken !== '[]') {
            activeActions = [log.actions_taken];
            isExecution = true;
        }
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

    // Action label translation map
    const ACTION_LABELS = {
        'OPEN_LONG': '开多',
        'OPEN_SHORT': '开空',
        'CLOSE_LONG': '平多',
        'CLOSE_SHORT': '平空',
        'ADJUST_SL': '调整止损',
        'ADJUST_TP': '调整止盈',
        'SET_SL': '设置止损',
        'SET_TP': '设置止盈',
        'ADD_POSITION': '加仓',
        'REDUCE_POSITION': '减仓',
        'HOLD': '持仓观望',
        'CANCEL_ORDER': '取消委托',
        'REVERSE': '反手',
    };
    const translateAction = (act) => {
        const upper = act?.toUpperCase?.() || '';
        return ACTION_LABELS[upper] || act;
    };

    return (
        <div onClick={() => setOpen(!open)} className={`p-4 rounded-2xl border transition-all cursor-pointer ${open ? 'bg-[#0a0d0f] border-emerald-500/30' : 'bg-[#0e1215]/40 border-white/5 hover:border-white/10'}`}>
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    <span className="text-[9px] font-mono text-slate-500 font-bold">{formattedDate}</span>
                    {exchangeName && renderProviderLogo(exchangeName, 'exchange')}
                    {modelName && renderProviderLogo(modelName, 'llm')}
                </div>
                <div className="flex items-center gap-1.5">
                    <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">本轮决策：</span>
                    {!isExecution && (
                        <div className="px-2 py-0.5 rounded-[4px] text-[8px] font-black bg-amber-500/10 text-amber-500 border border-amber-500/20">
                            持仓观望
                        </div>
                    )}
                    {isExecution && activeActions.map((act, i) => (
                        <div key={i} className="px-2 py-0.5 rounded-[4px] text-[8px] font-black bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                            {translateAction(act)}
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
