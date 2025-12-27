"""
Dashboard API router.
Provides news, tokens, fear-greed index, and indicators data.
"""
from fastapi import APIRouter
import requests
import time
import os
from ..services.cache_service import is_cache_valid, set_cache, get_cache

# Binance API base URL (configurable via environment variable)
BINANCE_API_BASE = os.getenv("BINANCE_API_BASE", "https://api.binance.com")

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def fetch_with_retry(url, params=None, headers=None, timeout=5, retries=1):
    """Fetch URL with minimal retry (fast fail)"""
    last_error = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                time.sleep(0.2)  # Short delay
    print(f"[Dashboard] Failed: {url} - {last_error}")
    return None


@router.get("/news")
async def get_dashboard_news():
    """Get latest crypto news headlines with AI summary (10min cache)"""
    try:
        if is_cache_valid("news", 600):
            cached = get_cache("news")
            if cached and len(cached) > 0:
                return {"news": cached}
        
        news_data = []
        raw_news = []
        
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
                    timeout=5
                )
                
                if resp.status_code == 200:
                    results = resp.json().get("news", [])[:6]
                    raw_news = [
                        {
                            "title": r.get("title", ""), 
                            "source": r.get("source", "Google News"),
                            "snippet": r.get("snippet", "")
                        }
                        for r in results if r.get("title")
                    ]
                    print(f"[Dashboard News] Serper returned {len(raw_news)} items")
        except Exception as e:
            print(f"[Dashboard News] Serper error: {e}")
        
        # Use AI to summarize news in both languages
        if raw_news and len(raw_news) >= 3:
            news_data = summarize_news_with_ai(raw_news)
        
        if not news_data or len(news_data) < 3:
            print("[Dashboard News] Using static fallback")
            news_data = [
                {"title_en": "Bitcoin holds steady above $90K as market awaits Fed decision", "title_zh": "比特币在9万美元上方保持稳定，市场等待美联储决议", "source": "CoinDesk"},
                {"title_en": "Ethereum Layer 2 solutions see record TVL growth", "title_zh": "以太坊二层解决方案TVL创历史新高", "source": "The Block"},
                {"title_en": "Institutional crypto adoption accelerates in Asia", "title_zh": "亚洲机构加密货币采用加速", "source": "Bloomberg"},
                {"title_en": "DeFi protocols show renewed growth momentum in Q4", "title_zh": "DeFi协议第四季度增长势头强劲", "source": "DeFiLlama"},
                {"title_en": "NFT market sees signs of recovery with blue-chip sales", "title_zh": "NFT市场蓝筹销售回暖，复苏迹象显现", "source": "OpenSea"},
                {"title_en": "Regulatory clarity improves for crypto industry globally", "title_zh": "全球加密货币行业监管逐渐明朗", "source": "CoinTelegraph"}
            ]
        
        set_cache("news", news_data)
        return {"news": news_data}
    except Exception as e:
        print(f"[Dashboard News] Error: {e}")
        return {"news": [], "error": str(e)}


def summarize_news_with_ai(raw_news):
    """Use AI to summarize news headlines in both English and Chinese"""
    import os
    from openai import OpenAI
    
    try:
        # Use DeepSeek API (compatible with OpenAI SDK)
        client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url="https://api.deepseek.com"
        )
        
        # Prepare news text for summarization
        news_text = "\n".join([
            f"{i+1}. [{n['source']}] {n['title']}" + (f" - {n['snippet']}" if n.get('snippet') else "")
            for i, n in enumerate(raw_news[:6])
        ])
        
        prompt = f"""Summarize each of the following crypto news headlines. For each news item, provide:
1. A concise English summary (max 20 words)
2. A concise Chinese summary (max 20 characters)

Format your response as JSON array with objects containing: title_en, title_zh, source

News:
{news_text}

Respond ONLY with valid JSON array, no markdown, no explanation."""
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500
        )
        
        import json
        result_text = response.choices[0].message.content.strip()
        # Clean potential markdown formatting
        if result_text.startswith("```"):
            result_text = result_text.split("\n", 1)[1]
            result_text = result_text.rsplit("```", 1)[0]
        
        summarized = json.loads(result_text)
        print(f"[Dashboard News] AI summarized {len(summarized)} news items")
        return summarized
        
    except Exception as e:
        print(f"[Dashboard News] AI summarization failed: {e}")
        # Fallback: return original titles with simple format
        return [
            {"title_en": n["title"], "title_zh": n["title"], "source": n["source"]}
            for n in raw_news
        ]


@router.get("/tokens")
async def get_dashboard_tokens():
    """Get popular tokens with price and 24h change (1min cache)"""
    try:
        if is_cache_valid("tokens", 60):
            return {"tokens": get_cache("tokens")}
        
        tokens_data = []
        symbols = ["BTC", "ETH", "SOL", "XRP", "ADA", "DOGE"]
        
        try:
            url = f"{BINANCE_API_BASE}/api/v3/ticker/24hr"
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
                        "change_24h": round(change, 2)
                    })
            
            order = {s: i for i, s in enumerate(symbols)}
            tokens_data.sort(key=lambda x: order.get(x["name"], 999))
            
        except Exception as e:
            print(f"[Dashboard] Token fetch error: {e}")
        
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
            f"{BINANCE_API_BASE}/api/v3/ticker/price?symbol=ETHBTC",
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
