"""
专业技术分析工具模块 (Professional Technical Analysis Tools)

提供多周期EMA均线系统、Vegas通道、MACD信号等专业技术分析能力。
默认分析周期: 日线 + 4H
深度分析周期: 月线 + 周线 + 日线 + 4H

Author: Crypto Agent System
Version: 1.0
"""

import requests
import pandas as pd
import pandas_ta as ta
from typing import Dict, List, Optional, Any


# ==========================================
# 🔧 基础设施：Binance K线数据获取
# ==========================================

import os
BINANCE_BASE_URL = os.getenv("BINANCE_API_BASE", "https://api.binance.com")


# 周期映射：用户友好名称 -> Binance API interval
TIMEFRAME_MAP = {
    "1M": "1M",      # 月线
    "1w": "1w",      # 周线  
    "1d": "1d",      # 日线
    "4h": "4h",      # 4小时
    "1h": "1h",      # 1小时
    "monthly": "1M",
    "weekly": "1w",
    "daily": "1d",
}

# 各周期需要的K线数量（确保EMA200有足够数据）
KLINE_LIMITS = {
    "1M": 24,   # 2年月线
    "1w": 52,   # 1年周线
    "1d": 250,  # 约1年日线
    "4h": 250,  # 约42天4h线
    "1h": 200,  # 约8天1h线
}


def _get_binance_klines(symbol: str, interval: str, limit: int = None) -> Optional[pd.DataFrame]:
    """
    从 Binance 获取 K线数据
    
    Args:
        symbol: 交易对符号 (如 "BTC", "ETH")
        interval: K线周期 (1M, 1w, 1d, 4h, 1h)
        limit: K线数量，如不指定则根据周期自动选择
    
    Returns:
        DataFrame with columns: time, open, high, low, close, volume
        None if failed
    """
    # 标准化周期
    interval = TIMEFRAME_MAP.get(interval, interval)
    
    # 确定K线数量
    if limit is None:
        limit = KLINE_LIMITS.get(interval, 200)
    
    pair = f"{symbol.upper().strip()}USDT"
    
    try:
        url = f"{BINANCE_BASE_URL}/api/v3/klines?symbol={pair}&interval={interval}&limit={limit}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        
        if not data:
            return None
        
        # Binance K线格式: [Open time, Open, High, Low, Close, Volume, ...]
        df = pd.DataFrame(data, columns=[
            'time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        
        # 转换为数值类型
        for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 转换时间
        df['time'] = pd.to_datetime(df['time'], unit='ms')
        
        return df
    
    except Exception as e:
        print(f"Error fetching klines for {symbol} {interval}: {e}")
        return None


def _get_current_price(symbol: str) -> Optional[float]:
    """获取当前价格"""
    pair = f"{symbol.upper().strip()}USDT"
    try:
        url = f"{BINANCE_BASE_URL}/api/v3/ticker/price?symbol={pair}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return float(resp.json()['price'])
    except:
        pass
    return None


# ==========================================
# 📊 EMA 均线结构分析
# ==========================================

def get_ema_structure(symbol: str, timeframe: str = "1d") -> str:
    """
    分析EMA均线结构 (EMA21, EMA55, EMA200)
    
    判断趋势：
    - 多头排列: Price > EMA21 > EMA55 > EMA200
    - 空头排列: Price < EMA21 < EMA55 < EMA200
    - 震荡/缠绕: 均线交织
    
    Args:
        symbol: 代币符号 (如 "BTC", "ETH")
        timeframe: 周期 (1M, 1w, 1d, 4h)
    
    Returns:
        结构化分析报告
    """
    # 获取K线数据
    df = _get_binance_klines(symbol, timeframe)
    
    if df is None or len(df) < 200:
        return f"无法获取 {symbol} 的 {timeframe} K线数据（需要至少200根K线）"
    
    # 获取当前价格
    price = _get_current_price(symbol)
    if price is None:
        price = df['close'].iloc[-1]
    
    # 计算 EMA
    ema21 = ta.ema(df['close'], length=21)
    ema55 = ta.ema(df['close'], length=55)
    ema200 = ta.ema(df['close'], length=200)
    
    if ema21 is None or ema55 is None or ema200 is None:
        return f"EMA计算失败，数据不足"
    
    # 取最新值
    ema21_val = ema21.iloc[-1]
    ema55_val = ema55.iloc[-1]
    ema200_val = ema200.iloc[-1]
    
    # 判断排列类型
    if price > ema21_val > ema55_val > ema200_val:
        structure = "🟢 多头排列 (Strong Uptrend)"
        advice = "趋势强劲，回踩EMA21/55是买入机会"
    elif price < ema21_val < ema55_val < ema200_val:
        structure = "🔴 空头排列 (Strong Downtrend)"
        advice = "趋势向下，反弹至EMA21/55是减仓机会"
    elif ema21_val < price < ema55_val:
        structure = "🟡 回踩区间 (Pullback Zone)"
        advice = "价格在EMA21-55之间，关键决策区域"
    elif price > ema200_val and ema21_val < ema55_val:
        structure = "🟡 修复中 (Recovery)"
        advice = "短期弱势但长期仍在牛市，观察能否站稳EMA55"
    elif price < ema200_val and ema21_val > ema55_val:
        structure = "🟡 反弹中 (Bounce)"
        advice = "短期反弹但长期仍在熊市，谨慎追高"
    else:
        structure = "⚪ 震荡缠绕 (Consolidation)"
        advice = "均线缠绕，等待方向选择"
    
    # 计算距离百分比
    dist_ema21 = ((price - ema21_val) / ema21_val) * 100
    dist_ema55 = ((price - ema55_val) / ema55_val) * 100
    dist_ema200 = ((price - ema200_val) / ema200_val) * 100
    
    # 构建报告
    tf_label = {"1M": "月线", "1w": "周线", "1d": "日线", "4h": "4小时"}.get(timeframe, timeframe)
    
    report = f"[{symbol} EMA结构分析 - {tf_label}]\n"
    report += "=" * 35 + "\n\n"
    
    report += f"💰 当前价格: ${price:,.2f}\n\n"
    
    report += "📊 均线数值:\n"
    report += f"   EMA21:  ${ema21_val:,.2f} ({dist_ema21:+.2f}%)\n"
    report += f"   EMA55:  ${ema55_val:,.2f} ({dist_ema55:+.2f}%)\n"
    report += f"   EMA200: ${ema200_val:,.2f} ({dist_ema200:+.2f}%)\n\n"
    
    report += f"📐 结构判断: {structure}\n\n"
    
    report += f"💡 建议: {advice}"
    
    # 附加警告
    if abs(dist_ema21) > 10:
        report += f"\n\n⚠️ 警告: 价格偏离EMA21超过10%，短期回调/反弹风险较高"
    
    return report


# ==========================================
# 📈 Vegas 通道分析
# ==========================================

def get_vegas_channel(symbol: str, timeframe: str = "1d") -> str:
    """
    分析Vegas通道 (EMA144 + EMA169)
    
    Vegas通道是专业交易者常用的趋势通道指标。
    
    Args:
        symbol: 代币符号
        timeframe: 周期
    
    Returns:
        通道分析报告
    """
    # 获取K线数据
    df = _get_binance_klines(symbol, timeframe)
    
    if df is None or len(df) < 170:
        return f"无法获取 {symbol} 的 {timeframe} K线数据（Vegas通道需要至少170根K线）"
    
    # 获取当前价格
    price = _get_current_price(symbol)
    if price is None:
        price = df['close'].iloc[-1]
    
    # 计算 Vegas 通道
    ema144 = ta.ema(df['close'], length=144)
    ema169 = ta.ema(df['close'], length=169)
    
    if ema144 is None or ema169 is None:
        return f"Vegas通道计算失败，数据不足"
    
    ema144_val = ema144.iloc[-1]
    ema169_val = ema169.iloc[-1]
    
    # 通道上下轨
    channel_top = max(ema144_val, ema169_val)
    channel_bottom = min(ema144_val, ema169_val)
    channel_mid = (ema144_val + ema169_val) / 2
    
    # 通道宽度百分比
    channel_width = ((channel_top - channel_bottom) / channel_mid) * 100
    
    # 判断位置
    if price > channel_top:
        position = "🟢 通道上方 (Above Channel)"
        advice = "上升趋势确认，回踩通道顶部是买点"
        dist_to_channel = ((price - channel_top) / channel_top) * 100
        dist_desc = f"距通道顶部: +{dist_to_channel:.2f}%"
    elif price < channel_bottom:
        position = "🔴 通道下方 (Below Channel)"
        advice = "下降趋势确认，反弹至通道底部是卖点"
        dist_to_channel = ((price - channel_bottom) / channel_bottom) * 100
        dist_desc = f"距通道底部: {dist_to_channel:.2f}%"
    else:
        position = "🟡 通道内部 (Inside Channel)"
        advice = "趋势不明确，等待突破方向"
        # 计算在通道内的相对位置 (0-100%)
        relative_pos = ((price - channel_bottom) / (channel_top - channel_bottom)) * 100
        dist_desc = f"通道内位置: {relative_pos:.1f}%（0=底部, 100=顶部）"
    
    # 构建报告
    tf_label = {"1M": "月线", "1w": "周线", "1d": "日线", "4h": "4小时"}.get(timeframe, timeframe)
    
    report = f"[{symbol} Vegas通道分析 - {tf_label}]\n"
    report += "=" * 35 + "\n\n"
    
    report += f"💰 当前价格: ${price:,.2f}\n\n"
    
    report += "📊 通道数值:\n"
    report += f"   EMA144: ${ema144_val:,.2f}\n"
    report += f"   EMA169: ${ema169_val:,.2f}\n"
    report += f"   通道宽度: {channel_width:.2f}%\n\n"
    
    report += f"📐 位置判断: {position}\n"
    report += f"   {dist_desc}\n\n"
    
    report += f"💡 建议: {advice}"
    
    # 通道收窄警告
    if channel_width < 1:
        report += f"\n\n⚠️ 警告: 通道极度收窄（{channel_width:.2f}%），大幅波动即将到来"
    
    return report


# ==========================================
# 📉 MACD 信号分析
# ==========================================

def get_macd_signal(symbol: str, timeframe: str = "1d") -> str:
    """
    分析MACD指标信号
    
    - 金叉: MACD线上穿信号线
    - 死叉: MACD线下穿信号线
    - 区分零轴上下的信号强度
    
    Args:
        symbol: 代币符号
        timeframe: 周期
    
    Returns:
        MACD分析报告
    """
    # 获取K线数据
    df = _get_binance_klines(symbol, timeframe)
    
    if df is None or len(df) < 50:
        return f"无法获取 {symbol} 的 {timeframe} K线数据"
    
    # 获取当前价格
    price = _get_current_price(symbol)
    if price is None:
        price = df['close'].iloc[-1]
    
    # 计算 MACD (12, 26, 9)
    macd_result = ta.macd(df['close'], fast=12, slow=26, signal=9)
    
    if macd_result is None or len(macd_result) < 3:
        return f"MACD计算失败"
    
    # 取最新值
    macd_line = macd_result.iloc[-1, 0]  # MACD线
    signal_line = macd_result.iloc[-1, 1]  # 信号线
    histogram = macd_result.iloc[-1, 2]  # 柱状图
    
    # 取前一个值用于判断金叉/死叉
    macd_prev = macd_result.iloc[-2, 0]
    signal_prev = macd_result.iloc[-2, 1]
    hist_prev = macd_result.iloc[-3, 2] if len(macd_result) > 3 else 0
    
    # 判断金叉/死叉
    cross_type = None
    if macd_prev <= signal_prev and macd_line > signal_line:
        cross_type = "golden"  # 金叉
    elif macd_prev >= signal_prev and macd_line < signal_line:
        cross_type = "death"  # 死叉
    
    # 判断信号强度
    if cross_type == "golden":
        if macd_line > 0:
            signal = "🟢 强势金叉 (Golden Cross Above Zero)"
            advice = "最佳买入信号，趋势和动量双重确认"
            strength = "Very Strong"
        else:
            signal = "🟡 弱势金叉 (Golden Cross Below Zero)"
            advice = "反弹信号，但需等待MACD上穿零轴确认"
            strength = "Weak"
    elif cross_type == "death":
        if macd_line < 0:
            signal = "🔴 强势死叉 (Death Cross Below Zero)"
            advice = "最佳卖出信号，建议减仓或做空"
            strength = "Very Strong"
        else:
            signal = "🟡 弱势死叉 (Death Cross Above Zero)"
            advice = "获利回吐信号，但不是做空时机"
            strength = "Weak"
    else:
        # 没有交叉，分析当前状态
        if macd_line > signal_line and histogram > hist_prev:
            signal = "📈 多头动能增强"
            advice = "动量向上，持有多单"
            strength = "Bullish"
        elif macd_line < signal_line and histogram < hist_prev:
            signal = "📉 空头动能增强"
            advice = "动量向下，谨慎做多"
            strength = "Bearish"
        elif macd_line > signal_line and histogram < hist_prev:
            signal = "⚠️ 多头动能减弱"
            advice = "上涨动力衰竭，警惕回调"
            strength = "Weakening"
        else:
            signal = "⚠️ 空头动能减弱"
            advice = "下跌动力衰竭，可能反弹"
            strength = "Recovering"
    
    # 构建报告
    tf_label = {"1M": "月线", "1w": "周线", "1d": "日线", "4h": "4小时"}.get(timeframe, timeframe)
    
    report = f"[{symbol} MACD分析 - {tf_label}]\n"
    report += "=" * 35 + "\n\n"
    
    report += f"💰 当前价格: ${price:,.2f}\n\n"
    
    report += "📊 MACD数值:\n"
    report += f"   MACD线:  {macd_line:,.4f}\n"
    report += f"   信号线:  {signal_line:,.4f}\n"
    report += f"   柱状图:  {histogram:,.4f}\n"
    report += f"   零轴位置: {'上方' if macd_line > 0 else '下方'}\n\n"
    
    report += f"📐 信号判断: {signal}\n"
    report += f"   信号强度: {strength}\n\n"
    
    report += f"💡 建议: {advice}"
    
    return report


# ==========================================
# 📊 Phase 2: 量价分析 (Volume Analysis)
# ==========================================

def get_volume_analysis(symbol: str, timeframe: str = "1d") -> str:
    """
    分析成交量特征和量价关系
    
    包括：
    - 当前成交量 vs 平均成交量
    - 量价背离检测
    - 成交量趋势
    
    Args:
        symbol: 代币符号
        timeframe: 周期 (1d, 4h, 1h)
    
    Returns:
        量价分析报告
    """
    # 获取K线数据
    df = _get_binance_klines(symbol, timeframe)
    
    if df is None or len(df) < 50:
        return f"无法获取 {symbol} 的 {timeframe} K线数据"
    
    # 获取当前价格
    price = _get_current_price(symbol)
    if price is None:
        price = df['close'].iloc[-1]
    
    # 使用 quote_volume (USDT 计价成交额) 而不是 volume (基础货币)
    # 这样对于 BTC 等高价币，数值更有意义
    vol_col = 'quote_volume' if 'quote_volume' in df.columns else 'volume'
    current_volume = df[vol_col].iloc[-1]
    avg_volume_20 = df[vol_col].iloc[-20:].mean()
    avg_volume_50 = df[vol_col].iloc[-50:].mean()
    
    # 成交量比率
    vol_ratio_20 = current_volume / avg_volume_20 if avg_volume_20 > 0 else 0
    vol_ratio_50 = current_volume / avg_volume_50 if avg_volume_50 > 0 else 0
    
    # 判断成交量状态
    if vol_ratio_20 >= 2.0:
        vol_status = "🔥 放量异常"
        vol_desc = "成交量是近20周期平均的2倍以上，有大资金活动"
    elif vol_ratio_20 >= 1.5:
        vol_status = "📈 明显放量"
        vol_desc = "成交量高于平均50%+，市场活跃"
    elif vol_ratio_20 >= 0.8:
        vol_status = "📊 正常水平"
        vol_desc = "成交量接近平均水平"
    elif vol_ratio_20 >= 0.5:
        vol_status = "📉 缩量"
        vol_desc = "成交量低于平均，市场观望"
    else:
        vol_status = "💤 极度缩量"
        vol_desc = "成交量极低，可能酝酿变盘"
    
    # 量价背离检测 (近5根K线)
    recent_closes = df['close'].iloc[-5:].values
    recent_volumes = df[vol_col].iloc[-5:].values
    
    price_up = recent_closes[-1] > recent_closes[0]
    volume_up = recent_volumes[-1] > recent_volumes[0]
    
    # 5根K线的价格变化
    price_change_5 = ((recent_closes[-1] - recent_closes[0]) / recent_closes[0]) * 100
    volume_change_5 = ((recent_volumes[-1] - recent_volumes[0]) / recent_volumes[0]) * 100 if recent_volumes[0] > 0 else 0
    
    divergence = None
    if price_up and not volume_up and vol_ratio_20 < 0.8:
        divergence = "⚠️ 量价背离（顶背离风险）"
        div_reason = f"价格上涨{price_change_5:+.1f}%但成交量萎缩{volume_change_5:.1f}%，上涨动力不足"
    elif not price_up and volume_up and vol_ratio_20 > 1.2:
        divergence = "⚠️ 放量下跌（恐慌卖出）"
        div_reason = f"价格下跌{price_change_5:.1f}%且成交量放大{volume_change_5:+.1f}%，可能加速下跌"
    elif price_up and volume_up:
        divergence = "✅ 量价配合（健康上涨）"
        div_reason = f"价格上涨{price_change_5:+.1f}%伴随成交量增加{volume_change_5:+.1f}%，上涨有效"
    elif not price_up and not volume_up:
        divergence = "📊 缩量回调（正常调整）"
        div_reason = f"价格回调{price_change_5:.1f}%但成交量萎缩，调整较温和"
    
    # 成交量趋势 (OBV简化版)
    obv_trend = "中性"
    vol_sum_up = 0
    vol_sum_down = 0
    for i in range(1, min(20, len(df))):
        if df['close'].iloc[-i] > df['close'].iloc[-i-1]:
            vol_sum_up += df[vol_col].iloc[-i]
        else:
            vol_sum_down += df[vol_col].iloc[-i]
    
    # 使用B（十亿）作为单位，更适合USDT成交额
    if vol_sum_up > vol_sum_down * 1.5:
        obv_trend = "🟢 资金净流入"
        obv_reason = f"上涨时成交额 > 下跌时成交额（${vol_sum_up/1e9:.2f}B vs ${vol_sum_down/1e9:.2f}B）"
    elif vol_sum_down > vol_sum_up * 1.5:
        obv_trend = "🔴 资金净流出"
        obv_reason = f"下跌时成交额 > 上涨时成交额（${vol_sum_down/1e9:.2f}B vs ${vol_sum_up/1e9:.2f}B）"
    else:
        obv_trend = "🟡 资金平衡"
        obv_reason = f"上涨/下跌成交额接近（${vol_sum_up/1e9:.2f}B vs ${vol_sum_down/1e9:.2f}B）"
    
    # 构建报告
    tf_label = {"1M": "月线", "1w": "周线", "1d": "日线", "4h": "4小时"}.get(timeframe, timeframe)
    
    report = f"[{symbol} 量价分析 - {tf_label}]\n"
    report += "=" * 40 + "\n\n"
    
    report += f"💰 当前价格: ${price:,.2f}\n\n"
    
    report += "📊 成交量分析:\n"
    report += f"   当前成交额: ${current_volume/1e9:.2f}B\n"
    report += f"   20周期均额: ${avg_volume_20/1e9:.2f}B\n"
    report += f"   量比(20): {vol_ratio_20:.2f}x\n"
    report += f"   状态: {vol_status}\n"
    report += f"   ↳ {vol_desc}\n\n"
    
    if divergence:
        report += "📈 量价关系:\n"
        report += f"   {divergence}\n"
        report += f"   ↳ {div_reason}\n\n"
    
    report += "💧 资金流向趋势(20周期):\n"
    report += f"   {obv_trend}\n"
    report += f"   ↳ {obv_reason}\n"
    
    return report


def get_volume_profile(symbol: str, timeframe: str = "1d", periods: int = 100) -> str:
    """
    识别密集成交区（支撑/阻力位）
    
    通过分析历史成交量分布，找出最活跃的价格区间。
    
    Args:
        symbol: 代币符号
        timeframe: 周期
        periods: 分析周期数
    
    Returns:
        密集成交区分析报告
    """
    # 获取K线数据
    df = _get_binance_klines(symbol, timeframe, limit=periods)
    
    if df is None or len(df) < 50:
        return f"无法获取 {symbol} 的 {timeframe} K线数据"
    
    # 获取当前价格
    price = _get_current_price(symbol)
    if price is None:
        price = df['close'].iloc[-1]
    
    # 计算价格范围
    price_high = df['high'].max()
    price_low = df['low'].min()
    price_range = price_high - price_low
    
    # 将价格分成20个区间
    num_bins = 20
    bin_size = price_range / num_bins
    
    # 统计每个区间的成交量
    volume_by_level = {}
    for i in range(len(df)):
        typical_price = (df['high'].iloc[i] + df['low'].iloc[i] + df['close'].iloc[i]) / 3
        volume = df['volume'].iloc[i]
        
        # 找到价格所属区间
        bin_idx = int((typical_price - price_low) / bin_size)
        bin_idx = min(bin_idx, num_bins - 1)  # 防止越界
        
        bin_center = price_low + (bin_idx + 0.5) * bin_size
        
        if bin_center not in volume_by_level:
            volume_by_level[bin_center] = 0
        volume_by_level[bin_center] += volume
    
    # 排序找出成交量最大的区域
    sorted_levels = sorted(volume_by_level.items(), key=lambda x: x[1], reverse=True)
    
    # 识别密集成交区
    high_volume_zones = []
    total_volume = sum(volume_by_level.values())
    
    for level_price, level_volume in sorted_levels[:5]:  # Top 5
        vol_pct = (level_volume / total_volume) * 100
        if vol_pct >= 5:  # 至少占5%
            zone_type = "支撑" if level_price < price else "阻力"
            dist_pct = ((level_price - price) / price) * 100
            high_volume_zones.append({
                "price": level_price,
                "volume_pct": vol_pct,
                "type": zone_type,
                "distance": dist_pct
            })
    
    # 找出最近的支撑和阻力
    supports = [z for z in high_volume_zones if z["type"] == "支撑"]
    resistances = [z for z in high_volume_zones if z["type"] == "阻力"]
    
    nearest_support = min(supports, key=lambda x: abs(x["distance"])) if supports else None
    nearest_resistance = min(resistances, key=lambda x: abs(x["distance"])) if resistances else None
    
    # 构建报告
    tf_label = {"1M": "月线", "1w": "周线", "1d": "日线", "4h": "4小时"}.get(timeframe, timeframe)
    
    report = f"[{symbol} 密集成交区分析 - {tf_label}]\n"
    report += "=" * 40 + "\n\n"
    
    report += f"💰 当前价格: ${price:,.2f}\n"
    report += f"📅 分析周期: 近{periods}根K线\n"
    report += f"📊 价格区间: ${price_low:,.2f} ~ ${price_high:,.2f}\n\n"
    
    # 关键位置
    report += "🎯 关键价格区域:\n"
    
    if nearest_support:
        report += f"   📗 最近支撑: ${nearest_support['price']:,.2f} ({nearest_support['distance']:+.1f}%)\n"
        report += f"      ↳ 该区域成交量占比{nearest_support['volume_pct']:.1f}%，有较强买盘支撑\n"
    
    if nearest_resistance:
        report += f"   📕 最近阻力: ${nearest_resistance['price']:,.2f} ({nearest_resistance['distance']:+.1f}%)\n"
        report += f"      ↳ 该区域成交量占比{nearest_resistance['volume_pct']:.1f}%，可能有抛压\n"
    
    report += "\n📊 所有密集成交区:\n"
    for i, zone in enumerate(high_volume_zones, 1):
        emoji = "📗" if zone["type"] == "支撑" else "📕"
        report += f"   {i}. ${zone['price']:,.2f} ({zone['type']}) - "
        report += f"成交量占比{zone['volume_pct']:.1f}%，距当前{zone['distance']:+.1f}%\n"
    
    if not high_volume_zones:
        report += "   未发现明显密集成交区，价格分布较均匀\n"
    
    # 交易建议
    report += "\n💡 交易参考:\n"
    if nearest_support and abs(nearest_support['distance']) < 3:
        report += f"   ⚠️ 当前价格接近支撑位${nearest_support['price']:,.2f}，关注能否守住\n"
    if nearest_resistance and abs(nearest_resistance['distance']) < 3:
        report += f"   ⚠️ 当前价格接近阻力位${nearest_resistance['price']:,.2f}，关注能否突破\n"
    
    if supports and resistances:
        support_p = nearest_support['price'] if nearest_support else supports[0]['price']
        resist_p = nearest_resistance['price'] if nearest_resistance else resistances[0]['price']
        range_pct = ((resist_p - support_p) / support_p) * 100
        report += f"   📐 当前震荡区间: ${support_p:,.2f} ~ ${resist_p:,.2f} (约{range_pct:.1f}%)\n"
    
    return report


# ==========================================
# 🎯 多周期综合分析 (Agent 主入口)
# ==========================================

def get_multi_timeframe_analysis(symbol: str, timeframes: str = None, deep_analysis: bool = False) -> str:
    """
    多周期技术分析 - Agent主入口工具
    
    提供完整的多维度技术分析，包括EMA结构、Vegas通道、MACD信号。
    
    Args:
        symbol: 代币符号 (如 "BTC", "ETH", "SOL")
        timeframes: 要分析的周期，逗号分隔 (如 "1d,4h" 或 "1M,1w,1d,4h")
                   如不指定，默认为 "1d,4h"
        deep_analysis: 是否深度分析（使用月/周/日/4h全周期）
    
    Returns:
        综合技术分析报告，包含各周期信号汇总和交易建议
    """
    clean_symbol = symbol.upper().strip()
    
    # 确定分析周期
    if timeframes:
        tf_list = [tf.strip() for tf in timeframes.split(",")]
    elif deep_analysis:
        tf_list = ["1M", "1w", "1d", "4h"]
    else:
        tf_list = ["1d", "4h"]  # 默认日线+4小时
    
    # 获取当前价格
    price = _get_current_price(clean_symbol)
    if price is None:
        return f"无法获取 {clean_symbol} 的价格数据，请确认代币符号正确"
    
    # 构建报告头部
    report = f"╔{'═' * 50}╗\n"
    report += f"║  {clean_symbol} 多周期技术分析  \n"
    report += f"╚{'═' * 50}╝\n\n"
    
    report += f"💰 当前价格: ${price:,.2f}\n"
    report += f"📅 分析周期: {', '.join(tf_list)}\n"
    report += "=" * 52 + "\n\n"
    
    # 存储各周期分析结果用于汇总
    ema_signals = {}
    vegas_signals = {}
    macd_signals = {}
    
    # 逐周期分析
    for tf in tf_list:
        tf_label = {"1M": "月线", "1w": "周线", "1d": "日线", "4h": "4小时"}.get(tf, tf)
        
        report += f"【{tf_label}分析】\n"
        report += "-" * 30 + "\n"
        
        # 获取K线
        df = _get_binance_klines(clean_symbol, tf)
        
        if df is None or len(df) < 50:
            report += f"⚠️ 数据不足，跳过此周期\n\n"
            continue
        
        # EMA分析
        try:
            ema21 = ta.ema(df['close'], length=21)
            ema55 = ta.ema(df['close'], length=55)
            ema200 = ta.ema(df['close'], length=200) if len(df) >= 200 else None
            
            ema21_val = ema21.iloc[-1] if ema21 is not None else None
            ema55_val = ema55.iloc[-1] if ema55 is not None else None
            ema200_val = ema200.iloc[-1] if ema200 is not None else None
            
            # 判断EMA结构
            if ema21_val and ema55_val:
                dist_21 = ((price - ema21_val) / ema21_val) * 100
                dist_55 = ((price - ema55_val) / ema55_val) * 100
                
                if ema200_val:
                    dist_200 = ((price - ema200_val) / ema200_val) * 100
                    if price > ema21_val > ema55_val > ema200_val:
                        ema_status = "🟢 多头排列"
                        ema_reason = f"价格${price:,.0f} > EMA21(${ema21_val:,.0f}) > EMA55(${ema55_val:,.0f}) > EMA200(${ema200_val:,.0f})"
                        ema_signals[tf] = 1
                    elif price < ema21_val < ema55_val < ema200_val:
                        ema_status = "🔴 空头排列"
                        ema_reason = f"价格${price:,.0f} < EMA21(${ema21_val:,.0f}) < EMA55(${ema55_val:,.0f}) < EMA200(${ema200_val:,.0f})"
                        ema_signals[tf] = -1
                    else:
                        ema_status = "🟡 震荡/过渡"
                        ema_reason = f"均线交织，价格距EMA21({dist_21:+.1f}%)、EMA55({dist_55:+.1f}%)、EMA200({dist_200:+.1f}%)"
                        ema_signals[tf] = 0
                else:
                    if price > ema21_val > ema55_val:
                        ema_status = "🟢 短期多头"
                        ema_reason = f"价格${price:,.0f} > EMA21(${ema21_val:,.0f}) > EMA55(${ema55_val:,.0f})"
                        ema_signals[tf] = 0.5
                    elif price < ema21_val < ema55_val:
                        ema_status = "🔴 短期空头"
                        ema_reason = f"价格${price:,.0f} < EMA21(${ema21_val:,.0f}) < EMA55(${ema55_val:,.0f})"
                        ema_signals[tf] = -0.5
                    else:
                        ema_status = "🟡 震荡"
                        ema_reason = f"均线交织，距EMA21({dist_21:+.1f}%)、EMA55({dist_55:+.1f}%)"
                        ema_signals[tf] = 0
                
                report += f"EMA: {ema_status}\n"
                report += f"     ↳ {ema_reason}\n"
        except Exception as e:
            report += f"EMA: 计算失败\n"
        
        # Vegas通道分析
        try:
            if len(df) >= 170:
                ema144 = ta.ema(df['close'], length=144)
                ema169 = ta.ema(df['close'], length=169)
                
                ema144_val = ema144.iloc[-1]
                ema169_val = ema169.iloc[-1]
                
                channel_top = max(ema144_val, ema169_val)
                channel_bottom = min(ema144_val, ema169_val)
                channel_width = ((channel_top - channel_bottom) / channel_bottom) * 100
                
                if price > channel_top:
                    dist_pct = ((price - channel_top) / channel_top) * 100
                    vegas_status = "🟢 通道上方"
                    vegas_reason = f"价格${price:,.0f} > 通道顶${channel_top:,.0f}，高出{dist_pct:.1f}%"
                    vegas_signals[tf] = 1
                elif price < channel_bottom:
                    dist_pct = ((channel_bottom - price) / channel_bottom) * 100
                    vegas_status = "🔴 通道下方"
                    vegas_reason = f"价格${price:,.0f} < 通道底${channel_bottom:,.0f}，低于{dist_pct:.1f}%"
                    vegas_signals[tf] = -1
                else:
                    vegas_status = "🟡 通道内"
                    vegas_reason = f"价格在${channel_bottom:,.0f}~${channel_top:,.0f}区间，通道宽{channel_width:.1f}%"
                    vegas_signals[tf] = 0
                
                report += f"Vegas: {vegas_status}\n"
                report += f"     ↳ {vegas_reason}\n"
        except:
            pass
        
        # MACD分析
        try:
            macd_result = ta.macd(df['close'], fast=12, slow=26, signal=9)
            if macd_result is not None:
                macd_line = macd_result.iloc[-1, 0]
                signal_line = macd_result.iloc[-1, 1]
                histogram = macd_result.iloc[-1, 2]
                
                macd_prev = macd_result.iloc[-2, 0]
                signal_prev = macd_result.iloc[-2, 1]
                
                zero_pos = "零轴上方" if macd_line > 0 else "零轴下方"
                
                # 判断信号
                if macd_prev <= signal_prev and macd_line > signal_line:
                    if macd_line > 0:
                        macd_status = "🟢 强势金叉"
                        macd_reason = f"MACD({macd_line:.2f})上穿信号线({signal_line:.2f})，位于{zero_pos}"
                        macd_signals[tf] = 2
                    else:
                        macd_status = "🟡 弱势金叉"
                        macd_reason = f"MACD({macd_line:.2f})上穿信号线({signal_line:.2f})，但仍在{zero_pos}"
                        macd_signals[tf] = 1
                elif macd_prev >= signal_prev and macd_line < signal_line:
                    if macd_line < 0:
                        macd_status = "🔴 强势死叉"
                        macd_reason = f"MACD({macd_line:.2f})下穿信号线({signal_line:.2f})，位于{zero_pos}"
                        macd_signals[tf] = -2
                    else:
                        macd_status = "🟡 弱势死叉"
                        macd_reason = f"MACD({macd_line:.2f})下穿信号线({signal_line:.2f})，仍在{zero_pos}"
                        macd_signals[tf] = -1
                elif macd_line > signal_line:
                    macd_status = "📈 多头动能"
                    macd_reason = f"MACD({macd_line:.2f}) > 信号线({signal_line:.2f})，柱状图{histogram:+.2f}"
                    macd_signals[tf] = 0.5
                else:
                    macd_status = "📉 空头动能"
                    macd_reason = f"MACD({macd_line:.2f}) < 信号线({signal_line:.2f})，柱状图{histogram:+.2f}"
                    macd_signals[tf] = -0.5
                
                report += f"MACD: {macd_status}\n"
                report += f"     ↳ {macd_reason}\n"
        except:
            pass
        
        report += "\n"
    
    # 汇总分析
    report += "=" * 52 + "\n"
    report += "【综合信号汇总】\n"
    report += "-" * 30 + "\n"
    
    # 计算综合得分
    ema_score = sum(ema_signals.values()) / len(ema_signals) if ema_signals else 0
    vegas_score = sum(vegas_signals.values()) / len(vegas_signals) if vegas_signals else 0
    macd_score = sum(macd_signals.values()) / len(macd_signals) if macd_signals else 0
    
    total_score = (ema_score + vegas_score + macd_score) / 3
    
    # 各维度判断
    def score_to_text(score):
        if score >= 0.7:
            return "🟢 强势看多"
        elif score >= 0.3:
            return "🟢 偏多"
        elif score >= -0.3:
            return "🟡 中性"
        elif score >= -0.7:
            return "🔴 偏空"
        else:
            return "🔴 强势看空"
    
    # 统计各维度的信号分布
    def count_signals(signals_dict):
        bullish = sum(1 for v in signals_dict.values() if v > 0)
        bearish = sum(1 for v in signals_dict.values() if v < 0)
        neutral = sum(1 for v in signals_dict.values() if v == 0)
        return bullish, bearish, neutral
    
    ema_b, ema_bear, ema_n = count_signals(ema_signals)
    vegas_b, vegas_bear, vegas_n = count_signals(vegas_signals)
    macd_b, macd_bear, macd_n = count_signals(macd_signals)
    
    report += f"EMA结构: {score_to_text(ema_score)}"
    if ema_signals:
        report += f" ({ema_b}个多头/{ema_bear}个空头周期)\n"
    else:
        report += "\n"
        
    report += f"Vegas通道: {score_to_text(vegas_score)}"
    if vegas_signals:
        report += f" ({vegas_b}个通道上/{vegas_bear}个通道下周期)\n"
    else:
        report += "\n"
        
    report += f"MACD动能: {score_to_text(macd_score)}"
    if macd_signals:
        report += f" ({macd_b}个多头/{macd_bear}个空头信号)\n"
    else:
        report += "\n"
    
    report += "\n"
    
    # 综合结论 - 添加解释
    total_bullish = ema_b + vegas_b + macd_b
    total_bearish = ema_bear + vegas_bear + macd_bear
    total_signals = len(ema_signals) + len(vegas_signals) + len(macd_signals)
    
    if total_score >= 0.5:
        conclusion = "🟢 多头信号明确"
        reason = f"{total_bullish}/{total_signals}个指标看多，三个维度共振向上"
        suggestion = "趋势向上，可寻找回调买入机会"
    elif total_score >= 0.2:
        conclusion = "🟢 偏多震荡"
        reason = f"多头信号({total_bullish})略多于空头({total_bearish})，但未形成共振"
        suggestion = "整体偏多但不够强势，轻仓参与"
    elif total_score >= -0.2:
        conclusion = "🟡 多空平衡"
        reason = f"多头({total_bullish})与空头({total_bearish})信号接近，方向不明"
        suggestion = "方向不明，建议观望或区间操作"
    elif total_score >= -0.5:
        conclusion = "🔴 偏空震荡"
        reason = f"空头信号({total_bearish})略多于多头({total_bullish})，但未形成共振"
        suggestion = "整体偏空，谨慎做多，考虑减仓"
    else:
        conclusion = "🔴 空头信号明确"
        reason = f"{total_bearish}/{total_signals}个指标看空，三个维度共振向下"
        suggestion = "趋势向下，建议规避风险或寻找做空机会"
    
    report += f"📋 综合判断: {conclusion}\n"
    report += f"   ↳ 判断依据: {reason}\n"
    report += f"💡 操作建议: {suggestion}\n"
    
    return report


# ==========================================
# 🧪 测试入口
# ==========================================

if __name__ == "__main__":
    # 测试多周期分析
    print("Testing BTC multi-timeframe analysis...")
    print(get_multi_timeframe_analysis("BTC"))
    print("\n" + "=" * 60 + "\n")
    
    # 测试深度分析
    print("Testing BTC deep analysis...")
    print(get_multi_timeframe_analysis("BTC", deep_analysis=True))
