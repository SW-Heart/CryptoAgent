import React, { useState } from 'react';
import {
    ArrowUpRight,
    ArrowDownRight,
    Eye,
    EyeOff
} from 'lucide-react';

export default function StatCard({ icon: Icon, label, value, subValue, trend, tone = 'emerald', headerRight, hidden, onToggleHidden }) {
    const tones = {
        emerald: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/10',
        amber: 'text-amber-400 bg-amber-500/10 border-amber-500/10',
        rose: 'text-rose-400 bg-rose-500/10 border-rose-500/10',
    };
    const EyeIcon = hidden ? EyeOff : Eye;
    return (
        <div className="flex-1 min-w-[200px] rounded-2xl bg-[#0e1215]/50 border border-white/5 hover:border-emerald-500/20 transition-all group relative">
            {/* Background Layer with Overflow Hidden for the Blur */}
            <div className="absolute inset-0 overflow-hidden rounded-2xl pointer-events-none">
                <div className={`absolute top-0 right-0 w-24 h-24 blur-[60px] opacity-20 -mr-12 -mt-12 transition-all group-hover:opacity-40 ${tones[tone].split(' ')[0].replace('text', 'bg')}`} />
            </div>

            {/* Content Layer without Overflow Hidden (Allows Dropdown to Escape) */}
            <div className="relative z-10 p-5">
                <div className="flex items-center justify-between mb-4">
                    <div className={`p-2.5 rounded-xl border ${tones[tone]}`}><Icon className="w-5 h-5" /></div>
                    <div className="flex items-center gap-2">
                        {headerRight ? headerRight : trend !== undefined && (
                            <div className={`flex items-center gap-1 text-xs font-bold ${trend >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                {trend >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                                {Math.abs(trend).toFixed(1)}%
                            </div>
                        )}
                        {onToggleHidden && (
                            <button onClick={onToggleHidden} className="p-1 rounded-lg text-slate-600 hover:text-slate-400 hover:bg-white/5 transition-all focus:outline-none">
                                <EyeIcon className="w-3.5 h-3.5" />
                            </button>
                        )}
                    </div>
                </div>
                <div className="flex flex-col gap-1">
                    <span className="text-xs font-bold text-slate-500 uppercase tracking-widest">{label}</span>
                    <div className="text-2xl font-black text-white tracking-tight">{hidden ? <span className="text-slate-600 select-none">****</span> : value}</div>
                    {subValue && <div className="text-[10px] font-medium text-slate-500 tracking-wide uppercase opacity-60">{hidden ? '' : subValue}</div>}
                </div>
            </div>
        </div>
    );
}
