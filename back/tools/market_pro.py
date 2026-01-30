"""
市场行情工具 - 价格、技术指标、市场情绪等
"""
import requests
import pandas as pd
import pandas_ta as ta
import os
from typing import Dict, Any

CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY", "")
CRYPTOPANIC_BASE_URL = "https://cryptopanic.com/api/developer/v2/posts/"


# ==========================================
# 🧱 基础组件：混合数据源 (Binance + DexScreener)
# ==========================================

def get_binance_data(symbol: str, interval: str = "4h", limit: int = 100):
    """
    尝试从 Binance 获取实时价格和 K 线 (毫秒级延迟)
    """
    pair = f"{symbol.upper()}USDT"
    base_url = "https://api.binance.com"
    
    try:
        ticker_url = f"{base_url}/api/v3/ticker/price?symbol={pair}"
        ticker_resp = requests.get(ticker_url, timeout=2) 
        
        if ticker_resp.status_code != 200:
            return None
            
        current_price = float(ticker_resp.json()['price'])
        
        klines_url = f"{base_url}/api/v3/klines?symbol={pair}&interval={interval}&limit={limit}"
        klines_resp = requests.get(klines_url, timeout=2).json()
        
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


def get_dexscreener_data(symbol: str):
    """
    尝试从 DexScreener 获取链上价格 (针对土狗/Meme)
    """
    try:
        search_url = f"https://api.dexscreener.com/latest/dex/search?q={symbol}"
        resp = requests.get(search_url, timeout=5).json()
        
        if not resp.get('pairs'):
            return None
            
        best_pair = resp['pairs'][0]
        
        return {
            "source": f"DexScreener ({best_pair['dexId']} on {best_pair['chainId']})",
            "name": best_pair.get('baseToken', {}).get('name', symbol),
            "price": float(best_pair['priceUsd']),
            "change_24h": best_pair.get('priceChange', {}).get('h24', 0),
            "liquidity": best_pair.get('liquidity', {}).get('usd', 0),
            "history_df": None
        }
    except:
        return None


# ==========================================
# 🚀 核心市场工具
# ==========================================

def get_token_analysis(symbol: str) -> str:
    """
    Get real-time price and technical analysis (RSI, EMA, trend) for a token.
    Tries Binance first, falls back to DexScreener for meme coins.
    
    Args:
        symbol: Token symbol (e.g., "BTC", "ETH", "PEPE")
    """
    clean_symbol = symbol.upper().strip()
    
    data = None
    binance_error = None
    try:
        data = get_binance_data(clean_symbol)
    except Exception as e:
        binance_error = str(e)
    
    dex_error = None
    if not data:
        try:
            data = get_dexscreener_data(clean_symbol)
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

    price = data['price']
    source = data['source']
    report = f"[{clean_symbol} Analysis]\n"
    report += f"Data Source: {source}\n"
    
    if price < 0.01:
        report += f"Price: ${format(price, '.8f')}\n"
    else:
        report += f"Price: ${price:,.4f}\n"

    if data.get('history_df') is not None:
        df = data['history_df']
        
        try:
            rsi_series = ta.rsi(df['close'], length=14)
            rsi = rsi_series.iloc[-1] if rsi_series is not None and len(rsi_series) > 0 else None
            
            ema20_series = ta.ema(df['close'], length=20)
            ema50_series = ta.ema(df['close'], length=50)
            ema20 = ema20_series.iloc[-1] if ema20_series is not None and len(ema20_series) > 0 else None
            ema50 = ema50_series.iloc[-1] if ema50_series is not None and len(ema50_series) > 0 else None
            
            if ema20 is not None and ema50 is not None:
                trend = "Sideways"
                if price > ema20 > ema50: trend = "Strong Uptrend"
                elif price < ema20 < ema50: trend = "Downtrend"
                elif price < ema20 and ema20 > ema50: trend = "Pullback"
                report += f"Trend: {trend}\n"
            
            if rsi is not None:
                rsi_signal = "Neutral"
                if rsi > 70: rsi_signal = "Overbought (High Risk)"
                elif rsi < 30: rsi_signal = "Oversold (Bounce Opportunity)"
                report += f"RSI: {rsi:.1f} - {rsi_signal}\n"
            
            if ema20 is not None:
                report += f"Support (EMA20): ${ema20:.4f}"
        except Exception as e:
            report += f"\nTechnical indicator error: {str(e)}"

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
        headers = {'User-Agent': 'Mozilla/5.0'}
        trend = requests.get("https://api.coingecko.com/api/v3/search/trending", headers=headers, timeout=5).json()
        hot_coins = [f"{i['item']['symbol']}" for i in trend['coins'][:5]]
        return f"Trending coins: {', '.join(hot_coins)}"
    except:
        return "Failed to fetch trending data"


def get_top_gainers_cex(limit: int = 10) -> str:
    """
    Get top gaining tokens by 24h price change from Binance (CEX).
    Strictly filters for tokens with 'TRADING' status to avoid delisted/halted assets.
    
    Args:
        limit: Number of results (default 10)
    """
    try:
        base_url = "https://api.binance.com"
        
        # 1. Fetch Exchange Info to identify active trading pairs
        # Crucial: This filters out halted/delisted tokens (like CREAM) that might still yield ticker data
        info_url = f"{base_url}/api/v3/exchangeInfo"
        info_resp = requests.get(info_url, timeout=10).json()
        
        # Build whitelist: Only symbols with status='TRADING' and quoteAsset='USDT'
        valid_symbols = set()
        for s in info_resp.get('symbols', []):
            if s['status'] == 'TRADING' and s['quoteAsset'] == 'USDT':
                valid_symbols.add(s['symbol'])
                
        # 2. Fetch 24hr ticker data for ALL symbols
        ticker_url = f"{base_url}/api/v3/ticker/24hr"
        ticker_resp = requests.get(ticker_url, timeout=10).json()
        
        # 3. Filter ticker data using the valid_symbols whitelist
        # Also exclude stablecoins and fiat pairs
        stablecoins = ['USDCUSDT', 'BUSDUSDT', 'TUSDUSDT', 'DAIUSDT', 'FDUSDUSDT', 'EURUSDT', 'GBPUSDT']
        
        filtered_pairs = [
            t for t in ticker_resp 
            if t['symbol'] in valid_symbols 
            and t['symbol'] not in stablecoins
        ]
        
        # 4. Sort by percentage change
        sorted_pairs = sorted(filtered_pairs, key=lambda x: float(x['priceChangePercent']), reverse=True)
        
        result = "Top Gainers - Binance (24h):\n"
        for i, t in enumerate(sorted_pairs[:limit], 1):
            symbol = t['symbol'].replace('USDT', '')
            change = float(t['priceChangePercent'])
            price = float(t['lastPrice'])
            volume = float(t['quoteVolume']) / 1e6  # Quote volume is in USDT
            
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
        
        assets = [a for a in resp['data'] if a.get('changePercent24Hr')]
        sorted_assets = sorted(assets, key=lambda x: float(x['changePercent24Hr']), reverse=True)
        
        result = "Top Gainers - All Markets (24h):\n"
        for i, a in enumerate(sorted_assets[:limit], 1):
            symbol = a['symbol']
            name = a['name'][:15]
            change = float(a['changePercent24Hr'])
            price = float(a['priceUsd']) if a.get('priceUsd') else 0
            mcap = float(a['marketCapUsd']) / 1e9 if a.get('marketCapUsd') else 0
            
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
        
        total_mcap = data['total_market_cap']['usd']
        total_volume = data['total_volume']['usd']
        mcap_change_24h = data.get('market_cap_change_percentage_24h_usd', 0)
        active_coins = data.get('active_cryptocurrencies', 0)
        markets = data.get('markets', 0)
        
        btc_dom = data['market_cap_percentage']['btc']
        eth_dom = data['market_cap_percentage']['eth']
        
        ongoing_icos = data.get('ongoing_icos', 0)
        upcoming_icos = data.get('upcoming_icos', 0)
        
        result = "📊 Global Crypto Market Overview\n"
        result += "=" * 35 + "\n\n"
        
        result += f"💰 Total Market Cap: ${total_mcap/1e12:.3f}T\n"
        
        btc_mcap = total_mcap * (btc_dom / 100)
        eth_mcap = total_mcap * (eth_dom / 100)
        result += f"₿  BTC Market Cap: ${btc_mcap/1e12:.3f}T\n"
        result += f"⟠  ETH Market Cap: ${eth_mcap/1e9:.1f}B\n"
        
        change_emoji = "📈" if mcap_change_24h >= 0 else "📉"
        result += f"{change_emoji} 24h Change: {mcap_change_24h:+.2f}%\n"
        
        result += f"💱 24h Volume: ${total_volume/1e9:.2f}B\n"
        result += f"📐 Volume/MCap Ratio: {(total_volume/total_mcap)*100:.2f}%\n\n"
        
        result += "🏆 Market Dominance\n"
        result += f"   BTC: {btc_dom:.1f}%\n"
        result += f"   ETH: {eth_dom:.1f}%\n"
        result += f"   Others: {100 - btc_dom - eth_dom:.1f}%\n\n"
        
        result += "🔢 Market Activity\n"
        result += f"   Active Coins: {active_coins:,}\n"
        result += f"   Active Markets: {markets:,}\n"
        
        if ongoing_icos or upcoming_icos:
            result += f"   Ongoing ICOs: {ongoing_icos}\n"
            result += f"   Upcoming ICOs: {upcoming_icos}\n"
        
        result += "\n📋 Market Health Assessment\n"
        
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
        url = "https://api.binance.com/api/v3/ticker/24hr?symbol=ETHBTC"
        resp = requests.get(url, timeout=5).json()
        
        ratio = float(resp['lastPrice'])
        change_24h = float(resp['priceChangePercent'])
        high_24h = float(resp['highPrice'])
        low_24h = float(resp['lowPrice'])
        
        result = "⟠/₿ ETH/BTC Ratio\n"
        result += "=" * 30 + "\n\n"
        
        result += f"📊 Current Ratio: {ratio:.5f}\n"
        
        change_emoji = "📈" if change_24h >= 0 else "📉"
        result += f"{change_emoji} 24h Change: {change_24h:+.2f}%\n"
        result += f"📈 24h High: {high_24h:.5f}\n"
        result += f"📉 24h Low: {low_24h:.5f}\n\n"
        
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
        
        funding_rate = float(data[0]['fundingRate']) * 100
        
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


def get_narrative_dominance() -> str:
    """
    Analyze dominant crypto narratives (AI, Meme, L2, RWA, DeFi, etc.) by scanning news keywords.
    Returns bar chart showing sector strength.
    """
    if "你的" in CRYPTOPANIC_API_KEY:
        return "❌ 配置错误: 请填入 Key"

    try:
        params = {
            "auth_token": CRYPTOPANIC_API_KEY,
            "public": "true",
            "filter": "hot",
            "kind": "news",
            "regions": "en"
        }
        
        resp = requests.get(CRYPTOPANIC_BASE_URL, params=params, timeout=10)
        
        if resp.status_code != 200:
            return f"API request failed: {resp.status_code}"

        data = resp.json()
        if "results" not in data:
            return "API returned empty data"

        all_text = " ".join([p.get('title', '') for p in data['results']])
        
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
        "public": "true",
        "filter": filter_type,
        "kind": "news",
        "regions": "en"
    }
    
    try:
        resp = requests.get(CRYPTOPANIC_BASE_URL, params=params, timeout=10)
        
        if resp.status_code != 200:
            return f"CryptoPanic API error ({resp.status_code}): {resp.text}"
            
        data = resp.json()
        
        if "results" not in data:
            return f"API data error: {data}"
        
        report = f"[Crypto News Radar ({filter_type.upper()})]\n"
        
        for post in data['results'][:5]: 
            title = post.get('title', 'No title')
            
            domain = "Unknown"
            if post.get('source'):
                domain = post['source'].get('domain', 'Unknown')
            
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
# 🧩 聚合工具 (Module Aggregators)
# ==========================================

def get_market_macro_metrics() -> str:
    """
    Get a comprehensive macro overview of the crypto market (Aggregated Report).
    Combines: Global Overview, Sentiment, BTC Dominance, ETH/BTC Ratio, and BTC Funding Rate.
    Use this ONE tool to answer questions like: 'How is the market?', 'Market health', 'Bull or Bear?'.
    """
    try:
        overview = get_global_market_overview()
        sentiment = get_market_sentiment()
        btc_dom = get_btc_dominance()
        eth_btc = get_eth_btc_ratio()
        funding = get_funding_rate("BTC")
        
        return f"""
{overview}

{sentiment}

{btc_dom}

{eth_btc}

{funding}
"""
    except Exception as e:
        return f"Failed to fetch macro metrics: {str(e)}"

def get_market_trends() -> str:
    """
    Get current market trends, hotspots and top gainers (Aggregated Report).
    Combines: Search Trending, Narrative Dominance, and Top 5 Gainers (CEX).
    Use this ONE tool to answer questions like: 'What is trending?', 'Hot sectors', 'What to buy?'.
    """
    try:
        hotspots = get_market_hotspots()
        narrative = get_narrative_dominance()
        gainers = get_top_gainers_cex(limit=5)
        
        return f"""
{hotspots}

{narrative}

{gainers}
"""
    except Exception as e:
        return f"Failed to fetch market trends: {str(e)}"
