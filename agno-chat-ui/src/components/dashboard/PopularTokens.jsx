import React, { useState, useEffect } from 'react';
import { TrendingUp, Search, ExternalLink, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

export default function PopularTokens({ tokens = [], onAnalyzeToken }) {
    const { t, i18n } = useTranslation();
    const isZh = i18n.language === 'zh';

    // Tab state: 'cex' or 'onchain'
    const [activeTab, setActiveTab] = useState('cex');
    const [onchainTokens, setOnchainTokens] = useState([]);
    const [loading, setLoading] = useState(false);

    // Fetch on-chain data on mount (preload for instant switch)
    useEffect(() => {
        if (onchainTokens.length === 0) {
            fetchOnchainTokens();
        }
    }, []);

    const fetchOnchainTokens = async () => {
        setLoading(true);
        try {
            const response = await fetch('/api/dashboard/onchain-hot?limit=6');
            const data = await response.json();
            if (data.tokens) {
                setOnchainTokens(data.tokens);
            }
        } catch (error) {
            console.error('Failed to fetch on-chain tokens:', error);
        } finally {
            setLoading(false);
        }
    };

    // Format price smartly
    const formatPrice = (price) => {
        if (!price) return '-';
        if (price < 0.0001) return `$${price.toFixed(8)}`;
        if (price < 0.01) return `$${price.toFixed(6)}`;
        if (price < 1) return `$${price.toFixed(4)}`;
        if (price < 1000) return `$${price.toFixed(2)}`;
        return `$${price.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
    };

    // Chain badge colors
    const chainColors = {
        'SOLANA': 'bg-purple-500/20 text-purple-400',
        'solana': 'bg-purple-500/20 text-purple-400',
        'ETHEREUM': 'bg-blue-500/20 text-blue-400',
        'ethereum': 'bg-blue-500/20 text-blue-400',
        'BSC': 'bg-yellow-500/20 text-yellow-400',
        'bsc': 'bg-yellow-500/20 text-yellow-400',
        'BASE': 'bg-blue-400/20 text-blue-300',
        'base': 'bg-blue-400/20 text-blue-300',
        'ARBITRUM': 'bg-cyan-500/20 text-cyan-400',
        'arbitrum': 'bg-cyan-500/20 text-cyan-400',
    };

    return (
        <div className="bg-[#131722] rounded-xl p-5 border border-slate-800 h-[330px] overflow-hidden flex flex-col">
            {/* Header with tabs */}
            <div className="flex items-center justify-between mb-3 flex-shrink-0">
                <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-green-400" />
                    {isZh ? '热门代币' : 'Popular Tokens'}
                </h3>

                {/* Tab switcher */}
                <div className="flex bg-slate-800/50 rounded-lg p-0.5">
                    <button
                        onClick={() => setActiveTab('cex')}
                        className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${activeTab === 'cex'
                            ? 'bg-indigo-500/20 text-indigo-400'
                            : 'text-slate-400 hover:text-slate-300'
                            }`}
                    >
                        {isZh ? '交易所' : 'CEX'}
                    </button>
                    <button
                        onClick={() => setActiveTab('onchain')}
                        className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${activeTab === 'onchain'
                            ? 'bg-green-500/20 text-green-400'
                            : 'text-slate-400 hover:text-slate-300'
                            }`}
                    >
                        {isZh ? '链上' : 'On-chain'}
                    </button>
                </div>
            </div>

            {/* Content Area - Flex Grow to fill height */}
            <div className="flex-1 flex flex-col justify-between overflow-hidden">
                {/* CEX View */}
                {activeTab === 'cex' && (
                    <>
                        <div className="grid grid-cols-4 text-xs text-slate-500 px-2 pb-1 border-b border-slate-800/50 mb-1 flex-shrink-0">
                            <span>{isZh ? '名称' : 'Name'}</span>
                            <span className="text-right">{isZh ? '价格' : 'Price'}</span>
                            <span className="text-right">24h(%)</span>
                            <span className="text-right"></span>
                        </div>

                        <div className="flex-1 flex flex-col justify-between">
                            {tokens.slice(0, 6).map((token, i) => (
                                <div key={i} className="grid grid-cols-4 items-center px-2 py-1.5 hover:bg-slate-800 rounded text-sm transition-colors">
                                    <span className="text-white font-medium">{token.name}</span>
                                    <span className="text-right text-slate-300 text-xs">
                                        {formatPrice(token.price)}
                                    </span>
                                    <span className={`text-right text-xs ${token.change_24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                        {token.change_24h >= 0 ? '+' : ''}{token.change_24h?.toFixed(2)}%
                                    </span>
                                    <button
                                        onClick={() => onAnalyzeToken(`Analyze token: ${token.name}`)}
                                        className="text-right text-indigo-400 hover:text-indigo-300"
                                    >
                                        <Search className="w-3.5 h-3.5 ml-auto" />
                                    </button>
                                </div>
                            ))}
                        </div>
                    </>
                )}

                {/* On-chain View */}
                {activeTab === 'onchain' && (
                    <>
                        {loading ? (
                            <div className="flex-1 flex items-center justify-center">
                                <Loader2 className="w-6 h-6 text-green-400 animate-spin" />
                                <span className="ml-2 text-slate-400 text-sm animate-pulse">
                                    {isZh ? '扫描链上数据...' : 'Scanning on-chain data...'}
                                </span>
                            </div>
                        ) : onchainTokens.length === 0 ? (
                            <div className="flex-1 flex flex-col items-center justify-center text-slate-500 text-sm gap-2">
                                <span>{isZh ? '暂无符合条件的链上热点' : 'No qualified on-chain hot tokens'}</span>
                                <button
                                    onClick={fetchOnchainTokens}
                                    className="text-xs text-indigo-400 hover:text-indigo-300 underline cursor-pointer"
                                >
                                    {isZh ? '刷新重试' : 'Refresh'}
                                </button>
                            </div>
                        ) : (
                            <>
                                {/* Header row */}
                                <div className="grid grid-cols-12 text-xs text-slate-500 px-2 pb-1 border-b border-slate-800/50 mb-1 flex-shrink-0">
                                    <span className="col-span-4">{isZh ? '代币' : 'Token'}</span>
                                    <span className="col-span-2 text-right">{isZh ? '价格' : 'Price'}</span>
                                    <span className="col-span-2 text-right">24h</span>
                                    <span className="col-span-3 text-right">{isZh ? '市值' : 'MCap'}</span>
                                    <span className="col-span-1 text-right"></span>
                                </div>

                                <div className="flex-1 flex flex-col justify-between">
                                    {onchainTokens.slice(0, 6).map((token, i) => (
                                        <div key={i} className="grid grid-cols-12 items-center px-2 py-1.5 hover:bg-slate-800 rounded text-sm transition-colors">
                                            {/* Token Symbol + Chain Badge */}
                                            <div className="col-span-4 flex items-center gap-2 overflow-hidden">
                                                <span className="text-white font-medium truncate" title={token.symbol}>
                                                    {token.symbol}
                                                </span>
                                                <span className={`text-[9px] px-1 py-0.5 rounded leading-none flex-shrink-0 ${chainColors[token.chain] || 'bg-slate-600/30 text-slate-400'
                                                    }`}>
                                                    {token.chain?.slice(0, 3).toUpperCase()}
                                                </span>
                                            </div>

                                            {/* Price */}
                                            <span className="col-span-2 text-right text-slate-300 text-xs">
                                                {formatPrice(token.price)}
                                            </span>

                                            {/* 24h Change */}
                                            <span className={`col-span-2 text-right text-xs font-medium ${(token.change_24h || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                                                }`}>
                                                +{token.change_24h?.toFixed(0)}%
                                            </span>

                                            {/* Market Cap */}
                                            <span className="col-span-3 text-right text-slate-400 text-xs truncate">
                                                {token.market_cap || '-'}
                                            </span>

                                            {/* Twitter Link */}
                                            <div className="col-span-1 flex justify-end">
                                                {token.twitter ? (
                                                    <a
                                                        href={token.twitter}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="text-sky-400 hover:text-sky-300 transition-colors"
                                                        title="Twitter"
                                                    >
                                                        <ExternalLink className="w-3.5 h-3.5" />
                                                    </a>
                                                ) : (
                                                    <button
                                                        onClick={() => onAnalyzeToken(`Analyze on-chain token: ${token.symbol}`)}
                                                        className="text-indigo-400 hover:text-indigo-300"
                                                    >
                                                        <Search className="w-3.5 h-3.5" />
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}
