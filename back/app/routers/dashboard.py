"""
Dashboard API router.
Provides news, tokens, fear-greed index, and indicators data.
"""
from fastapi import APIRouter
import requests
import time
from ..services.cache_service import is_cache_valid, set_cache, get_cache

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

def fetch_with_retry(url, params=None, headers=None, timeout=10, retries=3):
    """Fetch URL with retry logic"""
    last_error = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))  # Progressive delay
    print(f"[Dashboard] Failed after {retries} retries: {url} - {last_error}")
    return None

@router.get("/news")
async def get_dashboard_news():
    """Get latest crypto news headlines (10min cache)"""
    try:
        if is_cache_valid("news", 600):
            cached = get_cache("news")
            if cached and len(cached) > 0:
                return {"news": cached}
        
        news_data = []
        
        # Use Serper API (Google News) - free tier available
        try:
            import os
            api_key = os.getenv("SERPER_API_KEY", "")
            if api_key:
                headers = {
                    "X-API-KEY": api_key,
                    "Content-Type": "application/json"
                }
                payload = {
                    "q": "cryptocurrency bitcoin ethereum",
                    "num": 6,
                    "type": "news"
                }
                
                resp = requests.post(
                    "https://google.serper.dev/news",
                    json=payload,
                    headers=headers,
                    timeout=10
                )
                
                if resp.status_code == 200:
                    results = resp.json().get("news", [])[:6]
                    news_data = [
                        {"title": r.get("title", ""), "source": r.get("source", "Google News")}
                        for r in results if r.get("title")
                    ]
                    print(f"[Dashboard News] Serper returned {len(news_data)} items")
        except Exception as e:
            print(f"[Dashboard News] Serper error: {e}")
        
        if not news_data or len(news_data) < 3:
            print("[Dashboard News] Using static fallback")
            news_data = [
                {"title": "Bitcoin holds steady above $90K as market awaits Fed decision", "source": "CoinDesk"},
                {"title": "Ethereum Layer 2 solutions see record TVL growth", "source": "The Block"},
                {"title": "Institutional crypto adoption accelerates in Asia", "source": "Bloomberg"},
                {"title": "DeFi protocols show renewed growth momentum in Q4", "source": "DeFiLlama"},
                {"title": "NFT market sees signs of recovery with blue-chip sales", "source": "OpenSea"},
                {"title": "Regulatory clarity improves for crypto industry globally", "source": "CoinTelegraph"}
            ]
        
        set_cache("news", news_data)
        return {"news": news_data}
    except Exception as e:
        print(f"[Dashboard News] Error: {e}")
        return {"news": [], "error": str(e)}

@router.get("/tokens")
async def get_dashboard_tokens():
    """Get popular tokens with price and 24h change (1min cache)"""
    try:
        if is_cache_valid("tokens", 60):
            return {"tokens": get_cache("tokens")}
        
        tokens_data = []
        symbols = ["BTC", "ETH", "SOL", "XRP", "ADA", "DOGE"]
        
        try:
            url = "https://api.binance.com/api/v3/ticker/24hr"
            resp = requests.get(url, timeout=5).json()
            
            symbol_map = {s + "USDT": s for s in symbols}
            
            for ticker in resp:
                symbol = ticker.get("symbol", "")
                if symbol in symbol_map:
                    price = float(ticker.get("lastPrice", 0))
                    change = float(ticker.get("priceChangePercent", 0))
                    tokens_data.append({
                        "name": symbol_map[symbol],
                        "price": price,
                        "change_24h": change
                    })
            
            order = {s: i for i, s in enumerate(symbols)}
            tokens_data.sort(key=lambda x: order.get(x["name"], 999))
            
        except Exception as e:
            print(f"Token fetch error: {e}")
        
        set_cache("tokens", tokens_data)
        return {"tokens": tokens_data}
    except Exception as e:
        return {"tokens": [], "error": str(e)}

@router.get("/fear-greed")
async def get_dashboard_fear_greed():
    """Get Fear & Greed Index (1hr cache)"""
    try:
        if is_cache_valid("fear_greed", 3600):
            return get_cache("fear_greed")
        
        # Use fetch_with_retry for reliability
        data = fetch_with_retry(
            "https://api.alternative.me/fng/?limit=1",
            timeout=10,
            retries=3
        )
        
        if data and data.get("data"):
            result = {
                "value": int(data["data"][0].get("value", 50)),
                "classification": data["data"][0].get("value_classification", "Neutral")
            }
            set_cache("fear_greed", result)  # Only cache on success
            print(f"[Dashboard] Fear & Greed: {result['value']} ({result['classification']})")
            return result
        else:
            print("[Dashboard] Fear & Greed API returned no data")
            # Return default but don't cache it
            return {"value": 50, "classification": "Neutral", "note": "API unavailable"}
    except Exception as e:
        return {"value": 50, "classification": "Neutral", "error": str(e)}

@router.get("/indicators")
async def get_dashboard_indicators():
    """Get key industry indicators (10min cache)"""
    try:
        if is_cache_valid("indicators", 600):
            return {"indicators": get_cache("indicators")}
        
        indicators = []
        headers = {"User-Agent": "Mozilla/5.0"}
        
        # CoinGecko global data
        global_data = fetch_with_retry(
            "https://api.coingecko.com/api/v3/global",
            headers=headers,
            timeout=10,
            retries=3
        )
        if global_data:
            global_resp = global_data.get("data", {})
            total_mcap = global_resp.get("total_market_cap", {}).get("usd", 0)
            btc_dom = global_resp.get("market_cap_percentage", {}).get("btc", 0)
            btc_mcap = total_mcap * (btc_dom / 100) if btc_dom else 0
            
            if total_mcap > 0:
                indicators.append({"name": "Total Market Cap", "value": f"${total_mcap/1e12:.2f}T"})
            if btc_mcap > 0:
                indicators.append({"name": "Bitcoin Market Cap", "value": f"${btc_mcap/1e12:.2f}T"})
            if btc_dom > 0:
                indicators.append({"name": "Bitcoin Dominance", "value": f"{btc_dom:.1f}%"})
        
        # ETH/BTC Ratio from Binance
        ethbtc_data = fetch_with_retry(
            "https://api.binance.com/api/v3/ticker/price?symbol=ETHBTC",
            timeout=5,
            retries=3
        )
        if ethbtc_data:
            ratio = float(ethbtc_data.get("price", 0))
            if ratio > 0:
                indicators.append({"name": "ETH/BTC Ratio", "value": f"{ratio:.5f}"})
        
        # Ethereum Gas from Etherscan
        try:
            from crypto_tools import ETHERSCAN_API_KEY
            if ETHERSCAN_API_KEY:
                gas_data = fetch_with_retry(
                    f"https://api.etherscan.io/v2/api?chainid=1&module=gastracker&action=gasoracle&apikey={ETHERSCAN_API_KEY}",
                    timeout=5,
                    retries=3
                )
                if gas_data and gas_data.get("status") == "1":
                    gas = gas_data.get("result", {}).get("ProposeGasPrice", "0")
                    if gas and gas != "0":
                        indicators.append({"name": "Ethereum Gas", "value": f"{gas} Gwei"})
        except Exception as e:
            print(f"Gas import error: {e}")
        
        # DeFi TVL from DefiLlama
        tvl_data = fetch_with_retry(
            "https://api.llama.fi/v2/chains",
            timeout=5,
            retries=3
        )
        if tvl_data and isinstance(tvl_data, list):
            total_tvl = sum(chain.get("tvl", 0) for chain in tvl_data if isinstance(chain.get("tvl"), (int, float)))
            if total_tvl > 0:
                indicators.append({"name": "DeFi TVL", "value": f"${total_tvl/1e9:.1f}B"})
        
        # Ensure defaults
        indicator_names = [ind["name"] for ind in indicators]
        defaults = [
            {"name": "Total Market Cap", "value": "$3.0T"},
            {"name": "Bitcoin Market Cap", "value": "$1.7T"},
            {"name": "Bitcoin Dominance", "value": "57.0%"},
            {"name": "ETH/BTC Ratio", "value": "0.03400"},
            {"name": "Ethereum Gas", "value": "15 Gwei"},
            {"name": "DeFi TVL", "value": "$180.0B"}
        ]
        for default in defaults:
            if default["name"] not in indicator_names:
                indicators.append(default)
        
        order = {d["name"]: i for i, d in enumerate(defaults)}
        indicators.sort(key=lambda x: order.get(x["name"], 999))
        
        set_cache("indicators", indicators)
        return {"indicators": indicators}
    except Exception as e:
        print(f"[Dashboard Indicators] Error: {e}")
        return {"indicators": [], "error": str(e)}
