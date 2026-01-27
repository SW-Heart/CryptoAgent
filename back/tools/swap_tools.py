"""
Swap Tools - DEX 交易工具集

提供 Uniswap 等 DEX 交易报价和交易执行工具。
使用 GeckoTerminal API 获取实时价格数据（免费、无需 API Key）。
"""

import requests
from typing import Optional
from datetime import datetime

# A2UI 协议
from a2ui_protocol import create_swap_card_surface, wrap_a2ui_in_markdown


# ==========================================
# 代币配置
# ==========================================

# Ethereum Mainnet 代币地址映射
TOKEN_ADDRESSES = {
    # 稳定币
    "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "DAI": "0x6B175474E89094C44Da98b954EescdececfE1f9",
    
    # 主流币 (Wrapped)
    "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
    
    # 符号别名
    "ETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", 
    "BTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", 
    
    # 热门 DeFi 代币
    "UNI": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
    "LINK": "0x514910771AF9Ca656af840dff83E8264EcF986CA",
    "AAVE": "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9",
}

# Uniswap V3 合约地址 (Ethereum Mainnet)
UNISWAP_CONTRACTS = {
    "universal_router": "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD",
    "permit2": "0x000000000022D473030F116dDEE9F6B43aC78BA3",
    "quoter_v2": "0x61fFE014bA17989E743c5F6cB21bF9697530B21e",
}

# GeckoTerminal API
GECKOTERMINAL_API = "https://api.geckoterminal.com/api/v2"


# ==========================================
# GeckoTerminal API 工具
# ==========================================

def get_token_price_geckoterminal(token_address: str, network: str = "eth") -> Optional[dict]:
    """
    从 GeckoTerminal 获取代币价格。
    
    Args:
        token_address: 代币合约地址
        network: 网络标识 (eth, polygon, arbitrum 等)
    
    Returns:
        {
            "price_usd": float,
            "price_change_24h": float,
            "volume_24h": float,
            "fdv": float,
            "name": str,
            "symbol": str
        }
    """
    try:
        url = f"{GECKOTERMINAL_API}/networks/{network}/tokens/{token_address}"
        headers = {"Accept": "application/json"}
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            print(f"[GeckoTerminal] Error: {resp.status_code} - {resp.text}")
            return None
        
        data = resp.json()
        attributes = data.get("data", {}).get("attributes", {})
        
        return {
            "price_usd": float(attributes.get("price_usd", 0) or 0),
            "price_change_24h": float(attributes.get("price_change_percentage", {}).get("h24", 0) or 0),
            "volume_24h": float(attributes.get("volume_usd", {}).get("h24", 0) or 0),
            "fdv": float(attributes.get("fdv_usd", 0) or 0),
            "name": attributes.get("name", ""),
            "symbol": attributes.get("symbol", ""),
        }
    except Exception as e:
        print(f"[GeckoTerminal] Exception: {e}")
        return None


def get_pool_info_geckoterminal(pool_address: str, network: str = "eth") -> Optional[dict]:
    """
    从 GeckoTerminal 获取流动性池信息。
    
    Args:
        pool_address: 池合约地址
        network: 网络标识
    
    Returns:
        池信息字典
    """
    try:
        url = f"{GECKOTERMINAL_API}/networks/{network}/pools/{pool_address}"
        headers = {"Accept": "application/json"}
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        return data.get("data", {}).get("attributes", {})
    
    except Exception as e:
        print(f"[GeckoTerminal Pool] Exception: {e}")
        return None


def search_pools_geckoterminal(query: str, network: str = "eth") -> list:
    """
    在 GeckoTerminal 上搜索流动性池。
    
    Args:
        query: 搜索关键词（代币名称或符号）
        network: 网络标识
    
    Returns:
        池列表
    """
    try:
        url = f"{GECKOTERMINAL_API}/search/pools"
        params = {"query": query, "network": network}
        headers = {"Accept": "application/json"}
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        
        if resp.status_code != 200:
            return []
        
        data = resp.json()
        return data.get("data", [])
    
    except Exception as e:
        print(f"[GeckoTerminal Search] Exception: {e}")
        return []


# ==========================================
# Agent Tools
# ==========================================

def get_swap_quote(
    from_token: str,
    to_token: str,
    amount: float,
    network: str = "ethereum"
) -> dict:
    """
    获取 DEX 交易报价。
    
    使用 GeckoTerminal API 获取代币价格，计算交易报价。
    注意：这是一个简化的报价，实际交易需要考虑滑点和路由。
    
    Args:
        from_token: 源代币符号 (e.g., "USDT", "USDC", "ETH")
        to_token: 目标代币符号 (e.g., "WBTC", "ETH", "UNI")
        amount: 源代币数量
        network: 网络 ("ethereum" 只在第一期支持)
    
    Returns:
        {
            "success": bool,
            "from_token": str,
            "to_token": str,
            "from_amount": float,
            "to_amount": float,
            "exchange_rate": float,
            "price_usd": float,
            "price_impact": float,
            "gas_estimate": str,
            "route": str,
            "updated_at": str
        }
    """
    try:
        # 标准化代币符号
        from_symbol = from_token.upper()
        to_symbol = to_token.upper()
        
        # 获取代币地址
        from_address = TOKEN_ADDRESSES.get(from_symbol)
        to_address = TOKEN_ADDRESSES.get(to_symbol)
        
        if not from_address:
            return {"success": False, "error": f"Unknown token: {from_symbol}"}
        if not to_address:
            return {"success": False, "error": f"Unknown token: {to_symbol}"}
        
        # 网络标识转换
        network_map = {"ethereum": "eth", "polygon": "polygon_pos"}
        geckoterminal_network = network_map.get(network, "eth")
        
        # 获取代币价格
        from_token_data = get_token_price_geckoterminal(from_address, geckoterminal_network)
        to_token_data = get_token_price_geckoterminal(to_address, geckoterminal_network)
        
        # 备用静态价格（当 API 超时时使用）
        FALLBACK_PRICES = {
            "USDT": 1.0,
            "USDC": 1.0,
            "DAI": 1.0,
            "WETH": 3200.0,
            "ETH": 3200.0,
            "WBTC": 100000.0,
            "BTC": 100000.0,
            "UNI": 5.0,
            "LINK": 15.0,
            "AAVE": 200.0,
        }
        
        # 使用备用价格源（稳定币假设为 1 USD）
        if from_symbol in ["USDT", "USDC", "DAI"]:
            from_price = 1.0
        elif from_token_data and from_token_data["price_usd"] > 0:
            from_price = from_token_data["price_usd"]
        elif from_symbol in FALLBACK_PRICES:
            from_price = FALLBACK_PRICES[from_symbol]
            print(f"[SwapQuote] Using fallback price for {from_symbol}: ${from_price}")
        else:
            return {"success": False, "error": f"Cannot get price for {from_symbol}"}
        
        if to_symbol in ["USDT", "USDC", "DAI"]:
            to_price = 1.0
        elif to_token_data and to_token_data["price_usd"] > 0:
            to_price = to_token_data["price_usd"]
        elif to_symbol in FALLBACK_PRICES:
            to_price = FALLBACK_PRICES[to_symbol]
            print(f"[SwapQuote] Using fallback price for {to_symbol}: ${to_price}")
        else:
            return {"success": False, "error": f"Cannot get price for {to_symbol}"}
        
        # 计算交易数量
        from_value_usd = amount * from_price
        to_amount = from_value_usd / to_price
        exchange_rate = from_price / to_price
        
        # 估算价格影响（简化版：基于交易规模）
        # 实际应该查询 Uniswap quoter 获取精确值
        if from_value_usd < 1000:
            price_impact = 0.05
        elif from_value_usd < 10000:
            price_impact = 0.15
        elif from_value_usd < 100000:
            price_impact = 0.5
        else:
            price_impact = 1.0
        
        # 考虑滑点后的实际获得数量
        to_amount_after_slippage = to_amount * (1 - price_impact / 100)
        
        # 估算 Gas 费用（简化版）
        gas_estimate = "$2.50 - $5.00"
        
        return {
            "success": True,
            "from_token": from_symbol,
            "to_token": to_symbol,
            "from_amount": amount,
            "to_amount": to_amount_after_slippage,
            "exchange_rate": exchange_rate,
            "price_usd": to_price,
            "from_price_usd": from_price,
            "price_impact": price_impact,
            "gas_estimate": gas_estimate,
            "route": f"{from_symbol} → {to_symbol} (Uniswap V3)",
            "network": network,
            "router_address": UNISWAP_CONTRACTS["universal_router"],
            "updated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_swap_a2ui(
    from_token: str,
    to_token: str,
    amount: float,
    network: str = "ethereum"
) -> str:
    """
    生成 Swap 交易的 A2UI 卡片。
    
    此函数是给 Agent 调用的主入口，会：
    1. 获取实时报价
    2. 生成 A2UI JSON
    3. 返回 Markdown 包装的结果
    
    Args:
        from_token: 源代币符号 (e.g., "USDT")
        to_token: 目标代币符号 (e.g., "WBTC", "BTC", "ETH")
        amount: 源代币数量
        network: 网络 ("ethereum")
    
    Returns:
        包含 A2UI JSON 的 Markdown 字符串，或错误信息
    
    Example:
        用户说 "购买 1000U 的 BTC"
        -> generate_swap_a2ui("USDT", "WBTC", 1000.0)
        -> 返回 A2UI 交易卡片
    """
    # 获取报价
    quote = get_swap_quote(from_token, to_token, amount, network)
    
    if not quote.get("success"):
        error_msg = quote.get("error", "Unknown error")
        return f"❌ 获取报价失败: {error_msg}"
    
    # 生成 A2UI Surface
    surface = create_swap_card_surface(
        from_token=quote["from_token"],
        to_token=quote["to_token"],
        from_amount=quote["from_amount"],
        to_amount=quote["to_amount"],
        exchange_rate=quote["exchange_rate"],
        price_usd=quote["price_usd"],
        gas_estimate=quote["gas_estimate"],
        price_impact=quote["price_impact"],
        transaction_data={
            "routerAddress": quote["router_address"],
            "network": quote["network"],
            "route": quote["route"],
            # 实际 calldata 需要通过 Uniswap SDK 生成
            # 这里先留占位符，由前端钱包服务生成
            "calldata": "PENDING_GENERATION",
        }
    )
    
    # 包装为 Markdown
    a2ui_block = wrap_a2ui_in_markdown(surface)
    
    # 添加交易摘要
    summary = f"""
## 🔄 交易预览

| 项目 | 数值 |
|------|------|
| 支付 | **{quote['from_amount']:,.2f} {quote['from_token']}** |
| 获得 | **≈ {quote['to_amount']:.6f} {quote['to_token']}** |
| 汇率 | 1 {quote['to_token']} = ${quote['price_usd']:,.2f} |
| 路由 | {quote['route']} |
| 价格影响 | {quote['price_impact']:.2f}% |
| Gas 费用 | {quote['gas_estimate']} |

---

{a2ui_block}

> 点击"确认交易"将唤起 MetaMask 钱包进行签名。
"""
    
    return summary


# ==========================================
# 测试
# ==========================================

if __name__ == "__main__":
    # 测试获取报价
    print("=== Test get_swap_quote ===")
    quote = get_swap_quote("USDT", "WBTC", 1000.0)
    print(quote)
    
    # 测试生成 A2UI
    print("\n=== Test generate_swap_a2ui ===")
    result = generate_swap_a2ui("USDT", "BTC", 1000.0)
    print(result)
