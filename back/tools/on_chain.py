"""
链上数据工具 - 多链支持
EVM 链: Ethereum, Arbitrum, Optimism, Base, Polygon, BSC, Avalanche, Fantom (Etherscan API v2)
非 EVM 链: Solana (Solana RPC), Sui (Sui RPC)
"""
import os
import requests
from datetime import datetime

ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
ETHERSCAN_BASE_URL = "https://api.etherscan.io/v2/api"

# 支持的链配置 (Etherscan v2 API 的 chainid)
SUPPORTED_CHAINS = {
    "ethereum": {"chainid": "1", "symbol": "ETH", "name": "Ethereum"},
    "eth": {"chainid": "1", "symbol": "ETH", "name": "Ethereum"},
    "arbitrum": {"chainid": "42161", "symbol": "ETH", "name": "Arbitrum One"},
    "arb": {"chainid": "42161", "symbol": "ETH", "name": "Arbitrum One"},
    "optimism": {"chainid": "10", "symbol": "ETH", "name": "Optimism"},
    "op": {"chainid": "10", "symbol": "ETH", "name": "Optimism"},
    "base": {"chainid": "8453", "symbol": "ETH", "name": "Base"},
    "polygon": {"chainid": "137", "symbol": "MATIC", "name": "Polygon"},
    "matic": {"chainid": "137", "symbol": "MATIC", "name": "Polygon"},
    "bsc": {"chainid": "56", "symbol": "BNB", "name": "BNB Chain"},
    "bnb": {"chainid": "56", "symbol": "BNB", "name": "BNB Chain"},
    "avalanche": {"chainid": "43114", "symbol": "AVAX", "name": "Avalanche C-Chain"},
    "avax": {"chainid": "43114", "symbol": "AVAX", "name": "Avalanche C-Chain"},
    "fantom": {"chainid": "250", "symbol": "FTM", "name": "Fantom"},
    "ftm": {"chainid": "250", "symbol": "FTM", "name": "Fantom"},
}

def _get_chain_config(chain: str = "ethereum"):
    """获取链配置，默认 Ethereum"""
    chain_lower = chain.lower().strip()
    if chain_lower in SUPPORTED_CHAINS:
        return SUPPORTED_CHAINS[chain_lower]
    return SUPPORTED_CHAINS["ethereum"]

def _get_supported_chains_str():
    """返回支持的链列表字符串"""
    unique_chains = []
    seen = set()
    for key, val in SUPPORTED_CHAINS.items():
        if val["chainid"] not in seen:
            seen.add(val["chainid"])
            unique_chains.append(val["name"])
    return ", ".join(unique_chains)


def get_gas_price(chain: str = "ethereum") -> str:
    """
    Get real-time gas prices (Safe/Standard/Fast) for EVM chains.
    Shows current gas costs for different transaction speeds.
    
    Args:
        chain: Chain name (ethereum, arbitrum, optimism, base, polygon, bsc, avalanche, fantom)
              Default: ethereum
    """
    if not ETHERSCAN_API_KEY:
        return "❌ 配置错误: 未设置 ETHERSCAN_API_KEY，请在 .env 中添加"
    
    try:
        data = get_raw_gas_data(chain)
        if "error" in data:
             return data["error"]
        
        safe_gas = data['safe']
        standard_gas = data['standard']
        fast_gas = data['fast']
        base_fee = data['base']
        chain_name = data['chain_name']
        symbol = data['symbol']
        
        result = f"⛽ {chain_name} Gas Prices\n"
        result += "=" * 30 + "\n\n"
        
        def fmt_gas(g):
            if g < 0.01:
                return "<0.01"
            if g < 1:
                return f"{g:.3f}" 
            return f"{int(g)}"
        
        result += f"🐢 Safe (Low): {fmt_gas(safe_gas)} Gwei\n"
        result += f"🚗 Standard: {fmt_gas(standard_gas)} Gwei\n"
        result += f"🚀 Fast: {fmt_gas(fast_gas)} Gwei\n"
        if base_fee > 0:
            result += f"📊 Base Fee: {base_fee:.3f} Gwei\n"
        result += "\n"
        
        # 估算转账成本
        native_price = 3000
        if symbol == "ETH":
            try:
                from tools.market_tools import get_binance_data
                md = get_binance_data("ETH")
                if md: native_price = float(md['price'])
            except: pass
        else:
            native_price = 500 # Fallback for others
            
        standard_cost = (standard_gas * 21000) / 1e9
        standard_cost_usd = standard_cost * native_price
        
        result += f"💵 Estimated Transfer Cost: ~ ${standard_cost_usd:.2f} (21k gas)\n\n"
        
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
        chain_config = _get_chain_config(chain)
        return f"Failed to fetch gas price for {chain_config['name']}: {str(e)}"


def get_raw_gas_data(chain: str = "ethereum") -> dict:
    """内部使用的获取原始 Gas 数据的函数"""
    chain_config = _get_chain_config(chain)
    chainid = chain_config["chainid"]
    chain_name = chain_config["name"]
    symbol = chain_config["symbol"]
    
    url = f"{ETHERSCAN_BASE_URL}?chainid={chainid}&module=gastracker&action=gasoracle&apikey={ETHERSCAN_API_KEY}"
    resp = requests.get(url, timeout=10).json()
    
    if resp.get('status') != '1':
        return {"error": f"API error for {chain_name}: {resp.get('message', 'Unknown error')}. Gas tracker may not be available for this chain."}
    
    data = resp['result']
    return {
        "safe": float(data.get('SafeGasPrice', 0)),
        "standard": float(data.get('ProposeGasPrice', 0)),
        "fast": float(data.get('FastGasPrice', 0)),
        "base": float(data.get('suggestBaseFee', 0)),
        "chain_name": chain_name,
        "symbol": symbol
    }


def get_bitcoin_fee() -> str:
    """
    Get real-time Bitcoin transaction fee rates from Mempool.space.
    Shows recommended fees for different confirmation speeds.
    No API key required.
    """
    try:
        url = "https://mempool.space/api/v1/fees/recommended"
        resp = requests.get(url, timeout=10).json()
        
        fastest = resp.get("fastestFee", 0)
        half_hour = resp.get("halfHourFee", 0)
        hour = resp.get("hourFee", 0)
        economy = resp.get("economyFee", 0)
        minimum = resp.get("minimumFee", 0)
        
        result = "₿ Bitcoin Transaction Fees\n"
        result += "=" * 35 + "\n\n"
        
        result += f"🚀 Fastest (Next Block): {fastest} sat/vB\n"
        result += f"⚡ Fast (~30 min): {half_hour} sat/vB\n"
        result += f"🚗 Standard (~1 hour): {hour} sat/vB\n"
        result += f"🐢 Economy (Low priority): {economy} sat/vB\n"
        result += f"📉 Minimum: {minimum} sat/vB\n\n"
        
        # 估算典型交易费用（假设 250 vBytes 的普通交易）
        typical_size = 250  # vBytes
        btc_price = 60000  # 简化估价
        
        standard_fee_sats = hour * typical_size
        standard_fee_btc = standard_fee_sats / 1e8
        standard_fee_usd = standard_fee_btc * btc_price
        
        result += "💵 Estimated Cost (typical 250 vB tx):\n"
        result += f"   Standard: {standard_fee_sats:,} sats (~${standard_fee_usd:.2f})\n"
        result += f"   Fastest: {fastest * typical_size:,} sats (~${(fastest * typical_size / 1e8) * btc_price:.2f})\n\n"
        
        # 费率状态判断
        if hour <= 5:
            status = "🟢 Very Low - Great time to transact!"
        elif hour <= 15:
            status = "🟢 Low - Good time to transact"
        elif hour <= 30:
            status = "🟡 Moderate - Normal fees"
        elif hour <= 50:
            status = "🟠 High - Consider waiting"
        else:
            status = "🔴 Very High - Network congested"
        
        result += f"Status: {status}\n"
        result += "📊 Data: mempool.space"
        
        return result
    except Exception as e:
        return f"Failed to fetch Bitcoin fees: {str(e)}"


def get_bitcoin_stats() -> str:
    """
    Get current Bitcoin network statistics from Mempool.space.
    Includes Block Height, Hashrate (Estimated), Difficulty, and Block Time.
    No API key required.
    """
    try:
        # 1. Height
        height_url = "https://mempool.space/api/blocks/tip/height"
        height = requests.get(height_url, timeout=10).json()
        
        # 2. Hashrate & Difficulty (Both available in hashrate endpoint)
        hashrate_url = "https://mempool.space/api/v1/mining/hashrate/3d"
        hashrate_data = requests.get(hashrate_url, timeout=10).json()
        
        current_hashrate = hashrate_data.get("currentHashrate", 0)
        difficulty = hashrate_data.get("currentDifficulty", 0)
        
        # Format Hashrate (H/s -> EH/s)
        hashrate_eh = current_hashrate / 1e18
        
        # Format Difficulty (Trillions)
        difficulty_t = difficulty / 1e12
        
        result = "📊 Bitcoin Network Statistics\n"
        result += "=" * 35 + "\n\n"
        
        result += f"🧱 Current Block Height: {height:,}\n"
        result += f"⛏️ Network Hashrate: {hashrate_eh:.2f} EH/s\n"
        result += f"🧩 Mining Difficulty: {difficulty_t:.2f} T\n\n"
        
        # Explain Difficulty
        result += f"ℹ️ Note: Hashrate is an estimate. Difficulty adjusts every 2016 blocks (~2 weeks).\n"
        
        return result
    except Exception as e:
        return f"Failed to fetch Bitcoin stats: {str(e)}"


def get_wallet_balance(address: str, chain: str = "ethereum") -> str:
    """
    Get native token balance for a wallet address on supported EVM chains.
    
    Args:
        address: Wallet address (e.g., "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045")
        chain: Chain name (ethereum, arbitrum, optimism, base, polygon, bsc, avalanche, fantom)
              Default: ethereum
    """
    if not ETHERSCAN_API_KEY:
        return "❌ 配置错误: 未设置 ETHERSCAN_API_KEY，请在 .env 中添加"
    
    if not address.startswith('0x') or len(address) != 42:
        return f"❌ 无效地址格式: {address}. 地址应以 0x 开头，长度为 42 字符"
    
    chain_config = _get_chain_config(chain)
    chainid = chain_config["chainid"]
    chain_name = chain_config["name"]
    symbol = chain_config["symbol"]
    
    try:
        url = f"{ETHERSCAN_BASE_URL}?chainid={chainid}&module=account&action=balance&address={address}&tag=latest&apikey={ETHERSCAN_API_KEY}"
        resp = requests.get(url, timeout=10).json()
        
        if resp.get('status') != '1':
            return f"API error for {chain_name}: {resp.get('message', 'Unknown error')}"
        
        balance_wei = int(resp['result'])
        balance = balance_wei / 1e18
        
        result = f"💰 Wallet Balance on {chain_name}\n"
        result += "=" * 35 + "\n\n"
        result += f"📍 Address: {address[:10]}...{address[-8:]}\n"
        result += f"💎 Balance: {balance:,.6f} {symbol}\n"
        
        # 估算价值
        prices = {"ETH": 3000, "MATIC": 0.5, "BNB": 300, "AVAX": 25, "FTM": 0.3}
        native_price = prices.get(symbol, 1)
        usd_value = balance * native_price
        result += f"💵 Value: ~${usd_value:,.2f} USD\n\n"
        
        # 鲸鱼分类（基于 ETH 等价值）
        eth_equivalent = usd_value / 3000
        if eth_equivalent >= 10000:
            whale_status = "🐋 Whale Account"
        elif eth_equivalent >= 1000:
            whale_status = "🦈 Large Holder"
        elif eth_equivalent >= 100:
            whale_status = "🐬 Medium Holder"
        elif eth_equivalent >= 10:
            whale_status = "🐟 Small Holder"
        else:
            whale_status = "🦐 Retail Account"
        
        result += f"Classification: {whale_status}"
        
        return result
    except Exception as e:
        return f"Failed to fetch wallet balance on {chain_name}: {str(e)}"


def get_wallet_transactions(address: str, chain: str = "ethereum", limit: int = 10) -> str:
    """
    Get recent transactions for a wallet address on supported EVM chains.
    Shows latest inbound and outbound native token transfers.
    
    Args:
        address: Wallet address to query
        chain: Chain name (ethereum, arbitrum, optimism, base, polygon, bsc, avalanche, fantom)
              Default: ethereum
        limit: Number of transactions to return (default 10, max 50)
    """
    if not ETHERSCAN_API_KEY:
        return "❌ 配置错误: 未设置 ETHERSCAN_API_KEY，请在 .env 中添加"
    
    if not address.startswith('0x') or len(address) != 42:
        return f"❌ 无效地址格式: {address}. 地址应以 0x 开头，长度为 42 字符"
    
    chain_config = _get_chain_config(chain)
    chainid = chain_config["chainid"]
    chain_name = chain_config["name"]
    symbol = chain_config["symbol"]
    
    limit = min(limit, 50)
    
    try:
        url = f"{ETHERSCAN_BASE_URL}?chainid={chainid}&module=account&action=txlist&address={address}&startblock=0&endblock=99999999&page=1&offset={limit}&sort=desc&apikey={ETHERSCAN_API_KEY}"
        resp = requests.get(url, timeout=10).json()
        
        if resp.get('status') != '1':
            if resp.get('message') == 'No transactions found':
                return f"📭 No transactions found for address {address[:10]}...{address[-8:]} on {chain_name}"
            return f"API error for {chain_name}: {resp.get('message', 'Unknown error')}"
        
        txs = resp['result']
        
        result = f"📜 Recent Transactions on {chain_name}\n"
        result += "=" * 40 + "\n"
        result += f"📍 Address: {address[:10]}...{address[-8:]}\n"
        result += f"📊 Showing last {len(txs)} transactions\n\n"
        
        for i, tx in enumerate(txs[:limit], 1):
            value = int(tx['value']) / 1e18
            
            is_incoming = tx['to'].lower() == address.lower()
            direction = "📥 IN" if is_incoming else "📤 OUT"
            
            timestamp = datetime.fromtimestamp(int(tx['timeStamp']))
            time_str = timestamp.strftime('%m/%d %H:%M')
            
            status = "✅" if tx.get('isError') == '0' else "❌"
            
            counterparty = tx['from'] if is_incoming else tx['to']
            counterparty_short = f"{counterparty[:8]}...{counterparty[-6:]}"
            
            result += f"{i}. {status} {direction} | {value:.4f} {symbol}\n"
            result += f"   {time_str} | {counterparty_short}\n"
            
            if i < len(txs[:limit]):
                result += "   " + "-" * 25 + "\n"
        
        return result
    except Exception as e:
        return f"Failed to fetch transactions on {chain_name}: {str(e)}"


# 为了向后兼容，保留原函数名作为别名
def get_eth_gas_price() -> str:
    """Alias for get_gas_price('ethereum') for backward compatibility."""
    return get_gas_price("ethereum")


# ==================== 非 EVM 链支持 ====================

# Solana RPC 配置
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"

# Sui RPC 配置
SUI_RPC_URL = "https://fullnode.mainnet.sui.io:443"


def get_solana_balance(address: str) -> str:
    """
    Get SOL balance for a Solana wallet address.
    
    Args:
        address: Solana wallet address (base58 encoded public key)
    """
    if not address or len(address) < 32 or len(address) > 44:
        return f"❌ 无效地址格式: {address}. Solana 地址应为 32-44 字符的 base58 编码"
    
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [address]
        }
        
        resp = requests.post(SOLANA_RPC_URL, json=payload, timeout=10).json()
        
        if "error" in resp:
            return f"Solana RPC error: {resp['error'].get('message', 'Unknown error')}"
        
        balance_lamports = resp.get("result", {}).get("value", 0)
        balance_sol = balance_lamports / 1e9  # 1 SOL = 1e9 lamports
        
        result = f"💰 Solana Wallet Balance\n"
        result += "=" * 35 + "\n\n"
        result += f"📍 Address: {address[:8]}...{address[-6:]}\n"
        result += f"💎 Balance: {balance_sol:,.6f} SOL\n"
        
        # 估算价值
        sol_price = 150  # 简化估价
        usd_value = balance_sol * sol_price
        result += f"💵 Value: ~${usd_value:,.2f} USD\n\n"
        
        # 鲸鱼分类
        if balance_sol >= 100000:
            whale_status = "🐋 Whale Account"
        elif balance_sol >= 10000:
            whale_status = "🦈 Large Holder"
        elif balance_sol >= 1000:
            whale_status = "🐬 Medium Holder"
        elif balance_sol >= 100:
            whale_status = "🐟 Small Holder"
        else:
            whale_status = "🦐 Retail Account"
        
        result += f"Classification: {whale_status}"
        
        return result
    except Exception as e:
        return f"Failed to fetch Solana balance: {str(e)}"


def get_solana_transactions(address: str, limit: int = 10) -> str:
    """
    Get recent transactions for a Solana wallet address.
    
    Args:
        address: Solana wallet address (base58 encoded public key)
        limit: Number of transactions to return (default 10, max 20)
    """
    if not address or len(address) < 32 or len(address) > 44:
        return f"❌ 无效地址格式: {address}. Solana 地址应为 32-44 字符的 base58 编码"
    
    limit = min(limit, 20)
    
    try:
        # 获取最近的签名
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [address, {"limit": limit}]
        }
        
        resp = requests.post(SOLANA_RPC_URL, json=payload, timeout=15).json()
        
        if "error" in resp:
            return f"Solana RPC error: {resp['error'].get('message', 'Unknown error')}"
        
        signatures = resp.get("result", [])
        
        if not signatures:
            return f"📭 No transactions found for Solana address {address[:8]}...{address[-6:]}"
        
        result = f"📜 Solana Transactions\n"
        result += "=" * 40 + "\n"
        result += f"📍 Address: {address[:8]}...{address[-6:]}\n"
        result += f"📊 Showing last {len(signatures)} transactions\n\n"
        
        for i, sig_info in enumerate(signatures, 1):
            signature = sig_info.get("signature", "")[:20] + "..."
            slot = sig_info.get("slot", 0)
            block_time = sig_info.get("blockTime")
            err = sig_info.get("err")
            memo = sig_info.get("memo", "")
            
            status = "✅" if err is None else "❌"
            
            time_str = ""
            if block_time:
                from datetime import datetime
                time_str = datetime.fromtimestamp(block_time).strftime('%m/%d %H:%M')
            else:
                time_str = "Unknown"
            
            result += f"{i}. {status} | Slot: {slot}\n"
            result += f"   {time_str} | Sig: {signature}\n"
            if memo:
                result += f"   Memo: {memo[:30]}...\n"
            
            if i < len(signatures):
                result += "   " + "-" * 25 + "\n"
        
        result += f"\n💡 Tip: Use a Solana explorer for detailed transaction info."
        
        return result
    except Exception as e:
        return f"Failed to fetch Solana transactions: {str(e)}"


def get_sui_balance(address: str) -> str:
    """
    Get SUI balance for a Sui wallet address.
    
    Args:
        address: Sui wallet address (0x prefixed)
    """
    if not address.startswith("0x") or len(address) != 66:
        return f"❌ 无效地址格式: {address}. Sui 地址应以 0x 开头，长度为 66 字符"
    
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "suix_getBalance",
            "params": [address, "0x2::sui::SUI"]
        }
        
        resp = requests.post(SUI_RPC_URL, json=payload, timeout=10).json()
        
        if "error" in resp:
            return f"Sui RPC error: {resp['error'].get('message', 'Unknown error')}"
        
        result_data = resp.get("result", {})
        balance_mist = int(result_data.get("totalBalance", 0))
        balance_sui = balance_mist / 1e9  # 1 SUI = 1e9 MIST
        
        result = f"💰 Sui Wallet Balance\n"
        result += "=" * 35 + "\n\n"
        result += f"📍 Address: {address[:10]}...{address[-8:]}\n"
        result += f"💎 Balance: {balance_sui:,.6f} SUI\n"
        
        # 估算价值
        sui_price = 4  # 简化估价
        usd_value = balance_sui * sui_price
        result += f"💵 Value: ~${usd_value:,.2f} USD\n\n"
        
        # 鲸鱼分类
        if balance_sui >= 1000000:
            whale_status = "🐋 Whale Account"
        elif balance_sui >= 100000:
            whale_status = "🦈 Large Holder"
        elif balance_sui >= 10000:
            whale_status = "🐬 Medium Holder"
        elif balance_sui >= 1000:
            whale_status = "🐟 Small Holder"
        else:
            whale_status = "🦐 Retail Account"
        
        result += f"Classification: {whale_status}"
        
        return result
    except Exception as e:
        return f"Failed to fetch Sui balance: {str(e)}"


# ==================== Phase 2: 全生态支持 ====================

# Bitcoin (Mempool API)
BTC_API_URL = "https://mempool.space/api/address"

# TON (TonAPI)
TON_API_URL = "https://toncenter.com/api/v2/jsonRPC" # 使用 TonCenter 免费节点作为备选

# Tron (TronScan)
TRONSCAN_API_URL = "https://apilist.tronscanapi.com/api/account"


def get_bitcoin_balance(address: str) -> str:
    """
    Get BTC balance for a Bitcoin address using Mempool.space API (No Key needed).
    
    Args:
        address: Bitcoin address (Legacy, SegWit, Taproot supported)
    """
    if not address or len(address) < 26:
        return f"❌ Invalid Bitcoin address format: {address}"

    try:
        url = f"{BTC_API_URL}/{address}"
        resp = requests.get(url, timeout=10).json()
        
        # 检查是否有效地址 (key error check)
        if "chain_stats" not in resp:
            return f"Failed to fetch Bitcoin data. Address might be invalid or unused."

        chain_stats = resp["chain_stats"]
        mempool_stats = resp["mempool_stats"]
        
        # 计算余额 (Satoshis)
        confirmed_sats = chain_stats["funded_txo_sum"] - chain_stats["spent_txo_sum"]
        unconfirmed_sats = mempool_stats["funded_txo_sum"] - mempool_stats["spent_txo_sum"]
        total_sats = confirmed_sats + unconfirmed_sats
        
        balance_btc = total_sats / 1e8
        
        result = f"💰 Bitcoin Wallet Balance\n"
        result += "=" * 35 + "\n\n"
        result += f"📍 Address: {address[:8]}...{address[-6:]}\n"
        result += f"💎 Balance: {balance_btc:,.8f} BTC\n"
        
        if unconfirmed_sats != 0:
            result += f"   (Pending: {unconfirmed_sats/1e8:,.8f} BTC)\n"

        # 估算价值
        btc_price = 60000 # 简化估价，实际应从 market tools 获取，这里仅作静态兜底
        usd_value = balance_btc * btc_price
        result += f"💵 Value: ~${usd_value:,.2f} USD (Est.)\n"
        
        return result
    except Exception as e:
        return f"Failed to fetch Bitcoin balance: {str(e)}"


def get_bitcoin_transactions(address: str, limit: int = 10) -> str:
    """
    Get recent transactions for a Bitcoin address using Mempool.space API.
    
    Args:
        address: Bitcoin address (Legacy, SegWit, Taproot supported)
        limit: Number of transactions to return (default 10, max 25)
    """
    if not address or len(address) < 26:
        return f"❌ Invalid Bitcoin address format: {address}"

    limit = min(limit, 25)
    
    try:
        url = f"{BTC_API_URL}/{address}/txs"
        resp = requests.get(url, timeout=15).json()
        
        if not resp or not isinstance(resp, list):
            return f"No transactions found for Bitcoin address {address[:8]}...{address[-6:]}"
        
        result = f"📜 Bitcoin Transactions\n"
        result += "=" * 40 + "\n"
        result += f"📍 Address: {address[:8]}...{address[-6:]}\n"
        result += f"📊 Showing last {min(len(resp), limit)} transactions\n\n"
        
        for i, tx in enumerate(resp[:limit], 1):
            txid = tx.get("txid", "")[:16] + "..."
            confirmed = tx.get("status", {}).get("confirmed", False)
            block_time = tx.get("status", {}).get("block_time")
            
            # 计算进出
            total_in = 0
            total_out = 0
            is_sender = False
            
            for vin in tx.get("vin", []):
                prev_addr = vin.get("prevout", {}).get("scriptpubkey_address", "")
                prev_value = vin.get("prevout", {}).get("value", 0)
                if prev_addr.lower() == address.lower():
                    is_sender = True
                    total_out += prev_value
            
            for vout in tx.get("vout", []):
                out_addr = vout.get("scriptpubkey_address", "")
                out_value = vout.get("value", 0)
                if out_addr.lower() == address.lower():
                    total_in += out_value
            
            # 净变化
            net_sats = total_in - total_out if is_sender else total_in
            net_btc = net_sats / 1e8
            
            direction = "📤 OUT" if is_sender and net_btc < 0 else "📥 IN"
            status = "✅" if confirmed else "⏳"
            
            time_str = ""
            if block_time:
                from datetime import datetime
                time_str = datetime.fromtimestamp(block_time).strftime('%m/%d %H:%M')
            else:
                time_str = "Pending"
            
            result += f"{i}. {status} {direction} | {abs(net_btc):.8f} BTC\n"
            result += f"   {time_str} | TX: {txid}\n"
            
            if i < min(len(resp), limit):
                result += "   " + "-" * 25 + "\n"
        
        return result
    except Exception as e:
        return f"Failed to fetch Bitcoin transactions: {str(e)}"


def get_ton_balance(address: str) -> str:
    """
    Get TON balance for a TON address using TonCenter API (Free tier).
    
    Args:
        address: TON address (EQ... or UQ...)
    """
    try:
        # TonCenter jsonRPC getAddressBalance
        payload = {
            "id": 1,
            "jsonrpc": "2.0",
            "method": "getAddressBalance",
            "params": {"address": address}
        }
        
        resp = requests.post(TON_API_URL, json=payload, timeout=10).json()
        
        if "error" in resp:
            return f"TON API error: {resp['error'].get('message', 'Unknown')}"
            
        balance_nanoton = int(resp.get("result", 0))
        balance_ton = balance_nanoton / 1e9
        
        result = f"💰 TON Wallet Balance\n"
        result += "=" * 35 + "\n\n"
        result += f"📍 Address: {address[:8]}...{address[-6:]}\n"
        result += f"💎 Balance: {balance_ton:,.4f} TON\n"
        
        result += f"💵 Value: ~${balance_ton * 5.0:,.2f} USD (Est.)\n" # 简化估价
        
        return result
    except Exception as e:
        return f"Failed to fetch TON balance: {str(e)}"


def get_tron_balance(address: str) -> str:
    """
    Get TRX balance and USDT/USDC for a Tron address using TronScan API.
    
    Args:
        address: Tron address (Starts with T)
    """
    if not address.startswith("T") or len(address) != 34:
        return f"❌ Invalid Tron address: {address}. Should start with 'T' and be 34 chars."

    try:
        url = f"{TRONSCAN_API_URL}?address={address}"
        resp = requests.get(url, timeout=10).json()
        
        tokens = resp.get("tokens", [])
        balances = resp.get("balances", []) # 有时候结构不同，TronScan 返回较杂
        
        # 提取 TRX
        trx_balance = 0
        for b in resp.get("totalTokenOverview", []):
             if b.get("name") == "TRX":
                 trx_balance = float(b.get("balance", 0))

        # 提取 USDT (TRC20)
        usdt_balance = 0
        for t in resp.get("trc20token_balances", []):
            if t.get("symbol") == "USDT":
                usdt_balance = float(t.get("balance", 0)) * (10 ** -int(t.get("decimals", 6)))

        result = f"💰 Tron Wallet Balance\n"
        result += "=" * 35 + "\n\n"
        result += f"📍 Address: {address}\n"
        result += f"💎 TRX: {trx_balance:,.2f}\n"
        result += f"💵 USDT: {usdt_balance:,.2f}\n"
        
        return result
    except Exception as e:
        return f"Failed to fetch Tron balance: {str(e)}"
