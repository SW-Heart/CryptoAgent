"""
指标历史规律记忆模块 (Indicator Memory System)

使用阿里云OSS存储各币种对不同技术指标的历史遵循统计数据。
支持分时段统计（近60天/180天/365天），智能识别当前最适用的指标。

Author: Crypto Agent System
Version: 1.0
"""

import os
import json
import oss2
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
import pandas_ta as ta
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 导入技术分析基础设施
from technical_analysis import _get_binance_klines, _get_current_price


# ==========================================
# 🔧 OSS 配置
# ==========================================

# 从环境变量读取OSS配置
OSS_ACCESS_KEY_ID = os.getenv("ALIYUN_OSS_ACCESS_KEY_ID", "")
OSS_ACCESS_KEY_SECRET = os.getenv("ALIYUN_OSS_ACCESS_KEY_SECRET", "")
OSS_ENDPOINT = os.getenv("ALIYUN_OSS_ENDPOINT", "oss-cn-hangzhou.aliyuncs.com")
OSS_BUCKET_NAME = os.getenv("ALIYUN_OSS_BUCKET_NAME", "")
OSS_INDICATOR_FILE = "crypto_agent/indicator_memory.json"


def _get_oss_bucket() -> Optional[oss2.Bucket]:
    """获取OSS Bucket对象"""
    if not OSS_ACCESS_KEY_ID or not OSS_ACCESS_KEY_SECRET or not OSS_BUCKET_NAME:
        print("Warning: OSS配置不完整，使用本地缓存模式")
        return None
    
    auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
    bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET_NAME)
    return bucket


def _load_memory_from_oss() -> Dict:
    """从OSS加载记忆数据"""
    bucket = _get_oss_bucket()
    if bucket is None:
        return _load_memory_local()
    
    try:
        result = bucket.get_object(OSS_INDICATOR_FILE)
        content = result.read().decode('utf-8')
        return json.loads(content)
    except oss2.exceptions.NoSuchKey:
        return {}
    except Exception as e:
        print(f"OSS读取失败: {e}")
        return _load_memory_local()


def _save_memory_to_oss(data: Dict) -> bool:
    """保存记忆数据到OSS"""
    bucket = _get_oss_bucket()
    if bucket is None:
        return _save_memory_local(data)
    
    try:
        content = json.dumps(data, ensure_ascii=False, indent=2)
        bucket.put_object(OSS_INDICATOR_FILE, content.encode('utf-8'))
        # 同时保存本地备份
        _save_memory_local(data)
        return True
    except Exception as e:
        print(f"OSS写入失败: {e}")
        return _save_memory_local(data)


# 本地备份
LOCAL_MEMORY_FILE = os.path.join(os.path.dirname(__file__), "data", "indicator_memory.json")


def _load_memory_local() -> Dict:
    """从本地加载记忆数据（备份）"""
    try:
        if os.path.exists(LOCAL_MEMORY_FILE):
            with open(LOCAL_MEMORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}


def _save_memory_local(data: Dict) -> bool:
    """保存到本地（备份）"""
    try:
        os.makedirs(os.path.dirname(LOCAL_MEMORY_FILE), exist_ok=True)
        with open(LOCAL_MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, ensure_ascii=False, indent=2, fp=f)
        return True
    except Exception as e:
        print(f"本地写入失败: {e}")
        return False


# ==========================================
# 📊 指标触碰分析
# ==========================================

def _analyze_indicator_touches(df: pd.DataFrame, indicator_name: str, 
                                indicator_values: pd.Series) -> Dict:
    """
    分析价格对某个指标的触碰和反弹情况
    
    分别统计：
    - 从上方触碰（支撑测试）：价格在均线上方，回踩均线后是否反弹
    - 从下方触碰（阻力测试）：价格在均线下方，反弹到均线后是否受阻
    
    Args:
        df: K线数据
        indicator_name: 指标名称
        indicator_values: 指标值序列
    
    Returns:
        包含支撑/阻力分别统计的字典
    """
    # 支撑测试统计（从上方触碰）
    support_tests = 0
    support_holds = 0  # 支撑有效（触碰后上涨）
    support_breaks = 0  # 支撑失效（触碰后下跌）
    
    # 阻力测试统计（从下方触碰）
    resistance_tests = 0
    resistance_holds = 0  # 阻力有效（触碰后下跌）
    resistance_breaks = 0  # 阻力失效（突破上涨）
    
    # 确保足够的数据
    if len(df) < 30:
        return {
            "touches": 0, "bounces": 0, "breaks": 0, "rate": 0,
            "support_tests": 0, "support_hold_rate": 0,
            "resistance_tests": 0, "resistance_hold_rate": 0,
            "current_role": "unknown"
        }
    
    # 从第22根K线开始（确保EMA有值），到倒数第6根结束（需要5根K线观察结果）
    for i in range(22, len(df) - 5):
        try:
            indicator_val = indicator_values.iloc[i]
            if pd.isna(indicator_val) or indicator_val == 0:
                continue
            
            # 当前K线
            low = df['low'].iloc[i]
            high = df['high'].iloc[i]
            close = df['close'].iloc[i]
            
            # 前一根K线的收盘价（判断之前价格在均线上方还是下方）
            prev_close = df['close'].iloc[i - 1]
            prev_indicator = indicator_values.iloc[i - 1]
            
            # 判断触碰：K线的最高到最低之间是否包含均线价格
            if low <= indicator_val <= high:
                
                # 检查5根K线后的反应
                future_close = df['close'].iloc[i + 5]
                change_pct = ((future_close - close) / close) * 100
                
                # 判断是支撑测试还是阻力测试
                # 关键：看触碰前价格在均线哪一侧
                if prev_close > prev_indicator:
                    # 之前价格在均线上方 → 这是回踩支撑
                    support_tests += 1
                    
                    if change_pct > 1.0:  # 触碰后上涨 = 支撑有效
                        support_holds += 1
                    elif change_pct < -1.0:  # 触碰后下跌 = 支撑失效
                        support_breaks += 1
                else:
                    # 之前价格在均线下方 → 这是反弹测试阻力
                    resistance_tests += 1
                    
                    if change_pct < -1.0:  # 触碰后下跌 = 阻力有效
                        resistance_holds += 1
                    elif change_pct > 1.0:  # 触碰后上涨 = 突破阻力
                        resistance_breaks += 1
                        
        except Exception:
            continue
    
    # 计算成功率
    support_hold_rate = (support_holds / support_tests * 100) if support_tests > 0 else 0
    resistance_hold_rate = (resistance_holds / resistance_tests * 100) if resistance_tests > 0 else 0
    
    # 判断当前角色
    total_touches = support_tests + resistance_tests
    if resistance_tests > support_tests and resistance_hold_rate > 50:
        current_role = "阻力"  # 最近主要是阻力测试，且阻力有效
    elif support_tests > resistance_tests and support_hold_rate > 50:
        current_role = "支撑"  # 最近主要是支撑测试，且支撑有效
    elif resistance_tests > 0 and resistance_hold_rate > support_hold_rate:
        current_role = "阻力"
    elif support_tests > 0:
        current_role = "支撑"
    else:
        current_role = "中性"
    
    # 综合成功率（向后兼容）
    total_holds = support_holds + resistance_holds
    total_breaks = support_breaks + resistance_breaks
    overall_rate = (total_holds / total_touches * 100) if total_touches > 0 else 0
    
    return {
        # 兼容旧格式
        "touches": total_touches,
        "bounces": total_holds,
        "breaks": total_breaks,
        "rate": round(overall_rate, 1),
        # 新增：分类统计
        "support_tests": support_tests,
        "support_holds": support_holds,
        "support_hold_rate": round(support_hold_rate, 1),
        "resistance_tests": resistance_tests,
        "resistance_holds": resistance_holds,
        "resistance_hold_rate": round(resistance_hold_rate, 1),
        "current_role": current_role
    }


def _calculate_indicator_stats(symbol: str, timeframe: str = "1d") -> Dict:
    """
    计算某币种在某周期的各指标统计数据
    
    Args:
        symbol: 币种
        timeframe: 周期
    
    Returns:
        各指标的分时段统计
    """
    # 获取足够的K线数据（至少400根以覆盖1年+EMA200计算）
    df = _get_binance_klines(symbol, timeframe, limit=500)
    
    if df is None or len(df) < 200:
        return {"error": "数据不足"}
    
    # 计算各种指标
    ema21 = ta.ema(df['close'], length=21)
    ema55 = ta.ema(df['close'], length=55)
    ema200 = ta.ema(df['close'], length=200)
    ema144 = ta.ema(df['close'], length=144)
    ema169 = ta.ema(df['close'], length=169)
    
    indicators = {
        "EMA21": ema21,
        "EMA55": ema55,
        "EMA200": ema200,
        "Vegas_Mid": (ema144 + ema169) / 2  # Vegas通道中轨
    }
    
    # 时间段定义
    periods = {
        "recent_60d": 60,
        "mid_180d": 180,
        "long_365d": 365
    }
    
    result = {}
    
    for ind_name, ind_values in indicators.items():
        result[ind_name] = {}
        
        for period_name, days in periods.items():
            # 截取对应时间段的数据
            period_df = df.iloc[-days:] if len(df) >= days else df
            period_ind = ind_values.iloc[-days:] if len(ind_values) >= days else ind_values
            
            stats = _analyze_indicator_touches(period_df, ind_name, period_ind)
            result[ind_name][period_name] = stats
    
    # 找出当前最佳指标（基于近60天成功率）
    best_indicator = None
    best_rate = 0
    
    for ind_name, ind_data in result.items():
        recent = ind_data.get("recent_60d", {})
        if recent.get("touches", 0) >= 2:  # 至少有2次触碰才算有效
            if recent.get("rate", 0) > best_rate:
                best_rate = recent.get("rate", 0)
                best_indicator = ind_name
    
    result["current_best"] = best_indicator
    result["best_rate"] = best_rate
    result["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # 生成分析结论
    result["analysis"] = _generate_analysis(result)
    
    return result


def _generate_analysis(stats: Dict) -> str:
    """生成分析结论"""
    best = stats.get("current_best")
    if not best:
        return "近期触碰次数不足，暂无可靠结论"
    
    recent_rate = stats.get(best, {}).get("recent_60d", {}).get("rate", 0)
    mid_rate = stats.get(best, {}).get("mid_180d", {}).get("rate", 0)
    
    # 检查趋势变化
    trend_change = ""
    for ind_name in ["EMA21", "EMA55", "EMA200", "Vegas_Mid"]:
        if ind_name == best:
            continue
        other_mid = stats.get(ind_name, {}).get("mid_180d", {}).get("rate", 0)
        other_recent = stats.get(ind_name, {}).get("recent_60d", {}).get("rate", 0)
        
        # 如果其他指标在中期更好但近期变差
        if other_mid > mid_rate and other_recent < recent_rate:
            trend_change = f"市场风格已从{ind_name}转向{best}"
            break
    
    analysis = f"近60天{best}成功率{recent_rate}%"
    if trend_change:
        analysis += f"，{trend_change}"
    
    return analysis


# ==========================================
# 🎯 主工具函数
# ==========================================

def get_indicator_reliability(symbol: str, timeframe: str = "1d", 
                               force_refresh: bool = False) -> str:
    """
    获取某币种的指标可靠性分析
    
    分析各技术指标（EMA21/55/200、Vegas通道）在不同时间段的表现，
    找出当前最可靠的指标作为交易参考。
    
    Args:
        symbol: 代币符号 (如 BTC, ETH)
        timeframe: 周期 (1d, 4h)
        force_refresh: 是否强制刷新（忽略缓存）
    
    Returns:
        指标可靠性分析报告
    """
    symbol = symbol.upper().strip()
    
    # 加载记忆数据
    memory = _load_memory_from_oss()
    
    # 检查缓存
    cache_key = f"{symbol}_{timeframe}"
    cached = memory.get(cache_key)
    
    if cached and not force_refresh:
        # 检查是否过期（超过24小时需刷新）
        updated_at = cached.get("updated_at", "")
        if updated_at:
            try:
                updated_time = datetime.strptime(updated_at, "%Y-%m-%d %H:%M")
                if datetime.now() - updated_time < timedelta(hours=24):
                    # 使用缓存
                    return _format_report(symbol, timeframe, cached)
            except:
                pass
    
    # 计算新数据
    stats = _calculate_indicator_stats(symbol, timeframe)
    
    if "error" in stats:
        return f"无法获取 {symbol} 的K线数据进行分析"
    
    # 保存到记忆
    memory[cache_key] = stats
    _save_memory_to_oss(memory)
    
    return _format_report(symbol, timeframe, stats)


def _format_report(symbol: str, timeframe: str, stats: Dict) -> str:
    """格式化输出报告"""
    tf_label = {"1d": "日线", "4h": "4小时", "1w": "周线"}.get(timeframe, timeframe)
    
    report = f"[{symbol} 指标可靠性分析 - {tf_label}]\n"
    report += "=" * 50 + "\n\n"
    
    # 当前最佳指标
    best = stats.get("current_best")
    best_rate = stats.get("best_rate", 0)
    
    if best:
        report += f"🏆 当前最可靠指标: {best} (近60天成功率 {best_rate}%)\n"
        report += f"📊 分析: {stats.get('analysis', '')}\n\n"
    else:
        report += "⚠️ 近期触碰数据不足，暂无明确结论\n\n"
    
    # 各指标详情
    report += "📈 各指标分时段统计:\n"
    report += "-" * 40 + "\n"
    
    for ind_name in ["EMA21", "EMA55", "EMA200", "Vegas_Mid"]:
        ind_data = stats.get(ind_name, {})
        if not ind_data:
            continue
        
        is_best = "⭐" if ind_name == best else "  "
        report += f"{is_best}{ind_name}:\n"
        
        for period_name, period_label in [("recent_60d", "近60天"), 
                                           ("mid_180d", "近180天"), 
                                           ("long_365d", "近365天")]:
            period_stats = ind_data.get(period_name, {})
            touches = period_stats.get("touches", 0)
            
            # 新格式：分别显示支撑和阻力测试
            support_tests = period_stats.get("support_tests", 0)
            support_rate = period_stats.get("support_hold_rate", 0)
            resistance_tests = period_stats.get("resistance_tests", 0)
            resistance_rate = period_stats.get("resistance_hold_rate", 0)
            current_role = period_stats.get("current_role", "")
            
            if touches > 0:
                role_emoji = "🛡️" if current_role == "支撑" else ("🚧" if current_role == "阻力" else "")
                report += f"     {period_label}: {role_emoji}当前角色={current_role}\n"
                if support_tests > 0:
                    report += f"        支撑测试: {support_tests}次, 有效率{support_rate}%\n"
                if resistance_tests > 0:
                    report += f"        阻力测试: {resistance_tests}次, 有效率{resistance_rate}%\n"
            else:
                report += f"     {period_label}: 无触碰记录\n"
        
        report += "\n"
    
    # 交易建议
    report += "💡 交易建议:\n"
    
    # 获取近60天最佳指标的角色
    if best:
        best_recent = stats.get(best, {}).get("recent_60d", {})
        best_role = best_recent.get("current_role", "中性")
        resistance_rate = best_recent.get("resistance_hold_rate", 0)
        support_rate = best_recent.get("support_hold_rate", 0)
        
        if best_role == "阻力" and resistance_rate >= 60:
            report += f"   ⚠️ {best}目前是强阻力（{resistance_rate}%有效率）\n"
            report += f"   → 触碰{best}时多单应止盈，站稳再做多\n"
        elif best_role == "支撑" and support_rate >= 60:
            report += f"   ✅ {best}目前是可靠支撑（{support_rate}%有效率）\n"
            report += f"   → 回踩{best}可考虑入场做多\n"
        elif best_role == "阻力":
            report += f"   ⚠️ {best}目前偏向阻力，需警惕\n"
        else:
            report += f"   {best}有一定参考价值，但需结合其他信号确认\n"
    else:
        report += f"   近期指标参考性不足，建议观望或使用其他分析方法\n"
    
    report += f"\n⏰ 更新时间: {stats.get('updated_at', 'N/A')}\n"
    
    return report


def get_indicator_reliability_all_timeframes(symbol: str, force_refresh: bool = False) -> str:
    """
    多周期汇总分析 - 对比所有周期的指标遵循程度
    
    同时分析月线、周线、日线、4小时的EMA遵循情况，
    找出在哪个周期上哪个指标最可靠。
    
    Args:
        symbol: 代币符号 (如 BTC, ETH)
        force_refresh: 是否强制刷新
    
    Returns:
        多周期汇总分析报告
    """
    symbol = symbol.upper().strip()
    
    timeframes = ["1w", "1d", "4h"]  # 月线数据量可能不足，暂不包含
    tf_labels = {"1w": "周线", "1d": "日线", "4h": "4小时"}
    
    memory = _load_memory_from_oss()
    all_stats = {}
    
    # 获取各周期数据
    for tf in timeframes:
        cache_key = f"{symbol}_{tf}"
        cached = memory.get(cache_key)
        
        need_refresh = force_refresh
        if cached and not force_refresh:
            updated_at = cached.get("updated_at", "")
            if updated_at:
                try:
                    updated_time = datetime.strptime(updated_at, "%Y-%m-%d %H:%M")
                    if datetime.now() - updated_time > timedelta(hours=24):
                        need_refresh = True
                except:
                    need_refresh = True
            else:
                need_refresh = True
        else:
            need_refresh = True
        
        if need_refresh:
            stats = _calculate_indicator_stats(symbol, tf)
            if "error" not in stats:
                memory[cache_key] = stats
                all_stats[tf] = stats
        else:
            all_stats[tf] = cached
    
    # 保存更新
    _save_memory_to_oss(memory)
    
    # 构建汇总报告
    report = f"[{symbol} 多周期指标可靠性汇总]\n"
    report += "=" * 55 + "\n\n"
    
    # 汇总表格：每个指标在各周期的近60天成功率
    report += "📊 各周期近60天成功率对比:\n"
    report += "-" * 55 + "\n"
    report += f"{'指标':<12} | {'周线':<12} | {'日线':<12} | {'4小时':<12}\n"
    report += "-" * 55 + "\n"
    
    indicators = ["EMA21", "EMA55", "EMA200", "Vegas_Mid"]
    best_overall = None
    best_overall_rate = 0
    best_tf = None
    
    for ind_name in indicators:
        row = f"{ind_name:<12} |"
        for tf in timeframes:
            tf_stats = all_stats.get(tf, {})
            ind_stats = tf_stats.get(ind_name, {})
            recent = ind_stats.get("recent_60d", {})
            
            touches = recent.get("touches", 0)
            rate = recent.get("rate", 0)
            
            if touches >= 2:
                cell = f" {rate:.0f}% ({touches}次)"
                # 追踪最佳
                if rate > best_overall_rate:
                    best_overall_rate = rate
                    best_overall = ind_name
                    best_tf = tf
            else:
                cell = " -"
            
            row += f"{cell:<12} |"
        
        report += row + "\n"
    
    report += "-" * 55 + "\n\n"
    
    # 最佳推荐
    report += "🏆 最可靠指标推荐:\n"
    if best_overall and best_overall_rate > 0:
        report += f"   {tf_labels.get(best_tf, best_tf)} {best_overall}: 成功率 {best_overall_rate:.0f}%\n\n"
    else:
        report += "   近期触碰数据不足，暂无明确推荐\n\n"
    
    # 各周期最佳
    report += "📈 各周期最佳指标:\n"
    for tf in timeframes:
        tf_stats = all_stats.get(tf, {})
        tf_best = tf_stats.get("current_best")
        tf_rate = tf_stats.get("best_rate", 0)
        
        if tf_best:
            report += f"   {tf_labels.get(tf, tf)}: {tf_best} ({tf_rate:.0f}%)\n"
        else:
            report += f"   {tf_labels.get(tf, tf)}: 数据不足\n"
    
    report += "\n"
    
    # 风格变化分析
    report += "💡 交易建议:\n"
    
    # 检查是否有周期间的差异
    daily_best = all_stats.get("1d", {}).get("current_best")
    h4_best = all_stats.get("4h", {}).get("current_best")
    
    if daily_best and h4_best:
        if daily_best == h4_best:
            report += f"   日线和4小时都遵循{daily_best}，信号一致性强\n"
        else:
            report += f"   日线遵循{daily_best}，4小时遵循{h4_best}，注意周期选择\n"
    
    if best_overall and best_overall_rate >= 70:
        report += f"   当前最推荐在{tf_labels.get(best_tf, best_tf)}用{best_overall}做支撑/阻力参考\n"
    else:
        report += f"   各周期成功率偏低，建议谨慎使用均线信号\n"
    
    return report


# ==========================================
# 🧪 测试入口
# ==========================================

if __name__ == "__main__":
    print("Testing BTC indicator reliability...")
    print(get_indicator_reliability("BTC"))
    print("\n" + "=" * 60 + "\n")
    print("Testing BTC all timeframes...")
    print(get_indicator_reliability_all_timeframes("BTC"))
