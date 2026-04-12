/**
 * SwapCard - 交易卡片组件
 * 
 * 专门用于展示 DEX Swap 交易预览的精美卡片。
 * 采用 glassmorphism 风格设计。
 */

import React, { useState } from 'react';
import { ArrowRight, Loader2, Check, X, AlertTriangle, Wallet } from 'lucide-react';

// Token Logo URLs (可以使用 CoinGecko 或本地资源)
const TOKEN_LOGOS = {
    USDT: 'https://assets.coingecko.com/coins/images/325/small/Tether.png',
    USDC: 'https://assets.coingecko.com/coins/images/6319/small/usdc.png',
    DAI: 'https://assets.coingecko.com/coins/images/9956/small/Badge_Dai.png',
    WETH: 'https://assets.coingecko.com/coins/images/2518/small/weth.png',
    ETH: 'https://assets.coingecko.com/coins/images/279/small/ethereum.png',
    WBTC: 'https://assets.coingecko.com/coins/images/7598/small/wrapped_bitcoin_wbtc.png',
    BTC: 'https://assets.coingecko.com/coins/images/1/small/bitcoin.png',
    UNI: 'https://assets.coingecko.com/coins/images/12504/small/uniswap-uni.png',
    LINK: 'https://assets.coingecko.com/coins/images/877/small/chainlink-new-logo.png',
    AAVE: 'https://assets.coingecko.com/coins/images/12645/small/AAVE.png',
};

// 获取 Token Logo
const getTokenLogo = (symbol) => {
    const upperSymbol = symbol?.toUpperCase();
    return TOKEN_LOGOS[upperSymbol] || `https://ui-avatars.com/api/?name=${symbol}&background=random&size=32`;
};

/**
 * Token 显示组件
 */
const TokenDisplay = ({ symbol, amount, label, align = 'left' }) => {
    const isRight = align === 'right';

    return (
        <div className={`flex flex-col gap-1 ${isRight ? 'items-end' : 'items-start'}`}>
            <span className="text-xs text-slate-500 uppercase tracking-wide">{label}</span>
            <div className={`flex items-center gap-2 ${isRight ? 'flex-row-reverse' : ''}`}>
                <img
                    src={getTokenLogo(symbol)}
                    alt={symbol}
                    className="w-8 h-8 rounded-full ring-2 ring-slate-700/50"
                    onError={(e) => { e.target.src = `https://ui-avatars.com/api/?name=${symbol}&background=6366f1&color=fff&size=32`; }}
                />
                <div className={`flex flex-col ${isRight ? 'items-end' : 'items-start'}`}>
                    <span className="text-xl font-bold text-white">
                        {typeof amount === 'number' ? amount.toLocaleString(undefined, { maximumFractionDigits: 6 }) : amount}
                    </span>
                    <span className="text-sm text-slate-400">{symbol}</span>
                </div>
            </div>
        </div>
    );
};

/**
 * 信息行组件
 */
const InfoRow = ({ label, value, highlight = false, warning = false }) => (
    <div className="flex justify-between items-center py-1">
        <span className="text-sm text-slate-500">{label}</span>
        <span className={`text-sm font-medium ${warning ? 'text-amber-400' :
                highlight ? 'text-emerald-400' :
                    'text-slate-300'
            }`}>
            {value}
        </span>
    </div>
);

/**
 * 交易状态组件
 */
const TransactionStatus = ({ status, txHash }) => {
    const statusConfig = {
        pending: {
            icon: Loader2,
            text: '等待确认...',
            color: 'text-blue-400',
            animate: true,
        },
        success: {
            icon: Check,
            text: '交易成功',
            color: 'text-emerald-400',
            animate: false,
        },
        failed: {
            icon: X,
            text: '交易失败',
            color: 'text-red-400',
            animate: false,
        },
        cancelled: {
            icon: X,
            text: '已取消',
            color: 'text-slate-400',
            animate: false,
        },
    };

    const config = statusConfig[status] || statusConfig.pending;
    const Icon = config.icon;

    return (
        <div className="flex flex-col items-center gap-2 py-4">
            <div className={`p-3 rounded-full bg-slate-800 ${config.color}`}>
                <Icon className={`w-6 h-6 ${config.animate ? 'animate-spin' : ''}`} />
            </div>
            <span className={`text-sm font-medium ${config.color}`}>{config.text}</span>
            {txHash && (
                <a
                    href={`https://etherscan.io/tx/${txHash}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-400 hover:underline"
                >
                    查看交易详情 →
                </a>
            )}
        </div>
    );
};

/**
 * SwapCard 主组件
 */
const SwapCard = ({
    fromToken,
    toToken,
    fromAmount,
    toAmount,
    exchangeRate,
    priceUsd,
    gasEstimate,
    priceImpact = 0,
    route,
    onConfirm,
    onCancel,
    isLoading = false,
    status = null, // 'pending' | 'success' | 'failed' | 'cancelled'
    txHash = null,
}) => {
    const [isConnecting, setIsConnecting] = useState(false);

    // 价格影响警告阈值
    const isPriceImpactHigh = priceImpact > 1.0;
    const isPriceImpactDanger = priceImpact > 3.0;

    // 如果有交易状态，显示状态视图
    if (status) {
        return (
            <div className="swap-card-container rounded-2xl bg-gradient-to-br from-slate-900/90 to-slate-800/90 backdrop-blur-xl border border-slate-700/50 p-6 shadow-2xl shadow-black/30">
                <TransactionStatus status={status} txHash={txHash} />
            </div>
        );
    }

    return (
        <div className="swap-card-container rounded-2xl bg-gradient-to-br from-slate-900/90 to-slate-800/90 backdrop-blur-xl border border-slate-700/50 overflow-hidden shadow-2xl shadow-black/30">
            {/* 标题栏 */}
            <div className="px-6 py-4 border-b border-slate-700/50 bg-gradient-to-r from-blue-500/10 to-purple-500/10">
                <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                    <span className="w-1.5 h-5 bg-gradient-to-b from-blue-400 to-purple-500 rounded-full" />
                    确认交易
                </h3>
            </div>

            {/* 代币交换区域 */}
            <div className="p-6">
                <div className="flex items-center justify-between gap-4">
                    <TokenDisplay
                        symbol={fromToken}
                        amount={fromAmount}
                        label="支付"
                        align="left"
                    />

                    <div className="flex-shrink-0 p-2 rounded-full bg-slate-800 border border-slate-700">
                        <ArrowRight className="w-5 h-5 text-blue-400" />
                    </div>

                    <TokenDisplay
                        symbol={toToken}
                        amount={toAmount}
                        label="获得"
                        align="right"
                    />
                </div>
            </div>

            {/* 分隔线 */}
            <div className="mx-6">
                <div className="h-px bg-gradient-to-r from-transparent via-slate-600 to-transparent" />
            </div>

            {/* 交易详情 */}
            <div className="px-6 py-4 space-y-1">
                <InfoRow
                    label="汇率"
                    value={`1 ${toToken} = $${priceUsd?.toLocaleString() || 'N/A'}`}
                />
                <InfoRow
                    label="路由"
                    value={route || `${fromToken} → ${toToken}`}
                />
                <InfoRow
                    label="预计 Gas 费用"
                    value={gasEstimate || '~$3.00'}
                />
                <InfoRow
                    label="价格影响"
                    value={`${priceImpact?.toFixed(2) || '0.00'}%`}
                    warning={isPriceImpactHigh}
                />
            </div>

            {/* 价格影响警告 */}
            {isPriceImpactHigh && (
                <div className={`mx-6 mb-4 p-3 rounded-lg flex items-start gap-2 ${isPriceImpactDanger
                        ? 'bg-red-500/10 border border-red-500/30'
                        : 'bg-amber-500/10 border border-amber-500/30'
                    }`}>
                    <AlertTriangle className={`w-5 h-5 flex-shrink-0 ${isPriceImpactDanger ? 'text-red-400' : 'text-amber-400'
                        }`} />
                    <div className={`text-sm ${isPriceImpactDanger ? 'text-red-300' : 'text-amber-300'}`}>
                        {isPriceImpactDanger
                            ? '⚠️ 价格影响过高！此交易可能导致较大损失。'
                            : '注意：价格影响略高，请确认是否继续。'}
                    </div>
                </div>
            )}

            {/* 操作按钮 */}
            <div className="px-6 pb-6">
                <div className="flex gap-3">
                    <button
                        onClick={onCancel}
                        disabled={isLoading}
                        className="flex-1 py-3 px-4 rounded-xl bg-slate-700/50 hover:bg-slate-700 text-slate-300 font-medium transition-all duration-200 disabled:opacity-50"
                    >
                        取消
                    </button>
                    <button
                        onClick={onConfirm}
                        disabled={isLoading || isPriceImpactDanger}
                        className={`
              flex-1 py-3 px-4 rounded-xl font-medium
              flex items-center justify-center gap-2
              transition-all duration-200
              disabled:opacity-50 disabled:cursor-not-allowed
              ${isPriceImpactDanger
                                ? 'bg-red-500/20 text-red-400 cursor-not-allowed'
                                : 'bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 text-white shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40'
                            }
            `}
                    >
                        {isLoading ? (
                            <>
                                <Loader2 className="w-5 h-5 animate-spin" />
                                连接钱包...
                            </>
                        ) : (
                            <>
                                <Wallet className="w-5 h-5" />
                                确认交易
                            </>
                        )}
                    </button>
                </div>
            </div>

            {/* 底部提示 */}
            <div className="px-6 pb-4">
                <p className="text-xs text-slate-500 text-center">
                    点击确认后将唤起 MetaMask 钱包进行签名
                </p>
            </div>
        </div>
    );
};

export default SwapCard;
