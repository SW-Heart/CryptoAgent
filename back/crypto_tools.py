import requests
import pandas as pd
import pandas_ta as ta
import time
import re
import os
from collections import Counter
from typing import Dict, Any

CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY", "")
CRYPTOPANIC_BASE_URL = "https://cryptopanic.com/api/developer/v2/posts/"

# ==========================================
# 🧱 基础组件：混合数据源 (Binance + DexScreener)
# ==========================================

def _get_binance_data(symbol: str):
    """
    尝试从 Binance 获取实时价格和 K 线 (毫秒级延迟)
    """
    # 构造交易对，通常是 币种+USDT
    pair = f"{symbol.upper()}USDT"
    base_url = os.getenv("BINANCE_API_BASE", "https://api.binance.com")

    
    try:
        # 1. 查实时价格
        ticker_url = f"{base_url}/api/v3/ticker/price?symbol={pair}"
        # 设置极短超时，如果Binance没这个币(400 error)，马上切备用源
        ticker_resp = requests.get(ticker_url, timeout=2) 
        
        if ticker_resp.status_code != 200:
            return None # 币安没有这个币
            
        current_price = float(ticker_resp.json()['price'])
        
        # 2. 查 K 线 (用于算 RSI) - 4小时级别，取最近100根
        klines_url = f"{base_url}/api/v3/klines?symbol={pair}&interval=4h&limit=100"
        klines_resp = requests.get(klines_url, timeout=2).json()
        
        # Binance K线格式: [Open time, Open, High, Low, Close, Volume, ...]
        df = pd.DataFrame(klines_resp, columns=[
            'time', 'open', 'high', 'low', 'close', 'vol', 
            'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'
        ])
        df['close'] = df['close'].astype(float)
        
        return {
            "source": "Binance (CEX)",
            "price": current_price,
            "history_df": df
        }
    except Exception as e:
        return None

def _get_dexscreener_data(symbol: str):
    """
    尝试从 DexScreener 获取链上价格 (针对土狗/Meme)
    """
    try:
        # 搜索最活跃的交易对
        search_url = f"https://api.dexscreener.com/latest/dex/search?q={symbol}"
        resp = requests.get(search_url, timeout=5).json()
        
        if not resp.get('pairs'):
            return None
            
        # 取流动性最好的那个池子
        best_pair = resp['pairs'][0]
        
        return {
            "source": f"DexScreener ({best_pair['dexId']} on {best_pair['chainId']})",
            "price": float(best_pair['priceUsd']),
            "change_24h": best_pair.get('priceChange', {}).get('h24', 0),
            "liquidity": best_pair.get('liquidity', {}).get('usd', 0),
            "history_df": None # DexScreener API 免费版不直接提供 K 线数组用于计算 RSI，暂时只看价格
        }
    except:
        return None

# ==========================================
# 🚀 核心 Agent 工具
# ==========================================

def get_token_analysis(symbol: str) -> str:
    """
    Get real-time price and technical analysis (RSI, EMA, trend) for a token.
    Tries Binance first, falls back to DexScreener for meme coins.
    
    Args:
        symbol: Token symbol (e.g., "BTC", "ETH", "PEPE")
    """
    clean_symbol = symbol.upper().strip()
    
    # --- 策略 1: 优先查 Binance (最快、最准、有技术指标) ---
    data = None
    binance_error = None
    try:
        data = _get_binance_data(clean_symbol)
    except Exception as e:
        binance_error = str(e)
    
    # --- Strategy 2: Fallback to DexScreener (covers meme coins) ---
    dex_error = None
    if not data:
        try:
            data = _get_dexscreener_data(clean_symbol)
        except Exception as e:
            dex_error = str(e)
        
    if not data:
        error_msg = f"Cannot fetch data for {clean_symbol}.\n"
        error_msg += "Possible reasons:\n"
        error_msg += "- Binance API inaccessible (VPN/proxy required)\n"
        error_msg += "- Token not listed on Binance or DexScreener\n"
        if binance_error:
            error_msg += f"- Binance error: {binance_error}\n"
        if dex_error:
            error_msg += f"- DexScreener error: {dex_error}\n"
        return error_msg

    # --- Generate report ---
    price = data['price']
    source = data['source']
    report = f"[{clean_symbol} Analysis]\n"
    report += f"Data Source: {source}\n"
    
    # Smart price formatting
    if price < 0.01:
        report += f"Price: ${format(price, '.8f')}\n"
    else:
        report += f"Price: ${price:,.4f}\n"

    # K-line data available (from Binance) - deep technical analysis
    if data.get('history_df') is not None:
        df = data['history_df']
        
        try:
            # Calculate RSI
            rsi_series = ta.rsi(df['close'], length=14)
            rsi = rsi_series.iloc[-1] if rsi_series is not None and len(rsi_series) > 0 else None
            
            # Calculate EMA
            ema20_series = ta.ema(df['close'], length=20)
            ema50_series = ta.ema(df['close'], length=50)
            ema20 = ema20_series.iloc[-1] if ema20_series is not None and len(ema20_series) > 0 else None
            ema50 = ema50_series.iloc[-1] if ema50_series is not None and len(ema50_series) > 0 else None
            
            # Trend analysis
            if ema20 is not None and ema50 is not None:
                trend = "Sideways"
                if price > ema20 > ema50: trend = "Strong Uptrend"
                elif price < ema20 < ema50: trend = "Downtrend"
                elif price < ema20 and ema20 > ema50: trend = "Pullback"
                report += f"Trend: {trend}\n"
            
            # RSI signal
            if rsi is not None:
                rsi_signal = "Neutral"
                if rsi > 70: rsi_signal = "Overbought (High Risk)"
                elif rsi < 30: rsi_signal = "Oversold (Bounce Opportunity)"
                report += f"RSI: {rsi:.1f} - {rsi_signal}\n"
            
            # Support level
            if ema20 is not None:
                report += f"Support (EMA20): ${ema20:.4f}"
        except Exception as e:
            report += f"\nTechnical indicator error: {str(e)}"

    # On-chain data (DexScreener) - show liquidity and price change
    else:
        change = data.get('change_24h', 0)
        liq = data.get('liquidity', 0)
        
        report += f"24h Change: {change}%\n"
        report += f"Pool Liquidity: ${liq:,.0f}\n"
        report += "Note: This is an on-chain token with high volatility. Check contract safety."

    return report

def get_market_sentiment() -> str:
    """
    Get Fear & Greed Index (0-100) for crypto market sentiment.
    Returns index value and classification (Extreme Fear/Fear/Neutral/Greed/Extreme Greed).
    """
    try:
        url = "https://api.alternative.me/fng/?limit=1"
        data = requests.get(url, timeout=5).json()['data'][0]
        return f"Fear & Greed Index: {data['value']} - Status: {data['value_classification']}"
    except:
        return "Failed to fetch sentiment data"

def get_market_hotspots() -> str:
    """
    Get top 5 trending cryptocurrencies by search volume from CoinGecko.
    Shows what tokens are getting the most attention.
    """
    try:
        # 这个接口虽然慢，但是看'搜什么'还是最准的
        headers = {'User-Agent': 'Mozilla/5.0'}
        trend = requests.get("https://api.coingecko.com/api/v3/search/trending", headers=headers, timeout=5).json()
        hot_coins = [f"{i['item']['symbol']}" for i in trend['coins'][:5]]
        return f"Trending coins: {', '.join(hot_coins)}"
    except:
        return "Failed to fetch trending data"


def get_top_gainers_cex(limit: int = 10) -> str:
    """
    Get top gaining tokens by 24h price change from Binance (CEX).
    Best for mainstream tokens listed on major exchanges.
    
    Args:
        limit: Number of results (default 10)
    """
    try:
        binance_base = os.getenv("BINANCE_API_BASE", "https://api.binance.com")
        url = f"{binance_base}/api/v3/ticker/24hr"
        resp = requests.get(url, timeout=5).json()
        
        # Filter USDT pairs and sort by price change
        usdt_pairs = [t for t in resp if t['symbol'].endswith('USDT') and not t['symbol'].startswith('USDT')]
        # Filter out stablecoins
        stablecoins = ['USDCUSDT', 'BUSDUSDT', 'TUSDUSDT', 'DAIUSDT', 'FDUSDUSDT']
        usdt_pairs = [t for t in usdt_pairs if t['symbol'] not in stablecoins]
        
        sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x['priceChangePercent']), reverse=True)
        
        result = "Top Gainers - Binance (24h):\n"
        for i, t in enumerate(sorted_pairs[:limit], 1):
            symbol = t['symbol'].replace('USDT', '')
            change = float(t['priceChangePercent'])
            price = float(t['lastPrice'])
            volume = float(t['quoteVolume']) / 1e6  # Convert to millions
            
            # Smart price formatting
            if price < 0.01:
                price_str = f"${price:.8f}"
            elif price < 1:
                price_str = f"${price:.4f}"
            else:
                price_str = f"${price:,.2f}"
            
            result += f"{i}. {symbol}: +{change:.2f}% | {price_str} | Vol: ${volume:.1f}M\n"
        
        return result
    except Exception as e:
        return f"Failed to fetch Binance gainers: {str(e)}"


def get_top_gainers_all(limit: int = 10) -> str:
    """
    Get top gaining tokens by 24h price change from CoinCap (all markets).
    Covers on-chain tokens, DEX tokens, and smaller cap coins not on Binance.
    
    Args:
        limit: Number of results (default 10)
    """
    try:
        url = "https://api.coincap.io/v2/assets?limit=200"
        headers = {'Accept-Encoding': 'gzip'}
        resp = requests.get(url, headers=headers, timeout=10).json()
        
        if 'data' not in resp:
            return "Failed to fetch CoinCap data"
        
        # Filter out assets with no change data and sort
        assets = [a for a in resp['data'] if a.get('changePercent24Hr')]
        sorted_assets = sorted(assets, key=lambda x: float(x['changePercent24Hr']), reverse=True)
        
        result = "Top Gainers - All Markets (24h):\n"
        for i, a in enumerate(sorted_assets[:limit], 1):
            symbol = a['symbol']
            name = a['name'][:15]  # Truncate long names
            change = float(a['changePercent24Hr'])
            price = float(a['priceUsd']) if a.get('priceUsd') else 0
            mcap = float(a['marketCapUsd']) / 1e9 if a.get('marketCapUsd') else 0  # Billions
            
            # Smart price formatting
            if price < 0.01:
                price_str = f"${price:.6f}"
            elif price < 1:
                price_str = f"${price:.4f}"
            else:
                price_str = f"${price:,.2f}"
            
            result += f"{i}. {symbol} ({name}): +{change:.2f}% | {price_str} | MCap: ${mcap:.2f}B\n"
        
        return result
    except Exception as e:
        return f"Failed to fetch market gainers: {str(e)}"


def get_btc_dominance() -> str:
    """
    Get BTC market dominance percentage and altcoin season indicator.
    Higher dominance = BTC draining alts, lower = altcoin season.
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = "https://api.coingecko.com/api/v3/global"
        data = requests.get(url, headers=headers, timeout=5).json()['data']
        
        btc_dom = data['market_cap_percentage']['btc']
        eth_dom = data['market_cap_percentage']['eth']
        total_mcap = data['total_market_cap']['usd']
        
        # Determine market phase
        if btc_dom < 40:
            season = "Altcoin Season - Capital flowing heavily into altcoins"
        elif btc_dom < 50:
            season = "Altcoin Active - Partial capital flowing to alts"
        elif btc_dom < 55:
            season = "Balanced - BTC and alts share the market"
        elif btc_dom < 60:
            season = "BTC Dominant - Capital returning to BTC, alts under pressure"
        else:
            season = "BTC Draining - Risk-off mode, high altcoin risk"
        
        result = f"BTC Dominance: {btc_dom:.1f}%\n"
        result += f"ETH Share: {eth_dom:.1f}%\n"
        result += f"Total Market Cap: ${total_mcap/1e12:.2f}T\n"
        result += f"Market Phase: {season}"
        
        return result
    except Exception as e:
        return f"Failed to fetch BTC dominance: {str(e)}"


def get_global_market_overview() -> str:
    """
    Get comprehensive global crypto market overview from CoinGecko.
    Includes total market cap, 24h volume, market cap change, active coins, BTC/ETH dominance.
    Best for macro market analysis and understanding overall market health.
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = "https://api.coingecko.com/api/v3/global"
        data = requests.get(url, headers=headers, timeout=10).json()['data']
        
        # Core metrics
        total_mcap = data['total_market_cap']['usd']
        total_volume = data['total_volume']['usd']
        mcap_change_24h = data.get('market_cap_change_percentage_24h_usd', 0)
        active_coins = data.get('active_cryptocurrencies', 0)
        markets = data.get('markets', 0)
        
        # Dominance
        btc_dom = data['market_cap_percentage']['btc']
        eth_dom = data['market_cap_percentage']['eth']
        
        # ICO data (if available)
        ongoing_icos = data.get('ongoing_icos', 0)
        upcoming_icos = data.get('upcoming_icos', 0)
        
        # Build report
        result = "📊 Global Crypto Market Overview\n"
        result += "=" * 35 + "\n\n"
        
        # Market Size
        result += f"💰 Total Market Cap: ${total_mcap/1e12:.3f}T\n"
        
        # Calculate BTC and ETH market cap from dominance
        btc_mcap = total_mcap * (btc_dom / 100)
        eth_mcap = total_mcap * (eth_dom / 100)
        result += f"₿  BTC Market Cap: ${btc_mcap/1e12:.3f}T\n"
        result += f"⟠  ETH Market Cap: ${eth_mcap/1e9:.1f}B\n"
        
        # 24h change with emoji
        change_emoji = "📈" if mcap_change_24h >= 0 else "📉"
        result += f"{change_emoji} 24h Change: {mcap_change_24h:+.2f}%\n"
        
        result += f"💱 24h Volume: ${total_volume/1e9:.2f}B\n"
        result += f"📐 Volume/MCap Ratio: {(total_volume/total_mcap)*100:.2f}%\n\n"
        
        # Dominance Section
        result += "🏆 Market Dominance\n"
        result += f"   BTC: {btc_dom:.1f}%\n"
        result += f"   ETH: {eth_dom:.1f}%\n"
        result += f"   Others: {100 - btc_dom - eth_dom:.1f}%\n\n"
        
        # Market Activity
        result += "🔢 Market Activity\n"
        result += f"   Active Coins: {active_coins:,}\n"
        result += f"   Active Markets: {markets:,}\n"
        
        if ongoing_icos or upcoming_icos:
            result += f"   Ongoing ICOs: {ongoing_icos}\n"
            result += f"   Upcoming ICOs: {upcoming_icos}\n"
        
        # Market Health Interpretation
        result += "\n📋 Market Health Assessment\n"
        
        # Volume/MCap ratio interpretation
        vol_ratio = (total_volume/total_mcap)*100
        if vol_ratio > 10:
            vol_status = "Very High - Strong trading activity, potential volatility"
        elif vol_ratio > 5:
            vol_status = "High - Active trading, healthy liquidity"
        elif vol_ratio > 2:
            vol_status = "Normal - Standard market activity"
        else:
            vol_status = "Low - Reduced trading, watch for breakouts"
        result += f"   Trading Activity: {vol_status}\n"
        
        # 24h change interpretation
        if mcap_change_24h > 5:
            trend_status = "Strong Rally - Consider taking profits"
        elif mcap_change_24h > 2:
            trend_status = "Bullish - Upward momentum"
        elif mcap_change_24h > -2:
            trend_status = "Sideways - Market consolidating"
        elif mcap_change_24h > -5:
            trend_status = "Bearish - Downward pressure"
        else:
            trend_status = "Sharp Decline - Risk off, potential opportunity"
        result += f"   Trend: {trend_status}"
        
        return result
    except Exception as e:
        return f"Failed to fetch global market data: {str(e)}"


def get_eth_btc_ratio() -> str:
    """
    Get ETH/BTC ratio from Binance. Shows the relative strength of ETH vs BTC.
    Rising ratio = ETH outperforming BTC, falling ratio = BTC outperforming ETH.
    """
    try:
        # Get ETHBTC price from Binance
        binance_base = os.getenv("BINANCE_API_BASE", "https://api.binance.com")
        url = f"{binance_base}/api/v3/ticker/24hr?symbol=ETHBTC"
        resp = requests.get(url, timeout=5).json()
        
        ratio = float(resp['lastPrice'])
        change_24h = float(resp['priceChangePercent'])
        high_24h = float(resp['highPrice'])
        low_24h = float(resp['lowPrice'])
        
        result = "⟠/₿ ETH/BTC Ratio\n"
        result += "=" * 30 + "\n\n"
        
        result += f"📊 Current Ratio: {ratio:.5f}\n"
        
        # 24h change with emoji
        change_emoji = "📈" if change_24h >= 0 else "📉"
        result += f"{change_emoji} 24h Change: {change_24h:+.2f}%\n"
        result += f"📈 24h High: {high_24h:.5f}\n"
        result += f"📉 24h Low: {low_24h:.5f}\n\n"
        
        # Interpretation
        result += "📋 Interpretation:\n"
        if change_24h > 2:
            status = "ETH Outperforming - Capital rotating into ETH"
        elif change_24h > 0:
            status = "ETH Slightly Stronger - Neutral bias"
        elif change_24h > -2:
            status = "BTC Slightly Stronger - Neutral bias"
        else:
            status = "BTC Outperforming - Capital rotating into BTC"
        result += f"   {status}\n\n"
        
        # Historical context (rough benchmarks)
        if ratio > 0.08:
            context = "High - ETH historically strong vs BTC"
        elif ratio > 0.05:
            context = "Normal Range - Typical ETH/BTC levels"
        elif ratio > 0.03:
            context = "Low - BTC dominance period"
        else:
            context = "Very Low - Extreme BTC dominance"
        result += f"   Historical Context: {context}"
        
        return result
    except Exception as e:
        return f"Failed to fetch ETH/BTC ratio: {str(e)}"


def get_funding_rate(symbol: str = "BTC") -> str:
    """
    Get perpetual futures funding rate. Positive = longs pay shorts, negative = shorts pay longs.
    Extreme values often precede reversals.
    
    Args:
        symbol: Token symbol (e.g., "BTC", "ETH"). Default: BTC
    """
    try:
        clean_symbol = symbol.upper().strip() + "USDT"
        url = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={clean_symbol}&limit=1"
        data = requests.get(url, timeout=5).json()
        
        if not data or isinstance(data, dict) and data.get('code'):
            return f"Cannot fetch funding rate for {symbol} - may not support futures trading"
        
        funding_rate = float(data[0]['fundingRate']) * 100  # Convert to percentage
        
        # Interpret funding rate
        if funding_rate > 0.1:
            interpret = "Extremely Bullish - Longs overcrowded, risk of long squeeze"
        elif funding_rate > 0.05:
            interpret = "Bullish - Longs dominant, but not extreme"
        elif funding_rate > 0:
            interpret = "Slightly Bullish - Healthy state"
        elif funding_rate > -0.05:
            interpret = "Slightly Bearish - Healthy state"
        elif funding_rate > -0.1:
            interpret = "Bearish - Shorts dominant, but not extreme"
        else:
            interpret = "Extremely Bearish - Shorts overcrowded, potential short squeeze"
        
        result = f"{symbol} Funding Rate: {funding_rate:.4f}%\n"
        result += f"Interpretation: {interpret}\n"
        
        if abs(funding_rate) > 0.1:
            result += "WARNING: Extreme funding rate, high short-term reversal risk"
        
        return result
    except Exception as e:
        return f"Failed to fetch funding rate: {str(e)}"


# ==========================================
# 📰 [V2适配版] 工具：专业媒体情报
# ==========================================

def get_pro_crypto_news(filter_type: str = "hot") -> str:
    """
    Get curated crypto news from CryptoPanic with community sentiment (bullish/bearish votes).
    
    Args:
        filter_type: 'hot', 'rising', or 'important'. Default: 'hot'
    """
    if "你的" in CRYPTOPANIC_API_KEY or not CRYPTOPANIC_API_KEY:
        return "❌ 配置错误: 请在 crypto_tools.py 中填入 Key"

    params = {
        "auth_token": CRYPTOPANIC_API_KEY,
        "public": "true",   # V2文档推荐：公共模式
        "filter": filter_type,
        "kind": "news",     # 只看新闻，不看博客
        "regions": "en"     # 默认英语，防止混杂其他语言不好解析
    }
    
    try:
        # Use V2 URL
        resp = requests.get(CRYPTOPANIC_BASE_URL, params=params, timeout=10)
        
        if resp.status_code != 200:
            return f"CryptoPanic API error ({resp.status_code}): {resp.text}"
            
        data = resp.json()
        
        if "results" not in data:
            return f"API data error: {data}"
        
        report = f"[Crypto News Radar ({filter_type.upper()})]\n"
        
        for post in data['results'][:5]: 
            title = post.get('title', 'No title')
            
            # Get domain (Source Object)
            domain = "Unknown"
            if post.get('source'):
                domain = post['source'].get('domain', 'Unknown')
            
            # Get votes (Votes Object)
            votes = post.get('votes', {})
            bullish = votes.get('positive', 0)
            bearish = votes.get('negative', 0)
            important = votes.get('important', 0)
            
            sentiment = "Neutral"
            if bullish > bearish: sentiment = f"Bullish ({bullish} votes)"
            elif bearish > bullish: sentiment = f"Bearish ({bearish} votes)"
            if important > 5: sentiment += " [HOT]"
            
            report += f"- [{domain}] {title}\n  Sentiment: {sentiment}\n"
            
        return report
    except Exception as e:
        return f"News scan failed: {str(e)}"

# ==========================================
# 📊 [V2适配版] 工具：叙事强度分析
# ==========================================

def get_narrative_dominance() -> str:
    """
    Analyze dominant crypto narratives (AI, Meme, L2, RWA, DeFi, etc.) by scanning news keywords.
    Returns bar chart showing sector strength.
    """
    if "你的" in CRYPTOPANIC_API_KEY:
        return "❌ 配置错误: 请填入 Key"

    try:
        # 即使是分析叙事，我们也拉取 'hot' 或 'rising' 的列表
        params = {
            "auth_token": CRYPTOPANIC_API_KEY,
            "public": "true",
            "filter": "hot",   # 分析当前最热的内容
            "kind": "news",
            "regions": "en"
        }
        
        resp = requests.get(CRYPTOPANIC_BASE_URL, params=params, timeout=10)
        
        if resp.status_code != 200:
            return f"API request failed: {resp.status_code}"

        data = resp.json()
        if "results" not in data:
            return "API returned empty data"

        # Extract all titles for local keyword analysis
        all_text = " ".join([p.get('title', '') for p in data['results']])
        
        # Narrative keyword library
        narrative_keywords = {
            "AI": ["ai", "gpt", "compute", "render", "fet", "tao"],
            "Meme": ["meme", "doge", "pepe", "wif", "bonk", "shib", "cult"],
            "RWA": ["rwa", "blackrock", "ondo", "tokenization"],
            "Layer2": ["l2", "optimism", "base", "arb", "zk"],
            "Solana": ["solana", "sol", "pump"],
            "Regulation": ["sec", "gensler", "trump", "law", "etf"],
            "Macro": ["fed", "cpi", "rate", "powell"],
            "DeFi": ["defi", "dex", "swap", "yield"]
        }
        
        scores = {k: 0 for k in narrative_keywords}
        lower_text = all_text.lower()
        
        for category, keys in narrative_keywords.items():
            for k in keys:
                scores[category] += lower_text.count(k)
        
        top_narratives = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
        
        res = "[Current Market Narrative Strength]\n"
        has_narrative = False
        for name, score in top_narratives:
            if score > 0:
                has_narrative = True
                res += f"{name}: {score} mentions\n"
        
        if not has_narrative:
            res += "No significant narrative keywords detected in current news flow."
            
        return res
        
    except Exception as e:
        return f"Narrative analysis error: {str(e)}"


# ==========================================
# 🔍 自定义搜索工具 (过滤 imageUrl)
# ==========================================
import os

def search_news(query: str, num_results: int = 5) -> str:
    """
    Search Google News via Serper API. Primary news search tool.
    
    Args:
        query: Search keywords (2-5 words best)
        num_results: Number of results (default 5)
    """
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return "❌ 配置错误: 未设置 SERPER_API_KEY"
    
    try:
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "q": query,
            "num": num_results,
            "type": "news"
        }
        
        resp = requests.post("https://google.serper.dev/news", json=payload, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            return f"Search failed: HTTP {resp.status_code}"
        
        data = resp.json()
        news_items = data.get("news", [])
        
        if not news_items:
            return f"No news found for '{query}'"
        
        result = f"Latest news for '{query}':\n\n"
        for i, item in enumerate(news_items[:num_results], 1):
            title = item.get("title", "No title")
            link = item.get("link", "")
            snippet = item.get("snippet", "")[:200]
            source = item.get("source", "Unknown")
            date = item.get("date", "")
            
            result += f"{i}. {title}\n"
            result += f"   Date: {date} | Source: {source}\n"
            result += f"   {snippet}\n"
            result += f"   Link: {link}\n\n"
        
        return result
        
    except Exception as e:
        return f"Search error: {str(e)}"


def search_google(query: str, num_results: int = 5) -> str:
    """
    Search Google via Serper API. Primary web search for research.
    Includes Knowledge Graph info when available.
    
    Args:
        query: Search keywords (2-5 words best)
        num_results: Number of results (default 5)
    """
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return "❌ 配置错误: 未设置 SERPER_API_KEY"
    
    try:
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "q": query,
            "num": num_results
        }
        
        resp = requests.post("https://google.serper.dev/search", json=payload, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            return f"Search failed: HTTP {resp.status_code}"
        
        data = resp.json()
        organic = data.get("organic", [])
        
        if not organic:
            return f"No results found for '{query}'"
        
        result = f"Search results for '{query}':\n\n"
        for i, item in enumerate(organic[:num_results], 1):
            title = item.get("title", "No title")
            link = item.get("link", "")
            snippet = item.get("snippet", "")[:300]
            
            result += f"{i}. {title}\n"
            result += f"   {snippet}\n"
            result += f"   Link: {link}\n\n"
        
        # Add Knowledge Graph info (if available)
        kg = data.get("knowledgeGraph", {})
        if kg:
            result += "\nKnowledge Graph:\n"
            if kg.get("title"):
                result += f"   {kg.get('title')}"
                if kg.get("type"):
                    result += f" ({kg.get('type')})"
                result += "\n"
                result += f"   {kg.get('description')[:200]}\n"
        
        return result
        
    except Exception as e:
        return f"Search error: {str(e)}"


# ==========================================
# 🔗 Etherscan API 工具 (以太坊链上数据)
# ==========================================

ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
ETHERSCAN_BASE_URL = "https://api.etherscan.io/v2/api"  # V2 API
ETHERSCAN_CHAINID = "1"  # Ethereum Mainnet


def get_eth_gas_price() -> str:
    """
    Get real-time Ethereum gas prices (Safe/Standard/Fast) from Etherscan.
    Shows current gas costs for different transaction speeds.
    Best for checking if it's a good time to transact on Ethereum.
    """
    if not ETHERSCAN_API_KEY:
        return "❌ 配置错误: 未设置 ETHERSCAN_API_KEY，请在 .env 中添加"
    
    try:
        url = f"{ETHERSCAN_BASE_URL}?chainid={ETHERSCAN_CHAINID}&module=gastracker&action=gasoracle&apikey={ETHERSCAN_API_KEY}"
        resp = requests.get(url, timeout=10).json()
        
        if resp.get('status') != '1':
            return f"Etherscan API error: {resp.get('message', 'Unknown error')}"
        
        data = resp['result']
        
        safe_gas = float(data.get('SafeGasPrice', 0))
        standard_gas = float(data.get('ProposeGasPrice', 0))
        fast_gas = float(data.get('FastGasPrice', 0))
        base_fee = float(data.get('suggestBaseFee', 0))
        
        result = "⛽ Ethereum Gas Prices\n"
        result += "=" * 30 + "\n\n"
        
        # Smart formatting: show decimals if < 1, otherwise integers
        def fmt_gas(g):
            return f"{g:.2f}" if g < 1 else f"{int(g)}"
        
        result += f"🐢 Safe (Low): {fmt_gas(safe_gas)} Gwei\n"
        result += f"🚗 Standard: {fmt_gas(standard_gas)} Gwei\n"
        result += f"🚀 Fast: {fmt_gas(fast_gas)} Gwei\n"
        result += f"📊 Base Fee: {base_fee:.2f} Gwei\n\n"
        
        # Cost estimation (for a standard 21000 gas ETH transfer)
        # Assuming ETH price ~$3000 for rough estimate
        eth_price = 3000  # Rough estimate, could be fetched dynamically
        standard_cost_eth = (standard_gas * 21000) / 1e9
        standard_cost_usd = standard_cost_eth * eth_price
        
        result += f"💵 Estimated Transfer Cost: ~${standard_cost_usd:.4f} (21k gas)\n\n"
        
        # Gas level interpretation (adjusted for low gas environment)
        if standard_gas < 1:
            status = "🟢 Extremely Low - Best time to transact!"
        elif standard_gas < 10:
            status = "🟢 Very Low - Excellent time to transact!"
        elif standard_gas < 30:
            status = "🟢 Low - Good time to transact"
        elif standard_gas < 50:
            status = "🟡 Moderate - Acceptable"
        elif standard_gas < 100:
            status = "🟠 High - Consider waiting"
        else:
            status = "🔴 Very High - Wait for lower gas"
        
        result += f"Status: {status}"
        
        return result
    except Exception as e:
        return f"Failed to fetch gas price: {str(e)}"


def get_wallet_balance(address: str) -> str:
    """
    Get ETH balance for an Ethereum wallet address.
    Works for any valid Ethereum address (EOA or contract).
    
    Args:
        address: Ethereum address (e.g., "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045")
    """
    if not ETHERSCAN_API_KEY:
        return "❌ 配置错误: 未设置 ETHERSCAN_API_KEY，请在 .env 中添加"
    
    # Validate address format
    if not address.startswith('0x') or len(address) != 42:
        return f"❌ 无效地址格式: {address}. 以太坊地址应以 0x 开头，长度为 42 字符"
    
    try:
        url = f"{ETHERSCAN_BASE_URL}?chainid={ETHERSCAN_CHAINID}&module=account&action=balance&address={address}&tag=latest&apikey={ETHERSCAN_API_KEY}"
        resp = requests.get(url, timeout=10).json()
        
        if resp.get('status') != '1':
            return f"Etherscan API error: {resp.get('message', 'Unknown error')}"
        
        # Balance is returned in Wei, convert to ETH
        balance_wei = int(resp['result'])
        balance_eth = balance_wei / 1e18
        
        result = f"💰 Wallet Balance\n"
        result += "=" * 30 + "\n\n"
        result += f"📍 Address: {address[:10]}...{address[-8:]}\n"
        result += f"💎 Balance: {balance_eth:,.6f} ETH\n"
        
        # Rough USD estimate (ETH ~$3000)
        eth_price = 3000
        usd_value = balance_eth * eth_price
        result += f"💵 Value: ~${usd_value:,.2f} USD\n\n"
        
        # Classification
        if balance_eth >= 10000:
            whale_status = "🐋 Whale Account"
        elif balance_eth >= 1000:
            whale_status = "🦈 Large Holder"
        elif balance_eth >= 100:
            whale_status = "🐬 Medium Holder"
        elif balance_eth >= 10:
            whale_status = "🐟 Small Holder"
        else:
            whale_status = "🦐 Retail Account"
        
        result += f"Classification: {whale_status}"
        
        return result
    except Exception as e:
        return f"Failed to fetch wallet balance: {str(e)}"


def get_wallet_transactions(address: str, limit: int = 10) -> str:
    """
    Get recent transactions for an Ethereum wallet address.
    Shows latest inbound and outbound ETH transfers.
    
    Args:
        address: Ethereum address to query
        limit: Number of transactions to return (default 10, max 50)
    """
    if not ETHERSCAN_API_KEY:
        return "❌ 配置错误: 未设置 ETHERSCAN_API_KEY，请在 .env 中添加"
    
    # Validate address format
    if not address.startswith('0x') or len(address) != 42:
        return f"❌ 无效地址格式: {address}. 以太坊地址应以 0x 开头，长度为 42 字符"
    
    limit = min(limit, 50)  # Cap at 50
    
    try:
        url = f"{ETHERSCAN_BASE_URL}?chainid={ETHERSCAN_CHAINID}&module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset={limit}&sort=desc&apikey={ETHERSCAN_API_KEY}"
        resp = requests.get(url, timeout=10).json()
        
        if resp.get('status') != '1':
            if resp.get('message') == 'No transactions found':
                return f"📭 No transactions found for address {address[:10]}...{address[-8:]}"
            return f"Etherscan API error: {resp.get('message', 'Unknown error')}"
        
        txs = resp['result']
        
        result = f"📜 Recent Transactions\n"
        result += "=" * 35 + "\n"
        result += f"📍 Address: {address[:10]}...{address[-8:]}\n"
        result += f"📊 Showing last {len(txs)} transactions\n\n"
        
        for i, tx in enumerate(txs[:limit], 1):
            value_eth = int(tx['value']) / 1e18
            
            # Determine direction
            is_incoming = tx['to'].lower() == address.lower()
            direction = "📥 IN" if is_incoming else "📤 OUT"
            
            # Format timestamp
            from datetime import datetime
            timestamp = datetime.fromtimestamp(int(tx['timeStamp']))
            time_str = timestamp.strftime('%m/%d %H:%M')
            
            # Transaction status
            status = "✅" if tx.get('isError') == '0' else "❌"
            
            # Counterparty
            counterparty = tx['from'] if is_incoming else tx['to']
            counterparty_short = f"{counterparty[:8]}...{counterparty[-6:]}"
            
            result += f"{i}. {status} {direction} | {value_eth:.4f} ETH\n"
            result += f"   {time_str} | {counterparty_short}\n"
            
            # Add separator between transactions
            if i < len(txs[:limit]):
                result += "   " + "-" * 25 + "\n"
        
        return result
    except Exception as e:
        return f"Failed to fetch transactions: {str(e)}"


# ==========================================
# 📊 DefiLlama API 工具 (DeFi 生态数据)
# ==========================================

DEFILLAMA_BASE_URL = "https://api.llama.fi"
DEFILLAMA_YIELDS_URL = "https://yields.llama.fi"


def get_defi_tvl_ranking(limit: int = 10) -> str:
    """
    Get top DeFi protocols by Total Value Locked (TVL) from DefiLlama.
    Shows which protocols hold the most user funds.
    
    Args:
        limit: Number of protocols to show (default 10, max 50)
    """
    try:
        url = f"{DEFILLAMA_BASE_URL}/protocols"
        resp = requests.get(url, timeout=15).json()
        
        # Sort by TVL (already sorted, but ensure)
        protocols = sorted(resp, key=lambda x: x.get('tvl', 0) or 0, reverse=True)
        limit = min(limit, 50)
        
        result = "🏆 DeFi TVL Ranking\n"
        result += "=" * 35 + "\n\n"
        
        for i, p in enumerate(protocols[:limit], 1):
            name = p.get('name', 'Unknown')
            tvl = p.get('tvl', 0) or 0
            category = p.get('category', 'N/A')
            chain = p.get('chain', 'Multi-chain')
            change_1d = p.get('change_1d', 0) or 0
            
            # Format TVL
            if tvl >= 1e9:
                tvl_str = f"${tvl/1e9:.2f}B"
            elif tvl >= 1e6:
                tvl_str = f"${tvl/1e6:.1f}M"
            else:
                tvl_str = f"${tvl/1e3:.0f}K"
            
            # Change emoji
            change_emoji = "📈" if change_1d >= 0 else "📉"
            
            result += f"{i}. {name}\n"
            result += f"   TVL: {tvl_str} | {change_emoji} {change_1d:+.1f}%\n"
            result += f"   Category: {category} | Chain: {chain}\n"
            if i < limit:
                result += "   " + "-" * 25 + "\n"
        
        return result
    except Exception as e:
        return f"Failed to fetch DeFi ranking: {str(e)}"


def get_protocol_tvl(protocol: str) -> str:
    """
    Get detailed TVL information for a specific DeFi protocol.
    Shows total TVL, chain breakdown, and category.
    
    Args:
        protocol: Protocol name (e.g., "aave", "uniswap", "lido")
    """
    try:
        # Normalize protocol name (lowercase, no spaces)
        protocol_slug = protocol.lower().strip().replace(' ', '-')
        
        url = f"{DEFILLAMA_BASE_URL}/protocol/{protocol_slug}"
        resp = requests.get(url, timeout=15)
        
        if resp.status_code == 404:
            return f"❌ Protocol '{protocol}' not found. Try exact name like 'aave', 'uniswap', 'lido'"
        
        data = resp.json()
        
        name = data.get('name', protocol)
        category = data.get('category', 'N/A')
        description = data.get('description', '')[:200]
        chains = data.get('chains', [])
        
        # Use currentChainTvls for accurate current TVL (tvl field is historical data array)
        current_chain_tvls = data.get('currentChainTvls', {})
        
        # Calculate total TVL from currentChainTvls (exclude borrowed amounts)
        tvl = sum(v for k, v in current_chain_tvls.items() 
                  if not k.endswith('-borrowed') and not k.endswith('-staking') and k != 'borrowed'
                  and isinstance(v, (int, float)))
        
        # Format TVL
        if tvl >= 1e9:
            tvl_str = f"${tvl/1e9:.2f}B"
        elif tvl >= 1e6:
            tvl_str = f"${tvl/1e6:.1f}M"
        else:
            tvl_str = f"${tvl/1e3:.0f}K"
        
        result = f"📊 {name} Protocol Info\n"
        result += "=" * 35 + "\n\n"
        
        result += f"💰 Total TVL: {tvl_str}\n"
        result += f"📂 Category: {category}\n"
        result += f"🔗 Chains: {', '.join(chains[:5])}"
        if len(chains) > 5:
            result += f" (+{len(chains)-5} more)"
        result += "\n\n"
        
        # Top chains by TVL
        if current_chain_tvls:
            result += "📍 TVL by Chain:\n"
            # Sort chains by TVL (exclude borrowed/staking)
            sorted_chains = sorted(
                [(k, v) for k, v in current_chain_tvls.items() 
                 if not k.endswith('-borrowed') and not k.endswith('-staking') and k != 'borrowed'
                 and isinstance(v, (int, float))],
                key=lambda x: x[1],
                reverse=True
            )[:5]
            
            for chain_name, chain_tvl in sorted_chains:
                if isinstance(chain_tvl, (int, float)) and chain_tvl > 0:
                    if chain_tvl >= 1e9:
                        ct_str = f"${chain_tvl/1e9:.2f}B"
                    elif chain_tvl >= 1e6:
                        ct_str = f"${chain_tvl/1e6:.1f}M"
                    else:
                        ct_str = f"${chain_tvl/1e3:.0f}K"
                    result += f"   {chain_name}: {ct_str}\n"
        
        if description:
            result += f"\n📝 {description}"
        
        return result
    except Exception as e:
        return f"Failed to fetch protocol info: {str(e)}"


def get_chain_tvl() -> str:
    """
    Get TVL ranking of all blockchain chains from DefiLlama.
    Shows which chains have the most DeFi activity.
    """
    try:
        url = f"{DEFILLAMA_BASE_URL}/v2/chains"
        resp = requests.get(url, timeout=15).json()
        
        # Sort by TVL
        chains = sorted(resp, key=lambda x: x.get('tvl', 0) or 0, reverse=True)
        
        result = "⛓️ Blockchain TVL Ranking\n"
        result += "=" * 35 + "\n\n"
        
        total_tvl = sum(c.get('tvl', 0) or 0 for c in chains)
        result += f"🌍 Total DeFi TVL: ${total_tvl/1e9:.2f}B\n\n"
        
        for i, c in enumerate(chains[:15], 1):
            name = c.get('name', 'Unknown')
            tvl = c.get('tvl', 0) or 0
            
            # Calculate dominance
            dominance = (tvl / total_tvl * 100) if total_tvl > 0 else 0
            
            # Format TVL
            if tvl >= 1e9:
                tvl_str = f"${tvl/1e9:.2f}B"
            elif tvl >= 1e6:
                tvl_str = f"${tvl/1e6:.1f}M"
            else:
                tvl_str = f"${tvl/1e3:.0f}K"
            
            result += f"{i:2}. {name}: {tvl_str} ({dominance:.1f}%)\n"
        
        return result
    except Exception as e:
        return f"Failed to fetch chain TVL: {str(e)}"


def get_top_yields(limit: int = 10) -> str:
    """
    Get top DeFi yield pools by APY from DefiLlama.
    Shows best opportunities for earning yield on crypto assets.
    Filters for pools with >$1M TVL for safety.
    
    Args:
        limit: Number of pools to show (default 10, max 30)
    """
    try:
        url = f"{DEFILLAMA_YIELDS_URL}/pools"
        resp = requests.get(url, timeout=15).json()
        
        if 'data' not in resp:
            return "Failed to fetch yield data"
        
        pools = resp['data']
        
        # Filter: TVL > $1M, APY > 0, and not illusory (exclude pools with extreme APY)
        filtered = [
            p for p in pools 
            if (p.get('tvlUsd', 0) or 0) > 1_000_000 
            and 0 < (p.get('apy', 0) or 0) < 1000  # Reasonable APY range
            and p.get('stablecoin', False) == False  # Exclude stablecoin-only for variety
        ]
        
        # Sort by APY
        sorted_pools = sorted(filtered, key=lambda x: x.get('apy', 0) or 0, reverse=True)
        limit = min(limit, 30)
        
        result = "💰 Top DeFi Yield Pools\n"
        result += "=" * 40 + "\n"
        result += "⚠️ Higher APY = Higher Risk. DYOR!\n\n"
        
        for i, p in enumerate(sorted_pools[:limit], 1):
            project = p.get('project', 'Unknown')
            symbol = p.get('symbol', 'N/A')
            chain = p.get('chain', 'N/A')
            apy = p.get('apy', 0) or 0
            tvl = p.get('tvlUsd', 0) or 0
            
            # Format TVL
            if tvl >= 1e9:
                tvl_str = f"${tvl/1e9:.2f}B"
            elif tvl >= 1e6:
                tvl_str = f"${tvl/1e6:.1f}M"
            else:
                tvl_str = f"${tvl/1e3:.0f}K"
            
            result += f"{i}. {project} - {symbol}\n"
            result += f"   🔥 APY: {apy:.1f}% | TVL: {tvl_str} | {chain}\n"
            if i < limit:
                result += "   " + "-" * 30 + "\n"
        
        return result
    except Exception as e:
        return f"Failed to fetch yield data: {str(e)}"