"""
链上数据工具：Etherscan + DefiLlama + Gas/Wallet
"""
import requests
import os

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
