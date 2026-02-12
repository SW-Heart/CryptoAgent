"""
Technical Analysis Aggregator Tool

This module aggregates various technical analysis tools into a single entry point
to reduce the number of tool calls required by the agent.

Supports two output formats:
- "text" (default): Full text report for human reading
- "compact": Condensed JSON for agent consumption (saves ~83% tokens)
"""
from typing import Dict, Any, List, Optional
import json
import pandas as pd
import pandas_ta as ta

# Import underlying technical analysis tools
from technical_analysis import (
    get_multi_timeframe_analysis,
    get_volume_analysis,
    get_volume_profile,
    _get_binance_klines,
    _get_current_price
)
from pattern_recognition import (
    get_trendlines,
    find_confluence_zones,
    _find_local_extremes,
    _fit_trendline,
    _classify_trendline_pattern
)
from indicator_memory import get_indicator_reliability, _calculate_indicator_stats

# ============= Macro & Account Helpers for Super Aggregator =============
import requests

def _get_macro_data() -> Dict:
    """
    Fetch macro market data (Fear & Greed Index, BTC Dominance, Market Phase).
    Returns compact dict for agent consumption.
    """
    result = {
        "fng": None,
        "fng_label": None,
        "btc_dom": None,
        "market_phase": None
    }
    
    try:
        # Fear & Greed Index
        fng_url = "https://api.alternative.me/fng/?limit=1"
        fng_data = requests.get(fng_url, timeout=5).json()['data'][0]
        result["fng"] = int(fng_data['value'])
        result["fng_label"] = fng_data['value_classification']
    except:
        pass
    
    try:
        # BTC Dominance from CoinGecko
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = "https://api.coingecko.com/api/v3/global"
        data = requests.get(url, headers=headers, timeout=5).json()['data']
        btc_dom = data['market_cap_percentage']['btc']
        result["btc_dom"] = round(btc_dom, 1)
        
        # Market phase determination
        if btc_dom < 45:
            result["market_phase"] = "山寨季"
        elif btc_dom < 55:
            result["market_phase"] = "平衡"
        else:
            result["market_phase"] = "BTC主导"
    except:
        pass
    
    return result


def _get_account_summary(user_id: str = None) -> Dict:
    """
    Fetch account balance and positions summary.
    Returns compact dict for agent consumption.
    """
    result = {
        "balance": 0,
        "positions": []
    }
    
    try:
        from tools.binance_trading_tools import binance_get_positions_summary
        
        summary = binance_get_positions_summary(user_id=user_id)
        if "error" not in summary:
            # 使用 margin_balance（总权益）而不是 available_balance（可用余额）
            # 这样 Agent 才能正确计算仓位大小
            result["balance"] = summary.get("margin_balance", 0)
            result["available"] = summary.get("available_balance", 0)
            
            for pos in summary.get("open_positions", []):
                result["positions"].append({
                    "symbol": pos.get("symbol", "").replace("USDT", ""),
                    "dir": "L" if pos.get("direction") == "LONG" else "S",
                    "pnl": pos.get("unrealized_pnl", 0),
                    "roi": pos.get("roi_percent", 0)
                })
    except Exception as e:
        result["error"] = str(e)
    
    return result




def _get_compact_trend_data(symbol: str, timeframes: List[str], price: float) -> Dict:
    """
    Extract compact trend structure data for a symbol.
    
    Returns structured dict instead of text report.
    """
    result = {
        "direction": "neutral",
        "strength": "weak",
        "ema_bull": 0,
        "ema_bear": 0,
        "vegas_above": 0,
        "vegas_below": 0,
        "macd_bull": 0,
        "macd_bear": 0,
        "timeframes": {}
    }
    
    for tf in timeframes:
        df = _get_binance_klines(symbol, tf)
        if df is None or len(df) < 50:
            continue
        
        tf_data = {"ema": "neutral", "vegas": "neutral", "macd": "neutral"}
        
        try:
            # EMA analysis
            ema21 = ta.ema(df['close'], length=21)
            ema55 = ta.ema(df['close'], length=55)
            ema200 = ta.ema(df['close'], length=200) if len(df) >= 200 else None
            
            ema21_val = ema21.iloc[-1] if ema21 is not None else None
            ema55_val = ema55.iloc[-1] if ema55 is not None else None
            ema200_val = ema200.iloc[-1] if ema200 is not None else None
            
            # Save specific EMA values
            if ema21_val: tf_data["ema21"] = round(ema21_val, 2)
            if ema55_val: tf_data["ema55"] = round(ema55_val, 2)
            if ema200_val: tf_data["ema200"] = round(ema200_val, 2)
            
            if ema21_val and ema55_val and ema200_val:
                if price > ema21_val > ema55_val > ema200_val:
                    tf_data["ema"] = "bullish"
                    result["ema_bull"] += 1
                elif price < ema21_val < ema55_val < ema200_val:
                    tf_data["ema"] = "bearish"
                    result["ema_bear"] += 1
                    
            # Vegas channel (Three Tubes)
            # Tube 1: EMA 144/169
            # Tube 2: EMA 288/338
            # Tube 3: EMA 576/676
            tf_data["vegas"] = {}
            
            if len(df) >= 170:
                ema144 = ta.ema(df['close'], length=144).iloc[-1]
                ema169 = ta.ema(df['close'], length=169).iloc[-1]
                tf_data["vegas"]["channel1"] = {
                    "top": round(max(ema144, ema169), 2),
                    "bot": round(min(ema144, ema169), 2)
                }
                
                # Update legacy vegas status based on Channel 1
                channel1_top = max(ema144, ema169)
                channel1_bot = min(ema144, ema169)
                
                if price > channel1_top:
                    tf_data["vegas_status"] = "above"
                    result["vegas_above"] += 1
                elif price < channel1_bot:
                    tf_data["vegas_status"] = "below"
                    result["vegas_below"] += 1
                else:
                    tf_data["vegas_status"] = "inside"
            
            if len(df) >= 340:
                ema288 = ta.ema(df['close'], length=288).iloc[-1]
                ema338 = ta.ema(df['close'], length=338).iloc[-1]
                tf_data["vegas"]["channel2"] = {
                    "top": round(max(ema288, ema338), 2),
                    "bot": round(min(ema288, ema338), 2)
                }
                
            if len(df) >= 680:
                ema576 = ta.ema(df['close'], length=576).iloc[-1]
                ema676 = ta.ema(df['close'], length=676).iloc[-1]
                tf_data["vegas"]["channel3"] = {
                    "top": round(max(ema576, ema676), 2),
                    "bot": round(min(ema576, ema676), 2)
                }
                    
            # MACD
            macd_result = ta.macd(df['close'], fast=12, slow=26, signal=9)
            if macd_result is not None:
                macd_line = macd_result.iloc[-1, 0]
                signal_line = macd_result.iloc[-1, 1]
                if macd_line > signal_line:
                    tf_data["macd"] = "bullish"
                    result["macd_bull"] += 1
                else:
                    tf_data["macd"] = "bearish"
                    result["macd_bear"] += 1
                    
        except Exception:
            pass
        
        result["timeframes"][tf] = tf_data
    
    # Determine overall direction
    total_bull = result["ema_bull"] + result["vegas_above"] + result["macd_bull"]
    total_bear = result["ema_bear"] + result["vegas_below"] + result["macd_bear"]
    total_signals = total_bull + total_bear
    
    if total_signals > 0:
        if total_bull > total_bear * 2:
            result["direction"] = "bullish"
            result["strength"] = "strong"
        elif total_bull > total_bear:
            result["direction"] = "bullish"
            result["strength"] = "moderate"
        elif total_bear > total_bull * 2:
            result["direction"] = "bearish"
            result["strength"] = "strong"
        elif total_bear > total_bull:
            result["direction"] = "bearish"
            result["strength"] = "moderate"
    
    return result


def _get_compact_levels(symbol: str, timeframe: str, price: float) -> Dict:
    """
    Extract key support/resistance levels in compact format.
    """
    result = {
        "nearest_support": None,
        "nearest_resistance": None,
        "confluence_zones": []
    }
    
    df = _get_binance_klines(symbol, timeframe, limit=100)
    if df is None or len(df) < 30:
        return result
    
    all_levels = []
    
    try:
        # 1. Current timeframe EMA levels
        ema21 = ta.ema(df['close'], length=21)
        ema55 = ta.ema(df['close'], length=55)
        ema200 = ta.ema(df['close'], length=200) if len(df) >= 200 else None
        
        if ema21 is not None:
            all_levels.append((ema21.iloc[-1], f"EMA21_{timeframe}"))
        if ema55 is not None:
            all_levels.append((ema55.iloc[-1], f"EMA55_{timeframe}"))
        if ema200 is not None:
            all_levels.append((ema200.iloc[-1], f"EMA200_{timeframe}"))
            
        # 2. Multi-timeframe EMA levels (Key Feature)
        # We want to know where EMA21/55 are on other frames like 4h, 1d, 1w
        for tf in ["4h", "1d", "1w"]:
            if tf == timeframe: continue # Skip if already added
            
            df_tf = _get_binance_klines(symbol, tf)
            if df_tf is not None and len(df_tf) >= 55:
                # EMA 21 & 55
                ema21_tf = ta.ema(df_tf['close'], length=21).iloc[-1]
                ema55_tf = ta.ema(df_tf['close'], length=55).iloc[-1]
                all_levels.append((ema21_tf, f"EMA21_{tf}"))
                all_levels.append((ema55_tf, f"EMA55_{tf}"))
                
                # Vegas Channel Top/Bottom (EMA 144/169)
                if len(df_tf) >= 170:
                    ema144_tf = ta.ema(df_tf['close'], length=144).iloc[-1]
                    ema169_tf = ta.ema(df_tf['close'], length=169).iloc[-1]
                    all_levels.append((max(ema144_tf, ema169_tf), f"VegasTop_{tf}"))
                    all_levels.append((min(ema144_tf, ema169_tf), f"VegasBot_{tf}"))
        
        # 3. Fibonacci levels
        from pattern_recognition import _find_swing_points
        swing_high, swing_low = _find_swing_points(df, window=7)
        high_price = swing_high['price']
        low_price = swing_low['price']
        diff = high_price - low_price
        
        is_uptrend = swing_high['index'] > swing_low['index']
        for fib in [0.382, 0.5, 0.618]:
            if is_uptrend:
                level = high_price - diff * fib
            else:
                level = low_price + diff * fib
            all_levels.append((level, f"Fib_{fib}"))
        
    except Exception:
        pass
    
    # Find nearest support and resistance
    supports = [(l, n) for l, n in all_levels if l < price]
    resistances = [(l, n) for l, n in all_levels if l > price]
    
    if supports:
        supports.sort(key=lambda x: x[0], reverse=True)
        nearest = supports[0]
        result["nearest_support"] = {
            "price": round(nearest[0], 2),
            "dist_pct": round(((price - nearest[0]) / price) * 100, 1),
            "source": nearest[1]
        }
    
    if resistances:
        resistances.sort(key=lambda x: x[0])
        nearest = resistances[0]
        result["nearest_resistance"] = {
            "price": round(nearest[0], 2),
            "dist_pct": round(((nearest[0] - price) / price) * 100, 1),
            "source": nearest[1]
        }
    
    # Find confluence zones (levels within 1.5% of each other)
    all_levels.sort(key=lambda x: x[0])
    used = set()
    tolerance = 0.015
    
    for i, (level1, name1) in enumerate(all_levels):
        if i in used:
            continue
        cluster = [(level1, name1)]
        used.add(i)
        
        for j, (level2, name2) in enumerate(all_levels):
            if j in used:
                continue
            if level1 > 0 and abs(level2 - level1) / level1 <= tolerance:
                cluster.append((level2, name2))
                used.add(j)
        
        if len(cluster) >= 2:
            avg_price = sum(l[0] for l in cluster) / len(cluster)
            dist_pct = ((avg_price - price) / price) * 100
            result["confluence_zones"].append({
                "price": round(avg_price, 2),
                "dist_pct": round(dist_pct, 1),
                "type": "support" if avg_price < price else "resistance",
                "indicators": [n for _, n in cluster]
            })
    
    return result


def _get_compact_volume(symbol: str, timeframe: str) -> Dict:
    """
    Extract volume analysis in compact format.
    """
    result = {
        "ratio": 0,
        "status": "normal",
        "divergence": None,
        "flow": "neutral"
    }
    
    df = _get_binance_klines(symbol, timeframe)
    if df is None or len(df) < 50:
        return result
    
    try:
        vol_col = 'quote_volume' if 'quote_volume' in df.columns else 'volume'
        current_volume = df[vol_col].iloc[-1]
        avg_volume_20 = df[vol_col].iloc[-20:].mean()
        
        result["ratio"] = round(current_volume / avg_volume_20, 2) if avg_volume_20 > 0 else 0
        
        if result["ratio"] >= 2.0:
            result["status"] = "very_high"
        elif result["ratio"] >= 1.5:
            result["status"] = "high"
        elif result["ratio"] >= 0.8:
            result["status"] = "normal"
        elif result["ratio"] >= 0.5:
            result["status"] = "low"
        else:
            result["status"] = "very_low"
        
        # Volume/price divergence
        recent_closes = df['close'].iloc[-5:].values
        recent_volumes = df[vol_col].iloc[-5:].values
        price_up = recent_closes[-1] > recent_closes[0]
        volume_up = recent_volumes[-1] > recent_volumes[0]
        
        if price_up and not volume_up and result["ratio"] < 0.8:
            result["divergence"] = "bearish"  # Price up but volume down
        elif not price_up and volume_up and result["ratio"] > 1.2:
            result["divergence"] = "panic_sell"  # Price down with high volume
        elif price_up and volume_up:
            result["divergence"] = "healthy_up"
        elif not price_up and not volume_up:
            result["divergence"] = "normal_pullback"
        
        # Money flow
        vol_sum_up = 0
        vol_sum_down = 0
        for i in range(1, min(20, len(df))):
            if df['close'].iloc[-i] > df['close'].iloc[-i-1]:
                vol_sum_up += df[vol_col].iloc[-i]
            else:
                vol_sum_down += df[vol_col].iloc[-i]
        
        if vol_sum_up > vol_sum_down * 1.5:
            result["flow"] = "inflow"
        elif vol_sum_down > vol_sum_up * 1.5:
            result["flow"] = "outflow"
        
    except Exception:
        pass
    
    return result


def _get_compact_pattern(symbol: str, timeframe: str, price: float) -> Dict:
    """
    Extract pattern/trendline info in compact format.
    """
    result = {
        "name": None,
        "bias": "neutral",
        "support": None,
        "resistance": None
    }
    
    df = _get_binance_klines(symbol, timeframe, limit=100)
    if df is None or len(df) < 50:
        return result
    
    try:
        window = 7 if timeframe in ["1d", "1w", "1M"] else 5
        high_points, low_points = _find_local_extremes(df, window=window)
        
        cutoff = len(df) // 3
        recent_highs = [p for p in high_points if p['index'] > cutoff]
        recent_lows = [p for p in low_points if p['index'] > cutoff]
        
        uptrend = None
        if len(recent_lows) >= 2:
            uptrend = _fit_trendline(recent_lows, min_points=2, min_r_squared=0.5)
            if uptrend and uptrend['slope'] < 0:
                uptrend = None
        
        downtrend = None
        if len(recent_highs) >= 2:
            downtrend = _fit_trendline(recent_highs, min_points=2, min_r_squared=0.5)
        
        current_idx = len(df) - 1
        pattern_info = _classify_trendline_pattern(uptrend, downtrend, current_idx, price)
        
        result["name"] = pattern_info.get('pattern')
        result["bias"] = pattern_info.get('bias', 'neutral')
        if pattern_info.get('support'):
            result["support"] = round(pattern_info['support'], 2)
        if pattern_info.get('resistance'):
            result["resistance"] = round(pattern_info['resistance'], 2)
        
    except Exception:
        pass
    
    return result


def _get_compact_reliability(symbol: str, timeframe: str) -> Dict:
    """
    Extract indicator reliability in compact format.
    """
    result = {
        "best_indicator": None,
        "role": None,
        "rate_60d": 0,
        "advice": None
    }
    
    try:
        stats = _calculate_indicator_stats(symbol, timeframe)
        if "error" in stats:
            return result
        
        best = stats.get("current_best")
        if best:
            result["best_indicator"] = best
            result["rate_60d"] = stats.get("best_rate", 0)
            
            best_recent = stats.get(best, {}).get("recent_60d", {})
            result["role"] = best_recent.get("current_role", "neutral")
            
            support_rate = best_recent.get("support_hold_rate", 0)
            resistance_rate = best_recent.get("resistance_hold_rate", 0)
            
            if result["role"] == "支撑" and support_rate >= 60:
                result["advice"] = f"回踩{best}可入场"
            elif result["role"] == "阻力" and resistance_rate >= 60:
                result["advice"] = f"触碰{best}应止盈"
            
    except Exception:
        pass
    
    return result


def _generate_summary(trend: Dict, levels: Dict, volume: Dict, reliability: Dict) -> str:
    """Generate a one-line summary for quick agent understanding."""
    parts = []
    
    # Trend summary
    if trend["direction"] != "neutral":
        emoji = "📈" if trend["direction"] == "bullish" else "📉"
        strength = "强势" if trend["strength"] == "strong" else ""
        parts.append(f"{emoji}{strength}{trend['direction']}")
        
        total = trend["ema_bull"] + trend["ema_bear"] + trend["vegas_above"] + trend["vegas_below"]
        if trend["direction"] == "bearish":
            bear_count = trend["ema_bear"] + trend["vegas_below"] + trend["macd_bear"]
            parts.append(f"({bear_count}/{total}指标看空)")
        else:
            bull_count = trend["ema_bull"] + trend["vegas_above"] + trend["macd_bull"]
            parts.append(f"({bull_count}/{total}指标看多)")
    else:
        parts.append("⚖️震荡")
    
    # Key level
    if levels.get("nearest_support"):
        s = levels["nearest_support"]
        parts.append(f"支撑${s['price']:,.0f}({s['dist_pct']:+.1f}%)")
    if levels.get("nearest_resistance"):
        r = levels["nearest_resistance"]
        parts.append(f"阻力${r['price']:,.0f}(+{r['dist_pct']:.1f}%)")
    
    # Volume alert
    if volume["status"] in ["very_high", "very_low"]:
        vol_emoji = "🔥" if volume["status"] == "very_high" else "💤"
        parts.append(f"{vol_emoji}量比{volume['ratio']}x")
    
    return " ".join(parts)


def get_all_technical_indicators(
    symbols: str, 
    timeframe: str = "4h",
    extra_timeframes: str = "1d,1w",
    deep_analysis: bool = False,
    output_format: str = "text",
    include_account: bool = False
) -> str:
    """
    Get all technical indicators for one or more symbols in a single call.
    
    This tool aggregates:
    1. Multi-timeframe trend analysis (MA/EMA, MACD, etc.)
    2. Volume analysis (Volume profile, Volume/Price divergence)
    3. Pattern recognition (Trendlines, Channels)
    4. Confluence zones (Key levels, Fibs)
    5. Indicator reliability checking
    6. (Optional) Macro market data (Fear & Greed, BTC Dominance)
    7. (Optional) Account balance and positions summary
    
    Args:
        symbols: Comma-separated list of symbols (e.g., "BTC,ETH,SOL") or single symbol ("BTC").
        timeframe: Primary analysis timeframe (default: "1d").
        extra_timeframes: Secondary timeframes for multi-period analysis (default: "4h,1h").
        deep_analysis: Whether to perform deep analysis (more computationally expensive).
        output_format: "text" for full report (default), "compact" for condensed JSON (~83% smaller).
        include_account: If True, also fetch macro data and account/positions summary (recommended for strategy analysis).
        
    Returns:
        String containing structured reports for all requested symbols.
        If output_format="compact", returns JSON string for token-efficient agent consumption.
    """
    symbol_list = [s.strip().upper() for s in symbols.split(',') if s.strip()]
    if not symbol_list:
        return "Error: No valid symbols provided."
    
    tf_list = [timeframe] + [tf.strip() for tf in extra_timeframes.split(',') if tf.strip()]
    
    # Compact mode: return condensed JSON
    if output_format == "compact":
        compact_result = {}
        
        for symbol in symbol_list:
            price = _get_current_price(symbol)
            if price is None:
                compact_result[symbol] = {"error": "无法获取价格"}
                continue
            
            trend = _get_compact_trend_data(symbol, tf_list, price)
            levels = _get_compact_levels(symbol, timeframe, price)
            volume = _get_compact_volume(symbol, timeframe)
            pattern = _get_compact_pattern(symbol, timeframe, price)
            reliability = _get_compact_reliability(symbol, timeframe)
            
            compact_result[symbol] = {
                "price": round(price, 2),
                "trend": {
                    "direction": trend["direction"],
                    "strength": trend["strength"],
                    "ema_aligned": f"{trend['ema_bull']}b/{trend['ema_bear']}s",
                    "vegas": f"{trend['vegas_above']}a/{trend['vegas_below']}b",
                    "macd": f"{trend['macd_bull']}b/{trend['macd_bear']}s"
                },
                "levels": levels,
                "volume": volume,
                "pattern": pattern,
                "reliability": reliability,
                "summary": _generate_summary(trend, levels, volume, reliability)
            }
        
        # Add macro and account data if requested
        if include_account:
            compact_result["macro"] = _get_macro_data()
            compact_result["account"] = _get_account_summary()
        
        return json.dumps(compact_result, ensure_ascii=False, separators=(',', ':'))
    
    # Text mode: original full report
    final_report = []
    
    for symbol in symbol_list:
        report_section = [f"\n{'='*40}"]
        report_section.append(f"📊 COMPREHENSIVE ANALYSIS: {symbol}")
        report_section.append(f"{'='*40}\n")
        
        try:
            # 1. Multi-Timeframe Analysis (The Core Trend)
            mta = get_multi_timeframe_analysis(symbol, timeframes=f"{timeframe},{extra_timeframes}", deep_analysis=deep_analysis)
            report_section.append("--- 1. TREND STRUCTURE (Multi-Timeframe) ---")
            report_section.append(str(mta))
            report_section.append("")

            # 2. Confluence Zones (Support/Resistance)
            confluence = find_confluence_zones(symbol, timeframe=timeframe)
            report_section.append("--- 2. CONFLUENCE ZONES (Support/Resistance) ---")
            report_section.append(str(confluence))
            report_section.append("")

            # 3. Volume Analysis
            vol = get_volume_analysis(symbol, timeframe=timeframe)
            report_section.append("--- 3. VOLUME ANALYSIS ---")
            report_section.append(str(vol))
            report_section.append("")

            # 4. Pattern / Trendlines
            patterns = get_trendlines(symbol, timeframes=timeframe)
            report_section.append("--- 4. PATTERNS & TRENDLINES ---")
            report_section.append(str(patterns))
            report_section.append("")

            # 5. Indicator Reliability
            reliability = get_indicator_reliability(symbol, timeframe=timeframe)
            report_section.append("--- 5. HISTORICAL RELIABILITY ---")
            report_section.append(str(reliability))
            
        except Exception as e:
            report_section.append(f"❌ Error analyzing {symbol}: {str(e)}")
            
        final_report.append("\n".join(report_section))
        
    return "\n\n".join(final_report)
