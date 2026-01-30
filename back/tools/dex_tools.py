"""
DEX 流动性池工具 - 使用 GeckoTerminal API (免费，无需 API Key)
支持 Uniswap、SushiSwap、PancakeSwap、Curve 等主流 DEX
查询代币的流动性池信息
"""
import requests
from typing import Optional

# GeckoTerminal API (免费，无需 API Key)
GECKOTERMINAL_BASE_URL = "https://api.geckoterminal.com/api/v2"

# 支持的网络映射
NETWORK_MAP = {
    "ethereum": "eth",
    "eth": "eth",
    "arbitrum": "arbitrum",
    "arb": "arbitrum",
    "polygon": "polygon_pos",
    "matic": "polygon_pos",
    "optimism": "optimism",
    "op": "optimism",
    "base": "base",
    "bsc": "bsc",
    "bnb": "bsc",
    "avalanche": "avax",
    "avax": "avax",
    "solana": "solana",
    "sol": "solana",
}

# DEX 跳转链接模板
DEX_URLS = {
    "uniswap_v3": "https://app.uniswap.org/explore/pools/{chain}/{pool_address}",
    "uniswap_v2": "https://app.uniswap.org/explore/pools/{chain}/{pool_address}",
    "sushiswap": "https://www.sushi.com/pool/{chain}:{pool_address}",
    "pancakeswap_v3": "https://pancakeswap.finance/info/v3/{chain}/pairs/{pool_address}",
    "default": "https://www.geckoterminal.com/{network}/pools/{pool_address}",
}


def get_dex_pools(token: str, chain: str = "ethereum", limit: int = 5) -> str:
    """
    Get top DEX liquidity pools for a token. Results are sorted by liquidity (highest first).
    Covers Uniswap, SushiSwap, PancakeSwap, Curve, and other major DEXes.
    
    IMPORTANT: The token should be a SYMBOL like "PEPE" or a contract address "0x..." - NOT a description.
    
    Examples:
        ✅ token="PEPE"     → finds PEPE pools
        ✅ token="ENA"      → finds ENA pools
        ✅ token="0x6982508145454ce325ddbe47a25d4ec3d2311933" → PEPE by address
        ❌ token="PEPE token" → WRONG
    
    Args:
        token: Token symbol (e.g., "PEPE", "ENA") or contract address (0x...). Just the symbol, not a sentence.
        chain: Blockchain (ethereum, arbitrum, polygon, bsc, etc.). Default: ethereum
        limit: Number of pools to show (default 5, max 10)
    """
    chain_lower = chain.lower().strip()
    network = NETWORK_MAP.get(chain_lower)
    if not network:
        return f"❌ Chain '{chain}' not supported. Available: {', '.join(set(NETWORK_MAP.values()))}"
    
    limit = min(limit, 10)
    
    # 判断是地址还是符号
    is_address = token.startswith("0x") and len(token) == 42
    
    try:
        headers = {"Accept": "application/json"}
        
        if is_address:
            # 直接用地址查询代币的池子
            token_address = token.lower()
            url = f"{GECKOTERMINAL_BASE_URL}/networks/{network}/tokens/{token_address}/pools"
            params = {"page": 1}
        else:
            # 用符号搜索代币池
            search_url = f"{GECKOTERMINAL_BASE_URL}/search/pools"
            params = {"query": token, "network": network, "page": 1}
            
            resp = requests.get(search_url, headers=headers, params=params, timeout=15)
            search_data = resp.json()
            
            pools_from_search = search_data.get("data", [])
            
            if pools_from_search:
                # 过滤：池名必须包含目标代币
                matching_pools = []
                token_upper = token.upper()
                for pool in pools_from_search:
                    attrs = pool.get("attributes", {})
                    name = attrs.get("name", "").upper()
                    # 精确匹配：代币符号在池名中（如 "ENA / WETH"）
                    name_parts = name.replace("/", " ").replace("-", " ").split()
                    if token_upper in name_parts:
                        matching_pools.append(pool)
                
                if matching_pools:
                    # 按流动性排序
                    matching_pools.sort(
                        key=lambda p: float(p.get("attributes", {}).get("reserve_in_usd", 0) or 0),
                        reverse=True
                    )
                    return _format_pools_result(matching_pools[:limit], token, chain, network)
            
            # 如果符号搜索没有结果，返回提示
            return f"❌ Token '{token}' not found on DEX ({chain}). Try using contract address (0x...)."
        
        # 用地址直接查询
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        data = resp.json()
        
        pools = data.get("data", [])
        
        if not pools:
            return f"❌ No DEX pools found for token {token[:10]}... on {chain}"
        
        return _format_pools_result(pools[:limit], token, chain, network)
        
    except Exception as e:
        return f"Failed to query DEX pools: {str(e)}"


def _format_pools_result(pools: list, token: str, chain: str, network: str) -> str:
    """格式化池子结果"""
    if not pools:
        return f"❌ No pools found for {token}"
    
    result = f"🦄 {token.upper()} - Top DEX Pools on {chain.capitalize()}\n"
    result += "=" * 50 + "\n\n"
    
    for i, pool in enumerate(pools, 1):
        attrs = pool.get("attributes", {})
        relationships = pool.get("relationships", {})
        
        # 从 pool id 解析地址
        pool_id = pool.get("id", "")
        # pool_id 格式通常是 "network_address"
        if "_" in pool_id:
            parts = pool_id.split("_", 1)
            pool_network = parts[0]
            pool_address = parts[1] if len(parts) > 1 else ""
        else:
            pool_network = network
            pool_address = pool_id
        
        name = attrs.get("name", "Unknown")
        
        # 从 relationships 获取 DEX 名称
        dex_data = relationships.get("dex", {}).get("data", {})
        dex_id = dex_data.get("id", "") if dex_data else ""
        
        # 如果 relationships 没有，尝试从 attributes 获取
        if not dex_id:
            dex_id = attrs.get("dex_id", "")
        
        # 美化 DEX 名称
        if dex_id:
            dex_name = dex_id.replace("_", " ").replace("-", " ").title()
        else:
            dex_name = "Unknown"
        
        # 流动性和交易量
        reserve_usd = float(attrs.get("reserve_in_usd", 0) or 0)
        
        # volume_usd 可能是 dict 或直接的值
        volume_data = attrs.get("volume_usd", {})
        if isinstance(volume_data, dict):
            volume_24h = float(volume_data.get("h24", 0) or 0)
        else:
            volume_24h = float(volume_data or 0)
        
        # 价格变化
        price_change_data = attrs.get("price_change_percentage", {})
        if isinstance(price_change_data, dict):
            price_change_24h = float(price_change_data.get("h24", 0) or 0)
        else:
            price_change_24h = float(price_change_data or 0)
        
        # 基础代币价格
        base_token_price = attrs.get("base_token_price_usd")
        
        # 费用
        pool_fee = attrs.get("pool_fee")
        if pool_fee:
            try:
                fee_pct = float(pool_fee) * 100
                fee_str = f"{fee_pct:.2f}%"
            except:
                fee_str = str(pool_fee)
        else:
            fee_str = "?"
        
        # 格式化数值
        def fmt_usd(val):
            if val >= 1e9: return f"${val/1e9:.2f}B"
            if val >= 1e6: return f"${val/1e6:.2f}M"
            if val >= 1e3: return f"${val/1e3:.1f}K"
            return f"${val:.0f}"
        
        # 构建链接 - 使用 GeckoTerminal 因为更可靠
        gecko_url = f"https://www.geckoterminal.com/{pool_network}/pools/{pool_address}"
        
        # 价格变化 emoji
        change_emoji = "📈" if price_change_24h >= 0 else "📉"
        
        result += f"{i}. {name} ({fee_str} fee)\n"
        result += f"   🏦 DEX: {dex_name}\n"
        result += f"   💰 Liquidity: {fmt_usd(reserve_usd)} | Vol 24h: {fmt_usd(volume_24h)}\n"
        result += f"   {change_emoji} 24h: {price_change_24h:+.2f}%"
        if base_token_price:
            try:
                result += f" | Price: ${float(base_token_price):.6f}"
            except:
                pass
        result += "\n"
        result += f"   🔗 {gecko_url}\n"
        
        if i < len(pools):
            result += "   " + "-" * 40 + "\n"
    
    return result


def get_dex_pool_detail(pool_address: str, chain: str = "ethereum") -> str:
    """
    Get detailed information for a specific DEX pool.
    
    Args:
        pool_address: Pool contract address (0x...)
        chain: Blockchain (ethereum, arbitrum, polygon, optimism, base, bsc, solana). Default: ethereum
    """
    chain_lower = chain.lower().strip()
    network = NETWORK_MAP.get(chain_lower)
    if not network:
        return f"❌ Chain '{chain}' not supported. Available: {', '.join(set(NETWORK_MAP.values()))}"
    
    if not pool_address.startswith("0x"):
        return f"❌ Invalid pool address: {pool_address}"
    
    try:
        headers = {"Accept": "application/json"}
        url = f"{GECKOTERMINAL_BASE_URL}/networks/{network}/pools/{pool_address.lower()}"
        
        resp = requests.get(url, headers=headers, timeout=15)
        
        if resp.status_code == 404:
            return f"❌ Pool {pool_address[:10]}... not found on {chain}"
        
        data = resp.json()
        pool = data.get("data", {})
        attrs = pool.get("attributes", {})
        
        if not attrs:
            return f"❌ Pool data not available for {pool_address[:10]}..."
        
        name = attrs.get("name", "Unknown")
        dex = attrs.get("dex_id", "unknown")
        
        reserve_usd = float(attrs.get("reserve_in_usd", 0) or 0)
        volume_24h = float(attrs.get("volume_usd", {}).get("h24", 0) or 0)
        volume_6h = float(attrs.get("volume_usd", {}).get("h6", 0) or 0)
        volume_1h = float(attrs.get("volume_usd", {}).get("h1", 0) or 0)
        
        txs_24h = int(attrs.get("transactions", {}).get("h24", {}).get("buys", 0) or 0) + \
                  int(attrs.get("transactions", {}).get("h24", {}).get("sells", 0) or 0)
        
        base_token_price = attrs.get("base_token_price_usd", "N/A")
        quote_token_price = attrs.get("quote_token_price_usd", "N/A")
        
        price_change_24h = float(attrs.get("price_change_percentage", {}).get("h24", 0) or 0)
        price_change_6h = float(attrs.get("price_change_percentage", {}).get("h6", 0) or 0)
        price_change_1h = float(attrs.get("price_change_percentage", {}).get("h1", 0) or 0)
        
        pool_fee = attrs.get("pool_fee", None)
        fee_str = f"{float(pool_fee)*100:.2f}%" if pool_fee else "Unknown"
        
        def fmt_usd(val):
            if val >= 1e9: return f"${val/1e9:.2f}B"
            if val >= 1e6: return f"${val/1e6:.2f}M"
            if val >= 1e3: return f"${val/1e3:.1f}K"
            return f"${val:.2f}"
        
        result = f"🦄 DEX Pool Detail\n"
        result += "=" * 45 + "\n\n"
        
        result += f"📍 Pool: {name}\n"
        result += f"🏦 DEX: {dex.replace('_', ' ').title()} | Fee: {fee_str}\n"
        result += f"🔗 Address: {pool_address[:10]}...{pool_address[-8:]}\n\n"
        
        result += f"💰 Liquidity: {fmt_usd(reserve_usd)}\n\n"
        
        result += f"📊 Volume:\n"
        result += f"   1h: {fmt_usd(volume_1h)} | 6h: {fmt_usd(volume_6h)} | 24h: {fmt_usd(volume_24h)}\n\n"
        
        result += f"📈 Price Change:\n"
        result += f"   1h: {price_change_1h:+.2f}% | 6h: {price_change_6h:+.2f}% | 24h: {price_change_24h:+.2f}%\n\n"
        
        result += f"🔄 Transactions 24h: {txs_24h:,}\n\n"
        
        if base_token_price and base_token_price != "N/A":
            result += f"💱 Base Token Price: ${float(base_token_price):.6f}\n"
        
        # GeckoTerminal 链接
        gecko_url = f"https://www.geckoterminal.com/{network}/pools/{pool_address.lower()}"
        result += f"\n🔗 View on GeckoTerminal: {gecko_url}"
        
        return result
        
    except Exception as e:
        return f"Failed to query pool detail: {str(e)}"


def search_dex_pools(query: str, chain: str = "ethereum", limit: int = 5) -> str:
    """
    Search DEX pools by token symbol or name. Results are sorted by liquidity (highest first).
    
    IMPORTANT: The query should be a token SYMBOL like "PEPE", "ENA", "UNI" - NOT a description.
    
    Examples:
        ✅ query="PEPE"     → finds PEPE/WETH, PEPE/USDC pools
        ✅ query="ENA"      → finds ENA/WETH, ENA/USDC pools  
        ❌ query="PEPE token contract address" → WRONG, this is not a symbol
        ❌ query="find pools for PEPE" → WRONG, just use "PEPE"
    
    Args:
        query: Token symbol (e.g., "PEPE", "ENA", "LINK"). Just the symbol, not a sentence.
        chain: Blockchain (ethereum, arbitrum, polygon, bsc, etc.). Default: ethereum
        limit: Number of results (default 5, max 10)
    """
    chain_lower = chain.lower().strip()
    network = NETWORK_MAP.get(chain_lower)
    if not network:
        return f"❌ Chain '{chain}' not supported."
    
    # 清理 query：如果用户传入了描述性语句，尝试提取代币符号
    query_clean = query.strip().upper()
    # 如果是长句子，尝试提取可能的代币符号（大写短词）
    if len(query_clean.split()) > 2:
        # 尝试提取可能的代币符号（2-10字符的大写词）
        words = query.replace(",", " ").replace(".", " ").split()
        potential_symbols = [w for w in words if 2 <= len(w) <= 10 and w.isalpha()]
        if potential_symbols:
            query_clean = potential_symbols[0].upper()
        else:
            return f"❌ Please provide a token symbol like 'PEPE' or 'ENA', not a sentence."
    
    limit = min(limit, 10)
    
    try:
        headers = {"Accept": "application/json"}
        url = f"{GECKOTERMINAL_BASE_URL}/search/pools"
        params = {"query": query_clean, "network": network, "page": 1}
        
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        data = resp.json()
        
        pools = data.get("data", [])
        
        if not pools:
            # 尝试全网搜索
            params_global = {"query": query_clean, "page": 1}
            resp_global = requests.get(url, headers=headers, params=params_global, timeout=15)
            data_global = resp_global.json()
            pools = data_global.get("data", [])
            
            if not pools:
                return f"❌ No pools found for '{query_clean}'. Check the token symbol."
        
        # 按流动性排序（从高到低）
        pools.sort(key=lambda p: float(p.get("attributes", {}).get("reserve_in_usd", 0) or 0), reverse=True)
        
        result = f"🔍 Search Results for '{query_clean}'\n"
        result += "=" * 45 + "\n\n"
        
        for i, pool in enumerate(pools[:limit], 1):
            attrs = pool.get("attributes", {})
            relationships = pool.get("relationships", {})
            pool_id = pool.get("id", "")
            
            # 解析 network 和 address
            if "_" in pool_id:
                parts = pool_id.split("_", 1)
                pool_network = parts[0]
                pool_address = parts[1] if len(parts) > 1 else pool_id
            else:
                pool_network = network
                pool_address = pool_id
            
            name = attrs.get("name", "Unknown")
            
            # 从 relationships 获取 DEX 名称
            dex_data = relationships.get("dex", {}).get("data", {})
            dex_id = dex_data.get("id", "") if dex_data else ""
            if not dex_id:
                dex_id = attrs.get("dex_id", "")
            dex_name = dex_id.replace("_", " ").replace("-", " ").title() if dex_id else "Unknown"
            
            reserve_usd = float(attrs.get("reserve_in_usd", 0) or 0)
            
            def fmt_usd(val):
                if val >= 1e9: return f"${val/1e9:.2f}B"
                if val >= 1e6: return f"${val/1e6:.2f}M"
                if val >= 1e3: return f"${val/1e3:.1f}K"
                return f"${val:.0f}"
            
            gecko_url = f"https://www.geckoterminal.com/{pool_network}/pools/{pool_address}"
            
            result += f"{i}. {name}\n"
            result += f"   🏦 {dex_name} on {pool_network}\n"
            result += f"   💰 Liquidity: {fmt_usd(reserve_usd)}\n"
            result += f"   🔗 {gecko_url}\n"
            
            if i < min(len(pools), limit):
                result += "   " + "-" * 35 + "\n"
        
        return result
        
    except Exception as e:
        return f"Failed to search pools: {str(e)}"
