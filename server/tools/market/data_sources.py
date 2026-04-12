"""
基础数据源：Binance + DexScreener
"""
import requests
import pandas as pd
import pandas_ta as ta
import time
import re
import os
from collections import Counter
from typing import Dict, Any

CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY", "")
CRYPTOPANIC_BASE_URL = "https://cryptopanic.com/api/developer/v2/posts/"

# ==========================================
# 🧱 基础组件：混合数据源 (Binance + DexScreener)
# ==========================================

def get_binance_data(symbol: str):
    """
    尝试从 Binance 获取实时价格和 K 线 (毫秒级延迟)
    """
    # 构造交易对，通常是 币种+USDT
    pair = f"{symbol.upper()}USDT"
    base_url = os.getenv("BINANCE_API_BASE", "https://api.binance.com")

    
    try:
        # 1. 查实时价格 & 24h变动
        ticker_url = f"{base_url}/api/v3/ticker/24hr?symbol={pair}"
        # 设置极短超时，如果Binance没这个币(400 error)，马上切备用源
        ticker_resp = requests.get(ticker_url, timeout=2) 
        
        if ticker_resp.status_code != 200:
            return None # 币安没有这个币
            
        ticker_data = ticker_resp.json()
        current_price = float(ticker_data['lastPrice'])
        change_24h = float(ticker_data['priceChangePercent'])
        
        # 2. 查 K 线 (用于算 RSI) - 4小时级别，取最近100根
        klines_url = f"{base_url}/api/v3/klines?symbol={pair}&interval=4h&limit=100"
        klines_resp = requests.get(klines_url, timeout=2).json()
        
        # Binance K线格式: [Open time, Open, High, Low, Close, Volume, ...]
        df = pd.DataFrame(klines_resp, columns=[
            'time', 'open', 'high', 'low', 'close', 'vol', 
            'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'
        ])
        df['close'] = df['close'].astype(float)
        
        return {
            "source": "Binance (CEX)",
            "price": current_price,
            "change_24h": change_24h,
            "history_df": df
        }
    except Exception as e:
        return None

def _get_dexscreener_data(symbol: str):
    """
    尝试从 DexScreener 获取链上价格 (针对土狗/Meme)
    """
    try:
        # 搜索最活跃的交易对
        search_url = f"https://api.dexscreener.com/latest/dex/search?q={symbol}"
        resp = requests.get(search_url, timeout=5).json()
        
        if not resp.get('pairs'):
            return None
            
        # 取流动性最好的那个池子
        best_pair = resp['pairs'][0]
        
        return {
            "source": f"DexScreener ({best_pair['dexId']} on {best_pair['chainId']})",
            "price": float(best_pair['priceUsd']),
            "change_24h": best_pair.get('priceChange', {}).get('h24', 0),
            "liquidity": best_pair.get('liquidity', {}).get('usd', 0),
            "history_df": None # DexScreener API 免费版不直接提供 K 线数组用于计算 RSI，暂时只看价格
        }
    except:
        return None

