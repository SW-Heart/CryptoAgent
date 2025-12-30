import React, { useState, useEffect } from 'react';
import { Sparkles, RefreshCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';

// Prompt library - comprehensive collection of crypto-related prompts
// Each prompt has an id for i18n lookup
const PROMPT_KEYS = [
    // Market Analysis
    'todayMarket',
    'weeklyOutlook',
    'btcTrend',
    'ethAnalysis',
    'altcoinSeason',
    'marketSentiment',

    // Strategy & Investment
    'investmentStrategy',
    'riskManagement',
    'entryPoints',
    'portfolioReview',
    'profitTaking',

    // News & Events
    'latestNews',
    'macroImpact',
    'etfFlows',
    'whaleActivity',
    'upcomingEvents',

    // Technical Analysis
    'supportResistance',
    'trendAnalysis',
    'indicatorSignals',
    'priceTargets',

    // DeFi & Ecosystem
    'defiOpportunities',
    'yieldFarming',
    'airdropAlerts',

    // Education & Research
    'tokenResearch',
    'projectComparison',
    'fundamentalAnalysis'
];

// Fisher-Yates shuffle algorithm
function shuffleArray(array) {
    const shuffled = [...array];
    for (let i = shuffled.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    return shuffled;
}

export default function QuickPrompts({ onSelectPrompt, displayCount = 4 }) {
    const { t } = useTranslation();
    const [displayedPrompts, setDisplayedPrompts] = useState([]);

    // Select random prompts on mount and when language changes
    useEffect(() => {
        refreshPrompts();
    }, [t]); // Re-shuffle when translation function changes (language switch)

    const refreshPrompts = () => {
        const shuffled = shuffleArray(PROMPT_KEYS);
        setDisplayedPrompts(shuffled.slice(0, displayCount));
    };

    return (
        <div className="bg-[#131722] rounded-xl p-5 border border-slate-800">
            <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-purple-400" />
                    {t('quickPrompts.title')}
                </h3>
                <button
                    onClick={refreshPrompts}
                    className="p-1.5 text-slate-500 hover:text-purple-400 hover:bg-slate-800 rounded-lg transition-colors"
                    title={t('quickPrompts.refresh')}
                >
                    <RefreshCw className="w-3.5 h-3.5" />
                </button>
            </div>
            <div className="space-y-2">
                {displayedPrompts.map((key) => (
                    <button
                        key={key}
                        onClick={() => onSelectPrompt(t(`quickPrompts.prompts.${key}`))}
                        className="w-full text-left px-3 py-2.5 text-sm text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
                    >
                        {t(`quickPrompts.prompts.${key}`)}
                    </button>
                ))}
            </div>
        </div>
    );
}
