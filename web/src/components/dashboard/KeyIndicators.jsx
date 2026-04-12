import React from 'react';
import { BarChart2, Activity } from 'lucide-react';

export default function KeyIndicators({ indicators = [], fearGreed = { value: 50, classification: 'Neutral' }, onAnalyze }) {
    // Color based on fear/greed value
    const getFearGreedColor = (value) => {
        if (value <= 25) return 'text-red-400';
        if (value <= 45) return 'text-orange-400';
        if (value <= 55) return 'text-yellow-400';
        if (value <= 75) return 'text-lime-400';
        return 'text-green-400';
    };

    return (
        <div className="bg-[#131722] rounded-xl p-5 border border-slate-800">
            <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                <BarChart2 className="w-4 h-4 text-cyan-400" />
                Key Indicators
            </h3>

            {/* Fear & Greed at top */}
            <button
                onClick={() => onAnalyze(`Analyze today's Fear & Greed Index: ${fearGreed.value} (${fearGreed.classification})`)}
                className="w-full flex items-center justify-between p-3 bg-slate-800/50 hover:bg-slate-700 rounded-lg mb-3 transition-colors"
            >
                <div className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-yellow-400" />
                    <span className="text-xs text-slate-400">Fear & Greed</span>
                </div>
                <div className="flex items-center gap-2">
                    <span className={`text-lg font-bold ${getFearGreedColor(fearGreed.value)}`}>
                        {fearGreed.value}
                    </span>
                    <span className="text-xs text-slate-500">{fearGreed.classification}</span>
                </div>
            </button>

            {/* Other indicators */}
            <div className="grid grid-cols-2 gap-2">
                {indicators.map((indicator, i) => (
                    <button
                        key={i}
                        onClick={() => onAnalyze(`Analyze ${indicator.name}: ${indicator.value}`)}
                        className="flex flex-col p-2.5 bg-slate-800/50 hover:bg-slate-700 rounded-lg transition-colors text-left"
                    >
                        <span className="text-xs text-slate-500 truncate">{indicator.name}</span>
                        <span className="text-sm font-medium text-white mt-0.5">{indicator.value}</span>
                    </button>
                ))}
            </div>
        </div>
    );
}
