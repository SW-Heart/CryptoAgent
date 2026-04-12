"""
Market Tools Package - 市场数据工具集

从原 crypto_tools.py 拆分而来，按功能域组织：
- data_sources: 基础数据源 (Binance + DexScreener)
- market_info: Token 分析、情绪、热点、Gainers、BTC 指标
- news: 新闻、搜索、叙事分析
- onchain: 链上数据 (Etherscan + DefiLlama)
- composite: 合并工具 (宏观分析、批量技术分析)
"""

# === data_sources ===
from tools.market.data_sources import (
    get_binance_data,
    _get_dexscreener_data,
)

# === market_info ===
from tools.market.market_info import (
    get_token_analysis,
    get_market_sentiment,
    get_market_hotspots,
    get_trending_tokens,
    get_top_gainers_cex,
    get_top_gainers_all,
    get_onchain_hot_gainers,
    get_btc_dominance,
    get_global_market_overview,
    get_eth_btc_ratio,
    get_funding_rate,
    batch_funding_rate,
)

# === news ===
from tools.market.news import (
    get_pro_crypto_news,
    get_narrative_dominance,
    search_news,
    search_google,
)

# === onchain ===
from tools.market.onchain import (
    get_eth_gas_price,
    get_wallet_balance,
    get_wallet_transactions,
    get_defi_tvl_ranking,
    get_protocol_tvl,
    get_chain_tvl,
    get_top_yields,
)

# === composite ===
from tools.market.composite import (
    get_macro_overview,
    get_batch_technical_analysis,
    get_key_levels,
)
