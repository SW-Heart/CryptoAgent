import React from 'react';
import { Sparkles } from 'lucide-react';

const PROMPTS = [
    "Today's Market Analysis",
    "What investment strategies suit the current market?",
    "Market Forecast: Future trends prediction",
    "Current investment opportunities search"
];

export default function QuickPrompts({ onSelectPrompt }) {
    return (
        <div className="bg-[#131722] rounded-xl p-5 border border-slate-800">
            <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-purple-400" />
                Quick Prompts
            </h3>
            <div className="space-y-2">
                {PROMPTS.map((prompt, i) => (
                    <button
                        key={i}
                        onClick={() => onSelectPrompt(prompt)}
                        className="w-full text-left px-3 py-2.5 text-sm text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors whitespace-nowrap"
                    >
                        {prompt}
                    </button>
                ))}
            </div>
        </div>
    );
}
