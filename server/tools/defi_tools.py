"""
DeFi 数据工具 - DefiLlama API
"""
import requests

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
            
            if tvl >= 1e9:
                tvl_str = f"${tvl/1e9:.2f}B"
            elif tvl >= 1e6:
                tvl_str = f"${tvl/1e6:.1f}M"
            else:
                tvl_str = f"${tvl/1e3:.0f}K"
            
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
        
        current_chain_tvls = data.get('currentChainTvls', {})
        
        tvl = sum(v for k, v in current_chain_tvls.items() 
                  if not k.endswith('-borrowed') and not k.endswith('-staking') and k != 'borrowed'
                  and isinstance(v, (int, float)))
        
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
        
        if current_chain_tvls:
            result += "📍 TVL by Chain:\n"
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
        
        chains = sorted(resp, key=lambda x: x.get('tvl', 0) or 0, reverse=True)
        
        result = "⛓️ Blockchain TVL Ranking\n"
        result += "=" * 35 + "\n\n"
        
        total_tvl = sum(c.get('tvl', 0) or 0 for c in chains)
        result += f"🌍 Total DeFi TVL: ${total_tvl/1e9:.2f}B\n\n"
        
        for i, c in enumerate(chains[:15], 1):
            name = c.get('name', 'Unknown')
            tvl = c.get('tvl', 0) or 0
            
            dominance = (tvl / total_tvl * 100) if total_tvl > 0 else 0
            
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
        
        filtered = [
            p for p in pools 
            if (p.get('tvlUsd', 0) or 0) > 1_000_000 
            and 0 < (p.get('apy', 0) or 0) < 1000
            and p.get('stablecoin', False) == False
        ]
        
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
