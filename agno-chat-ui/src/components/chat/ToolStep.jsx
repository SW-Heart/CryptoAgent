import React, { useState, useEffect } from 'react';
import {
    BarChart2, Activity, Newspaper, Flame, TrendingUp,
    Search, Globe, Zap, Loader2
} from 'lucide-react';
import { getToolDisplayInfo } from '../../utils/toolUtils';

// LiveTimer component for real-time elapsed time display
const LiveTimer = ({ startTime }) => {
    const [elapsed, setElapsed] = useState(0);
    useEffect(() => {
        const interval = setInterval(() => {
            setElapsed((Date.now() - startTime) / 1000);
        }, 100);
        return () => clearInterval(interval);
    }, [startTime]);
    return <span className="text-xs text-indigo-500 font-mono flex-shrink-0 tabular-nums">{elapsed.toFixed(1)}s</span>;
};

// Icon mapping
const iconMap = {
    chart: { Icon: BarChart2, color: 'text-emerald-500' },
    sentiment: { Icon: Activity, color: 'text-purple-500' },
    news: { Icon: Newspaper, color: 'text-blue-500' },
    fire: { Icon: Flame, color: 'text-orange-500' },
    trend: { Icon: TrendingUp, color: 'text-cyan-500' },
    search: { Icon: Search, color: 'text-indigo-500' },
    globe: { Icon: Globe, color: 'text-teal-500' },
    zap: { Icon: Zap, color: 'text-amber-500' },
    activity: { Icon: Activity, color: 'text-purple-500' },
};

export default function ToolStep({ text, startTime }) {
    const isRunning = !text.includes('completed');
    const { label, icon } = getToolDisplayInfo(text);

    const { Icon, color: iconColor } = iconMap[icon] || iconMap.zap;
    let containerClass = "bg-[#131722] border border-slate-700";
    let textColor = "text-slate-200";

    if (isRunning) {
        containerClass = "relative overflow-hidden bg-[#131722] border border-transparent";
        textColor = "text-white";
    }

    return (
        <div className={`flex items-center gap-2 px-3 py-2 my-1.5 rounded-lg transition-all duration-300 ${containerClass}`}>
            {isRunning && (
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full animate-shimmer" />
            )}
            <div className={`p-1.5 rounded-lg bg-slate-800 ${isRunning ? 'text-white' : iconColor} relative z-10`}>
                {isRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Icon className="w-4 h-4" />}
            </div>
            <div className="flex-1 min-w-0 relative z-10">
                <div className="flex items-center justify-between gap-2">
                    <span className={`text-sm font-medium truncate ${textColor}`}>
                        {label}
                    </span>
                    {isRunning && startTime ? (
                        <LiveTimer startTime={startTime} />
                    ) : (
                        <span className="text-xs text-slate-400 font-mono flex-shrink-0">
                            {text.match(/completed in ([\d.]+s)/)?.[1] || ''}
                        </span>
                    )}
                </div>
            </div>
        </div>
    );
}
