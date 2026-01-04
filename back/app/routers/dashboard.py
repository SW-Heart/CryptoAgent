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
        if is_cache_valid("news", 3600):
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

1. title_en: Concise English headline (max 12 words)
2. title_zh: Concise Chinese headline (max 12 characters)
3. summary_en: WHY THIS MATTERS - explain the impact, background context, or implications that the title doesn't mention (max 20 words). DO NOT repeat what the title says.
4. summary_zh: 这条新闻为什么重要 - 解释标题未提及的影响、背景或意义（max 20字）。不要重复标题内容。
5. source: Original news source

IMPORTANT for summary: Provide NEW information that complements the title. Examples:
- Title: "BTC drops 5%" → Summary: "Triggered by large whale sell-off and leveraged liquidations"
- Title: "ETH升级延期" → Summary: "开发者发现关键安全漏洞，需额外测试时间"

Format: JSON array with objects containing: title_en, title_zh, summary_en, summary_zh, source

News:
{news_text}

Respond ONLY with valid JSON array, no markdown."""
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000
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
    """Get key industry indicators (10min cache) - OPTIMIZED with parallel requests"""
    try:
        if is_cache_valid("indicators", 600):
            return {"indicators": get_cache("indicators")}
        
        import concurrent.futures
        
        indicators = []
        headers = {"User-Agent": "Mozilla/5.0"}
        
        # Define fetch functions for parallel execution
        def fetch_coingecko():
            return fetch_with_retry(
                "https://api.coingecko.com/api/v3/global",
                headers=headers,
                timeout=8,
                retries=2
            )
        
        def fetch_ethbtc():
            return fetch_with_retry(
                f"{BINANCE_API_BASE}/api/v3/ticker/price?symbol=ETHBTC",
                timeout=5,
                retries=2
            )
        
        def fetch_gas():
            try:
                from crypto_tools import ETHERSCAN_API_KEY
                if ETHERSCAN_API_KEY:
                    return fetch_with_retry(
                        f"https://api.etherscan.io/v2/api?chainid=1&module=gastracker&action=gasoracle&apikey={ETHERSCAN_API_KEY}",
                        timeout=5,
                        retries=2
                    )
            except Exception:
                pass
            return None
        
        def fetch_tvl():
            return fetch_with_retry(
                "https://api.llama.fi/v2/chains",
                timeout=5,
                retries=2
            )
        
        # Execute all API calls in parallel using ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_coingecko = executor.submit(fetch_coingecko)
            future_ethbtc = executor.submit(fetch_ethbtc)
            future_gas = executor.submit(fetch_gas)
            future_tvl = executor.submit(fetch_tvl)
            
            # Wait for all with timeout
            global_data = None
            ethbtc_data = None
            gas_data = None
            tvl_data = None
            
            try:
                global_data = future_coingecko.result(timeout=10)
            except Exception as e:
                print(f"[Indicators] CoinGecko timeout: {e}")
            
            try:
                ethbtc_data = future_ethbtc.result(timeout=6)
            except Exception as e:
                print(f"[Indicators] Binance timeout: {e}")
            
            try:
                gas_data = future_gas.result(timeout=6)
            except Exception as e:
                print(f"[Indicators] Etherscan timeout: {e}")
            
            try:
                tvl_data = future_tvl.result(timeout=6)
            except Exception as e:
                print(f"[Indicators] DefiLlama timeout: {e}")
        
        # Process CoinGecko global data
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
        
        # Process ETH/BTC Ratio
        if ethbtc_data:
            ratio = float(ethbtc_data.get("price", 0))
            if ratio > 0:
                indicators.append({"name": "ETH/BTC Ratio", "value": f"{ratio:.5f}"})
        
        # Process Ethereum Gas
        if gas_data and gas_data.get("status") == "1":
            gas = gas_data.get("result", {}).get("ProposeGasPrice", "0")
            if gas and gas != "0":
                indicators.append({"name": "Ethereum Gas", "value": f"{gas} Gwei"})
        
        # Process DeFi TVL
        if tvl_data and isinstance(tvl_data, list):
            total_tvl = sum(chain.get("tvl", 0) for chain in tvl_data if isinstance(chain.get("tvl"), (int, float)))
            if total_tvl > 0:
                indicators.append({"name": "DeFi TVL", "value": f"${total_tvl/1e9:.1f}B"})
        
        # Ensure defaults for missing data
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


@router.get("/onchain-hot")
async def get_dashboard_onchain_hot(limit: int = 6):
    """Get on-chain hot tokens from DexScreener (10min cache) - OPTIMIZED with parallel requests"""
    try:
        cache_key = f"onchain_hot_{limit}"
        if is_cache_valid(cache_key, 600):  # 10min cache
            return {"tokens": get_cache(cache_key)}
        
        import concurrent.futures
        
        tokens = []
        all_addresses = set()
        
        def format_usd(value):
            """Format USD values with K/M/B suffix"""
            if value >= 1e9:
                return f"${value/1e9:.1f}B"
            elif value >= 1e6:
                return f"${value/1e6:.1f}M"
            elif value >= 1e3:
                return f"${value/1e3:.0f}K"
            return f"${value:.0f}"
        
        def process_token(address: str, min_change: float = 10) -> dict:
            """Fetch token data and check quality criteria
            
            Args:
                address: Token contract address
                min_change: Minimum 24h price change percentage (default 10%)
            """
            try:
                token_url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
                resp = requests.get(token_url, timeout=5)
                if resp.status_code != 200:
                    return None
                
                data = resp.json()
                pairs = data.get('pairs', [])
                if not pairs:
                    return None
                
                # Get the pair with highest liquidity
                best_pair = max(pairs, key=lambda p: float(p.get('liquidity', {}).get('usd', 0) or 0))
                
                liquidity = float(best_pair.get('liquidity', {}).get('usd', 0) or 0)
                volume_24h = float(best_pair.get('volume', {}).get('h24', 0) or 0)
                market_cap = float(best_pair.get('marketCap', 0) or best_pair.get('fdv', 0) or 0)
                price_change_24h = float(best_pair.get('priceChange', {}).get('h24', 0) or 0)
                price_usd = float(best_pair.get('priceUsd', 0) or 0)
                
                # Quality filters - liquidity, volume, market cap are fixed
                # price_change threshold is configurable
                if liquidity < 50000 or volume_24h < 100000 or market_cap < 100000:
                    return None
                if price_change_24h < min_change:
                    return None
                
                # Extract social info
                info = best_pair.get('info', {})
                socials = info.get('socials', [])
                websites = info.get('websites', [])
                
                # Build social links list
                social_links = []
                for social in socials:
                    social_type = social.get('type', '').lower()
                    url = social.get('url', '')
                    if url:
                        social_links.append({'type': social_type, 'url': url})
                
                # Get website URL
                website_url = websites[0].get('url') if websites else None
                
                return {
                    'symbol': best_pair.get('baseToken', {}).get('symbol', 'Unknown'),
                    'chain': best_pair.get('chainId', 'unknown'),
                    'price': price_usd,
                    'change_24h': price_change_24h,
                    'market_cap': format_usd(market_cap),
                    'socials': social_links,
                    'website': website_url,
                    'dex_url': best_pair.get('url', ''),
                    'address': address
                }
            except Exception:
                return None
        
        # Step 1: Collect all candidate addresses first (fast)
        candidate_addresses = []
        
        try:
            boosts_resp = requests.get("https://api.dexscreener.com/token-boosts/latest/v1", timeout=8)
            if boosts_resp.status_code == 200:
                for token in boosts_resp.json()[:20]:  # Get more candidates for filtering
                    addr = token.get('tokenAddress', '')
                    if addr and addr not in all_addresses:
                        all_addresses.add(addr)
                        candidate_addresses.append(addr)
        except Exception as e:
            print(f"[Onchain Hot] Boosts latest error: {e}")
        
        # If not enough candidates, try top boosts
        if len(candidate_addresses) < limit * 2:
            try:
                top_resp = requests.get("https://api.dexscreener.com/token-boosts/top/v1", timeout=8)
                if top_resp.status_code == 200:
                    for token in top_resp.json()[:20]:
                        addr = token.get('tokenAddress', '')
                        if addr and addr not in all_addresses:
                            all_addresses.add(addr)
                            candidate_addresses.append(addr)
            except Exception as e:
                print(f"[Onchain Hot] Boosts top error: {e}")
        
        # If still not enough candidates, try Token Profiles from major chains
        if len(candidate_addresses) < limit * 3:
            chains = ['solana', 'ethereum', 'bsc', 'base', 'arbitrum']
            for chain in chains:
                if len(candidate_addresses) >= limit * 4:  # Stop when we have enough
                    break
                try:
                    profiles_resp = requests.get(
                        f"https://api.dexscreener.com/token-profiles/latest/v1?chainId={chain}",
                        timeout=8
                    )
                    if profiles_resp.status_code == 200:
                        for token in profiles_resp.json()[:15]:
                            addr = token.get('tokenAddress', '')
                            if addr and addr not in all_addresses:
                                all_addresses.add(addr)
                                candidate_addresses.append(addr)
                except Exception as e:
                    print(f"[Onchain Hot] Profiles {chain} error: {e}")
        
        # Step 2: Process tokens in PARALLEL using ThreadPoolExecutor
        # Two-pass strategy: first with strict criteria (10% gain), then relaxed (0%) if needed
        processed_addresses = set()
        
        def batch_process(addresses, min_change):
            """Process tokens with given min_change threshold"""
            results = []
            remaining_addrs = [a for a in addresses if a not in processed_addresses]
            
            if not remaining_addrs:
                return results
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                future_to_addr = {
                    executor.submit(process_token, addr, min_change): addr 
                    for addr in remaining_addrs[:limit * 4]
                }
                
                for future in concurrent.futures.as_completed(future_to_addr, timeout=15):
                    addr = future_to_addr[future]
                    processed_addresses.add(addr)
                    try:
                        result = future.result(timeout=6)
                        if result:
                            results.append(result)
                    except Exception:
                        pass
            
            return results
        
        if candidate_addresses:
            # Pass 1: Strict criteria (24h change >= 10%)
            tokens = batch_process(candidate_addresses, min_change=10)
            print(f"[Onchain Hot] Pass 1 (strict, >=10%): found {len(tokens)} tokens")
            
            # Pass 2: If not enough, relax to 0% change (just needs positive liquidity/volume/mcap)
            if len(tokens) < limit:
                relaxed_tokens = batch_process(candidate_addresses, min_change=0)
                print(f"[Onchain Hot] Pass 2 (relaxed, >=0%): found {len(relaxed_tokens)} additional tokens")
                
                # Add relaxed tokens that aren't duplicates
                existing_addrs = {t['address'] for t in tokens}
                for t in relaxed_tokens:
                    if t['address'] not in existing_addrs and len(tokens) < limit:
                        tokens.append(t)
        
        # Sort by 24h change (highest first)
        tokens.sort(key=lambda x: x['change_24h'], reverse=True)
        tokens = tokens[:limit]  # Ensure we only return requested limit
        
        set_cache(cache_key, tokens)
        print(f"[Onchain Hot] Final: Returned {len(tokens)} tokens")
        return {"tokens": tokens}
    except Exception as e:
        print(f"[Dashboard Onchain Hot] Error: {e}")
        return {"tokens": [], "error": str(e)}


@router.get("/trending")
async def get_dashboard_trending(limit: int = 10):
    """Get CoinGecko trending tokens with real-time Binance prices
    
    CoinGecko trending list is cached for 15min (to respect rate limits).
    Binance prices are fetched fresh on every request.
    """
    try:
        limit = max(1, min(15, limit))
        
        # ===== Step 1: Get CoinGecko trending list + prices (cached 15min) =====
        trending_cache_key = "trending_list_v2"
        coin_info = {}
        symbols = []
        cg_prices = {}  # Cached CoinGecko prices for fallback
        
        if is_cache_valid(trending_cache_key, 900):  # 15min cache
            cached_list = get_cache(trending_cache_key)
            if cached_list:
                coin_info = cached_list.get('coin_info', {})
                symbols = cached_list.get('symbols', [])
                cg_prices = cached_list.get('cg_prices', {})
        
        # If no cache or cache expired, fetch from CoinGecko
        if not symbols:
            coingecko_api_key = os.getenv("COINGECKO_API_KEY", "")
            
            if coingecko_api_key:
                headers = {
                    'User-Agent': 'Mozilla/5.0',
                    'x-cg-demo-api-key': coingecko_api_key
                }
            else:
                headers = {'User-Agent': 'Mozilla/5.0'}
            
            trending_resp = fetch_with_retry(
                "https://api.coingecko.com/api/v3/search/trending",
                headers=headers,
                timeout=10,
                retries=2
            )
            
            if not trending_resp or 'coins' not in trending_resp:
                return {"tokens": [], "error": "Failed to fetch CoinGecko trending"}
            
            trending_coins = trending_resp['coins'][:15]  # Cache up to 15 for flexibility
            
            for coin in trending_coins:
                item = coin.get('item', {})
                symbol = item.get('symbol', '').upper()
                symbols.append(symbol)
                coin_info[symbol] = {
                    'name': item.get('name', 'Unknown'),
                    'symbol': symbol,
                    'image': item.get('thumb', ''),
                    'market_cap_rank': item.get('market_cap_rank'),
                    'coingecko_id': item.get('id', '')
                }
            
            # Fetch prices from CoinGecko (once, cached with list)
            cg_ids = [info['coingecko_id'] for info in coin_info.values() if info.get('coingecko_id')]
            if cg_ids:
                try:
                    ids_str = ','.join(cg_ids)
                    price_resp = fetch_with_retry(
                        f"https://api.coingecko.com/api/v3/simple/price?ids={ids_str}&vs_currencies=usd&include_24hr_change=true",
                        headers=headers,
                        timeout=10,
                        retries=1
                    )
                    if price_resp:
                        for cg_id, data in price_resp.items():
                            for sym, info in coin_info.items():
                                if info['coingecko_id'] == cg_id:
                                    cg_prices[sym] = {
                                        'price': data.get('usd'),
                                        'change_24h': data.get('usd_24h_change', 0) or 0
                                    }
                                    break
                        print(f"[Dashboard Trending] Cached CoinGecko prices for {len(cg_prices)} tokens")
                except Exception as e:
                    print(f"[Dashboard Trending] CoinGecko price fetch error: {e}")
            
            # Cache everything together
            set_cache(trending_cache_key, {
                'coin_info': coin_info, 
                'symbols': symbols,
                'cg_prices': cg_prices
            })
            print(f"[Dashboard Trending] Cached trending list: {symbols[:5]}...")
        
        # ===== Step 2: Fetch REAL-TIME prices from Binance (no cache) =====
        price_map = {}
        try:
            ticker_resp = fetch_with_retry(
                f"{BINANCE_API_BASE}/api/v3/ticker/24hr",
                timeout=5,
                retries=1
            )
            if ticker_resp:
                for t in ticker_resp:
                    sym = t.get('symbol', '')
                    if sym.endswith('USDT'):
                        base = sym.replace('USDT', '')
                        price_map[base] = {
                            'price': float(t.get('lastPrice', 0)),
                            'change_24h': float(t.get('priceChangePercent', 0))
                        }
        except Exception as e:
            print(f"[Dashboard Trending] Binance price fetch error: {e}")
        
        # ===== Step 3: Build token list with fresh prices =====
        tokens = []
        for symbol in symbols[:limit]:
            if symbol not in coin_info:
                continue
            info = coin_info[symbol]
            token = {
                'symbol': symbol,
                'name': info['name'],
                'image': info['image'],
                'market_cap_rank': info['market_cap_rank'],
                'coingecko_id': info['coingecko_id']
            }
            
            # Priority: Binance (real-time) > CoinGecko (cached)
            if symbol in price_map:
                token['price'] = price_map[symbol]['price']
                token['change_24h'] = price_map[symbol]['change_24h']
            elif symbol in cg_prices:
                token['price'] = cg_prices[symbol]['price']
                token['change_24h'] = cg_prices[symbol]['change_24h']
            else:
                token['price'] = None
                token['change_24h'] = None
            
            tokens.append(token)
        
        return {"tokens": tokens}
    except Exception as e:
        print(f"[Dashboard Trending] Error: {e}")
        return {"tokens": [], "error": str(e)}

