"""
合并工具：宏观概览、批量技术分析、关键点位
"""
import requests
import os
from analysis.technical import _get_binance_klines, _get_current_price

def get_macro_overview() -> str:
    """
    一站式获取宏观市场环境 (合并多个工具)
    
    包含:
    - 恐惧贪婪指数
    - BTC 主导率
    - 总市值和24h变化
    - 市场阶段判断
    
    Returns:
        简洁的宏观市场报告
    """
    try:
        result = "📊 宏观市场概览\n"
        result += "=" * 35 + "\n\n"
        
        # 1. 恐惧贪婪指数
        try:
            fng_url = "https://api.alternative.me/fng/?limit=1"
            fng_data = requests.get(fng_url, timeout=5).json()['data'][0]
            fng_value = fng_data['value']
            fng_class = fng_data['value_classification']
            result += f"😱 恐贪指数: {fng_value} ({fng_class})\n"
        except:
            result += "😱 恐贪指数: 获取失败\n"
        
        # 2. 全局市场数据 (CoinGecko)
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            url = "https://api.coingecko.com/api/v3/global"
            data = requests.get(url, headers=headers, timeout=10).json()['data']
            
            total_mcap = data['total_market_cap']['usd']
            mcap_change_24h = data.get('market_cap_change_percentage_24h_usd', 0)
            btc_dom = data['market_cap_percentage']['btc']
            eth_dom = data['market_cap_percentage']['eth']
            total_volume = data['total_volume']['usd']
            
            # 市值
            change_emoji = "📈" if mcap_change_24h >= 0 else "📉"
            result += f"💰 总市值: ${total_mcap/1e12:.2f}T ({change_emoji}{mcap_change_24h:+.1f}%)\n"
            result += f"💱 24h成交: ${total_volume/1e9:.0f}B\n\n"
            
            # 主导率
            result += f"₿ BTC主导: {btc_dom:.1f}%\n"
            result += f"⟠ ETH主导: {eth_dom:.1f}%\n\n"
            
            # 市场阶段判断
            if btc_dom < 40:
                season = "🟢 山寨季 - 资金流入山寨"
            elif btc_dom < 50:
                season = "🟡 山寨活跃 - 部分资金流入山寨"
            elif btc_dom < 55:
                season = "⚪ 平衡 - BTC与山寨共存"
            elif btc_dom < 60:
                season = "🟠 BTC主导 - 山寨承压"
            else:
                season = "🔴 BTC吸血 - 高风险，山寨回撤"
            
            result += f"📌 市场阶段: {season}\n"
            
        except Exception as e:
            result += f"市场数据获取失败: {str(e)}\n"
        
        return result
    except Exception as e:
        return f"宏观概览获取失败: {str(e)}"


def get_batch_technical_analysis(symbols: str = "BTC,ETH,SOL") -> str:
    """
    一站式获取多币种技术分析 (合并多个批量工具)
    
    包含:
    - 周期对齐 (顺大逆小机会识别)
    - EMA/MACD 信号
    - ATR 波动率
    - 资金费率
    
    Args:
        symbols: 代币符号列表，逗号分隔
    
    Returns:
        简洁的技术分析汇总
    """
    import pandas_ta as ta
    from analysis.technical import _get_binance_klines, _get_current_price
    
    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    
    result = "📊 技术分析汇总\n"
    result += "=" * 40 + "\n\n"
    
    for symbol in symbol_list:
        try:
            price = _get_current_price(symbol)
            if price is None:
                result += f"❌ {symbol}: 无法获取价格\n\n"
                continue
            
            result += f"【{symbol}】 ${price:,.2f}\n"
            
            # 1. 周期分析 (日线和1小时)
            df_1d = _get_binance_klines(symbol, "1d")
            df_1h = _get_binance_klines(symbol, "1h")
            
            big_trend = "中性"
            small_trend = "中性"
            opportunity = "观望"
            
            if df_1d is not None and len(df_1d) >= 55:
                ema21_1d = ta.ema(df_1d['close'], length=21)
                ema55_1d = ta.ema(df_1d['close'], length=55)
                if ema21_1d is not None and ema55_1d is not None:
                    e21 = ema21_1d.iloc[-1]
                    e55 = ema55_1d.iloc[-1]
                    if price > e21 > e55:
                        big_trend = "多头 📈"
                    elif price < e21 < e55:
                        big_trend = "空头 📉"
            
            if df_1h is not None and len(df_1h) >= 55:
                ema21_1h = ta.ema(df_1h['close'], length=21)
                ema55_1h = ta.ema(df_1h['close'], length=55)
                if ema21_1h is not None and ema55_1h is not None:
                    e21 = ema21_1h.iloc[-1]
                    e55 = ema55_1h.iloc[-1]
                    if price > e21 > e55:
                        small_trend = "多头"
                    elif price < e21 < e55:
                        small_trend = "空头"
            
            # 顺大逆小判断
            if "多头" in big_trend and "空头" in small_trend:
                opportunity = "🟢 做多机会 (回调入场)"
            elif "空头" in big_trend and "多头" in small_trend:
                opportunity = "🔴 做空机会 (反弹入场)"
            elif "多头" in big_trend and "多头" in small_trend:
                opportunity = "🟡 等待回调"
            elif "空头" in big_trend and "空头" in small_trend:
                opportunity = "🟡 等待反弹"
            
            result += f"   日线: {big_trend} | 1h: {small_trend}\n"
            result += f"   📌 {opportunity}\n"
            
            # 2. ATR 波动率
            if df_1d is not None:
                atr = ta.atr(df_1d['high'], df_1d['low'], df_1d['close'], length=14)
                if atr is not None:
                    atr_val = atr.iloc[-1]
                    atr_pct = (atr_val / price) * 100
                    result += f"   ATR: {atr_pct:.1f}%"
            
            # 3. 资金费率
            try:
                fr_url = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}USDT&limit=1"
                fr_data = requests.get(fr_url, timeout=3).json()
                if fr_data and not (isinstance(fr_data, dict) and fr_data.get('code')):
                    fr = float(fr_data[0]['fundingRate']) * 100
                    fr_status = "🟢" if abs(fr) < 0.05 else ("🟡" if abs(fr) < 0.1 else "🔴")
                    result += f" | 费率: {fr:+.3f}% {fr_status}"
            except:
                pass
            
            result += "\n\n"
            
        except Exception as e:
            result += f"❌ {symbol}: {str(e)}\n\n"
    
    return result


def get_key_levels(symbol: str, timeframe: str = "1d") -> str:
    """
    一站式获取关键价位 (合并多个分析工具)
    
    包含:
    - ATH 历史最高点
    - 斐波那契关键位 (0.382/0.5/0.618)
    - EMA 关键位 (21/55/200)
    - 密集成交区 (POC)
    - 共振区识别
    
    Args:
        symbol: 代币符号
        timeframe: 周期 (1d, 4h)
    
    Returns:
        关键价位和共振区报告
    """
    import pandas_ta as ta
    from analysis.technical import _get_binance_klines, _get_current_price
    from analysis.pattern import _find_swing_points, _find_local_extremes
    
    clean_symbol = symbol.upper().strip()
    
    price = _get_current_price(clean_symbol)
    if price is None:
        return f"无法获取 {clean_symbol} 价格"
    
    result = f"🎯 {clean_symbol} 关键价位 ({timeframe})\n"
    result += "=" * 35 + "\n\n"
    result += f"💰 当前价格: ${price:,.2f}\n\n"
    
    all_levels = []  # [(价格, 名称, 类型)]
    
    # 1. ATH
    try:
        coin_map = {'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana'}
        coin_id = coin_map.get(clean_symbol)
        if coin_id:
            url = f'https://api.coingecko.com/api/v3/coins/{coin_id}'
            resp = requests.get(url, timeout=10).json()
            ath = resp['market_data']['ath']['usd']
            ath_dist = ((price - ath) / ath) * 100
            result += f"📈 ATH: ${ath:,.0f} ({ath_dist:+.1f}%)\n"
            all_levels.append((ath, 'ATH', 'resistance'))
    except:
        pass
    
    # 获取K线
    df = _get_binance_klines(clean_symbol, timeframe, limit=100)
    if df is None or len(df) < 30:
        return result + "数据不足"
    
    # 2. EMA
    try:
        ema21 = ta.ema(df['close'], length=21).iloc[-1]
        ema55 = ta.ema(df['close'], length=55).iloc[-1]
        all_levels.append((ema21, 'EMA21', 'support' if ema21 < price else 'resistance'))
        all_levels.append((ema55, 'EMA55', 'support' if ema55 < price else 'resistance'))
        if len(df) >= 200:
            ema200 = ta.ema(df['close'], length=200).iloc[-1]
            all_levels.append((ema200, 'EMA200', 'support' if ema200 < price else 'resistance'))
    except:
        pass
    
    # 3. 斐波那契
    try:
        window = 7 if timeframe == "1d" else 5
        swing_high, swing_low = _find_swing_points(df, window=window)
        high_p = swing_high['price']
        low_p = swing_low['price']
        diff = high_p - low_p
        
        is_uptrend = swing_high['index'] > swing_low['index']
        
        for fib in [0.382, 0.5, 0.618]:
            if is_uptrend:
                level = high_p - diff * fib
            else:
                level = low_p + diff * fib
            level_type = 'support' if level < price else 'resistance'
            all_levels.append((level, f'Fib{fib}', level_type))
    except:
        pass
    
    # 4. 密集成交区
    try:
        price_high = df['high'].max()
        price_low = df['low'].min()
        price_range = price_high - price_low
        bin_size = price_range / 20
        
        vol_by_level = {}
        for i in range(len(df)):
            tp = (df['high'].iloc[i] + df['low'].iloc[i] + df['close'].iloc[i]) / 3
            vol = df['volume'].iloc[i]
            bin_idx = min(int((tp - price_low) / bin_size), 19)
            bin_center = price_low + (bin_idx + 0.5) * bin_size
            vol_by_level[bin_center] = vol_by_level.get(bin_center, 0) + vol
        
        sorted_vols = sorted(vol_by_level.items(), key=lambda x: x[1], reverse=True)
        total_vol = sum(vol_by_level.values())
        
        for lp, lv in sorted_vols[:2]:
            vol_pct = (lv / total_vol) * 100
            if vol_pct >= 5:
                lt = 'support' if lp < price else 'resistance'
                all_levels.append((lp, f'POC({vol_pct:.0f}%)', lt))
    except:
        pass
    
    # 分类输出
    supports = sorted([(l, n) for l, n, t in all_levels if t == 'support'], key=lambda x: x[0], reverse=True)
    resistances = sorted([(l, n) for l, n, t in all_levels if t == 'resistance'], key=lambda x: x[0])
    
    result += "\n📗 支撑位:\n"
    for level, name in supports[:4]:
        dist = ((price - level) / level) * 100
        result += f"   ${level:,.0f} ({name}) -{dist:.1f}%\n"
    
    result += "\n📕 阻力位:\n"
    for level, name in resistances[:4]:
        dist = ((level - price) / price) * 100
        result += f"   ${level:,.0f} ({name}) +{dist:.1f}%\n"
    
    # 5. 共振区识别
    tolerance = 0.015
    all_levels.sort(key=lambda x: x[0])
    used = set()
    confluences = []
    
    for i, (l1, n1, t1) in enumerate(all_levels):
        if i in used:
            continue
        cluster = [(l1, n1)]
        used.add(i)
        for j, (l2, n2, t2) in enumerate(all_levels):
            if j in used:
                continue
            if abs(l2 - l1) / l1 <= tolerance:
                cluster.append((l2, n2))
                used.add(j)
        if len(cluster) >= 2:
            avg = sum(l[0] for l in cluster) / len(cluster)
            names = [l[1] for l in cluster]
            confluences.append((avg, names))
    
    if confluences:
        result += "\n⭐ 共振区:\n"
        for avg, names in sorted(confluences, key=lambda x: abs(x[0] - price))[:3]:
            dist = ((avg - price) / price) * 100
            emoji = "📗" if avg < price else "📕"
            strength = "🔥" if len(names) >= 3 else ""
            result += f"   {emoji} ${avg:,.0f} ({dist:+.1f}%) {strength}\n"
            result += f"      ↳ {', '.join(names)}\n"
    
    return result
