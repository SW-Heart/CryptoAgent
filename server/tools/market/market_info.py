"""
核心市场工具：Token 分析、情绪、热点、Gainers、BTC 指标等
"""
import requests
import pandas as pd
import pandas_ta as ta
import os
from .data_sources import get_binance_data as _get_binance_data, _get_dexscreener_data

COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")

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

    # Add 24h Change
    if 'change_24h' in data:
        change = data['change_24h']
        change_emoji = "📈" if change >= 0 else "📉"
        report += f"24h Change: {change_emoji} {change:+.2f}%\n"

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
        # change = data.get('change_24h', 0) # Already added above
        liq = data.get('liquidity', 0)
        
        # report += f"24h Change: {change}%\n"
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


# CoinGecko API configuration
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")


def get_trending_tokens(limit: int = 10) -> str:
    """
    Get top trending tokens from CoinGecko with real-time Binance prices.
    Returns token name, symbol, 24h price change, and current price.
    Best for discovering what tokens are getting the most attention right now.
    
    Args:
        limit: Number of results (1-15, default 10)
    
    Returns:
        List of trending tokens with prices and 24h changes
    """
    limit = max(1, min(15, limit))
    
    try:
        # Use CoinGecko Pro API if key available, otherwise free API
        if COINGECKO_API_KEY:
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'x-cg-demo-api-key': COINGECKO_API_KEY
            }
            url = "https://api.coingecko.com/api/v3/search/trending"
        else:
            headers = {'User-Agent': 'Mozilla/5.0'}
            url = "https://api.coingecko.com/api/v3/search/trending"
        
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return f"Failed to fetch trending data: HTTP {resp.status_code}"
        
        data = resp.json()
        trending_coins = data.get('coins', [])[:limit]
        
        if not trending_coins:
            return "No trending tokens found"
        
        # Extract coin symbols for Binance price lookup
        coin_symbols = []
        coin_data = {}
        for coin in trending_coins:
            item = coin.get('item', {})
            symbol = item.get('symbol', '').upper()
            coin_symbols.append(symbol)
            coin_data[symbol] = {
                'name': item.get('name', 'Unknown'),
                'symbol': symbol,
                'market_cap_rank': item.get('market_cap_rank'),
                'thumb': item.get('thumb', ''),
                'coingecko_id': item.get('id', ''),
                # CoinGecko trending API includes price data
                'price_btc': item.get('price_btc', 0),
            }
        
        # Fetch real-time prices from Binance
        binance_base = os.getenv("BINANCE_API_BASE", "https://api.binance.com")
        try:
            ticker_url = f"{binance_base}/api/v3/ticker/24hr"
            ticker_resp = requests.get(ticker_url, timeout=5).json()
            
            # Build price map
            price_map = {}
            for t in ticker_resp:
                sym = t.get('symbol', '')
                if sym.endswith('USDT'):
                    base = sym.replace('USDT', '')
                    price_map[base] = {
                        'price': float(t.get('lastPrice', 0)),
                        'change_24h': float(t.get('priceChangePercent', 0))
                    }
        except:
            price_map = {}
        
        # Build report
        result = "🔥 CoinGecko 热门搜索榜\n"
        result += "━" * 35 + "\n\n"
        
        for i, symbol in enumerate(coin_symbols, 1):
            info = coin_data[symbol]
            
            # Get price from Binance if available
            if symbol in price_map:
                price = price_map[symbol]['price']
                change = price_map[symbol]['change_24h']
                
                # Smart price formatting
                if price < 0.0001:
                    price_str = f"${price:.8f}"
                elif price < 0.01:
                    price_str = f"${price:.6f}"
                elif price < 1:
                    price_str = f"${price:.4f}"
                else:
                    price_str = f"${price:,.2f}"
                
                # Change emoji
                change_emoji = "📈" if change >= 0 else "📉"
                change_str = f"{change_emoji} {change:+.2f}%"
            else:
                price_str = "N/A"
                change_str = ""
            
            # Market cap rank
            rank_str = f"#{info['market_cap_rank']}" if info['market_cap_rank'] else ""
            
            result += f"{i}. {info['name']} ({symbol}) {rank_str}\n"
            if price_str != "N/A":
                result += f"   💰 {price_str} | {change_str}\n"
            else:
                result += f"   ⚠️ 未在 Binance 上市\n"
            result += "\n"
        
        return result.strip()
        
    except Exception as e:
        return f"Failed to fetch trending tokens: {str(e)}"


def get_top_gainers_cex(limit: int = 10) -> str:
    """
    Get top gaining tokens by 24h price change from Binance (CEX).
    Best for mainstream tokens listed on major exchanges.
    
    Args:
        limit: Number of results (default 10)
    """
    try:
        binance_base = os.getenv("BINANCE_API_BASE", "https://api.binance.com")
        
        # 首先获取所有活跃交易对 (TRADING状态)
        exchange_info_url = f"{binance_base}/api/v3/exchangeInfo"
        exchange_info = requests.get(exchange_info_url, timeout=10).json()
        
        # 创建只包含TRADING状态的USDT交易对的集合
        active_usdt_symbols = set()
        for s in exchange_info.get('symbols', []):
            if s['status'] == 'TRADING' and s['symbol'].endswith('USDT'):
                active_usdt_symbols.add(s['symbol'])
        
        # 获取24小时行情
        url = f"{binance_base}/api/v3/ticker/24hr"
        resp = requests.get(url, timeout=5).json()
        
        # Filter USDT pairs, only keep TRADING status symbols
        usdt_pairs = [t for t in resp if t['symbol'] in active_usdt_symbols and not t['symbol'].startswith('USDT')]
        
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


def get_onchain_hot_gainers(number: int = 10) -> str:
    """
    Get top gaining on-chain tokens from DexScreener with quality filters.
    Shows tokens with significant price movement AND real trading activity.
    
    Uses multiple data sources to ensure enough qualified tokens:
    - Token Boosts (latest & top)
    - Token Profiles from major chains (Solana, ETH, BSC, Base, Arbitrum)
    
    Filters applied:
    - Minimum liquidity: $50,000
    - Minimum 24h volume: $100,000
    - Minimum market cap: $100,000
    - Minimum 24h gain: 10%
    
    Args:
        number: Number of results to return (1-20, default 10)
    """
    # 限制参数范围
    number = max(1, min(20, number))
    
    # 用于存储所有代币地址和合格代币
    all_token_addresses = set()  # 去重用
    qualified_tokens = []
    
    # 辅助函数：处理单个代币
    def process_token(address: str, chain_hint: str = None) -> dict:
        """获取代币数据并检查是否符合条件"""
        try:
            token_url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
            token_resp = requests.get(token_url, timeout=5)
            
            if token_resp.status_code != 200:
                return None
            
            data = token_resp.json()
            pairs = data.get('pairs', [])
            
            if not pairs:
                return None
            
            # 取流动性最高的交易对
            best_pair = max(pairs, key=lambda p: float(p.get('liquidity', {}).get('usd', 0) or 0))
            
            # 提取数据
            liquidity = float(best_pair.get('liquidity', {}).get('usd', 0) or 0)
            volume_24h = float(best_pair.get('volume', {}).get('h24', 0) or 0)
            market_cap = float(best_pair.get('marketCap', 0) or best_pair.get('fdv', 0) or 0)
            price_change_24h = float(best_pair.get('priceChange', {}).get('h24', 0) or 0)
            price_usd = float(best_pair.get('priceUsd', 0) or 0)
            
            # 应用筛选条件
            if liquidity < 50000:  # 最低流动性 $50k
                return None
            if volume_24h < 100000:  # 最低24h交易量 $100k
                return None
            if market_cap < 100000:  # 最低市值 $100k
                return None
            if price_change_24h < 10:  # 最低涨幅 10%
                return None
            
            # 提取社交媒体信息
            info = best_pair.get('info', {})
            socials = info.get('socials', [])
            twitter_url = None
            for social in socials:
                if social.get('type') == 'twitter':
                    twitter_url = social.get('url')
                    break
            
            websites = info.get('websites', [])
            website_url = websites[0].get('url') if websites else None
            
            return {
                'symbol': best_pair.get('baseToken', {}).get('symbol', 'Unknown'),
                'name': best_pair.get('baseToken', {}).get('name', 'Unknown')[:20],
                'chain': best_pair.get('chainId', 'unknown'),
                'dex': best_pair.get('dexId', 'unknown'),
                'price': price_usd,
                'change_24h': price_change_24h,
                'volume_24h': volume_24h,
                'liquidity': liquidity,
                'market_cap': market_cap,
                'twitter': twitter_url,
                'website': website_url,
                'pair_url': best_pair.get('url', ''),
                'address': address
            }
        except Exception:
            return None
    
    try:
        # ========== 数据源1: Token Boosts (Latest) ==========
        try:
            boosts_resp = requests.get("https://api.dexscreener.com/token-boosts/latest/v1", timeout=10)
            if boosts_resp.status_code == 200:
                for token in boosts_resp.json():
                    addr = token.get('tokenAddress', '')
                    if addr and addr not in all_token_addresses:
                        all_token_addresses.add(addr)
                        result = process_token(addr)
                        if result:
                            qualified_tokens.append(result)
                            if len(qualified_tokens) >= number:
                                break
        except Exception:
            pass
        
        # 早期退出：如果已经找够了
        if len(qualified_tokens) >= number:
            pass  # 跳过后续数据源
        else:
            # ========== 数据源2: Token Boosts (Top) ==========
            try:
                top_resp = requests.get("https://api.dexscreener.com/token-boosts/top/v1", timeout=10)
                if top_resp.status_code == 200:
                    for token in top_resp.json():
                        addr = token.get('tokenAddress', '')
                        if addr and addr not in all_token_addresses:
                            all_token_addresses.add(addr)
                            result = process_token(addr)
                            if result:
                                qualified_tokens.append(result)
                                if len(qualified_tokens) >= number:
                                    break
            except Exception:
                pass
        
        # 早期退出检查
        if len(qualified_tokens) >= number:
            pass
        else:
            # ========== 数据源3: Token Profiles (各主链) ==========
            chains = ['solana', 'ethereum', 'bsc', 'base', 'arbitrum']
            for chain in chains:
                if len(qualified_tokens) >= number:
                    break
                try:
                    profiles_resp = requests.get(
                        f"https://api.dexscreener.com/token-profiles/latest/v1?chainId={chain}",
                        timeout=10
                    )
                    if profiles_resp.status_code == 200:
                        for token in profiles_resp.json():
                            addr = token.get('tokenAddress', '')
                            if addr and addr not in all_token_addresses:
                                all_token_addresses.add(addr)
                                result = process_token(addr, chain)
                                if result:
                                    qualified_tokens.append(result)
                                    if len(qualified_tokens) >= number:
                                        break
                except Exception:
                    continue
        
        if not qualified_tokens:
            return "No tokens meeting quality criteria (Liq>$50k, Vol>$100k, MCap>$100k, Gain>10%)"
        
        # 按涨幅排序
        sorted_tokens = sorted(qualified_tokens, key=lambda x: x['change_24h'], reverse=True)
        
        # 格式化输出
        result = "🔥 链上热点异动榜 (24h)\n"
        result += "━" * 35 + "\n"
        result += "筛选条件: 流动性>$50k | 交易量>$100k | 市值>$100k | 涨幅>10%\n\n"
        
        # 辅助函数：格式化大数字
        def format_usd(value):
            if value >= 1e9:
                return f"${value/1e9:.1f}B"
            elif value >= 1e6:
                return f"${value/1e6:.1f}M"
            elif value >= 1e3:
                return f"${value/1e3:.0f}K"
            else:
                return f"${value:.0f}"
        
        for i, token in enumerate(sorted_tokens[:number], 1):
            # 智能价格格式化
            price = token['price']
            if price < 0.0001:
                price_str = f"${price:.8f}"
            elif price < 0.01:
                price_str = f"${price:.6f}"
            elif price < 1:
                price_str = f"${price:.4f}"
            else:
                price_str = f"${price:,.2f}"
            
            result += f"{i}. {token['symbol']} ({token['chain'].upper()})\n"
            result += f"   📈 +{token['change_24h']:.1f}% | {price_str}\n"
            result += f"   💰 市值: {format_usd(token['market_cap'])} | 📊 交易量: {format_usd(token['volume_24h'])} | 💧 流动性: {format_usd(token['liquidity'])}\n"
            
            # 社交媒体链接
            if token['twitter']:
                result += f"   🐦 {token['twitter']}\n"
            
            result += "\n"
        
        # 显示找到的总数
        if len(sorted_tokens) < number:
            result += f"\n⚠️ 仅找到 {len(sorted_tokens)} 个符合条件的代币（请求 {number} 个）"
        
        return result.strip()
        
    except Exception as e:
        return f"Failed to fetch on-chain hot gainers: {str(e)}"


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


def batch_funding_rate(symbols: str = "BTC,ETH,SOL") -> str:
    """
    批量获取多个币种的资金费率
    
    一次调用分析多个币种，避免重复调用单个工具。
    
    Args:
        symbols: 代币符号列表，逗号分隔 (如 "BTC,ETH,SOL")
    
    Returns:
        所有币种的资金费率汇总报告
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    
    report = "=" * 40 + "\n"
    report += "💰 批量资金费率分析\n"
    report += "=" * 40 + "\n\n"
    
    for symbol in symbol_list:
        try:
            clean_symbol = symbol + "USDT"
            url = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={clean_symbol}&limit=1"
            data = requests.get(url, timeout=5).json()
            
            if not data or isinstance(data, dict) and data.get('code'):
                report += f"❌ {symbol}: 无法获取（可能不支持合约交易）\n"
                continue
            
            funding_rate = float(data[0]['fundingRate']) * 100
            
            # 判断状态
            if funding_rate > 0.1:
                status = "🔴 极度多头拥挤"
                warning = "⚠️ 多头挤爆风险"
            elif funding_rate > 0.05:
                status = "🟡 多头主导"
                warning = ""
            elif funding_rate > 0:
                status = "🟢 轻微多头"
                warning = ""
            elif funding_rate > -0.05:
                status = "🟢 轻微空头"
                warning = ""
            elif funding_rate > -0.1:
                status = "🟡 空头主导"
                warning = ""
            else:
                status = "🔴 极度空头拥挤"
                warning = "⚠️ 空头挤爆风险"
            
            report += f"【{symbol}】 费率: {funding_rate:+.4f}% | {status}"
            if warning:
                report += f" {warning}"
            report += "\n"
            
        except Exception as e:
            report += f"❌ {symbol}: {str(e)}\n"
    
    return report

