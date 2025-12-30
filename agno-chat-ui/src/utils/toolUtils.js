import i18n from '../i18n';

// Tool name to translation key mapping
const toolKeyMap = {
    'get_token_analysis': 'getTokenAnalysis',
    'get_market_sentiment': 'getMarketSentiment',
    'get_pro_crypto_news': 'getProCryptoNews',
    'get_market_hotspots': 'getMarketHotspots',
    'get_narrative_dominance': 'getNarrativeDominance',
    'get_btc_dominance': 'getBtcDominance',
    'get_funding_rate': 'getFundingRate',
    'get_top_gainers': 'getTopGainers',
    'get_global_market_overview': 'getGlobalMarketOverview',
    'get_eth_btc_ratio': 'getEthBtcRatio',
    'get_eth_gas_price': 'getEthGasPrice',
    'get_wallet_balance': 'getWalletBalance',
    'get_wallet_transactions': 'getWalletBalance',
    'get_defi_tvl_ranking': 'getDefiTvlRanking',
    'get_protocol_tvl': 'getProtocolTvl',
    'get_chain_tvl': 'getChainTvl',
    'get_top_yields': 'getTopYields',
    // ETF Tools
    'get_etf_flows': 'getEtfFlows',
    'get_etf_daily': 'getEtfDaily',
    'get_etf_summary': 'getEtfSummary',
    'get_etf_ticker': 'getEtfTicker',
    // Search Tools
    'search_news': 'searchNews',
    'duckduckgo_news': 'searchNews',
    'duckduckgo_search': 'webSearch',
    'search_exa': 'deepResearch',
    'exa': 'deepResearch',
    'search_google': 'webSearch',
    'search': 'aiSearch',
    'browse': 'browsingWeb',
    'get_positions_summary': 'getPositionsSummary',
    'open_position': 'openPosition',
    'close_position': 'closePosition',
    'partial_close_position': 'partialClosePosition',
    'log_strategy_analysis': 'logStrategyAnalysis',
    'update_stop_loss_take_profit': 'updateSlTp',
    'get_multi_timeframe_analysis': 'getMultiTimeframeAnalysis',
    'get_ema_structure': 'getEmaStructure',
    'get_vegas_channel': 'getVegasChannel',
    'get_macd_signal': 'getMacdSignal',
    'get_volume_analysis': 'getVolumeAnalysis',
    'get_volume_profile': 'getVolumeProfile',
    'get_trendlines': 'getTrendlines',
    'detect_chart_patterns': 'detectChartPatterns',
    'analyze_wave_structure': 'analyzeWaveStructure',
    'get_indicator_reliability_all_timeframes': 'getIndicatorReliability',
    'get_indicator_reliability': 'getIndicatorReliability'
};

// Icon mapping (unchanged)
const toolIconMap = {
    'get_token_analysis': 'chart',
    'get_market_sentiment': 'sentiment',
    'get_pro_crypto_news': 'news',
    'get_market_hotspots': 'fire',
    'get_narrative_dominance': 'trend',
    'get_btc_dominance': 'chart',
    'get_funding_rate': 'activity',
    'get_top_gainers': 'trend',
    'get_global_market_overview': 'globe',
    'get_eth_btc_ratio': 'chart',
    'get_eth_gas_price': 'zap',
    'get_wallet_balance': 'activity',
    'get_wallet_transactions': 'activity',
    'get_defi_tvl_ranking': 'trend',
    'get_protocol_tvl': 'chart',
    'get_chain_tvl': 'globe',
    'get_top_yields': 'fire',
    // ETF Tools
    'get_etf_flows': 'trend',
    'get_etf_daily': 'activity',
    'get_etf_summary': 'chart',
    'get_etf_ticker': 'activity',
    // Search Tools
    'search_news': 'news',
    'duckduckgo_news': 'news',
    'duckduckgo_search': 'globe',
    'search_exa': 'search',
    'exa': 'search',
    'search_google': 'globe',
    'search': 'search',
    'browse': 'globe',
    'get_positions_summary': 'activity',
    'open_position': 'trend',
    'close_position': 'activity',
    'partial_close_position': 'trend',
    'log_strategy_analysis': 'chart',
    'update_stop_loss_take_profit': 'activity',
    'get_multi_timeframe_analysis': 'chart',
    'get_ema_structure': 'chart',
    'get_vegas_channel': 'chart',
    'get_macd_signal': 'chart',
    'get_volume_analysis': 'trend',
    'get_volume_profile': 'chart',
    'get_trendlines': 'trend',
    'detect_chart_patterns': 'chart',
    'analyze_wave_structure': 'trend',
    'get_indicator_reliability': 'chart'
};

// Tool name to display info mapping
export const getToolDisplayInfo = (text) => {
    const timeMatch = text.match(/completed in ([\d\.]+s)/);
    const time = timeMatch ? timeMatch[1] : '';
    const toolName = text.split('(')[0].trim();

    let label = toolName;
    let icon = 'zap';

    // Find matching tool key
    for (const [toolPattern, translationKey] of Object.entries(toolKeyMap)) {
        if (toolName.includes(toolPattern)) {
            label = i18n.t(`tool.tools.${translationKey}`);
            icon = toolIconMap[toolPattern] || 'zap';
            break;
        }
    }

    // Fallback for searching text
    if (text.startsWith('Searching') || text.startsWith('搜索')) {
        label = i18n.t('tool.tools.searching');
        icon = 'search';
    } else if (text.startsWith('Browsing') || text.startsWith('浏览')) {
        label = i18n.t('tool.tools.browsingWeb');
        icon = 'globe';
    }

    return { label, time, icon };
};
