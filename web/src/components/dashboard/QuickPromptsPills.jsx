import React, { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Flame } from 'lucide-react';

import { BASE_URL } from '../../services/config';

// Module-level cache
const aiQuestionsCache = {};
const CACHE_DURATION = 10 * 60 * 1000;

/**
 * Check if text starts with an emoji
 */
function startsWithEmoji(text) {
    if (!text) return false;
    // Common emoji ranges
    const emojiRegex = /^[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{1F1E0}-\u{1F1FF}]/u;
    return emojiRegex.test(text.trim());
}

/**
 * Auto-match emoji icon based on question keywords
 */
function getIconForQuestion(text) {
    if (!text) return '💡';

    // If text already starts with emoji, return null (don't add another)
    if (startsWithEmoji(text)) {
        return null;
    }

    const lowerText = text.toLowerCase();

    // Keyword to emoji mapping (ordered by specificity)
    const iconRules = [
        // Specific coins/tokens - use colorful emojis
        { keywords: ['btc', 'bitcoin', '比特币'], icon: '🟠' },
        { keywords: ['eth', 'ethereum', '以太坊'], icon: '🔷' },
        { keywords: ['sol', 'solana'], icon: '🟣' },

        // Market sentiment
        { keywords: ['fear', 'greed', '恐惧', '贪婪', '情绪'], icon: '😰' },
        { keywords: ['牛市', 'bull', '上涨', '突破', '涨'], icon: '🐂' },
        { keywords: ['熊市', 'bear', '下跌', '跌'], icon: '🐻' },

        // Actions/strategies
        { keywords: ['买入', 'buy', '入场', '建仓', '加仓'], icon: '🛒' },
        { keywords: ['卖出', 'sell', '止盈', '止损', '出场'], icon: '💰' },
        { keywords: ['策略', 'strategy', '投资'], icon: '🎯' },
        { keywords: ['风险', 'risk'], icon: '⚠️' },

        // DeFi & Yield
        { keywords: ['defi', '收益', 'yield', '矿池', 'farm', 'apy', 'apr', '稳定币'], icon: '🌾' },
        { keywords: ['质押', 'stake', 'staking'], icon: '🔒' },
        { keywords: ['流动性', 'liquidity', 'lp'], icon: '💧' },

        // Entities
        { keywords: ['whale', '巨鲸', '大户'], icon: '🐳' },
        { keywords: ['机构', 'institution', 'etf'], icon: '🏛️' },

        // Categories
        { keywords: ['meme', '狗狗', 'doge', 'shib', 'pepe'], icon: '🐸' },
        { keywords: ['山寨', 'altcoin', 'alt', '潜力币'], icon: '💎' },
        { keywords: ['空投', 'airdrop'], icon: '🎁' },
        { keywords: ['nft'], icon: '🖼️' },
        { keywords: ['l2', 'layer2', 'layer 2', '二层'], icon: '⚡' },

        // Technical analysis
        { keywords: ['支撑', 'support', '阻力', 'resistance', '压力'], icon: '📊' },
        { keywords: ['趋势', 'trend', '走势'], icon: '📈' },
        { keywords: ['技术', 'technical', 'rsi', 'macd', 'ema'], icon: '📉' },

        // Events
        { keywords: ['新闻', 'news', '消息'], icon: '📰' },
        { keywords: ['美联储', 'fed', '宏观', 'macro', '利率'], icon: '🏦' },
        { keywords: ['监管', 'regulation', 'sec'], icon: '⚖️' },

        // Time-related
        { keywords: ['今天', 'today', '今日'], icon: '📅' },
        { keywords: ['下周', 'next week', '本周', 'this week'], icon: '🗓️' },
        { keywords: ['未来', 'future', '预测', 'forecast'], icon: '🔮' },

        // General Market
        { keywords: ['市场', 'market', '横盘'], icon: '🌐' },
        { keywords: ['热点', 'hot', '火', '轮动'], icon: '🔥' },
        { keywords: ['机会', 'opportunity'], icon: '💎' },
        { keywords: ['分析', 'analysis', 'analyze'], icon: '🔍' },
    ];

    for (const rule of iconRules) {
        if (rule.keywords.some(kw => lowerText.includes(kw))) {
            return rule.icon;
        }
    }

    // Default icons rotation for variety
    const defaultIcons = ['💡', '✨', '🚀', '⭐', '💫'];
    const hash = text.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
    return defaultIcons[hash % defaultIcons.length];
}

/**
 * Single Pill with internal text scrolling
 */
function ScrollingPill({ texts, currentIndex, isAnimating, onClick }) {
    const currentText = texts[currentIndex % texts.length] || '';
    const nextText = texts[(currentIndex + 1) % texts.length] || '';

    const currentIcon = getIconForQuestion(currentText);
    const nextIcon = getIconForQuestion(nextText);

    return (
        <button
            onClick={() => onClick?.(currentText)}
            className="
                w-full h-11 rounded-full flex-shrink-0
                bg-slate-800/60 border border-slate-700/50
                hover:bg-slate-700/80 hover:border-slate-600
                transition-colors duration-200
                overflow-hidden relative
            "
            title={currentText}
        >
            {/* Gradient mask for top/bottom fade inside pill */}
            <div
                className="absolute inset-0 overflow-hidden"
                style={{
                    maskImage: 'linear-gradient(to bottom, transparent 0%, black 25%, black 75%, transparent 100%)',
                    WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, black 25%, black 75%, transparent 100%)'
                }}
            >
                {/* Scrolling text container */}
                <div
                    className="flex flex-col transition-transform ease-out"
                    style={{
                        transform: isAnimating ? 'translateY(-50%)' : 'translateY(0)',
                        transitionDuration: isAnimating ? '400ms' : '0ms'
                    }}
                >
                    {/* Current text with icon */}
                    <div className="h-11 flex items-center px-4 gap-2">
                        {currentIcon && <span className="text-base flex-shrink-0">{currentIcon}</span>}
                        <span className="text-sm text-slate-300 truncate">{currentText}</span>
                    </div>
                    {/* Next text with icon (for animation) */}
                    <div className="h-11 flex items-center px-4 gap-2">
                        {nextIcon && <span className="text-base flex-shrink-0">{nextIcon}</span>}
                        <span className="text-sm text-slate-300 truncate">{nextText}</span>
                    </div>
                </div>
            </div>
        </button>
    );
}

/**
 * QuickPromptsPills - 5 fixed pills with internal text scrolling and auto icons
 */
export default function QuickPromptsPills({ staticPrompts = [], onSelectPrompt }) {
    const { t, i18n } = useTranslation();
    const [aiQuestions, setAiQuestions] = useState([]);
    const [rotationIndex, setRotationIndex] = useState(0);
    const [isLoading, setIsLoading] = useState(true);
    const [isAnimating, setIsAnimating] = useState(false);

    const language = i18n.language?.startsWith('zh') ? 'zh' : 'en';

    // Fetch AI questions
    useEffect(() => {
        const fetchAiQuestions = async () => {
            const cached = aiQuestionsCache[language];
            const now = Date.now();

            if (cached && (now - cached.timestamp < CACHE_DURATION) && cached.questions.length > 0) {
                setAiQuestions(cached.questions);
                setIsLoading(false);
                return;
            }

            try {
                const params = new URLSearchParams();
                params.set('language', language);

                const res = await fetch(`${BASE_URL}/api/suggested-questions?${params}`);
                const data = await res.json();
                const questions = data.all_questions || [];

                aiQuestionsCache[language] = { questions, timestamp: now };
                setAiQuestions(questions);
            } catch (err) {
                console.error('[QuickPromptsPills] Error:', err);
            } finally {
                setIsLoading(false);
            }
        };

        fetchAiQuestions();
    }, [language]);

    // Combine all prompts
    const allPrompts = useMemo(() => {
        const aiPrompts = aiQuestions.map(q => q);
        const staticTexts = staticPrompts.map(p => p.text);
        const combined = [...staticTexts, ...aiPrompts];

        // Shuffle
        const shuffled = [...combined];
        for (let i = shuffled.length - 1; i > 0; i--) {
            const j = (i * 13 + 7) % (i + 1);
            [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
        }
        return shuffled;
    }, [staticPrompts, aiQuestions]);

    // Distribute prompts across 5 pills
    const pillTexts = useMemo(() => {
        const pills = [[], [], [], [], []];
        allPrompts.forEach((text, i) => {
            pills[i % 5].push(text);
        });
        return pills;
    }, [allPrompts]);

    // Auto-rotate every 10 seconds
    useEffect(() => {
        if (allPrompts.length <= 5) return;

        const interval = setInterval(() => {
            setIsAnimating(true);
            setTimeout(() => {
                setRotationIndex(prev => prev + 1);
                setIsAnimating(false);
            }, 400);
        }, 10000);

        return () => clearInterval(interval);
    }, [allPrompts.length]);

    // Skeleton
    if (isLoading) {
        return (
            <div className="bg-[#131722] rounded-xl p-5 border border-slate-800 h-[330px] overflow-hidden">
                <div className="flex items-center gap-2 mb-4">
                    <div className="bg-slate-700/50 animate-pulse rounded-full w-4 h-4" />
                    <div className="bg-slate-700/50 animate-pulse rounded w-16 h-4" />
                </div>
                <div className="flex flex-col gap-2">
                    {[...Array(5)].map((_, i) => (
                        <div key={i} className="bg-slate-700/30 animate-pulse rounded-full h-11" />
                    ))}
                </div>
            </div>
        );
    }

    return (
        <div className="bg-[#131722] rounded-xl p-5 border border-slate-800 h-[330px] overflow-hidden flex flex-col">
            {/* Header - no refresh button */}
            <div className="flex items-center mb-3 flex-shrink-0">
                <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                    <Flame className="w-4 h-4 text-orange-400" />
                    {t('home.quickPrompts.title')}
                </h3>
            </div>

            {/* 5 Fixed Pills */}
            <div className="flex flex-col gap-2 flex-1">
                {pillTexts.map((texts, i) => (
                    <ScrollingPill
                        key={i}
                        texts={texts.length > 0 ? texts : ['...']}
                        currentIndex={rotationIndex}
                        isAnimating={isAnimating}
                        onClick={onSelectPrompt}
                    />
                ))}
            </div>
        </div>
    );
}
