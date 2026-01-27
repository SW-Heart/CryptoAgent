from tools.crypto_tools import (
    get_market_sentiment,
    get_token_analysis,
    search_news,
    get_pro_crypto_news,
    get_market_hotspots,
    get_trending_tokens,
    get_top_gainers_cex,
    get_onchain_hot_gainers,
    get_eth_btc_ratio,
    get_global_market_overview,
    get_btc_dominance,
)
from technical_analysis import get_multi_timeframe_analysis
from tools.etf_tools import get_etf_daily, get_etf_summary

def get_comprehensive_daily_report_data() -> str:
    """
    Get all necessary data for the Crypto Daily Report in a single call.
    Aggregates sentiment, market overview, BTC/ETH analysis, ETF flows, news, and hot tokens.
    
    Returns:
        A structured string containing all data sections required for the report.
    """
    sections = []
    
    # 1. Market Pulse (Sentiment & Overview)
    print("Fetching Market Pulse...")
    sentiment = get_market_sentiment()
    overview = get_global_market_overview()
    btc_dom = get_btc_dominance()
    
    sections.append(f"=== 📊 Market Pulse ===\n{sentiment}\n\n{overview}\n\n{btc_dom}")

    # 2. Major Assets Analysis (BTC & ETH)
    print("Fetching BTC & ETH Analysis...")
    btc_analysis = get_token_analysis("BTC")
    btc_tech = get_multi_timeframe_analysis("BTC", deep_analysis=False)
    eth_btc = get_eth_btc_ratio()
    
    sections.append(f"=== 💰 BTC & ETH Analysis ===\n{btc_analysis}\n\n{btc_tech}\n\n{eth_btc}")

    # 3. ETF Data (BTC)
    print("Fetching ETF Data...")
    etf_daily = get_etf_daily("btc")
    etf_summary = get_etf_summary("btc")
    
    sections.append(f"=== 🏦 ETF Flows (BTC) ===\n{etf_daily}\n\n{etf_summary}")

    # 4. News & Headlines
    print("Fetching News...")
    # Try pro news first, fallback to search if needed (though pro news usually better for major events)
    news = get_pro_crypto_news(limit=5)
    if "No news found" in news or len(news) < 50:
        news = search_news("crypto market news", num_results=5)
        
    sections.append(f"=== ⚡ Headlines ===\n{news}")

    # 5. Market Scans (Hotspots & Gainers)
    print("Fetching Market Scans...")
    hotspots = get_market_hotspots()
    trending = get_trending_tokens(limit=5)
    gainers_cex = get_top_gainers_cex(limit=5)
    gainers_onchain = get_onchain_hot_gainers(number=5)
    
    sections.append(f"=== 🔥 Market Scans ===\n{hotspots}\n\n{trending}\n\n{gainers_cex}\n\n{gainers_onchain}")

    return "\n\n".join(sections)
