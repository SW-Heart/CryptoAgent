
import React, { useState, useEffect } from 'react';
import { Flame, Star, TrendingUp, Pause, Play, Download, ExternalLink } from 'lucide-react';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * TrendingBar - Horizontal scrolling bar showing CoinGecko trending tokens
 * Features:
 * - Auto-scrolling marquee effect
 * - Pauses on hover
 * - Shows price and 24h change from Binance
 */
export default function TrendingBar({ onTokenClick }) {
    const [tokens, setTokens] = useState([]);
    const [isPaused, setIsPaused] = useState(false);
    const [loading, setLoading] = useState(true);

    // Fetch trending tokens
    useEffect(() => {
        const fetchTrending = async () => {
            try {
                const res = await fetch(`${BASE_URL}/api/dashboard/trending?limit=10`);
                if (res.ok) {
                    const data = await res.json();
                    setTokens(data.tokens || []);
                }
            } catch (err) {
                console.error('[TrendingBar] Fetch error:', err);
            } finally {
                setLoading(false);
            }
        };

        fetchTrending();

        // Refresh every 5 minutes
        const interval = setInterval(fetchTrending, 300000);
        return () => clearInterval(interval);
    }, []);

    // Format price with smart decimals
    const formatPrice = (price) => {
        if (!price) return 'N/A';
        if (price < 0.0001) return `$${price.toFixed(8)} `;
        if (price < 0.01) return `$${price.toFixed(6)} `;
        if (price < 1) return `$${price.toFixed(4)} `;
        return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} `;
    };

    if (loading || tokens.length === 0) {
        return null; // Don't render if no data
    }

    // Duplicate tokens for seamless loop
    const displayTokens = [...tokens, ...tokens];

    return (
        <div
            className="w-full bg-slate-900/50 border-b border-slate-800 h-10 overflow-hidden"
            onMouseEnter={() => setIsPaused(true)}
            onMouseLeave={() => setIsPaused(false)}
        >
            <div className="flex items-center h-full w-full">
                {/* Trending icon */}
                <div className="flex items-center gap-1.5 px-3 text-orange-400 flex-shrink-0 border-r border-slate-700 h-full">
                    <Flame className="w-4 h-4" />
                    <span className="text-xs font-medium hidden sm:inline">Trending</span>
                </div>

                {/* Scrolling container - CRITICAL: must have overflow:hidden and explicit width */}
                <div className="flex-1 overflow-hidden relative h-full min-w-0">
                    <div className="absolute inset-0 flex items-center">
                        <div
                            className="flex gap-6 whitespace-nowrap animate-marquee"
                            style={{
                                animationDuration: `${tokens.length * 4}s`,
                                animationPlayState: isPaused ? 'paused' : 'running',
                            }}
                        >
                            {displayTokens.map((token, idx) => (
                                <button
                                    key={`${token.symbol}-${idx}`}
                                    onClick={() => onTokenClick?.(token.symbol)}
                                    className="flex items-center gap-2 px-2 py-1 rounded hover:bg-slate-800/50 transition-colors flex-shrink-0"
                                >
                                    {/* Token image */}
                                    {token.image && (
                                        <img
                                            src={token.image}
                                            alt={token.symbol}
                                            className="w-4 h-4 rounded-full"
                                        />
                                    )}

                                    {/* Symbol */}
                                    <span className="text-sm font-medium text-slate-200">
                                        {token.symbol}
                                    </span>

                                    {/* Price */}
                                    <span className="text-sm text-slate-400">
                                        {formatPrice(token.price)}
                                    </span>

                                    {/* 24h Change */}
                                    {token.change_24h !== null && (
                                        <span className={`text-xs font-medium ${token.change_24h >= 0 ? 'text-green-400' : 'text-red-400'
                                            }`}>
                                            {token.change_24h >= 0 ? '+' : ''}{token.change_24h?.toFixed(2)}%
                                        </span>
                                    )}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            {/* CSS for marquee animation */}
            <style>{`
@keyframes marquee {
    0% { transform: translateX(0); }
    100% { transform: translateX(-50%); }
}
.animate-marquee {
    animation: marquee linear infinite;
}
`}</style>
        </div>
    );
}
