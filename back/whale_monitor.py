"""
🐋 Bitcoin Whale Monitor - 比特币鲸鱼监控工具

使用免费公开 API 获取链上鲸鱼数据：
- Blockchair: 持有者分布统计
- Mempool.space: 大额转账监控
- Blockchain.info: 富豪榜地址追踪

Author: CryptoAgent Team
"""

import requests
import time
from typing import Optional, Dict, Any
from datetime import datetime


# ==========================================
# 📊 工具1: 持有者分布统计
# ==========================================

def get_btc_holder_distribution() -> str:
    """
    Get Bitcoin holder distribution by balance tiers.
    Shows the number of addresses holding different amounts of BTC.
    
    Tiers:
    - Shrimp: < 1 BTC
    - Crab: 1-10 BTC
    - Fish: 10-100 BTC
    - Shark: 100-1000 BTC
    - Whale: 1000+ BTC
    
    Returns:
        Formatted report with holder distribution and market interpretation.
    """
    try:
        # 使用 Blockchair API 获取地址分布数据
        # 这是一个聚合统计，不需要逐个查询
        
        # 方案: 使用 Blockchain.info 的统计 API (更稳定)
        stats_url = "https://api.blockchain.info/stats"
        resp = requests.get(stats_url, timeout=10)
        
        if resp.status_code != 200:
            return f"Failed to fetch blockchain stats: HTTP {resp.status_code}"
        
        stats = resp.json()
        
        # 获取富豪榜来估算分布
        rich_list_url = "https://blockchain.info/balance?active="
        
        # 预定义的鲸鱼地址样本 (Top 10 已知大户)
        # 注: 这些是公开已知的大户地址
        whale_addresses = [
            "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo",  # Binance 冷钱包
            "bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97",  # Bitfinex
            "1P5ZEDWTKTFGxQjZphgWPQUpe554WKDfHQ",  # 早期矿工
        ]
        
        # 获取这些鲸鱼地址的余额情况
        whale_info = []
        for addr in whale_addresses[:3]:  # 限制查询数量
            try:
                addr_url = f"https://blockchain.info/rawaddr/{addr}?limit=0"
                addr_resp = requests.get(addr_url, timeout=5)
                if addr_resp.status_code == 200:
                    data = addr_resp.json()
                    balance_btc = data.get('final_balance', 0) / 1e8
                    if balance_btc > 1000:
                        whale_info.append({
                            'address': addr[:15] + '...',
                            'balance': balance_btc
                        })
                time.sleep(0.5)  # 限速
            except:
                continue
        
        # 构建报告
        result = "🐋 比特币持有者分布统计\n"
        result += "━" * 35 + "\n\n"
        
        # 链上总体统计
        total_btc = stats.get('totalbc', 0) / 1e8
        n_tx = stats.get('n_tx', 0)
        hash_rate = stats.get('hash_rate', 0) / 1e12  # TH/s
        difficulty = stats.get('difficulty', 0) / 1e12  # T
        
        result += "📊 链上概况\n"
        result += f"   总流通量: {total_btc:,.0f} BTC\n"
        result += f"   总交易数: {n_tx:,}\n"
        result += f"   算力: {hash_rate:.2f} EH/s\n"
        result += f"   难度: {difficulty:.2f} T\n\n"
        
        # 持有者分级说明
        result += "📈 持有者分级标准\n"
        result += "   🦐 Shrimp (虾米): < 1 BTC\n"
        result += "   🦀 Crab (螃蟹): 1-10 BTC\n"
        result += "   🐟 Fish (小鱼): 10-100 BTC\n"
        result += "   🦈 Shark (鲨鱼): 100-1000 BTC\n"
        result += "   🐋 Whale (鲸鱼): 1000+ BTC\n\n"
        
        # 已知鲸鱼地址
        if whale_info:
            result += "🐋 已知鲸鱼地址余额\n"
            for w in whale_info:
                result += f"   {w['address']}: {w['balance']:,.0f} BTC\n"
            result += "\n"
        
        # 数据来源说明
        result += "📌 数据来源: Blockchain.info\n"
        result += "⚠️ 注: 精确分布数据需付费 API (Glassnode/CryptoQuant)"
        
        return result
        
    except Exception as e:
        return f"Failed to fetch holder distribution: {str(e)}"


# ==========================================
# 💸 工具2: 大额转账监控
# ==========================================

def get_whale_transactions(min_btc: int = 100, limit: int = 10) -> str:
    """
    Get recent large Bitcoin transactions.
    Monitors transactions above a specified BTC threshold.
    
    Args:
        min_btc: Minimum BTC amount to filter (default: 100)
        limit: Number of transactions to return (default: 10, max: 20)
    
    Returns:
        Formatted list of recent large transactions with details.
    """
    # 参数验证
    min_btc = max(10, min(10000, min_btc))
    limit = max(1, min(20, limit))
    
    try:
        # 使用 Mempool.space API 获取最近交易
        # 这个 API 完全免费且无限制
        
        # 获取最近的区块哈希
        blocks_url = "https://mempool.space/api/blocks"
        blocks_resp = requests.get(blocks_url, timeout=10)
        
        if blocks_resp.status_code != 200:
            return f"Failed to fetch blocks: HTTP {blocks_resp.status_code}"
        
        blocks = blocks_resp.json()
        
        large_txs = []
        
        # 遍历最近几个区块查找大额交易
        for block in blocks[:5]:  # 检查最近5个区块
            block_hash = block.get('id')
            if not block_hash:
                continue
            
            # 获取区块中的交易
            txs_url = f"https://mempool.space/api/block/{block_hash}/txs"
            txs_resp = requests.get(txs_url, timeout=10)
            
            if txs_resp.status_code != 200:
                continue
            
            txs = txs_resp.json()
            
            for tx in txs:
                # 计算交易总输出金额 (聪 -> BTC)
                total_output = sum(out.get('value', 0) for out in tx.get('vout', []))
                total_btc = total_output / 1e8
                
                if total_btc >= min_btc:
                    # 获取 BTC 当前价格来计算 USD
                    try:
                        price_resp = requests.get(
                            "https://mempool.space/api/v1/prices",
                            timeout=5
                        )
                        btc_price = price_resp.json().get('USD', 100000) if price_resp.status_code == 200 else 100000
                    except:
                        btc_price = 100000  # 默认价格
                    
                    usd_value = total_btc * btc_price
                    
                    large_txs.append({
                        'txid': tx.get('txid', '')[:16] + '...',
                        'btc': total_btc,
                        'usd': usd_value,
                        'fee': tx.get('fee', 0) / 1e8,
                        'block_height': block.get('height', 0),
                        'time': datetime.fromtimestamp(block.get('timestamp', 0)).strftime('%Y-%m-%d %H:%M')
                    })
                    
                    if len(large_txs) >= limit:
                        break
            
            if len(large_txs) >= limit:
                break
            
            time.sleep(0.3)  # 避免请求过快
        
        if not large_txs:
            return f"No transactions >= {min_btc} BTC found in recent blocks"
        
        # 按金额排序
        large_txs.sort(key=lambda x: x['btc'], reverse=True)
        
        # 构建报告
        result = f"🐋 大额 BTC 转账监控 (>= {min_btc} BTC)\n"
        result += "━" * 40 + "\n\n"
        
        for i, tx in enumerate(large_txs[:limit], 1):
            # 格式化金额
            btc_str = f"{tx['btc']:,.2f} BTC"
            usd_str = f"${tx['usd']/1e6:.2f}M" if tx['usd'] >= 1e6 else f"${tx['usd']:,.0f}"
            
            result += f"{i}. {btc_str} ({usd_str})\n"
            result += f"   📋 TxID: {tx['txid']}\n"
            result += f"   🧱 区块: {tx['block_height']}\n"
            result += f"   🕐 时间: {tx['time']}\n"
            result += f"   💰 手续费: {tx['fee']:.8f} BTC\n\n"
        
        result += f"📌 数据来源: Mempool.space\n"
        result += f"📅 查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return result
        
    except Exception as e:
        return f"Failed to fetch whale transactions: {str(e)}"


# ==========================================
# 📈 工具3: 鲸鱼余额变化追踪
# ==========================================

def get_whale_balance_changes(top_n: int = 20) -> str:
    """
    Track balance changes of top Bitcoin whale addresses.
    Shows the richest Bitcoin addresses and their recent balance changes.
    
    Args:
        top_n: Number of top addresses to track (default: 20, max: 50)
    
    Returns:
        Formatted report with whale address balances and known entities.
    """
    # 参数验证
    top_n = max(5, min(50, top_n))
    
    try:
        # 已知的大型持有者地址及其标签
        # 这些是公开信息，来自链上分析
        known_whales = [
            {
                "address": "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo",
                "label": "Binance 冷钱包",
                "type": "Exchange"
            },
            {
                "address": "bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97",
                "label": "Bitfinex",
                "type": "Exchange"
            },
            {
                "address": "1P5ZEDWTKTFGxQjZphgWPQUpe554WKDfHQ",
                "label": "早期矿工/巨鲸",
                "type": "Whale"
            },
            {
                "address": "37XuVSEpWW4trkfmvWzegTHQt7BdktSKUs",
                "label": "可能机构持有",
                "type": "Institution"
            },
            {
                "address": "1FeexV6bAHb8ybZjqQMjJrcCrHGW9sb6uF",
                "label": "早期矿工",
                "type": "Whale"
            },
        ]
        
        # 获取这些地址的当前余额
        whale_data = []
        
        for whale in known_whales[:min(top_n, len(known_whales))]:
            try:
                # 使用 Blockchain.info API
                addr_url = f"https://blockchain.info/rawaddr/{whale['address']}?limit=1"
                resp = requests.get(addr_url, timeout=5)
                
                if resp.status_code == 200:
                    data = resp.json()
                    balance_btc = data.get('final_balance', 0) / 1e8
                    total_received = data.get('total_received', 0) / 1e8
                    total_sent = data.get('total_sent', 0) / 1e8
                    n_tx = data.get('n_tx', 0)
                    
                    # 获取最近交易判断趋势
                    txs = data.get('txs', [])
                    last_tx_time = None
                    if txs:
                        last_tx_time = datetime.fromtimestamp(txs[0].get('time', 0)).strftime('%Y-%m-%d')
                    
                    whale_data.append({
                        'address': whale['address'][:20] + '...',
                        'full_address': whale['address'],
                        'label': whale['label'],
                        'type': whale['type'],
                        'balance': balance_btc,
                        'total_received': total_received,
                        'total_sent': total_sent,
                        'n_tx': n_tx,
                        'last_tx': last_tx_time
                    })
                
                time.sleep(0.5)  # 限速，避免被封
                
            except Exception as e:
                continue
        
        if not whale_data:
            return "Failed to fetch whale balance data"
        
        # 按余额排序
        whale_data.sort(key=lambda x: x['balance'], reverse=True)
        
        # 获取 BTC 当前价格
        try:
            price_resp = requests.get("https://mempool.space/api/v1/prices", timeout=5)
            btc_price = price_resp.json().get('USD', 100000) if price_resp.status_code == 200 else 100000
        except:
            btc_price = 100000
        
        # 构建报告
        result = "🐋 比特币鲸鱼地址追踪\n"
        result += "━" * 40 + "\n\n"
        
        # 汇总统计
        total_balance = sum(w['balance'] for w in whale_data)
        total_usd = total_balance * btc_price
        
        result += f"📊 监控地址: {len(whale_data)} 个\n"
        result += f"💰 总持有量: {total_balance:,.0f} BTC (${total_usd/1e9:.2f}B)\n"
        result += f"💱 BTC 单价: ${btc_price:,.0f}\n\n"
        
        result += "━" * 40 + "\n\n"
        
        # 类型图标映射
        type_emoji = {
            'Exchange': '🏦',
            'Whale': '🐋',
            'Institution': '🏛️',
            'Unknown': '❓'
        }
        
        for i, whale in enumerate(whale_data, 1):
            emoji = type_emoji.get(whale['type'], '❓')
            usd_value = whale['balance'] * btc_price
            
            # 格式化 USD
            if usd_value >= 1e9:
                usd_str = f"${usd_value/1e9:.2f}B"
            elif usd_value >= 1e6:
                usd_str = f"${usd_value/1e6:.1f}M"
            else:
                usd_str = f"${usd_value:,.0f}"
            
            result += f"{i}. {emoji} {whale['label']}\n"
            result += f"   💎 余额: {whale['balance']:,.0f} BTC ({usd_str})\n"
            result += f"   📍 地址: {whale['address']}\n"
            result += f"   📊 交易次数: {whale['n_tx']:,}\n"
            if whale['last_tx']:
                result += f"   🕐 最近活动: {whale['last_tx']}\n"
            result += "\n"
        
        result += "━" * 40 + "\n"
        result += "📌 数据来源: Blockchain.info\n"
        result += f"📅 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        result += "> 💡 提示: 交易所冷钱包余额变化可能反映市场存取款趋势"
        
        return result
        
    except Exception as e:
        return f"Failed to fetch whale balance changes: {str(e)}"


# ==========================================
# 🔧 辅助函数
# ==========================================

def _format_btc_amount(btc: float) -> str:
    """格式化 BTC 金额显示"""
    if btc >= 10000:
        return f"{btc/1000:,.1f}K BTC"
    elif btc >= 1:
        return f"{btc:,.2f} BTC"
    else:
        return f"{btc:.8f} BTC"


def _format_usd_amount(usd: float) -> str:
    """格式化 USD 金额显示"""
    if usd >= 1e9:
        return f"${usd/1e9:.2f}B"
    elif usd >= 1e6:
        return f"${usd/1e6:.1f}M"
    elif usd >= 1e3:
        return f"${usd/1e3:.1f}K"
    else:
        return f"${usd:,.0f}"


# ==========================================
# 🐋 扩展地址库 - 包含交易所/大户/ETF/矿池标签
# ==========================================

WHALE_ADDRESS_DB = [
    # ==========================================
    # 🏦 交易所冷钱包 (Exchange)
    # ==========================================
    {
        "address": "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo",
        "label": "Binance 冷钱包",
        "type": "Exchange",
        "emoji": "🏦"
    },
    {
        "address": "bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97",
        "label": "Bitfinex",
        "type": "Exchange",
        "emoji": "🏦"
    },
    {
        "address": "1Kr6QSydW9bFQG1mXiPNNu6WpJGmUa9i1g",
        "label": "Bittrex",
        "type": "Exchange",
        "emoji": "🏦"
    },
    {
        "address": "3M219KR5vEneNb47ewrPfWyb5jQ2DjxRP6",
        "label": "Kraken",
        "type": "Exchange",
        "emoji": "🏦"
    },
    {
        "address": "bc1qa5wkgaew2dkv56kfvj49j0av5nml45x9ek9hz6",
        "label": "Kraken 2",
        "type": "Exchange",
        "emoji": "🏦"
    },
    
    # ==========================================
    # 🐋 个人/机构大户 (Whale)
    # ==========================================
    {
        "address": "1P5ZEDWTKTFGxQjZphgWPQUpe554WKDfHQ",
        "label": "早期矿工/巨鲸",
        "type": "Whale",
        "emoji": "🐋"
    },
    {
        "address": "37XuVSEpWW4trkfmvWzegTHQt7BdktSKUs",
        "label": "机构持有者",
        "type": "Whale",
        "emoji": "🐋"
    },
    {
        "address": "1FeexV6bAHb8ybZjqQMjJrcCrHGW9sb6uF",
        "label": "早期矿工 #2",
        "type": "Whale",
        "emoji": "🐋"
    },
    {
        "address": "bc1qx9t2l3pyny2spqpqlye8svce70nppwtaxwdrp4",
        "label": "未知巨鲸",
        "type": "Whale",
        "emoji": "🐋"
    },
    
    # ==========================================
    # 📈 ETF 托管地址
    # ==========================================
    {
        "address": "bc1qjasf9z3h7w3jspkhtgatgpyvvzgpa2wwd2lr0eh5tx44reyn2k7sfc27a4",
        "label": "BlackRock IBIT",
        "type": "ETF",
        "emoji": "📈"
    },
    {
        "address": "bc1qe75775tzuvspl59cw77ycc472jl0sgue57aj0s",
        "label": "Fidelity FBTC",
        "type": "ETF",
        "emoji": "📈"
    },
    
    # ==========================================
    # ⛏️ 矿池地址
    # ==========================================
    {
        "address": "1F1tAaz5x1HUXrCNLbtMDqcw6o5GNn4xqX",
        "label": "F2Pool",
        "type": "Mining",
        "emoji": "⛏️"
    },
    {
        "address": "3Cbq7aT1tY8kMxWLbitaG7yT6bPbKChq64",
        "label": "AntPool",
        "type": "Mining",
        "emoji": "⛏️"
    },
]


# ==========================================
# 📊 工具4: 鲸鱼买卖信号监控
# ==========================================

def get_whale_signals(min_balance: int = 1000) -> str:
    """
    Monitor buy/sell signals from whale addresses (1000+ BTC holders).
    Tracks balance changes to determine net buying or selling activity.
    
    Signal Logic:
    - Balance increase → 🟢 Net Buying (Accumulation)
    - Balance decrease → 🔴 Net Selling (Distribution)
    - Exchange balance increase → ⚠️ Potential sell pressure
    - Exchange balance decrease → 💪 Bullish (withdrawals)
    
    Args:
        min_balance: Minimum BTC balance to track (default: 1000)
    
    Returns:
        Formatted report with whale buy/sell signals and market interpretation.
    """
    min_balance = max(100, min(100000, min_balance))
    
    try:
        # 获取 BTC 当前价格
        try:
            price_resp = requests.get("https://mempool.space/api/v1/prices", timeout=5)
            btc_price = price_resp.json().get('USD', 100000) if price_resp.status_code == 200 else 100000
        except:
            btc_price = 100000
        
        # 汇总统计
        signals = []
        exchange_signals = []
        whale_signals = []
        etf_signals = []
        
        total_exchange_balance = 0
        total_whale_balance = 0
        total_etf_balance = 0
        
        # 遍历地址库，查询余额
        for whale in WHALE_ADDRESS_DB:
            try:
                addr = whale['address']
                addr_url = f"https://blockchain.info/rawaddr/{addr}?limit=1"
                resp = requests.get(addr_url, timeout=5)
                
                if resp.status_code != 200:
                    continue
                
                data = resp.json()
                balance_btc = data.get('final_balance', 0) / 1e8
                
                # 跳过余额不足的地址
                if balance_btc < min_balance:
                    continue
                
                total_received = data.get('total_received', 0) / 1e8
                total_sent = data.get('total_sent', 0) / 1e8
                n_tx = data.get('n_tx', 0)
                
                # 分析最近交易判断买卖方向
                # 获取最近几笔交易
                txs = data.get('txs', [])
                
                recent_inflow = 0
                recent_outflow = 0
                last_tx_time = None
                
                if txs:
                    last_tx = txs[0]
                    last_tx_time = datetime.fromtimestamp(last_tx.get('time', 0))
                    
                    # 分析这笔交易对该地址的影响
                    for inp in last_tx.get('inputs', []):
                        prev_out = inp.get('prev_out', {})
                        if prev_out.get('addr') == addr:
                            recent_outflow += prev_out.get('value', 0) / 1e8
                    
                    for out in last_tx.get('out', []):
                        if out.get('addr') == addr:
                            recent_inflow += out.get('value', 0) / 1e8
                
                net_change = recent_inflow - recent_outflow
                
                # 判断信号
                if net_change > 0:
                    signal = "🟢 净买入"
                    signal_type = "BUY"
                elif net_change < 0:
                    signal = "🔴 净卖出"
                    signal_type = "SELL"
                else:
                    signal = "⚪ 持平"
                    signal_type = "HOLD"
                
                # 交易所特殊逻辑
                if whale['type'] == 'Exchange':
                    if net_change > 0:
                        signal = "⚠️ 资金流入(抛压)"
                        signal_type = "BEARISH"
                    elif net_change < 0:
                        signal = "💪 资金流出(看涨)"
                        signal_type = "BULLISH"
                    total_exchange_balance += balance_btc
                    exchange_signals.append({
                        'label': whale['label'],
                        'emoji': whale['emoji'],
                        'type': whale['type'],
                        'balance': balance_btc,
                        'net_change': net_change,
                        'signal': signal,
                        'signal_type': signal_type,
                        'last_tx_time': last_tx_time,
                        'n_tx': n_tx
                    })
                elif whale['type'] == 'ETF':
                    total_etf_balance += balance_btc
                    etf_signals.append({
                        'label': whale['label'],
                        'emoji': whale['emoji'],
                        'type': whale['type'],
                        'balance': balance_btc,
                        'net_change': net_change,
                        'signal': signal,
                        'signal_type': signal_type,
                        'last_tx_time': last_tx_time,
                        'n_tx': n_tx
                    })
                else:
                    total_whale_balance += balance_btc
                    whale_signals.append({
                        'label': whale['label'],
                        'emoji': whale['emoji'],
                        'type': whale['type'],
                        'balance': balance_btc,
                        'net_change': net_change,
                        'signal': signal,
                        'signal_type': signal_type,
                        'last_tx_time': last_tx_time,
                        'n_tx': n_tx
                    })
                
                time.sleep(0.5)  # 限速
                
            except Exception as e:
                continue
        
        # 构建报告
        result = "🐋 鲸鱼买卖信号监控\n"
        result += "━" * 40 + "\n"
        result += f"筛选条件: 余额 >= {min_balance:,} BTC\n\n"
        
        # 汇总统计
        total_all = total_exchange_balance + total_whale_balance + total_etf_balance
        result += "📊 持仓汇总\n"
        result += f"   🏦 交易所: {total_exchange_balance:,.0f} BTC (${total_exchange_balance * btc_price / 1e9:.2f}B)\n"
        result += f"   🐋 大户: {total_whale_balance:,.0f} BTC (${total_whale_balance * btc_price / 1e9:.2f}B)\n"
        result += f"   📈 ETF: {total_etf_balance:,.0f} BTC (${total_etf_balance * btc_price / 1e9:.2f}B)\n"
        result += f"   📍 总计: {total_all:,.0f} BTC\n\n"
        
        # 计算整体情绪
        buy_count = sum(1 for s in whale_signals + etf_signals if s['signal_type'] == 'BUY')
        sell_count = sum(1 for s in whale_signals + etf_signals if s['signal_type'] == 'SELL')
        bullish_exchange = sum(1 for s in exchange_signals if s['signal_type'] == 'BULLISH')
        bearish_exchange = sum(1 for s in exchange_signals if s['signal_type'] == 'BEARISH')
        
        result += "━" * 40 + "\n\n"
        result += "📈 整体情绪判断\n"
        if buy_count > sell_count and bullish_exchange >= bearish_exchange:
            result += "   🟢 看涨 - 鲸鱼净买入 + 交易所资金流出\n"
        elif sell_count > buy_count or bearish_exchange > bullish_exchange:
            result += "   🔴 看跌 - 鲸鱼净卖出 / 交易所资金流入\n"
        else:
            result += "   ⚪ 中性 - 无明显方向\n"
        
        result += f"   大户买入: {buy_count} | 大户卖出: {sell_count}\n"
        result += f"   交易所流出(看涨): {bullish_exchange} | 流入(抛压): {bearish_exchange}\n\n"
        
        result += "━" * 40 + "\n\n"
        
        # 交易所信号
        if exchange_signals:
            result += "🏦 交易所动态\n"
            for s in sorted(exchange_signals, key=lambda x: abs(x['net_change']), reverse=True):
                change_str = f"{s['net_change']:+,.0f} BTC" if s['net_change'] != 0 else "无变化"
                result += f"   {s['emoji']} {s['label']}\n"
                result += f"      余额: {s['balance']:,.0f} BTC | 变化: {change_str}\n"
                result += f"      {s['signal']}\n"
                if s['last_tx_time']:
                    result += f"      最近活动: {s['last_tx_time'].strftime('%Y-%m-%d %H:%M')}\n"
                result += "\n"
        
        # ETF 信号
        if etf_signals:
            result += "📈 ETF 托管\n"
            for s in sorted(etf_signals, key=lambda x: x['balance'], reverse=True):
                change_str = f"{s['net_change']:+,.0f} BTC" if s['net_change'] != 0 else "无变化"
                result += f"   {s['emoji']} {s['label']}\n"
                result += f"      余额: {s['balance']:,.0f} BTC | 变化: {change_str}\n"
                result += f"      {s['signal']}\n"
                result += "\n"
        
        # 大户信号
        if whale_signals:
            result += "🐋 大户/机构\n"
            for s in sorted(whale_signals, key=lambda x: x['balance'], reverse=True):
                change_str = f"{s['net_change']:+,.0f} BTC" if s['net_change'] != 0 else "无变化"
                result += f"   {s['emoji']} {s['label']}\n"
                result += f"      余额: {s['balance']:,.0f} BTC | 变化: {change_str}\n"
                result += f"      {s['signal']}\n"
                if s['last_tx_time']:
                    result += f"      最近活动: {s['last_tx_time'].strftime('%Y-%m-%d %H:%M')}\n"
                result += "\n"
        
        result += "━" * 40 + "\n"
        result += "📌 数据来源: Blockchain.info\n"
        result += f"📅 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        result += "> 💡 信号说明:\n"
        result += "> - 交易所流入 = 潜在抛压 ⚠️\n"
        result += "> - 交易所流出 = 看涨信号 💪\n"
        result += "> - 大户买入 = 鲸鱼在吸筹 🟢\n"
        result += "> - 大户卖出 = 鲸鱼在出货 🔴"
        
        return result
        
    except Exception as e:
        return f"Failed to fetch whale signals: {str(e)}"


# ==========================================
# 测试入口
# ==========================================

if __name__ == "__main__":
    print("=" * 50)
    print("🐋 Whale Monitor Test")
    print("=" * 50)
    
    print("\n\n=== 测试1: 持有者分布 ===\n")
    print(get_btc_holder_distribution())
    
    print("\n\n=== 测试2: 大额转账 ===\n")
    print(get_whale_transactions(min_btc=100, limit=5))
    
    print("\n\n=== 测试3: 鲸鱼余额追踪 ===\n")
    print(get_whale_balance_changes(top_n=5))
    
    print("\n\n=== 测试4: 鲸鱼买卖信号 ===\n")
    print(get_whale_signals(min_balance=1000))
