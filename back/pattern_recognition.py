"""
图表形态识别模块 (Chart Pattern Recognition)

提供趋势线识别、经典形态识别、波浪理论分析等高级技术分析功能。

Author: Crypto Agent System
Version: 1.0
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
    closes = df['close'].values
    
    # 使用scipy找局部极值
    local_max_idx = argrelextrema(highs, np.greater, order=window)[0]
    local_min_idx = argrelextrema(lows, np.less, order=window)[0]
    
    # 构建高点列表
    high_points = []
    for idx in local_max_idx:
        high_points.append({
            'index': int(idx),
            'price': float(highs[idx]),
            'date': df['time'].iloc[idx] if 'time' in df.columns else idx
        })
    
    # 构建低点列表
    low_points = []
    for idx in local_min_idx:
        low_points.append({
            'index': int(idx),
            'price': float(lows[idx]),
            'date': df['time'].iloc[idx] if 'time' in df.columns else idx
        })
    
    return high_points, low_points


def _fit_trendline(points: List[Dict], min_points: int = 3) -> Optional[Dict]:
    """
    用线性回归拟合趋势线
    
    Args:
        points: 点列表 [{'index': int, 'price': float}, ...]
        min_points: 最少需要的点数
    
    Returns:
        趋势线信息 或 None
    """
    if len(points) < min_points:
        return None
    
    x = np.array([p['index'] for p in points])
    y = np.array([p['price'] for p in points])
    
    # 线性回归
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    
    # R²太低说明拟合不好
    if abs(r_value) < 0.7:
        return None
    
    return {
        'slope': slope,
        'intercept': intercept,
        'r_squared': r_value ** 2,
        'points': points,
        'start_idx': int(min(x)),
        'end_idx': int(max(x)),
        'start_price': slope * min(x) + intercept,
        'end_price': slope * max(x) + intercept
    }


def _count_touches(df: pd.DataFrame, trendline: Dict, tolerance_pct: float = 1.0) -> int:
    """
    统计价格触碰趋势线的次数
    
    Args:
        df: K线数据
        trendline: 趋势线信息
        tolerance_pct: 容差百分比
    
    Returns:
        触碰次数
    """
    touches = 0
    for i in range(trendline['start_idx'], min(trendline['end_idx'] + 1, len(df))):
        trend_price = trendline['slope'] * i + trendline['intercept']
        
        # 检查高点或低点是否触碰趋势线
        high = df['high'].iloc[i]
        low = df['low'].iloc[i]
        
        tolerance = trend_price * (tolerance_pct / 100)
        
        if abs(high - trend_price) <= tolerance or abs(low - trend_price) <= tolerance:
            touches += 1
    
    return touches


# ==========================================
# 📈 趋势线识别
# ==========================================

def get_trendlines(symbol: str, timeframe: str = "1d", periods: int = 100) -> str:
    """
    自动识别上升和下降趋势线
    
    通过连接局部高点（下降趋势线）和低点（上升趋势线）来识别趋势。
    
    Args:
        symbol: 代币符号
        timeframe: 周期
        periods: 分析周期数
    
    Returns:
        趋势线分析报告
    """
    # 获取K线数据
    df = _get_binance_klines(symbol, timeframe, limit=periods)
    
    if df is None or len(df) < 50:
        return f"无法获取 {symbol} 的 {timeframe} K线数据"
    
    # 获取当前价格
    price = _get_current_price(symbol)
    if price is None:
        price = df['close'].iloc[-1]
    
    # 找出高低点
    high_points, low_points = _find_local_extremes(df, window=5)
    
    # 只使用后半部分的点来拟合（更相关）
    recent_highs = [p for p in high_points if p['index'] > len(df) // 3]
    recent_lows = [p for p in low_points if p['index'] > len(df) // 3]
    
    # 拟合上升趋势线（连接低点）
    uptrend = None
    if len(recent_lows) >= 3:
        # 尝试找到最佳的上升趋势线
        uptrend = _fit_trendline(recent_lows, min_points=3)
        if uptrend and uptrend['slope'] <= 0:
            uptrend = None  # 上升趋势线斜率必须为正
    
    # 拟合下降趋势线（连接高点）
    downtrend = None
    if len(recent_highs) >= 3:
        downtrend = _fit_trendline(recent_highs, min_points=3)
        if downtrend and downtrend['slope'] >= 0:
            downtrend = None  # 下降趋势线斜率必须为负
    
    # 构建报告
    tf_label = {"1M": "月线", "1w": "周线", "1d": "日线", "4h": "4小时"}.get(timeframe, timeframe)
    
    report = f"[{symbol} 趋势线分析 - {tf_label}]\n"
    report += "=" * 45 + "\n\n"
    
    report += f"💰 当前价格: ${price:,.2f}\n"
    report += f"📅 分析周期: 近{periods}根K线\n\n"
    
    # 上升趋势线
    report += "📈 上升趋势线 (连接低点):\n"
    if uptrend:
        touches = _count_touches(df, uptrend)
        current_support = uptrend['slope'] * (len(df) - 1) + uptrend['intercept']
        dist_to_support = ((price - current_support) / current_support) * 100
        
        # 计算趋势线斜率（每日涨幅百分比）
        daily_change = (uptrend['slope'] / uptrend['start_price']) * 100
        
        report += f"   ✅ 检测到有效上升趋势\n"
        report += f"   起点: ${uptrend['start_price']:,.0f}\n"
        report += f"   当前趋势线位置: ${current_support:,.0f}\n"
        report += f"   斜率: 每根K线+{daily_change:.2f}%\n"
        report += f"   触碰次数: {touches}次\n"
        report += f"   拟合度(R²): {uptrend['r_squared']:.2f}\n"
        report += f"   当前价距趋势线: {dist_to_support:+.1f}%\n"
        
        if dist_to_support < 3:
            report += f"   ⚠️ 价格接近趋势线支撑，关注能否守住\n"
        elif dist_to_support < 0:
            report += f"   🔴 价格已跌破上升趋势线！\n"
    else:
        report += "   ❌ 未检测到有效上升趋势线\n"
    
    report += "\n"
    
    # 下降趋势线
    report += "📉 下降趋势线 (连接高点):\n"
    if downtrend:
        touches = _count_touches(df, downtrend)
        current_resistance = downtrend['slope'] * (len(df) - 1) + downtrend['intercept']
        dist_to_resistance = ((price - current_resistance) / current_resistance) * 100
        
        daily_change = (downtrend['slope'] / downtrend['start_price']) * 100
        
        report += f"   ✅ 检测到有效下降趋势\n"
        report += f"   起点: ${downtrend['start_price']:,.0f}\n"
        report += f"   当前趋势线位置: ${current_resistance:,.0f}\n"
        report += f"   斜率: 每根K线{daily_change:.2f}%\n"
        report += f"   触碰次数: {touches}次\n"
        report += f"   拟合度(R²): {downtrend['r_squared']:.2f}\n"
        report += f"   当前价距趋势线: {dist_to_resistance:+.1f}%\n"
        
        if dist_to_resistance > -3 and dist_to_resistance < 0:
            report += f"   ⚠️ 价格接近趋势线阻力\n"
        elif dist_to_resistance > 0:
            report += f"   🟢 价格已突破下降趋势线！\n"
    else:
        report += "   ❌ 未检测到有效下降趋势线\n"
    
    # 综合判断
    report += "\n💡 趋势判断:\n"
    if uptrend and not downtrend:
        report += "   上升趋势中，关注趋势线支撑\n"
    elif downtrend and not uptrend:
        report += "   下降趋势中，关注趋势线阻力\n"
    elif uptrend and downtrend:
        # 收敛形态
        current_support = uptrend['slope'] * (len(df) - 1) + uptrend['intercept']
        current_resistance = downtrend['slope'] * (len(df) - 1) + downtrend['intercept']
        if current_support < price < current_resistance:
            width_pct = ((current_resistance - current_support) / current_support) * 100
            report += f"   ⚠️ 三角收敛形态，区间${current_support:,.0f}~${current_resistance:,.0f} ({width_pct:.1f}%)\n"
            report += f"   即将选择方向，关注突破\n"
    else:
        report += "   无明显趋势，可能处于震荡区间\n"
    
    return report


# ==========================================
# 🔍 经典形态识别
# ==========================================

def _detect_head_and_shoulders(high_points: List[Dict], low_points: List[Dict], 
                                current_price: float, is_top: bool = True) -> Optional[Dict]:
    """
    检测头肩形态
    
    Args:
        high_points: 高点列表
        low_points: 低点列表
        current_price: 当前价格
        is_top: True=头肩顶, False=头肩底
    
    Returns:
        形态信息 或 None
    """
    points = high_points if is_top else low_points
    valleys = low_points if is_top else high_points
    
    if len(points) < 3 or len(valleys) < 2:
        return None
    
    # 只看最近的点
    recent_points = points[-5:] if len(points) >= 5 else points
    
    # 找头肩结构: 中间点是极值
    for i in range(len(recent_points) - 2):
        left = recent_points[i]
        head = recent_points[i + 1]
        right = recent_points[i + 2]
        
        if is_top:
            # 头肩顶: 头 > 左肩, 头 > 右肩
            if head['price'] > left['price'] and head['price'] > right['price']:
                # 左右肩大致相等 (差异<10%)
                shoulder_diff = abs(left['price'] - right['price']) / left['price']
                if shoulder_diff < 0.1:
                    # 找颈线（两个低点）
                    neckline_points = [v for v in valleys 
                                       if left['index'] < v['index'] < right['index']]
                    if neckline_points:
                        neckline = min(p['price'] for p in neckline_points)
                        return {
                            'type': '头肩顶',
                            'left_shoulder': left,
                            'head': head,
                            'right_shoulder': right,
                            'neckline': neckline,
                            'target': neckline - (head['price'] - neckline),
                            'status': 'forming' if current_price > neckline else 'confirmed'
                        }
        else:
            # 头肩底: 头 < 左肩, 头 < 右肩
            if head['price'] < left['price'] and head['price'] < right['price']:
                shoulder_diff = abs(left['price'] - right['price']) / left['price']
                if shoulder_diff < 0.1:
                    neckline_points = [v for v in valleys 
                                       if left['index'] < v['index'] < right['index']]
                    if neckline_points:
                        neckline = max(p['price'] for p in neckline_points)
                        return {
                            'type': '头肩底',
                            'left_shoulder': left,
                            'head': head,
                            'right_shoulder': right,
                            'neckline': neckline,
                            'target': neckline + (neckline - head['price']),
                            'status': 'forming' if current_price < neckline else 'confirmed'
                        }
    
    return None


def _detect_double_top_bottom(high_points: List[Dict], low_points: List[Dict],
                               current_price: float, is_top: bool = True) -> Optional[Dict]:
    """
    检测双顶/双底形态
    """
    points = high_points if is_top else low_points
    valleys = low_points if is_top else high_points
    
    if len(points) < 2:
        return None
    
    # 检查最近两个高点/低点
    recent = points[-3:] if len(points) >= 3 else points
    
    for i in range(len(recent) - 1):
        p1 = recent[i]
        p2 = recent[i + 1]
        
        # 两个点价格接近 (差异<5%)
        price_diff = abs(p1['price'] - p2['price']) / p1['price']
        if price_diff < 0.05:
            # 中间有明显的回调/反弹
            middle_points = [v for v in valleys if p1['index'] < v['index'] < p2['index']]
            if middle_points:
                if is_top:
                    neckline = min(p['price'] for p in middle_points)
                    height = ((p1['price'] + p2['price']) / 2) - neckline
                    return {
                        'type': '双顶(M顶)',
                        'peak1': p1,
                        'peak2': p2,
                        'neckline': neckline,
                        'target': neckline - height,
                        'status': 'forming' if current_price > neckline else 'confirmed'
                    }
                else:
                    neckline = max(p['price'] for p in middle_points)
                    height = neckline - ((p1['price'] + p2['price']) / 2)
                    return {
                        'type': '双底(W底)',
                        'bottom1': p1,
                        'bottom2': p2,
                        'neckline': neckline,
                        'target': neckline + height,
                        'status': 'forming' if current_price < neckline else 'confirmed'
                    }
    
    return None


def detect_chart_patterns(symbol: str, timeframe: str = "1d", periods: int = 100) -> str:
    """
    检测经典图表形态
    
    支持识别：头肩顶/底、双顶/底
    
    Args:
        symbol: 代币符号
        timeframe: 周期
        periods: 分析周期数
    
    Returns:
        形态识别报告
    """
    # 获取K线数据
    df = _get_binance_klines(symbol, timeframe, limit=periods)
    
    if df is None or len(df) < 50:
        return f"无法获取 {symbol} 的 {timeframe} K线数据"
    
    # 获取当前价格
    price = _get_current_price(symbol)
    if price is None:
        price = df['close'].iloc[-1]
    
    # 找出高低点
    high_points, low_points = _find_local_extremes(df, window=5)
    
    # 检测各种形态
    patterns_found = []
    
    # 头肩顶
    hs_top = _detect_head_and_shoulders(high_points, low_points, price, is_top=True)
    if hs_top:
        patterns_found.append(hs_top)
    
    # 头肩底
    hs_bottom = _detect_head_and_shoulders(high_points, low_points, price, is_top=False)
    if hs_bottom:
        patterns_found.append(hs_bottom)
    
    # 双顶
    double_top = _detect_double_top_bottom(high_points, low_points, price, is_top=True)
    if double_top:
        patterns_found.append(double_top)
    
    # 双底
    double_bottom = _detect_double_top_bottom(high_points, low_points, price, is_top=False)
    if double_bottom:
        patterns_found.append(double_bottom)
    
    # 构建报告
    tf_label = {"1M": "月线", "1w": "周线", "1d": "日线", "4h": "4小时"}.get(timeframe, timeframe)
    
    report = f"[{symbol} 形态识别 - {tf_label}]\n"
    report += "=" * 45 + "\n\n"
    
    report += f"💰 当前价格: ${price:,.2f}\n"
    report += f"📅 分析周期: 近{periods}根K线\n"
    report += f"📊 检测到的局部高点: {len(high_points)}个\n"
    report += f"📊 检测到的局部低点: {len(low_points)}个\n\n"
    
    if not patterns_found:
        report += "🔍 形态检测结果:\n"
        report += "   未检测到明显的经典形态\n"
        report += "   ↳ 可能处于趋势运行或震荡整理中\n"
    else:
        report += f"🔍 检测到 {len(patterns_found)} 个形态:\n\n"
        
        for i, pattern in enumerate(patterns_found, 1):
            pattern_type = pattern['type']
            
            if '头肩' in pattern_type:
                report += f"📐 形态 {i}: {pattern_type}\n"
                report += f"   左肩: ${pattern['left_shoulder']['price']:,.0f}\n"
                report += f"   头部: ${pattern['head']['price']:,.0f}\n"
                report += f"   右肩: ${pattern['right_shoulder']['price']:,.0f}\n"
                report += f"   颈线: ${pattern['neckline']:,.0f}\n"
                report += f"   状态: {'形成中' if pattern['status'] == 'forming' else '已确认'}\n"
                report += f"   目标位: ${pattern['target']:,.0f}\n"
                
                if '顶' in pattern_type:
                    report += f"   ⚠️ 看跌信号！跌破颈线${pattern['neckline']:,.0f}确认\n"
                else:
                    report += f"   🟢 看涨信号！突破颈线${pattern['neckline']:,.0f}确认\n"
            
            elif '双' in pattern_type:
                report += f"📐 形态 {i}: {pattern_type}\n"
                if '顶' in pattern_type:
                    report += f"   第一个顶: ${pattern['peak1']['price']:,.0f}\n"
                    report += f"   第二个顶: ${pattern['peak2']['price']:,.0f}\n"
                else:
                    report += f"   第一个底: ${pattern['bottom1']['price']:,.0f}\n"
                    report += f"   第二个底: ${pattern['bottom2']['price']:,.0f}\n"
                report += f"   颈线: ${pattern['neckline']:,.0f}\n"
                report += f"   状态: {'形成中' if pattern['status'] == 'forming' else '已确认'}\n"
                report += f"   目标位: ${pattern['target']:,.0f}\n"
                
                if '顶' in pattern_type:
                    report += f"   ⚠️ 看跌信号！跌破颈线${pattern['neckline']:,.0f}确认\n"
                else:
                    report += f"   🟢 看涨信号！突破颈线${pattern['neckline']:,.0f}确认\n"
            
            report += "\n"
    
    # 交易建议
    report += "💡 操作建议:\n"
    bearish_patterns = [p for p in patterns_found if '顶' in p['type']]
    bullish_patterns = [p for p in patterns_found if '底' in p['type']]
    
    if bearish_patterns:
        p = bearish_patterns[0]
        report += f"   📕 看跌形态：关注颈线${p['neckline']:,.0f}，跌破则看向${p['target']:,.0f}\n"
    if bullish_patterns:
        p = bullish_patterns[0]
        report += f"   📗 看涨形态：关注颈线${p['neckline']:,.0f}，突破则看向${p['target']:,.0f}\n"
    if not patterns_found:
        report += "   暂无明显形态信号，建议结合趋势线和均线分析\n"
    
    return report


# ==========================================
# 🌊 波浪理论分析
# ==========================================

def _identify_significant_pivots(df: pd.DataFrame, threshold_pct: float = 5.0) -> List[Dict]:
    """
    识别重要的价格转折点（用于波浪分析）
    
    Args:
        df: K线数据
        threshold_pct: 最小波动幅度百分比
    
    Returns:
        转折点列表
    """
    pivots = []
    
    # 找到局部极值
    high_points, low_points = _find_local_extremes(df, window=7)
    
    # 合并所有极值点
    all_points = []
    for hp in high_points:
        hp['type'] = 'high'
        all_points.append(hp)
    for lp in low_points:
        lp['type'] = 'low'
        all_points.append(lp)
    
    # 按时间排序
    all_points.sort(key=lambda x: x['index'])
    
    # 过滤掉幅度太小的波动
    filtered = []
    for i, point in enumerate(all_points):
        if i == 0:
            filtered.append(point)
            continue
        
        last = filtered[-1]
        
        # 如果相邻两点类型相同，保留更极端的那个
        if point['type'] == last['type']:
            if point['type'] == 'high':
                if point['price'] > last['price']:
                    filtered[-1] = point
            else:
                if point['price'] < last['price']:
                    filtered[-1] = point
        else:
            # 检查幅度是否足够
            change_pct = abs(point['price'] - last['price']) / last['price'] * 100
            if change_pct >= threshold_pct:
                filtered.append(point)
    
    return filtered


def _classify_wave_structure(pivots: List[Dict], current_price: float) -> Dict:
    """
    将转折点分类为波浪结构
    
    Args:
        pivots: 转折点列表
        current_price: 当前价格
    
    Returns:
        波浪结构信息
    """
    if len(pivots) < 4:
        return {'status': 'insufficient_data'}
    
    # 判断大趋势方向
    first_pivot = pivots[0]
    last_pivot = pivots[-1]
    
    if last_pivot['price'] > first_pivot['price']:
        main_trend = 'bullish'
    else:
        main_trend = 'bearish'
    
    # 尝试识别5浪结构
    waves = []
    wave_num = 1
    
    for i in range(1, len(pivots)):
        prev = pivots[i-1]
        curr = pivots[i]
        
        change_pct = (curr['price'] - prev['price']) / prev['price'] * 100
        
        waves.append({
            'number': wave_num,
            'start_price': prev['price'],
            'end_price': curr['price'],
            'start_date': prev.get('date', 'N/A'),
            'end_date': curr.get('date', 'N/A'),
            'change_pct': change_pct,
            'direction': 'up' if change_pct > 0 else 'down'
        })
        
        wave_num += 1
        if wave_num > 5:
            break
    
    # 分析是否符合波浪规则
    analysis = {
        'main_trend': main_trend,
        'waves': waves,
        'wave_count': len(waves),
        'status': 'analyzing'
    }
    
    # 检查波浪规则
    if len(waves) >= 3:
        # 第3浪通常不是最短的
        if len(waves) >= 3:
            wave1_len = abs(waves[0]['change_pct'])
            wave3_len = abs(waves[2]['change_pct'])
            if main_trend == 'bullish':
                if wave3_len > wave1_len:
                    analysis['rule_wave3_longest'] = True
                else:
                    analysis['rule_wave3_longest'] = False
    
    # 判断当前位置
    if waves:
        last_wave = waves[-1]
        if main_trend == 'bullish':
            if last_wave['direction'] == 'up':
                if len(waves) in [1, 3, 5]:
                    analysis['current_position'] = f'第{len(waves)}浪运行中'
                else:
                    analysis['current_position'] = f'第{len(waves)}浪调整中'
            else:
                if len(waves) in [2, 4]:
                    analysis['current_position'] = f'第{len(waves)}浪调整中'
                else:
                    analysis['current_position'] = f'可能进入A-B-C调整'
        else:
            analysis['current_position'] = '下跌趋势中'
    
    return analysis


def analyze_wave_structure(symbol: str, timeframe: str = "1d", periods: int = 200) -> str:
    """
    分析波浪结构（艾略特波浪理论基础版）
    
    识别5浪推动结构和当前所处位置。
    
    Args:
        symbol: 代币符号
        timeframe: 周期
        periods: 分析周期数
    
    Returns:
        波浪分析报告
    """
    # 获取K线数据
    df = _get_binance_klines(symbol, timeframe, limit=periods)
    
    if df is None or len(df) < 100:
        return f"无法获取 {symbol} 的 {timeframe} K线数据，或数据不足"
    
    # 获取当前价格
    price = _get_current_price(symbol)
    if price is None:
        price = df['close'].iloc[-1]
    
    # 识别重要转折点
    pivots = _identify_significant_pivots(df, threshold_pct=8.0)
    
    if len(pivots) < 4:
        return f"{symbol} 在该周期内转折点太少，无法进行波浪分析"
    
    # 分类波浪结构
    wave_analysis = _classify_wave_structure(pivots, price)
    
    # 构建报告
    tf_label = {"1M": "月线", "1w": "周线", "1d": "日线", "4h": "4小时"}.get(timeframe, timeframe)
    
    report = f"[{symbol} 波浪分析 - {tf_label}]\n"
    report += "=" * 45 + "\n\n"
    
    report += f"💰 当前价格: ${price:,.2f}\n"
    report += f"📅 分析周期: 近{periods}根K线\n"
    report += f"🔍 识别到 {len(pivots)} 个重要转折点\n\n"
    
    # 大趋势判断
    if wave_analysis.get('main_trend') == 'bullish':
        report += "📊 大级别趋势: 🟢 上升推动浪\n\n"
    else:
        report += "📊 大级别趋势: 🔴 下降推动浪\n\n"
    
    # 波浪结构
    waves = wave_analysis.get('waves', [])
    if waves:
        report += "🌊 波浪结构:\n"
        report += "-" * 30 + "\n"
        
        for wave in waves:
            direction_emoji = "📈" if wave['change_pct'] > 0 else "📉"
            
            report += f"   第{wave['number']}浪: "
            report += f"${wave['start_price']:,.0f} → ${wave['end_price']:,.0f} "
            report += f"({wave['change_pct']:+.1f}%) {direction_emoji}\n"
        
        report += "\n"
    
    # 当前位置
    if 'current_position' in wave_analysis:
        report += f"📍 当前位置: {wave_analysis['current_position']}\n\n"
    
    # 波浪规则检查
    report += "📐 波浪规则检查:\n"
    if wave_analysis.get('rule_wave3_longest'):
        report += "   ✅ 第3浪是最长的推动浪（符合规则）\n"
    elif wave_analysis.get('rule_wave3_longest') == False:
        report += "   ⚠️ 第3浪不是最长的（可能结构不完整）\n"
    
    # 预测和建议
    report += "\n💡 分析建议:\n"
    
    wave_count = len(waves)
    main_trend = wave_analysis.get('main_trend', 'unknown')
    
    if main_trend == 'bullish':
        if wave_count <= 2:
            report += "   处于上升趋势早期，第3浪可能即将展开\n"
            report += "   ↳ 第3浪通常最强劲，可考虑顺势做多\n"
        elif wave_count == 3 or wave_count == 4:
            report += "   上升趋势中期，关注第5浪目标\n"
            if waves and len(waves) >= 1:
                wave1_height = abs(waves[0]['end_price'] - waves[0]['start_price'])
                target = waves[-1]['end_price'] + wave1_height * 1.618
                report += f"   ↳ 参考目标（1.618延伸）: ${target:,.0f}\n"
        elif wave_count >= 5:
            report += "   ⚠️ 可能接近5浪末端，警惕A-B-C调整\n"
            report += "   ↳ 建议设好止盈，减少仓位\n"
    else:
        report += "   下跌趋势中，建议规避风险或寻找做空机会\n"
        report += "   ↳ 等待下跌5浪完成后可能有反弹\n"
    
    return report


# ==========================================
# 🧪 测试入口
# ==========================================

if __name__ == "__main__":
    print("Testing BTC trendlines...")
    print(get_trendlines("BTC"))
    print("\n" + "=" * 60 + "\n")
    
    print("Testing BTC patterns...")
    print(detect_chart_patterns("BTC"))
    print("\n" + "=" * 60 + "\n")
    
    print("Testing BTC wave analysis...")
    print(analyze_wave_structure("BTC"))
