"""
趋势线分析模块 (Trendline Analysis)

提供趋势线识别、收敛/发散形态、旗形等基于趋势线的分析功能。
删除了双顶双底、头肩形态、波浪理论等难以准确量化的形态识别。

Author: Crypto Agent System
Version: 2.0
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from scipy import stats
from scipy.signal import argrelextrema

# 导入基础设施
from technical_analysis import _get_binance_klines, _get_current_price


# ==========================================
# 🔧 辅助函数
# ==========================================

def _find_local_extremes(df: pd.DataFrame, window: int = 5) -> Tuple[List[Dict], List[Dict]]:
    """
    找出K线数据中的局部高点和低点
    
    Args:
        df: K线数据
        window: 滑动窗口大小
    
    Returns:
        (高点列表, 低点列表)
    """
    highs = df['high'].values
    lows = df['low'].values
    
    # 使用scipy找局部极值
    local_max_idx = argrelextrema(highs, np.greater, order=window)[0]
    local_min_idx = argrelextrema(lows, np.less, order=window)[0]
    
    # 构建高点列表
    high_points = []
    for idx in local_max_idx:
        high_points.append({
            'index': int(idx),
            'price': float(highs[idx]),
        })
    
    # 构建低点列表
    low_points = []
    for idx in local_min_idx:
        low_points.append({
            'index': int(idx),
            'price': float(lows[idx]),
        })
    
    return high_points, low_points


def _fit_trendline(points: List[Dict], min_points: int = 2, min_r_squared: float = 0.6) -> Optional[Dict]:
    """
    用线性回归拟合趋势线
    
    Args:
        points: 点列表 [{'index': int, 'price': float}, ...]
        min_points: 最少需要的点数
        min_r_squared: 最小 R² 要求
    
    Returns:
        趋势线信息 或 None
    """
    if len(points) < min_points:
        return None
    
    x = np.array([p['index'] for p in points])
    y = np.array([p['price'] for p in points])
    
    # 线性回归
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    
    r_squared = r_value ** 2
    if r_squared < min_r_squared:
        return None
    
    return {
        'slope': slope,
        'intercept': intercept,
        'r_squared': r_squared,
        'points_count': len(points),
        'start_idx': int(min(x)),
        'end_idx': int(max(x)),
        'start_price': slope * min(x) + intercept,
        'end_price': slope * max(x) + intercept
    }


def _count_touches(df: pd.DataFrame, trendline: Dict, tolerance_pct: float = 1.5) -> int:
    """统计价格触碰趋势线的次数"""
    touches = 0
    for i in range(trendline['start_idx'], min(trendline['end_idx'] + 10, len(df))):
        trend_price = trendline['slope'] * i + trendline['intercept']
        
        high = df['high'].iloc[i]
        low = df['low'].iloc[i]
        
        tolerance = trend_price * (tolerance_pct / 100)
        
        if abs(high - trend_price) <= tolerance or abs(low - trend_price) <= tolerance:
            touches += 1
    
    return touches


def _classify_trendline_pattern(uptrend: Optional[Dict], downtrend: Optional[Dict], 
                                 current_idx: int, price: float) -> Dict:
    """
    根据趋势线组合识别形态
    
    Returns:
        形态信息
    """
    result = {
        'pattern': None,
        'bias': 'neutral',
        'description': '',
        'support': None,
        'resistance': None,
    }
    
    # 计算当前趋势线位置
    if uptrend:
        result['support'] = uptrend['slope'] * current_idx + uptrend['intercept']
    if downtrend:
        result['resistance'] = downtrend['slope'] * current_idx + downtrend['intercept']
    
    # 没有趋势线
    if not uptrend and not downtrend:
        result['pattern'] = '无明显趋势'
        result['description'] = '震荡整理，等待方向'
        return result
    
    # 只有上升趋势线
    if uptrend and not downtrend:
        result['pattern'] = '上升趋势'
        result['bias'] = 'bullish'
        dist = ((price - result['support']) / result['support']) * 100
        if dist < 0:
            result['description'] = f'⚠️ 已跌破上升趋势线！'
        elif dist < 3:
            result['description'] = f'接近趋势线支撑 ({dist:.1f}%)'
        else:
            result['description'] = f'趋势运行中，距支撑 {dist:.1f}%'
        return result
    
    # 只有下降趋势线
    if downtrend and not uptrend:
        result['pattern'] = '下降趋势'
        result['bias'] = 'bearish'
        dist = ((price - result['resistance']) / result['resistance']) * 100
        if dist > 0:
            result['description'] = f'🟢 已突破下降趋势线！'
        elif dist > -3:
            result['description'] = f'接近趋势线阻力 ({dist:.1f}%)'
        else:
            result['description'] = f'趋势运行中，距阻力 {dist:.1f}%'
        return result
    
    # 两条趋势线都存在 - 判断形态
    up_slope = uptrend['slope']
    down_slope = downtrend['slope']
    support = result['support']
    resistance = result['resistance']
    
    # 计算通道宽度
    if support and resistance and support < resistance:
        width_pct = ((resistance - support) / support) * 100
    else:
        width_pct = 0
    
    # 收敛: 上升趋势线向上 + 下降趋势线向下，两线逐渐靠近
    if up_slope > 0 and down_slope < 0:
        # 对称三角形收敛
        result['pattern'] = '三角收敛'
        result['bias'] = 'neutral'
        result['description'] = f'区间 ${support:,.0f}~${resistance:,.0f} ({width_pct:.1f}%)，等待突破'
        if width_pct < 5:
            result['description'] += '，即将选择方向！'
    
    # 上升三角形: 上升趋势线 + 水平阻力
    elif up_slope > 0 and abs(down_slope) < up_slope * 0.2:
        result['pattern'] = '上升三角形'
        result['bias'] = 'bullish'
        result['description'] = f'低点抬升，阻力 ${resistance:,.0f}，突破看涨'
    
    # 下降三角形: 下降趋势线 + 水平支撑
    elif down_slope < 0 and abs(up_slope) < abs(down_slope) * 0.2:
        result['pattern'] = '下降三角形'
        result['bias'] = 'bearish'
        result['description'] = f'高点降低，支撑 ${support:,.0f}，跌破看跌'
    
    # 上升通道: 两线平行向上
    elif up_slope > 0 and down_slope > 0:
        result['pattern'] = '上升通道'
        result['bias'] = 'bullish'
        result['description'] = f'通道运行中，支撑 ${support:,.0f}，压力 ${resistance:,.0f}'
    
    # 下降通道: 两线平行向下
    elif up_slope < 0 and down_slope < 0:
        result['pattern'] = '下降通道'
        result['bias'] = 'bearish'
        result['description'] = f'通道运行中，支撑 ${support:,.0f}，压力 ${resistance:,.0f}'
    
    # 扩散: 两线发散
    elif up_slope < 0 and down_slope > 0:
        result['pattern'] = '扩散形态'
        result['bias'] = 'neutral'
        result['description'] = '波动放大，方向不明，建议观望'
    
    else:
        result['pattern'] = '复杂形态'
        result['description'] = '趋势线结构复杂'
    
    return result


def _detect_flag_pattern(df: pd.DataFrame, high_points: List[Dict], low_points: List[Dict],
                          lookback: int = 30) -> Optional[Dict]:
    """
    检测牛旗/熊旗形态
    
    旗形特征:
    1. 先有一段快速的趋势移动 (旗杆)
    2. 然后进入逆向的小幅整理 (旗面)
    
    Args:
        df: K线数据
        high_points: 高点列表
        low_points: 低点列表
        lookback: 回看周期数
    
    Returns:
        旗形信息 或 None
    """
    if len(df) < lookback + 20:
        return None
    
    # 分析最近的价格走势
    recent_df = df.iloc[-lookback:]
    
    # 计算前半段和后半段的价格变化
    mid_point = lookback // 2
    first_half = recent_df.iloc[:mid_point]
    second_half = recent_df.iloc[mid_point:]
    
    first_change = (first_half['close'].iloc[-1] - first_half['close'].iloc[0]) / first_half['close'].iloc[0] * 100
    second_change = (second_half['close'].iloc[-1] - second_half['close'].iloc[0]) / second_half['close'].iloc[0] * 100
    
    # 计算波动幅度
    first_volatility = (first_half['high'].max() - first_half['low'].min()) / first_half['close'].mean() * 100
    second_volatility = (second_half['high'].max() - second_half['low'].min()) / second_half['close'].mean() * 100
    
    # 牛旗: 前半段大涨 + 后半段小幅回调整理
    if first_change > 8 and -5 < second_change < 2 and second_volatility < first_volatility * 0.6:
        flag_top = second_half['high'].max()
        flag_bottom = second_half['low'].min()
        pole_bottom = first_half['low'].min()
        pole_height = flag_top - pole_bottom
        
        return {
            'type': '牛旗 (Bull Flag)',
            'bias': 'bullish',
            'pole_start': pole_bottom,
            'pole_end': first_half['high'].max(),
            'flag_top': flag_top,
            'flag_bottom': flag_bottom,
            'target': flag_top + pole_height * 0.618,  # 保守目标
            'description': f'旗杆涨幅 {first_change:.1f}%，旗面整理中，突破 ${flag_top:,.0f} 看涨'
        }
    
    # 熊旗: 前半段大跌 + 后半段小幅反弹整理
    if first_change < -8 and -2 < second_change < 5 and second_volatility < first_volatility * 0.6:
        flag_top = second_half['high'].max()
        flag_bottom = second_half['low'].min()
        pole_top = first_half['high'].max()
        pole_height = pole_top - flag_bottom
        
        return {
            'type': '熊旗 (Bear Flag)',
            'bias': 'bearish',
            'pole_start': pole_top,
            'pole_end': first_half['low'].min(),
            'flag_top': flag_top,
            'flag_bottom': flag_bottom,
            'target': flag_bottom - pole_height * 0.618,
            'description': f'旗杆跌幅 {first_change:.1f}%，旗面整理中，跌破 ${flag_bottom:,.0f} 看跌'
        }
    
    return None


# ==========================================
# 📈 主工具: 多周期趋势线分析
# ==========================================

def get_trendlines(symbol: str, timeframes: str = "1d", periods: int = 100) -> str:
    """
    多周期趋势线分析
    
    识别:
    - 上升/下降趋势线
    - 三角收敛 (对称/上升/下降)
    - 上升/下降通道
    - 扩散形态
    - 牛旗/熊旗
    
    Args:
        symbol: 代币符号 (如 "BTC", "ETH", "SOL")
        timeframes: 周期，逗号分隔 (如 "1d" 或 "4h,1d")
        periods: 分析K线数量
    
    Returns:
        趋势线分析报告
    """
    clean_symbol = symbol.upper().strip()
    tf_list = [tf.strip() for tf in timeframes.split(",")]
    
    # 获取当前价格
    price = _get_current_price(clean_symbol)
    if price is None:
        return f"无法获取 {clean_symbol} 的价格数据"
    
    report = f"[{clean_symbol} 趋势线分析]\n"
    report += "=" * 45 + "\n\n"
    report += f"💰 当前价格: ${price:,.2f}\n"
    report += f"📅 分析周期: {', '.join(tf_list)}\n\n"
    
    for tf in tf_list:
        tf_label = {"1M": "月线", "1w": "周线", "1d": "日线", "4h": "4小时", "1h": "1小时"}.get(tf, tf)
        
        # 获取K线数据
        df = _get_binance_klines(clean_symbol, tf, limit=periods)
        
        if df is None or len(df) < 50:
            report += f"【{tf_label}】数据不足\n\n"
            continue
        
        # 找出高低点 (使用更大的窗口避免噪音)
        window = 7 if tf in ["1d", "1w", "1M"] else 5
        high_points, low_points = _find_local_extremes(df, window=window)
        
        # 只使用后 2/3 的点来拟合
        cutoff = len(df) // 3
        recent_highs = [p for p in high_points if p['index'] > cutoff]
        recent_lows = [p for p in low_points if p['index'] > cutoff]
        
        # 拟合上升趋势线（连接低点）
        uptrend = None
        if len(recent_lows) >= 2:
            uptrend = _fit_trendline(recent_lows, min_points=2, min_r_squared=0.5)
            # 验证斜率方向
            if uptrend and uptrend['slope'] < 0:
                uptrend = None
        
        # 拟合下降趋势线（连接高点）
        downtrend = None
        if len(recent_highs) >= 2:
            downtrend = _fit_trendline(recent_highs, min_points=2, min_r_squared=0.5)
            # 下降趋势线斜率应该为负（但我们可以接受水平阻力）
        
        # 分类形态
        current_idx = len(df) - 1
        pattern_info = _classify_trendline_pattern(uptrend, downtrend, current_idx, price)
        
        # 检测旗形
        flag = _detect_flag_pattern(df, high_points, low_points, lookback=30)
        
        # 构建报告
        report += f"【{tf_label}】\n"
        report += "-" * 30 + "\n"
        
        # 形态识别
        bias_emoji = {"bullish": "🟢", "bearish": "🔴", "neutral": "🟡"}[pattern_info['bias']]
        report += f"形态: {pattern_info['pattern']} {bias_emoji}\n"
        report += f"   ↳ {pattern_info['description']}\n"
        
        # 关键位置
        if pattern_info['support']:
            dist_s = ((price - pattern_info['support']) / pattern_info['support']) * 100
            report += f"支撑: ${pattern_info['support']:,.0f} (距离 {dist_s:+.1f}%)\n"
        if pattern_info['resistance']:
            dist_r = ((price - pattern_info['resistance']) / pattern_info['resistance']) * 100
            report += f"阻力: ${pattern_info['resistance']:,.0f} (距离 {dist_r:+.1f}%)\n"
        
        # 趋势线详情 (仅当存在时)
        if uptrend:
            touches = _count_touches(df, uptrend)
            slope_pct = (uptrend['slope'] / uptrend['start_price']) * 100
            report += f"上升线: R²={uptrend['r_squared']:.2f}, 斜率={slope_pct:+.3f}%/K, 触碰={touches}次\n"
        if downtrend:
            touches = _count_touches(df, downtrend)
            slope_pct = (downtrend['slope'] / downtrend['start_price']) * 100
            report += f"下降线: R²={downtrend['r_squared']:.2f}, 斜率={slope_pct:+.3f}%/K, 触碰={touches}次\n"
        
        # 旗形
        if flag:
            report += f"\n🚩 {flag['type']}\n"
            report += f"   ↳ {flag['description']}\n"
            report += f"   目标: ${flag['target']:,.0f}\n"
        
        report += "\n"
    
    return report


def batch_trendlines(symbols: str, timeframe: str = "1d") -> str:
    """
    批量趋势线分析
    
    一次调用分析多个币种的趋势线和形态。
    
    Args:
        symbols: 代币符号列表，逗号分隔 (如 "BTC,ETH,SOL")
        timeframe: 周期 (默认 1d)
    
    Returns:
        所有币种的趋势线汇总报告
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    tf_label = {"1M": "月线", "1w": "周线", "1d": "日线", "4h": "4小时"}.get(timeframe, timeframe)
    
    report = "=" * 50 + "\n"
    report += f"📈 批量趋势线分析 ({tf_label})\n"
    report += f"标的: {', '.join(symbol_list)}\n"
    report += "=" * 50 + "\n\n"
    
    for symbol in symbol_list:
        price = _get_current_price(symbol)
        if price is None:
            report += f"❌ {symbol}: 无法获取价格\n\n"
            continue
        
        df = _get_binance_klines(symbol, timeframe, limit=100)
        if df is None or len(df) < 50:
            report += f"❌ {symbol}: 数据不足\n\n"
            continue
        
        try:
            # 分析
            window = 7 if timeframe in ["1d", "1w", "1M"] else 5
            high_points, low_points = _find_local_extremes(df, window=window)
            
            cutoff = len(df) // 3
            recent_highs = [p for p in high_points if p['index'] > cutoff]
            recent_lows = [p for p in low_points if p['index'] > cutoff]
            
            uptrend = _fit_trendline(recent_lows, min_points=2, min_r_squared=0.5) if len(recent_lows) >= 2 else None
            if uptrend and uptrend['slope'] < 0:
                uptrend = None
            
            downtrend = _fit_trendline(recent_highs, min_points=2, min_r_squared=0.5) if len(recent_highs) >= 2 else None
            
            current_idx = len(df) - 1
            pattern = _classify_trendline_pattern(uptrend, downtrend, current_idx, price)
            flag = _detect_flag_pattern(df, high_points, low_points, lookback=30)
            
            # 汇总
            bias_emoji = {"bullish": "🟢", "bearish": "🔴", "neutral": "🟡"}[pattern['bias']]
            
            report += f"【{symbol}】 ${price:,.2f} | {pattern['pattern']} {bias_emoji}\n"
            
            # 关键位
            levels = []
            if pattern['support']:
                dist_s = ((price - pattern['support']) / pattern['support']) * 100
                levels.append(f"支撑 ${pattern['support']:,.0f} ({dist_s:+.1f}%)")
            if pattern['resistance']:
                dist_r = ((price - pattern['resistance']) / pattern['resistance']) * 100
                levels.append(f"阻力 ${pattern['resistance']:,.0f} ({dist_r:+.1f}%)")
            
            if levels:
                report += f"   {' | '.join(levels)}\n"
            
            if flag:
                report += f"   🚩 {flag['type']} → 目标 ${flag['target']:,.0f}\n"
            
            report += "\n"
            
        except Exception as e:
            report += f"❌ {symbol}: {str(e)}\n\n"
    
    return report


# ==========================================
# 📐 斐波那契回撤/延伸工具
# ==========================================

# 标准斐波那契比例
FIB_RETRACEMENT = [0.236, 0.382, 0.5, 0.618, 0.786]
FIB_EXTENSION = [1.0, 1.272, 1.618, 2.0, 2.618]


def _find_swing_points(df: pd.DataFrame, window: int = 5) -> Tuple[Dict, Dict]:
    """
    找到最近的波段高点和低点
    
    Args:
        df: K线数据
        window: 局部极值窗口
    
    Returns:
        (swing_high, swing_low) - 包含 index 和 price
    """
    high_points, low_points = _find_local_extremes(df, window=window)
    
    # 取最近的高点和低点
    if not high_points or not low_points:
        # 如果没有局部极值，用整体最高最低
        max_idx = df['high'].idxmax()
        min_idx = df['low'].idxmin()
        return (
            {'index': max_idx, 'price': df['high'].iloc[max_idx]},
            {'index': min_idx, 'price': df['low'].iloc[min_idx]}
        )
    
    # 找最近的重要高点和低点
    recent_high = max(high_points[-3:], key=lambda x: x['price']) if len(high_points) >= 3 else high_points[-1]
    recent_low = min(low_points[-3:], key=lambda x: x['price']) if len(low_points) >= 3 else low_points[-1]
    
    return recent_high, recent_low


def get_fibonacci_levels(symbol: str, timeframe: str = "1d", lookback: int = 100) -> str:
    """
    斐波那契回撤和延伸位计算
    
    自动识别最近波段的高低点，计算回撤位（找支撑）和延伸位（找目标）。
    
    Args:
        symbol: 代币符号 (如 "BTC", "ETH", "SOL")
        timeframe: 周期 (15m, 1h, 4h, 1d, 1w)
        lookback: 回看K线数量
    
    Returns:
        斐波那契分析报告
    """
    clean_symbol = symbol.upper().strip()
    
    # 获取当前价格
    price = _get_current_price(clean_symbol)
    if price is None:
        return f"无法获取 {clean_symbol} 的价格数据"
    
    # 获取K线数据
    df = _get_binance_klines(clean_symbol, timeframe, limit=lookback)
    if df is None or len(df) < 30:
        return f"无法获取 {clean_symbol} 的 {timeframe} K线数据"
    
    # 根据周期调整窗口大小
    window_map = {"15m": 3, "1h": 5, "4h": 5, "1d": 7, "1w": 10, "1M": 10}
    window = window_map.get(timeframe, 5)
    
    # 找波段高低点
    swing_high, swing_low = _find_swing_points(df, window=window)
    
    high_price = swing_high['price']
    low_price = swing_low['price']
    diff = high_price - low_price
    
    # 判断当前是上涨回调还是下跌反弹
    if swing_high['index'] > swing_low['index']:
        # 高点在后 = 上涨趋势，计算回调支撑
        trend = "uptrend"
        trend_label = "上涨回调"
    else:
        # 低点在后 = 下跌趋势，计算反弹阻力
        trend = "downtrend"
        trend_label = "下跌反弹"
    
    # 计算回撤位
    retracement_levels = {}
    for fib in FIB_RETRACEMENT:
        if trend == "uptrend":
            level = high_price - diff * fib
        else:
            level = low_price + diff * fib
        retracement_levels[fib] = level
    
    # 计算延伸位
    extension_levels = {}
    for fib in FIB_EXTENSION:
        if trend == "uptrend":
            level = high_price + diff * (fib - 1)  # 从高点向上延伸
        else:
            level = low_price - diff * (fib - 1)  # 从低点向下延伸
        extension_levels[fib] = level
    
    # 找当前价格最近的支撑和阻力
    all_levels = list(retracement_levels.values())
    supports = [l for l in all_levels if l < price]
    resistances = [l for l in all_levels if l > price]
    
    nearest_support = max(supports) if supports else None
    nearest_resistance = min(resistances) if resistances else None
    
    # 构建报告
    tf_label = {"15m": "15分钟", "1h": "1小时", "4h": "4小时", "1d": "日线", "1w": "周线", "1M": "月线"}.get(timeframe, timeframe)
    
    report = f"[{clean_symbol} 斐波那契分析 - {tf_label}]\n"
    report += "=" * 45 + "\n\n"
    
    report += f"💰 当前价格: ${price:,.2f}\n"
    report += f"📈 波段高点: ${high_price:,.0f}\n"
    report += f"📉 波段低点: ${low_price:,.0f}\n"
    report += f"📊 波段幅度: ${diff:,.0f} ({(diff/low_price)*100:.1f}%)\n"
    report += f"🔄 当前状态: {trend_label}\n\n"
    
    # 回撤位
    report += "📐 斐波那契回撤位:\n"
    for fib in FIB_RETRACEMENT:
        level = retracement_levels[fib]
        dist = ((price - level) / level) * 100
        
        # 标记关键位
        marker = ""
        if fib == 0.618:
            marker = " ⭐黄金分割"
        elif fib == 0.5:
            marker = " (心理价位)"
        
        # 标记当前价格位置
        position = ""
        if nearest_support and abs(level - nearest_support) < 1:
            position = " ← 最近支撑"
        elif nearest_resistance and abs(level - nearest_resistance) < 1:
            position = " ← 最近阻力"
        
        report += f"   {fib:.3f}: ${level:,.0f} (距离 {dist:+.1f}%){marker}{position}\n"
    
    report += "\n"
    
    # 延伸位
    report += "🎯 斐波那契延伸位:\n"
    for fib in FIB_EXTENSION:
        level = extension_levels[fib]
        dist = ((level - price) / price) * 100
        
        marker = ""
        if fib == 1.618:
            marker = " ⭐黄金延伸"
        
        report += f"   {fib:.3f}: ${level:,.0f} (距离 {dist:+.1f}%){marker}\n"
    
    report += "\n"
    
    # 交易建议
    report += "💡 交易参考:\n"
    if nearest_support:
        support_dist = ((price - nearest_support) / nearest_support) * 100
        report += f"   最近支撑: ${nearest_support:,.0f} ({support_dist:+.1f}%)\n"
    if nearest_resistance:
        resist_dist = ((nearest_resistance - price) / price) * 100
        report += f"   最近阻力: ${nearest_resistance:,.0f} (+{resist_dist:.1f}%)\n"
    
    if trend == "uptrend":
        report += f"   上涨趋势中，回调到 0.618 (${retracement_levels[0.618]:,.0f}) 是常见入场点\n"
    else:
        report += f"   下跌趋势中，反弹到 0.618 (${retracement_levels[0.618]:,.0f}) 可能遇阻\n"
    
    return report


def batch_fibonacci(symbols: str, timeframe: str = "1d") -> str:
    """
    批量斐波那契分析
    
    一次调用分析多个币种的斐波那契关键位。
    
    Args:
        symbols: 代币符号列表，逗号分隔 (如 "BTC,ETH,SOL")
        timeframe: 周期
    
    Returns:
        所有币种的斐波那契汇总报告
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    tf_label = {"15m": "15分钟", "1h": "1小时", "4h": "4小时", "1d": "日线", "1w": "周线"}.get(timeframe, timeframe)
    
    report = "=" * 50 + "\n"
    report += f"📐 批量斐波那契分析 ({tf_label})\n"
    report += "=" * 50 + "\n\n"
    
    for symbol in symbol_list:
        try:
            price = _get_current_price(symbol)
            if price is None:
                report += f"❌ {symbol}: 无法获取价格\n\n"
                continue
            
            df = _get_binance_klines(symbol, timeframe, limit=100)
            if df is None or len(df) < 30:
                report += f"❌ {symbol}: 数据不足\n\n"
                continue
            
            window_map = {"15m": 3, "1h": 5, "4h": 5, "1d": 7, "1w": 10}
            window = window_map.get(timeframe, 5)
            
            swing_high, swing_low = _find_swing_points(df, window=window)
            high_price = swing_high['price']
            low_price = swing_low['price']
            diff = high_price - low_price
            
            trend = "上涨回调" if swing_high['index'] > swing_low['index'] else "下跌反弹"
            
            # 计算关键的 0.618 位
            if swing_high['index'] > swing_low['index']:
                fib_618 = high_price - diff * 0.618
                fib_382 = high_price - diff * 0.382
            else:
                fib_618 = low_price + diff * 0.618
                fib_382 = low_price + diff * 0.382
            
            dist_618 = ((price - fib_618) / fib_618) * 100
            dist_382 = ((price - fib_382) / fib_382) * 100
            
            report += f"【{symbol}】 ${price:,.2f} | {trend}\n"
            report += f"   波段: ${low_price:,.0f} ~ ${high_price:,.0f}\n"
            report += f"   0.382: ${fib_382:,.0f} ({dist_382:+.1f}%) | 0.618: ${fib_618:,.0f} ({dist_618:+.1f}%)\n\n"
            
        except Exception as e:
            report += f"❌ {symbol}: {str(e)}\n\n"
    
    return report


# ==========================================
# 🎯 共振区识别工具 (Confluence Zones)
# ==========================================

import requests

def _get_ath(symbol: str) -> Optional[Dict]:
    """获取历史最高点 (ATH)"""
    coin_map = {
        'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana',
        'BNB': 'binancecoin', 'XRP': 'ripple', 'ADA': 'cardano',
        'DOGE': 'dogecoin', 'AVAX': 'avalanche-2', 'DOT': 'polkadot',
        'MATIC': 'matic-network', 'LINK': 'chainlink', 'UNI': 'uniswap'
    }
    
    coin_id = coin_map.get(symbol.upper())
    if not coin_id:
        # 尝试用K线数据获取
        df = _get_binance_klines(symbol, '1w', limit=260)
        if df is not None:
            return {'price': df['high'].max(), 'source': 'kline'}
        return None
    
    try:
        url = f'https://api.coingecko.com/api/v3/coins/{coin_id}'
        resp = requests.get(url, timeout=10)
        data = resp.json()
        return {
            'price': data['market_data']['ath']['usd'],
            'date': data['market_data']['ath_date']['usd'][:10],
            'source': 'coingecko'
        }
    except:
        # 回退到K线数据
        df = _get_binance_klines(symbol, '1w', limit=260)
        if df is not None:
            return {'price': df['high'].max(), 'source': 'kline'}
        return None


def _get_ema_levels(symbol: str, timeframe: str) -> Dict[str, float]:
    """获取EMA和Vegas通道关键位"""
    import pandas_ta as ta
    
    df = _get_binance_klines(symbol, timeframe, limit=250)
    if df is None or len(df) < 200:
        return {}
    
    levels = {}
    
    # EMA
    ema21 = ta.ema(df['close'], length=21)
    ema55 = ta.ema(df['close'], length=55)
    ema200 = ta.ema(df['close'], length=200)
    
    if ema21 is not None:
        levels['EMA21'] = ema21.iloc[-1]
    if ema55 is not None:
        levels['EMA55'] = ema55.iloc[-1]
    if ema200 is not None:
        levels['EMA200'] = ema200.iloc[-1]
    
    # Vegas通道
    if len(df) >= 170:
        ema144 = ta.ema(df['close'], length=144)
        ema169 = ta.ema(df['close'], length=169)
        if ema144 is not None and ema169 is not None:
            levels['Vegas上轨'] = max(ema144.iloc[-1], ema169.iloc[-1])
            levels['Vegas下轨'] = min(ema144.iloc[-1], ema169.iloc[-1])
    
    return levels


def find_confluence_zones(symbol: str, timeframe: str = "1d") -> str:
    """
    识别多指标共振区 (超稳区域)
    
    整合以下指标的关键位：
    - 密集成交区 (POC)
    - 斐波那契回撤位 (0.382/0.5/0.618)
    - EMA均线 (21/55/200)
    - Vegas通道
    - 历史最高点 (ATH)
    
    当多个指标在同一价格区域（±1.5%容差）重叠时，标记为共振区。
    
    Args:
        symbol: 代币符号 (如 "BTC", "ETH", "SOL")
        timeframe: 周期 (4h, 1d, 1w)
    
    Returns:
        综合分析报告，包含所有关键位和共振区
    """
    clean_symbol = symbol.upper().strip()
    
    # 获取当前价格
    price = _get_current_price(clean_symbol)
    if price is None:
        return f"无法获取 {clean_symbol} 的价格数据"
    
    # 收集所有关键位
    all_levels = []  # [(价格, 名称, 类型)]
    
    # 1. 获取ATH
    ath_data = _get_ath(clean_symbol)
    if ath_data:
        all_levels.append((ath_data['price'], 'ATH历史最高', 'resistance'))
    
    # 2. 获取EMA和Vegas
    ema_levels = _get_ema_levels(clean_symbol, timeframe)
    for name, level in ema_levels.items():
        level_type = 'support' if level < price else 'resistance'
        all_levels.append((level, name, level_type))
    
    # 3. 获取斐波那契
    df = _get_binance_klines(clean_symbol, timeframe, limit=100)
    if df is not None and len(df) >= 30:
        window_map = {"15m": 3, "1h": 5, "4h": 5, "1d": 7, "1w": 10}
        window = window_map.get(timeframe, 5)
        swing_high, swing_low = _find_swing_points(df, window=window)
        
        high_price = swing_high['price']
        low_price = swing_low['price']
        diff = high_price - low_price
        
        is_uptrend = swing_high['index'] > swing_low['index']
        
        for fib in [0.382, 0.5, 0.618]:
            if is_uptrend:
                level = high_price - diff * fib
            else:
                level = low_price + diff * fib
            level_type = 'support' if level < price else 'resistance'
            all_levels.append((level, f'Fib {fib}', level_type))
    
    # 4. 获取密集成交区 (简化版)
    if df is not None:
        price_high = df['high'].max()
        price_low = df['low'].min()
        price_range = price_high - price_low
        num_bins = 20
        bin_size = price_range / num_bins
        
        volume_by_level = {}
        for i in range(len(df)):
            typical_price = (df['high'].iloc[i] + df['low'].iloc[i] + df['close'].iloc[i]) / 3
            volume = df['volume'].iloc[i]
            bin_idx = int((typical_price - price_low) / bin_size)
            bin_idx = min(bin_idx, num_bins - 1)
            bin_center = price_low + (bin_idx + 0.5) * bin_size
            volume_by_level[bin_center] = volume_by_level.get(bin_center, 0) + volume
        
        sorted_levels = sorted(volume_by_level.items(), key=lambda x: x[1], reverse=True)
        total_volume = sum(volume_by_level.values())
        
        for level_price, level_volume in sorted_levels[:3]:
            vol_pct = (level_volume / total_volume) * 100
            if vol_pct >= 5:
                level_type = 'support' if level_price < price else 'resistance'
                all_levels.append((level_price, f'POC ({vol_pct:.0f}%)', level_type))
    
    # 5. 获取趋势线位置
    if df is not None:
        high_points, low_points = _find_local_extremes(df, window=5)
        cutoff = len(df) // 3
        recent_highs = [p for p in high_points if p['index'] > cutoff]
        recent_lows = [p for p in low_points if p['index'] > cutoff]
        
        uptrend = _fit_trendline(recent_lows, min_points=2, min_r_squared=0.5) if len(recent_lows) >= 2 else None
        if uptrend and uptrend['slope'] > 0:
            current_support = uptrend['slope'] * (len(df) - 1) + uptrend['intercept']
            all_levels.append((current_support, '上升趋势线', 'support'))
        
        downtrend = _fit_trendline(recent_highs, min_points=2, min_r_squared=0.5) if len(recent_highs) >= 2 else None
        if downtrend:
            current_resistance = downtrend['slope'] * (len(df) - 1) + downtrend['intercept']
            all_levels.append((current_resistance, '下降趋势线', 'resistance'))
    
    # 识别共振区 (容差 1.5%)
    tolerance = 0.015
    confluence_zones = []
    used = set()
    
    all_levels.sort(key=lambda x: x[0])
    
    for i, (level1, name1, type1) in enumerate(all_levels):
        if i in used:
            continue
        
        cluster = [(level1, name1, type1)]
        used.add(i)
        
        for j, (level2, name2, type2) in enumerate(all_levels):
            if j in used:
                continue
            if abs(level2 - level1) / level1 <= tolerance:
                cluster.append((level2, name2, type2))
                used.add(j)
        
        if len(cluster) >= 2:
            avg_price = sum(l[0] for l in cluster) / len(cluster)
            names = [l[1] for l in cluster]
            zone_type = 'support' if avg_price < price else 'resistance'
            confluence_zones.append({
                'price': avg_price,
                'indicators': names,
                'count': len(cluster),
                'type': zone_type
            })
    
    # 构建报告
    tf_label = {"15m": "15分钟", "1h": "1小时", "4h": "4小时", "1d": "日线", "1w": "周线"}.get(timeframe, timeframe)
    
    report = f"[{clean_symbol} 多指标共振分析 - {tf_label}]\n"
    report += "=" * 50 + "\n\n"
    
    report += f"💰 当前价格: ${price:,.2f}\n"
    if ath_data:
        ath_dist = ((price - ath_data['price']) / ath_data['price']) * 100
        report += f"📈 历史最高: ${ath_data['price']:,.0f} (距ATH {ath_dist:+.1f}%)\n"
    report += "\n"
    
    # 单个关键位
    report += "📊 所有关键位:\n"
    report += "-" * 40 + "\n"
    
    supports = [(l, n, t) for l, n, t in all_levels if t == 'support']
    resistances = [(l, n, t) for l, n, t in all_levels if t == 'resistance']
    
    supports.sort(key=lambda x: x[0], reverse=True)
    resistances.sort(key=lambda x: x[0])
    
    if resistances:
        report += "📕 阻力位 (由近到远):\n"
        for level, name, _ in resistances[:5]:
            dist = ((level - price) / price) * 100
            report += f"   ${level:,.0f} ({name}) +{dist:.1f}%\n"
    
    if supports:
        report += "📗 支撑位 (由近到远):\n"
        for level, name, _ in supports[:5]:
            dist = ((price - level) / level) * 100
            report += f"   ${level:,.0f} ({name}) -{dist:.1f}%\n"
    
    report += "\n"
    
    # 共振区
    if confluence_zones:
        confluence_zones.sort(key=lambda x: abs(x['price'] - price))
        
        report += "⭐ 共振区 (多指标重叠):\n"
        report += "-" * 40 + "\n"
        
        for zone in confluence_zones:
            dist = ((zone['price'] - price) / price) * 100
            strength = "🔥强" if zone['count'] >= 3 else "普通"
            zone_emoji = "📗" if zone['type'] == 'support' else "📕"
            
            report += f"{zone_emoji} ${zone['price']:,.0f} ({dist:+.1f}%) - {strength}共振\n"
            report += f"   重叠指标 ({zone['count']}个): {', '.join(zone['indicators'])}\n"
    else:
        report += "⚠️ 未发现明显共振区\n"
    
    report += "\n"
    
    # 交易建议
    report += "💡 交易参考:\n"
    
    # 最近的共振支撑和阻力
    confluence_supports = [z for z in confluence_zones if z['type'] == 'support']
    confluence_resistances = [z for z in confluence_zones if z['type'] == 'resistance']
    
    if confluence_supports:
        nearest = min(confluence_supports, key=lambda x: abs(x['price'] - price))
        dist = ((price - nearest['price']) / nearest['price']) * 100
        report += f"   共振支撑: ${nearest['price']:,.0f} ({dist:.1f}%)，做多参考\n"
    
    if confluence_resistances:
        nearest = min(confluence_resistances, key=lambda x: abs(x['price'] - price))
        dist = ((nearest['price'] - price) / price) * 100
        report += f"   共振阻力: ${nearest['price']:,.0f} (+{dist:.1f}%)，做空参考\n"
    
    return report


# ==========================================
# 🧪 测试入口
# ==========================================

if __name__ == "__main__":
    print("Testing BTC trendlines...")
    print(get_trendlines("BTC", "4h,1d"))
    print("\n" + "=" * 60 + "\n")
    
    print("Testing batch trendlines...")
    print(batch_trendlines("BTC,ETH,SOL"))
    print("\n" + "=" * 60 + "\n")
    
    print("Testing BTC fibonacci...")
    print(get_fibonacci_levels("BTC", "1d"))
    print("\n" + "=" * 60 + "\n")
    
    print("Testing batch fibonacci...")
    print(batch_fibonacci("BTC,ETH,SOL", "4h"))
    print("\n" + "=" * 60 + "\n")
    
    print("Testing confluence zones...")
    print(find_confluence_zones("BTC", "1d"))
