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
                                        onClick={() => onAnalyzeToken(`${isZh ? '分析代币' : 'Analyze token'}: ${token.name}`)}
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
                                    <span className="col-span-2 text-right">{isZh ? '市值' : 'MCap'}</span>
                                    <span className="col-span-2 text-right"></span>
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
                                                {(token.change_24h || 0) >= 0 ? '+' : ''}{token.change_24h?.toFixed(0)}%
                                            </span>

                                            {/* Market Cap */}
                                            <span className="col-span-2 text-right text-slate-400 text-xs truncate">
                                                {token.market_cap || '-'}
                                            </span>

                                            {/* Social Links + DEX */}
                                            <div className="col-span-2 flex justify-end items-center gap-2">
                                                {/* Social Media Icons */}
                                                {token.socials && token.socials.length > 0 ? (
                                                    token.socials.slice(0, 1).map((social, idx) => {
                                                        // Determine icon based on social type
                                                        const type = social.type?.toLowerCase() || '';
                                                        let iconClass = 'text-slate-400';
                                                        let icon = <ExternalLink className="w-3 h-3" />;
                                                        let title = social.type;

                                                        if (type === 'twitter' || type === 'x') {
                                                            iconClass = 'text-slate-300 hover:text-white';
                                                            title = 'X (Twitter)';
                                                            icon = (
                                                                <svg className="w-3 h-3" viewBox="0 0 24 24" fill="currentColor">
                                                                    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                                                                </svg>
                                                            );
                                                        } else if (type === 'telegram') {
                                                            iconClass = 'text-sky-400 hover:text-sky-300';
                                                            title = 'Telegram';
                                                            icon = (
                                                                <svg className="w-3 h-3" viewBox="0 0 24 24" fill="currentColor">
                                                                    <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
                                                                </svg>
                                                            );
                                                        } else if (type === 'discord') {
                                                            iconClass = 'text-indigo-400 hover:text-indigo-300';
                                                            title = 'Discord';
                                                            icon = (
                                                                <svg className="w-3 h-3" viewBox="0 0 24 24" fill="currentColor">
                                                                    <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z" />
                                                                </svg>
                                                            );
                                                        }

                                                        return (
                                                            <a
                                                                key={idx}
                                                                href={social.url}
                                                                target="_blank"
                                                                rel="noopener noreferrer"
                                                                className={`${iconClass} transition-colors`}
                                                                title={title}
                                                            >
                                                                {icon}
                                                            </a>
                                                        );
                                                    })
                                                ) : null}

                                                {/* DEX Link (DexScreener) */}
                                                {token.dex_url ? (
                                                    <a
                                                        href={token.dex_url}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="text-green-400 hover:text-green-300 transition-colors"
                                                        title={isZh ? '在 DexScreener 查看' : 'View on DexScreener'}
                                                    >
                                                        <ExternalLink className="w-3 h-3" />
                                                    </a>
                                                ) : (
                                                    <button
                                                        onClick={() => onAnalyzeToken(`${isZh ? '分析链上代币' : 'Analyze on-chain token'}: ${token.symbol}`)}
                                                        className="text-indigo-400 hover:text-indigo-300"
                                                    >
                                                        <Search className="w-3 h-3" />
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
