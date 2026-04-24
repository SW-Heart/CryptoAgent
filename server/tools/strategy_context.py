"""
统一策略数据引擎 (Strategy Context Engine)

将 Agent 所需的全部数据（账户、持仓、宏观、技术指标等）聚合为一次调用。
模块分为「必选」（始终加载）和「可选」（用户在前台策略配置中勾选）。

Usage:
    build_strategy_context(
        symbols="BTC,ETH",
        timeframes="4h,1d",
        enabled_modules="trend,levels,volume"
    )
"""
import json
import os
import time as _time
from typing import Dict, List, Any

import pandas as pd
import pandas_ta as ta

# ============ 底层数据源导入 ============
from analysis.technical import (
    _get_binance_klines,
    _get_current_price,
)
from analysis.pattern import (
    _find_local_extremes,
    _fit_trendline,
    _classify_trendline_pattern,
    _find_swing_points,
)
from analysis.indicator import _calculate_indicator_stats

import requests

# 统一的交易客户端获取入口（支持 trader_instance_id 上下文隔离）
from tools.trading._client import _get_trading_client


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 模块注册表
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STRATEGY_MODULES = {
    # ========== 必选模块 (always_on=True) ==========
    "account": {
        "name": "账户状态",
        "description": "余额、可用资金、总权益",
        "category": "core",
        "always_on": True,
        "icon": "💰",
    },
    "positions": {
        "name": "持仓信息",
        "description": "当前持仓方向、保证金、未实现盈亏、ROI",
        "category": "core",
        "always_on": True,
        "icon": "📊",
    },
    "macro": {
        "name": "市场宏观",
        "description": "恐贪指数、BTC支配率、市场阶段判断",
        "category": "core",
        "always_on": True,
        "icon": "🌍",
    },
    "funding": {
        "name": "资金费率",
        "description": "持仓币种的当前资金费率，用于判断市场倾向",
        "category": "core",
        "always_on": True,
        "icon": "💸",
    },

    # ========== 可选模块 (用户在前台策略配置中勾选) ==========
    "trend": {
        "name": "趋势结构",
        "description": "多周期 EMA 排列、Vegas 通道位置、MACD 动能方向",
        "category": "technical",
        "always_on": False,
        "default_on": True,
        "icon": "📈",
    },
    "levels": {
        "name": "支撑阻力",
        "description": "多周期 EMA/Fibonacci 关键价位、汇聚区识别",
        "category": "technical",
        "always_on": False,
        "default_on": True,
        "icon": "📐",
    },
    "volume": {
        "name": "量能分析",
        "description": "量比、量价背离检测、资金流向判断",
        "category": "technical",
        "always_on": False,
        "default_on": True,
        "icon": "📊",
    },
    "pattern": {
        "name": "形态识别",
        "description": "趋势线拟合、通道/三角/旗形等经典形态",
        "category": "technical",
        "always_on": False,
        "default_on": False,
        "icon": "🔺",
    },
    "reliability": {
        "name": "指标可靠性",
        "description": "基于历史数据统计各指标的支撑/阻力有效率",
        "category": "technical",
        "always_on": False,
        "default_on": False,
        "icon": "🎯",
    },
    "volatility": {
        "name": "波动率分析",
        "description": "ATR 波幅、波动率比率、布林带挤压、自适应止损建议",
        "category": "technical",
        "always_on": False,
        "default_on": False,
        "icon": "🌊",
    },
    "derivatives": {
        "name": "合约数据",
        "description": "持仓量 (OI) 变化、全网多空比、大户持仓比",
        "category": "technical",
        "always_on": False,
        "default_on": True,
        "icon": "📉",
    },
    "news": {
        "name": "重要新闻",
        "description": "监控24小时内市场突发与重磅(Trump/Fed)预警事件",
        "category": "technical",
        "always_on": False,
        "default_on": True,
        "icon": "📰",
    },
}


def get_available_modules() -> list:
    """返回所有可用模块的列表（供前端 API 使用）。"""
    result = []
    for module_id, info in STRATEGY_MODULES.items():
        result.append({
            "id": module_id,
            "name": info["name"],
            "description": info["description"],
            "category": info["category"],
            "always_on": info["always_on"],
            "default_on": info.get("default_on", False),
            "icon": info["icon"],
            "warning": info.get("warning"),
        })
    return result


def get_default_enabled_modules() -> list:
    """返回默认启用的可选模块 ID 列表。"""
    return [
        mid for mid, info in STRATEGY_MODULES.items()
        if not info["always_on"] and info.get("default_on", False)
    ]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 统一入口
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_strategy_context(
    symbols: str,
    timeframes: str = "4h,1d",
    enabled_modules: str = "trend,levels,volume",
    user_id: str = None,
) -> str:
    """
    一次性构建 Agent 策略分析所需的全部上下文数据。

    这是交易策略 Agent 的【唯一数据入口】。
    根据策略配置中启用的模块，聚合：
    - 账户余额与持仓（必选）
    - 市场宏观指标（必选）
    - 资金费率（必选）
    - 用户选择的技术指标模块（可选）

    所有数据一次性返回，Agent 无需再调用其他数据工具。

    Args:
        symbols: 逗号分隔的标的列表 (如 "BTC,ETH,SOL")
        timeframes: 分析周期，逗号分隔 (如 "4h,1d")
        enabled_modules: 启用的可选技术分析模块 ID，逗号分隔
                         (如 "trend,levels,volume,pattern")
        user_id: 用户 ID (通常由系统自动注入)

    Returns:
        JSON 字符串，包含所有请求模块的聚合数据
    """
    # 如果 LLM 没传 user_id，自动从线程上下文获取
    if not user_id:
        from tools.trading_tools import get_current_user
        user_id = get_current_user()
        if user_id:
            print(f"[StrategyContext] user_id auto-resolved from context: {user_id[:8]}...")
        else:
            print(f"[StrategyContext] ⚠️ WARNING: user_id is None! LLM did not pass it AND context is empty.")
    else:
        print(f"[StrategyContext] user_id provided by caller: {user_id[:8]}...")

    # 解析参数
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    tf_list = [t.strip() for t in timeframes.split(",") if t.strip()]
    module_list = [m.strip() for m in enabled_modules.split(",") if m.strip()]

    if not symbol_list:
        return json.dumps({"error": "未提供有效标的"}, ensure_ascii=False)

    result: Dict[str, Any] = {}

    # ============ 1. 必选模块 (Core) ============
    result["account"] = _fetch_account(user_id)
    result["open_orders"] = _fetch_open_orders(user_id)
    # 传入已获取的 open_orders，让 _fetch_positions 把每个仓位关联的 TP/SL 挂单内嵌进去
    result["positions"] = _fetch_positions(user_id, open_orders=result["open_orders"])
    result["macro"] = _fetch_macro()
    if "news" in module_list:
        result["news"] = _fetch_critical_news()
    result["funding"] = _fetch_funding(symbol_list, user_id)
    result["performance"] = _fetch_performance(user_id)

    # ============ 1.5 交易所合约限制 (OKX 等按张交易的交易所) ============
    result["exchange_constraints"] = _fetch_exchange_constraints(user_id, symbol_list)

    # ============ 1.6 价格警报 (Agent 自主设置的关键价位监控) ============
    result["alerts"] = _fetch_price_alerts(user_id)

    # ============ 1.7 上一次分析记忆 (跨心跳连续性) ============
    result["previous_analysis"] = _fetch_previous_analysis(user_id)

    # ============ 2. 逐标的技术分析 ============
    result["symbols"] = {}
    for symbol in symbol_list:
        price = _get_current_price(symbol)

        # BUG-3 修复: 如果公共 API 价格获取失败，用已有持仓的 mark_price 做 fallback
        if price is None:
            for pos in result.get("positions", {}).get("list", []):
                if pos.get("symbol") == symbol and pos.get("mark_price"):
                    price = pos["mark_price"]
                    print(f"[StrategyContext] Price fallback: using mark_price {price} for {symbol}")
                    break

        if price is None or price == 0:
            result["symbols"][symbol] = {"error": "无法获取价格"}
            continue

        sym_data: Dict[str, Any] = {"price": round(price, 2)}

        if "trend" in module_list:
            sym_data["trend"] = _fetch_trend(symbol, tf_list, price)

        if "levels" in module_list:
            sym_data["levels"] = _fetch_levels(symbol, tf_list[0], price)

        if "volume" in module_list:
            sym_data["volume"] = _fetch_volume(symbol, tf_list[0])

        if "pattern" in module_list:
            sym_data["pattern"] = _fetch_pattern(symbol, tf_list[0], price)

        if "reliability" in module_list:
            sym_data["reliability"] = _fetch_reliability(symbol, tf_list[0])

        if "volatility" in module_list:
            sym_data["volatility"] = _fetch_volatility(symbol, tf_list[0])

        if "derivatives" in module_list:
            sym_data["derivatives"] = _fetch_derivatives(symbol)

        result["symbols"][symbol] = sym_data

    # ============ 3. 生成摘要 ============
    result["enabled_modules"] = module_list
    result["summary"] = _build_overall_summary(result, symbol_list)

    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=_json_default)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 必选模块数据获取
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# BUG-5 修复: 限制 JSON 输出中的浮点精度，减少 token 浪费
def _json_default(obj):
    """JSON 序列化 fallback: 将 numpy/pandas 类型转为 Python 原生类型，并限制浮点精度。"""
    import numpy as np
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return round(float(obj), 4)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    if hasattr(obj, 'item'):
        return obj.item()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


# BUG-2 修复: 删除了原先独立的 _get_binance_client_fallback 函数。
# 现在统一使用 tools/trading/_client.py 的 _get_trading_client()，
# 该函数已支持通过 trader_instance_id 上下文精确隔离多实例，
# 避免了多 Agent 实例共享同一个交易所账户的数据串台风险。


def _fetch_account(user_id: str = None) -> Dict:
    """获取账户余额信息（支持 user_binance_keys + exchange_accounts 双路径）。"""
    print(f"[StrategyContext] _fetch_account called with user_id={user_id[:12] if user_id else 'None'}")
    result = {"balance": 0, "available": 0, "margin_balance": 0}

    # 先尝试标准路径
    try:
        from tools.exchange_trading_tools import get_positions_summary
        summary = get_positions_summary(user_id=user_id)
        if "error" not in summary:
            result["balance"] = summary.get("margin_balance", 0)
            result["available"] = summary.get("available_balance", 0)
            result["margin_balance"] = summary.get("margin_balance", 0)
            result["unrealized_pnl"] = summary.get("unrealized_pnl", 0)
            print(f"[StrategyContext] _fetch_account path-A OK: balance={result['balance']}")
            return result
        else:
            print(f"[StrategyContext] _fetch_account path-A failed: {summary.get('error', 'unknown')}")
    except Exception as e:
        print(f"[StrategyContext] _fetch_account path-A exception: {e}")

    # 回退：通过统一的 _get_trading_client 获取客户端（支持 trader_instance_id 隔离）
    if user_id:
        print(f"[StrategyContext] _fetch_account trying path-B for user {user_id[:8]}...")
        client, err = _get_trading_client(user_id, require_trading_enabled=False)
        if client:
            try:
                balance = client.get_usdt_balance()
                if "error" not in balance:
                    result["balance"] = balance.get("margin_balance", 0)
                    result["available"] = balance.get("available_balance", 0)
                    result["margin_balance"] = balance.get("margin_balance", 0)
                    result["unrealized_pnl"] = balance.get("unrealized_pnl", 0)
                    print(f"[StrategyContext] _fetch_account path-B OK: balance={result['balance']}")
                else:
                    print(f"[StrategyContext] _fetch_account path-B API error: {balance.get('error')}")
                    result["error"] = balance.get("error")
            except Exception as e:
                print(f"[StrategyContext] _fetch_account path-B exception: {e}")
                result["error"] = str(e)
        elif err:
            print(f"[StrategyContext] _fetch_account path-B no client: {err}")
            result["error"] = err
    else:
        print("[StrategyContext] _fetch_account: no user_id, skipping fallback")
    return result


def _fetch_positions(user_id: str = None, open_orders: Dict = None) -> Dict:
    """获取当前持仓列表，并内嵌每个仓位关联的 TP/SL 挂单信息。
    
    Args:
        user_id: 用户 ID
        open_orders: 已获取的挂单数据（来自 _fetch_open_orders），用于交叉匹配
    """
    result = {"count": 0, "list": []}

    # 条件订单类型分类
    TP_TYPES = {"TAKE_PROFIT_MARKET", "TAKE_PROFIT"}
    SL_TYPES = {"STOP_MARKET", "STOP", "TRAILING_STOP_MARKET"}

    def _match_orders_for_symbol(symbol_raw: str):
        """从 open_orders 中匹配该 symbol 的 TP/SL 挂单"""
        tp_orders = []
        sl_orders = []
        if not open_orders or not open_orders.get("list"):
            return tp_orders, sl_orders
        
        # symbol_raw 是不含 USDT 的简称（如 BTC）
        for order in open_orders["list"]:
            if order.get("symbol") != symbol_raw:
                continue
            order_type = order.get("type", "")
            if order_type in TP_TYPES:
                tp_orders.append({
                    "type": order_type,
                    "stop_price": order.get("stop_price", 0),
                    "quantity": order.get("quantity", 0),
                    "source": order.get("source", "unknown"),
                })
            elif order_type in SL_TYPES:
                sl_orders.append({
                    "type": order_type,
                    "stop_price": order.get("stop_price", 0),
                    "quantity": order.get("quantity", 0),
                    "source": order.get("source", "unknown"),
                })
        return tp_orders, sl_orders

    def _parse_positions(positions_list):
        for pos in positions_list:
            symbol = pos.get("symbol", "").replace("USDT", "")
            tp_orders, sl_orders = _match_orders_for_symbol(symbol)
            if tp_orders or sl_orders:
                print(f"[StrategyContext] Position {symbol}: matched {len(tp_orders)} TP + {len(sl_orders)} SL orders")
            result["list"].append({
                "symbol": symbol,
                "direction": "LONG" if pos.get("direction") == "LONG" else "SHORT",
                "margin": pos.get("margin") or pos.get("isolated_margin", 0),
                "entry_price": pos.get("entry_price", 0),
                "mark_price": pos.get("current_price") or pos.get("mark_price", 0),
                "pnl": pos.get("unrealized_pnl", 0),
                "roi": pos.get("roi_percent", 0),
                "leverage": pos.get("leverage", 1),
                "existing_tp_orders": tp_orders,
                "existing_sl_orders": sl_orders,
            })
        result["count"] = len(result["list"])

    # 先尝试标准路径
    try:
        from tools.exchange_trading_tools import get_positions_summary
        summary = get_positions_summary(user_id=user_id)
        if "error" not in summary:
            _parse_positions(summary.get("open_positions", []))
            return result
    except Exception:
        pass

    # 回退：通过统一的 _get_trading_client 获取客户端（支持 trader_instance_id 隔离）
    if user_id:
        client, err = _get_trading_client(user_id, require_trading_enabled=False)
        if client:
            try:
                positions = client.get_positions()
                if isinstance(positions, list):
                    _parse_positions(positions)
            except Exception as e:
                result["error"] = str(e)
        elif err:
            result["error"] = err
    return result


def _fetch_open_orders(user_id: str = None) -> Dict:
    """获取当前所有未成交委托（普通挂单 + Algo/条件订单）。
    
    这是 Agent 反重复挂单的关键数据源。Agent 必须先検查这里有没有
    已有的止损/止盈订单，再决定是否需要新挂单。
    """
    result = {"count": 0, "list": []}
    
    client, err = _get_trading_client(user_id, require_trading_enabled=False) if user_id else (None, "no user_id")
    if not client:
        if err:
            result["error"] = err
        return result
    
    try:
        def _safe_float(v):
            if v is None or v == "": return 0.0
            try: return float(v)
            except: return 0.0
        
        # 1. 获取普通挂单
        normal_orders = client.get_open_orders()
        normal_count = 0
        if isinstance(normal_orders, list):
            for order in normal_orders:
                order_type = order.get("type", "")
                side = order.get("side", "")
                symbol = order.get("symbol", "").replace("USDT", "")
                
                result["list"].append({
                    "symbol": symbol,
                    "type": order_type,
                    "side": side,
                    "quantity": _safe_float(order.get("origQty")),
                    "price": _safe_float(order.get("price")),
                    "stop_price": _safe_float(order.get("stopPrice")),
                    "reduce_only": str(order.get("reduceOnly", "")).lower() == "true",
                    "source": "normal",
                })
                normal_count += 1
        
        # 2. 获取 Algo/条件挂单
        algo_count = 0
        try:
            algo_orders = client.get_open_algo_orders()
            if isinstance(algo_orders, list):
                for order in algo_orders:
                    # 优先使用 algoType（OKX/Bitget 返回此字段区分 TP/SL），
                    # fallback 到 type（Binance 直接在 type 中标识）
                    order_type = order.get("algoType") or order.get("type", "")
                    side = order.get("side", "")
                    symbol = order.get("symbol", "").replace("USDT", "")
                    
                    result["list"].append({
                        "symbol": symbol,
                        "type": order_type,
                        "side": side,
                        "quantity": _safe_float(order.get("origQty") or order.get("quantity")),
                        "price": _safe_float(order.get("price")),
                        "stop_price": _safe_float(order.get("triggerPrice") or order.get("stopPrice")),
                        "reduce_only": str(order.get("reduceOnly", "")).lower() == "true",
                        "source": "algo",
                    })
                    algo_count += 1
        except Exception as e:
            print(f"[StrategyContext] _fetch_open_orders algo error: {e}")
        
        result["count"] = len(result["list"])
        print(f"[StrategyContext] _fetch_open_orders: {normal_count} normal + {algo_count} algo = {result['count']} total orders")
        if result["count"] > 0:
            types_summary = {}
            for o in result["list"]:
                t = o.get("type", "UNKNOWN")
                types_summary[t] = types_summary.get(t, 0) + 1
            print(f"[StrategyContext] Order types: {types_summary}")
    except Exception as e:
        result["error"] = str(e)
    
    return result

def _fetch_exchange_constraints(user_id: str, symbols: List[str]) -> Dict:
    """获取交易所合约限制信息（最小开仓保证金等）。

    对于 OKX 等按"张"交易的交易所，1 张合约价值固定（如 BTC 1张=0.01 BTC）。
    Agent 需要提前知道每个币种在不同杠杆下的最低保证金要求，
    避免算出一个太小的 margin 导致下单失败。
    """
    result: Dict[str, Any] = {}

    client, err = _get_trading_client(user_id, require_trading_enabled=False) if user_id else (None, "no user_id")
    if not client:
        return result

    exchange_name = client.get_exchange_name() if hasattr(client, 'get_exchange_name') else "Unknown"
    result["exchange"] = exchange_name

    for symbol in symbols:
        usdt_symbol = f"{symbol}USDT" if not symbol.endswith("USDT") else symbol
        try:
            inst_info = client.get_instrument_info(usdt_symbol)
            ct_val = inst_info.get("ct_val", 1.0)

            if ct_val == 1.0:
                # Binance 等币本位交易所无张数概念，不需要额外约束
                continue

            # 获取当前价格用于计算最低保证金
            from analysis.technical import _get_current_price
            price = _get_current_price(symbol)
            if not price or price <= 0:
                continue

            # 获取最小下单张数 (如 BTC=0.01, ETH=0.01, SOL=0.1)
            min_sz = inst_info.get("min_qty", 1.0)

            # 最小下单的名义价值 = minSz * ctVal * price
            min_notional = min_sz * ct_val * price

            # 常见杠杆下的最低保证金 = 最小名义价值 / 杠杆
            min_margins = {}
            for lev in [3, 5, 10, 15, 20, 25, 50, 100]:
                min_margins[f"{lev}x"] = round(min_notional / lev, 4)

            result[symbol] = {
                "ct_val": ct_val,
                "min_sz": min_sz,
                "min_notional": round(min_notional, 4),
                "min_margin_by_leverage": min_margins,
                "note": f"OKX合约最小下单{min_sz}张={min_sz * ct_val}{symbol.replace('USDT','')}, 最低保证金=min_notional/杠杆倍数"
            }
        except Exception as e:
            print(f"[StrategyContext] _fetch_exchange_constraints error for {symbol}: {e}")

    return result


def _fetch_price_alerts(user_id: str = None) -> Dict:
    """获取当前用户的活跃价格警报列表，注入到策略上下文中。
    
    让 Agent 每次分析时都能看到自己之前设置了哪些警报，
    便于决定是否需要新增、调整或取消警报。
    """
    result = {"count": 0, "list": []}
    if not user_id:
        return result
    
    try:
        from tools.alert_tools import list_price_alerts
        alerts_data = list_price_alerts(user_id=user_id)
        if isinstance(alerts_data, dict):
            result["count"] = alerts_data.get("count", 0)
            result["list"] = alerts_data.get("list", [])
            result["max_allowed"] = alerts_data.get("max_allowed", 10)
    except Exception as e:
        print(f"[StrategyContext] _fetch_price_alerts error: {e}")
    
    return result


# BUG-4 修复: 宏观数据全局缓存（5 分钟 TTL），避免 CoinGecko API 高频限流
_macro_cache: Dict = {}
_macro_cache_time: float = 0
_MACRO_CACHE_TTL = 300  # 5 分钟


def _fetch_macro() -> Dict:
    """获取市场宏观数据（带 5 分钟级别全局缓存）。"""
    global _macro_cache, _macro_cache_time
    now = _time.time()
    if _macro_cache and (now - _macro_cache_time) < _MACRO_CACHE_TTL:
        return _macro_cache

    result = {"fng": None, "fng_label": None, "btc_dom": None, "market_phase": None}
    try:
        fng_url = "https://api.alternative.me/fng/?limit=1"
        fng_data = requests.get(fng_url, timeout=5).json()["data"][0]
        result["fng"] = int(fng_data["value"])
        result["fng_label"] = fng_data["value_classification"]
    except Exception:
        pass

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://api.coingecko.com/api/v3/global"
        data = requests.get(url, headers=headers, timeout=5).json()["data"]
        btc_dom = data["market_cap_percentage"]["btc"]
        result["btc_dom"] = round(btc_dom, 1)

        if btc_dom < 45:
            result["market_phase"] = "山寨季"
        elif btc_dom < 55:
            result["market_phase"] = "平衡"
        else:
            result["market_phase"] = "BTC主导"
    except Exception:
        pass

    # 仅在至少有一项数据时更新缓存
    if result["fng"] is not None or result["btc_dom"] is not None:
        _macro_cache = result
        _macro_cache_time = now

    return result


def _fetch_funding(symbols: List[str], user_id: str = None) -> Dict:
    """获取各标的的当前资金费率。"""
    result = {}
    for symbol in symbols:
        try:
            usdt_symbol = f"{symbol}USDT" if not symbol.endswith("USDT") else symbol
            url = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={usdt_symbol}&limit=1"
            resp = requests.get(url, timeout=5).json()
            if isinstance(resp, list) and resp:
                rate = float(resp[0].get("fundingRate", 0))
                result[symbol] = {
                    "rate": rate,
                    "rate_pct": round(rate * 100, 4),
                    "bias": "空方付费(看多)" if rate > 0.0001 else ("多方付费(看空)" if rate < -0.0001 else "中性"),
                }
            else:
                result[symbol] = {"rate": 0, "rate_pct": 0, "bias": "未知"}
        except Exception:
            result[symbol] = {"error": "获取失败"}
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 可选技术分析模块
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _fetch_trend(symbol: str, timeframes: List[str], price: float) -> Dict:
    """多周期趋势结构分析（EMA + Vegas + MACD + RSI）。

    核心原则：顺大逆小
    - EMA 排列 + Vegas 通道位置 = 首要参照（权重 2）
    - MACD 动能 = 辅助确认（权重 1）
    - 大周期 (1w/1d) 权重远高于小周期 (4h/1h/15m)
    - major_trend 只看 1d+1w 的 EMA+Vegas，输出否决信号 veto
    """
    result = {
        "direction": "neutral",
        "strength": "weak",
        "ema_bull": 0, "ema_bear": 0,
        "vegas_above": 0, "vegas_below": 0,
        "macd_bull": 0, "macd_bear": 0,
        "rsi": {},  # 各周期 RSI 值
        "timeframes": {},
        # ===== 顺大逆小：大周期趋势 + 否决权 =====
        "major_trend": "neutral",   # 仅基于 1d+1w 的 EMA+Vegas 判定
        "veto": None,               # "no_long" / "no_short" / None
    }

    for tf in timeframes:
        df = _get_binance_klines(symbol, tf)
        if df is None or len(df) < 50:
            continue

        tf_data = {"ema": "neutral", "vegas_status": "neutral", "macd": "neutral"}

        try:
            # EMA 排列
            ema21 = ta.ema(df["close"], length=21)
            ema55 = ta.ema(df["close"], length=55)
            ema200 = ta.ema(df["close"], length=200) if len(df) >= 200 else None

            ema21_val = ema21.iloc[-1] if ema21 is not None else None
            ema55_val = ema55.iloc[-1] if ema55 is not None else None
            ema200_val = ema200.iloc[-1] if ema200 is not None else None

            if ema21_val:
                tf_data["ema21"] = round(ema21_val, 2)
            if ema55_val:
                tf_data["ema55"] = round(ema55_val, 2)
            if ema200_val:
                tf_data["ema200"] = round(ema200_val, 2)

            if ema21_val and ema55_val and ema200_val:
                if price > ema21_val > ema55_val > ema200_val:
                    tf_data["ema"] = "bullish"
                    result["ema_bull"] += 1
                elif price < ema21_val < ema55_val < ema200_val:
                    tf_data["ema"] = "bearish"
                    result["ema_bear"] += 1
            elif ema21_val and ema55_val:
                if price > ema21_val > ema55_val:
                    tf_data["ema"] = "bullish"
                    result["ema_bull"] += 1
                elif price < ema21_val < ema55_val:
                    tf_data["ema"] = "bearish"
                    result["ema_bear"] += 1

            # Vegas 通道 (EMA 144/169)
            if len(df) >= 170:
                ema144 = ta.ema(df["close"], length=144).iloc[-1]
                ema169 = ta.ema(df["close"], length=169).iloc[-1]
                ch_top = max(ema144, ema169)
                ch_bot = min(ema144, ema169)
                tf_data["vegas"] = {"top": round(ch_top, 2), "bot": round(ch_bot, 2)}

                if price > ch_top:
                    tf_data["vegas_status"] = "above"
                    result["vegas_above"] += 1
                elif price < ch_bot:
                    tf_data["vegas_status"] = "below"
                    result["vegas_below"] += 1
                else:
                    tf_data["vegas_status"] = "inside"

            # MACD
            macd_result = ta.macd(df["close"], fast=12, slow=26, signal=9)
            if macd_result is not None:
                macd_line = macd_result.iloc[-1, 0]
                signal_line = macd_result.iloc[-1, 1]
                histogram = macd_result.iloc[-1, 2]
                tf_data["macd_val"] = round(float(histogram), 2)
                if macd_line > signal_line:
                    tf_data["macd"] = "bullish"
                    result["macd_bull"] += 1
                else:
                    tf_data["macd"] = "bearish"
                    result["macd_bear"] += 1

            # RSI (14)
            rsi_series = ta.rsi(df["close"], length=14)
            if rsi_series is not None and len(rsi_series) > 0:
                rsi_val = round(float(rsi_series.iloc[-1]), 1)
                tf_data["rsi"] = rsi_val
                result["rsi"][tf] = rsi_val
                if rsi_val >= 70:
                    tf_data["rsi_status"] = "overbought"
                elif rsi_val <= 30:
                    tf_data["rsi_status"] = "oversold"
                else:
                    tf_data["rsi_status"] = "neutral"

            # K 线时间进度（当前 K 线完成度）
            try:
                _tf_seconds = {
                    "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
                    "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600,
                    "8h": 28800, "12h": 43200, "1d": 86400, "3d": 259200,
                    "1w": 604800, "1M": 2592000,
                }
                if tf in _tf_seconds:
                    candle_duration = _tf_seconds[tf]
                    last_open_ts = int(df["timestamp"].iloc[-1]) / 1000 if "timestamp" in df.columns else 0
                    if last_open_ts > 0:
                        now_ts = _time.time()
                        elapsed = now_ts - last_open_ts
                        progress = min(1.0, max(0.0, elapsed / candle_duration))
                        tf_data["candle_progress"] = round(progress, 2)
            except Exception:
                pass

        except Exception:
            pass

        result["timeframes"][tf] = tf_data

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 综合判断：加权模型 + 大周期否决权
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # 周期权重：大周期 >> 小周期
    TF_WEIGHTS = {"1w": 4, "1d": 3, "4h": 2, "1h": 1, "15m": 0.5, "30m": 0.5}
    # 指标类型权重：EMA/Vegas 是首要参照，MACD 是辅助
    INDICATOR_WEIGHTS = {"ema": 2, "vegas": 2, "macd": 1}

    weighted_bull = 0.0
    weighted_bear = 0.0

    # 大周期信号收集（仅 EMA + Vegas，不含 MACD）
    MAJOR_TFS = {"1w", "1d"}
    major_bull = 0.0
    major_bear = 0.0

    for tf, tf_data in result["timeframes"].items():
        w = TF_WEIGHTS.get(tf, 1)
        is_major = tf in MAJOR_TFS

        # EMA 排列（首要参照）
        if tf_data.get("ema") == "bullish":
            weighted_bull += w * INDICATOR_WEIGHTS["ema"]
            if is_major:
                major_bull += w * INDICATOR_WEIGHTS["ema"]
        elif tf_data.get("ema") == "bearish":
            weighted_bear += w * INDICATOR_WEIGHTS["ema"]
            if is_major:
                major_bear += w * INDICATOR_WEIGHTS["ema"]

        # Vegas 通道位置（首要参照）
        if tf_data.get("vegas_status") == "above":
            weighted_bull += w * INDICATOR_WEIGHTS["vegas"]
            if is_major:
                major_bull += w * INDICATOR_WEIGHTS["vegas"]
        elif tf_data.get("vegas_status") == "below":
            weighted_bear += w * INDICATOR_WEIGHTS["vegas"]
            if is_major:
                major_bear += w * INDICATOR_WEIGHTS["vegas"]

        # MACD 动能（辅助确认）
        if tf_data.get("macd") == "bullish":
            weighted_bull += w * INDICATOR_WEIGHTS["macd"]
        elif tf_data.get("macd") == "bearish":
            weighted_bear += w * INDICATOR_WEIGHTS["macd"]

    # 1) 综合趋势方向（加权）
    total_score = weighted_bull + weighted_bear
    if total_score > 0:
        bull_ratio = weighted_bull / total_score
        if bull_ratio >= 0.7:
            result["direction"] = "bullish"
            result["strength"] = "strong"
        elif bull_ratio >= 0.55:
            result["direction"] = "bullish"
            result["strength"] = "moderate"
        elif bull_ratio <= 0.3:
            result["direction"] = "bearish"
            result["strength"] = "strong"
        elif bull_ratio <= 0.45:
            result["direction"] = "bearish"
            result["strength"] = "moderate"
        # 0.45 < bull_ratio < 0.55 → neutral/weak (default)

    # 2) 大周期趋势（仅 1d+1w 的 EMA+Vegas）
    major_total = major_bull + major_bear
    if major_total > 0:
        major_ratio = major_bull / major_total
        if major_ratio >= 0.6:
            result["major_trend"] = "bullish"
        elif major_ratio <= 0.4:
            result["major_trend"] = "bearish"
        # else: "neutral" (default)

    # 3) 否决权：大周期明确方向时，禁止反向开仓
    if result["major_trend"] == "bearish":
        result["veto"] = "no_long"
    elif result["major_trend"] == "bullish":
        result["veto"] = "no_short"

    return result


def _fetch_levels(symbol: str, timeframe: str, price: float) -> Dict:
    """支撑阻力关键价位识别。

    优先级原则：
    - L1（首要）: EMA21/55/200 + Vegas 通道 → nearest_support / nearest_resistance
    - L2（参考）: Fib 回撤位 → fib_support / fib_resistance
    - 两类合并用于汇聚区检测 confluence_zones
    """
    result = {
        "nearest_support": None,
        "nearest_resistance": None,
        "fib_support": None,        # Fib 级别支撑（仅参考）
        "fib_resistance": None,     # Fib 级别阻力（仅参考）
        "confluence_zones": [],
    }
    # L1: EMA/Vegas 关键位
    ema_vegas_levels = []
    # L2: Fib 回撤位
    fib_levels = []

    df = _get_binance_klines(symbol, timeframe, limit=100)
    if df is None or len(df) < 30:
        return result

    try:
        # EMA 关键位（当前周期）
        for length, label in [(21, "EMA21"), (55, "EMA55"), (200, "EMA200")]:
            if len(df) >= length:
                val = ta.ema(df["close"], length=length)
                if val is not None:
                    ema_vegas_levels.append((val.iloc[-1], f"{label}_{timeframe}"))

        # 多周期 EMA 关键位
        for tf in ["4h", "1d", "1w"]:
            if tf == timeframe:
                continue
            df_tf = _get_binance_klines(symbol, tf)
            if df_tf is not None and len(df_tf) >= 55:
                ema21_tf = ta.ema(df_tf["close"], length=21).iloc[-1]
                ema55_tf = ta.ema(df_tf["close"], length=55).iloc[-1]
                ema_vegas_levels.append((ema21_tf, f"EMA21_{tf}"))
                ema_vegas_levels.append((ema55_tf, f"EMA55_{tf}"))

                if len(df_tf) >= 170:
                    ema144 = ta.ema(df_tf["close"], length=144).iloc[-1]
                    ema169 = ta.ema(df_tf["close"], length=169).iloc[-1]
                    ema_vegas_levels.append((max(ema144, ema169), f"VegasTop_{tf}"))
                    ema_vegas_levels.append((min(ema144, ema169), f"VegasBot_{tf}"))

        # Fibonacci 回撤（L2 参考）
        swing_high, swing_low = _find_swing_points(df, window=7)
        high_price = swing_high["price"]
        low_price = swing_low["price"]
        diff = high_price - low_price
        is_uptrend = swing_high["index"] > swing_low["index"]
        for fib in [0.382, 0.5, 0.618]:
            level = (high_price - diff * fib) if is_uptrend else (low_price + diff * fib)
            fib_levels.append((level, f"Fib_{fib}"))
    except Exception:
        pass

    # ===== nearest_support / nearest_resistance: 优先 EMA/Vegas =====
    ema_supports = [(l, n) for l, n in ema_vegas_levels if l < price]
    ema_resistances = [(l, n) for l, n in ema_vegas_levels if l > price]

    if ema_supports:
        ema_supports.sort(key=lambda x: x[0], reverse=True)
        s = ema_supports[0]
        result["nearest_support"] = {
            "price": round(s[0], 2),
            "dist_pct": round(((price - s[0]) / price) * 100, 1),
            "source": s[1],
        }

    if ema_resistances:
        ema_resistances.sort(key=lambda x: x[0])
        r = ema_resistances[0]
        result["nearest_resistance"] = {
            "price": round(r[0], 2),
            "dist_pct": round(((r[0] - price) / price) * 100, 1),
            "source": r[1],
        }

    # 如果 EMA/Vegas 没有支撑或阻力（罕见），回退到 Fib
    if result["nearest_support"] is None:
        fib_supports = [(l, n) for l, n in fib_levels if l < price]
        if fib_supports:
            fib_supports.sort(key=lambda x: x[0], reverse=True)
            s = fib_supports[0]
            result["nearest_support"] = {
                "price": round(s[0], 2),
                "dist_pct": round(((price - s[0]) / price) * 100, 1),
                "source": s[1],
            }

    if result["nearest_resistance"] is None:
        fib_resistances = [(l, n) for l, n in fib_levels if l > price]
        if fib_resistances:
            fib_resistances.sort(key=lambda x: x[0])
            r = fib_resistances[0]
            result["nearest_resistance"] = {
                "price": round(r[0], 2),
                "dist_pct": round(((r[0] - price) / price) * 100, 1),
                "source": r[1],
            }

    # ===== Fib 参考位（独立输出，不影响 Agent 止损止盈计算）=====
    fib_supports = [(l, n) for l, n in fib_levels if l < price]
    fib_resistances = [(l, n) for l, n in fib_levels if l > price]

    if fib_supports:
        fib_supports.sort(key=lambda x: x[0], reverse=True)
        s = fib_supports[0]
        result["fib_support"] = {
            "price": round(s[0], 2),
            "dist_pct": round(((price - s[0]) / price) * 100, 1),
            "source": s[1],
        }
    if fib_resistances:
        fib_resistances.sort(key=lambda x: x[0])
        r = fib_resistances[0]
        result["fib_resistance"] = {
            "price": round(r[0], 2),
            "dist_pct": round(((r[0] - price) / price) * 100, 1),
            "source": r[1],
        }

    # ===== 汇聚区：EMA/Vegas + Fib 合并检测 =====
    all_levels = ema_vegas_levels + fib_levels
    all_levels.sort(key=lambda x: x[0])
    used = set()
    tolerance = 0.015
    for i, (lv1, n1) in enumerate(all_levels):
        if i in used:
            continue
        cluster = [(lv1, n1)]
        used.add(i)
        for j, (lv2, n2) in enumerate(all_levels):
            if j in used:
                continue
            if lv1 > 0 and abs(lv2 - lv1) / lv1 <= tolerance:
                cluster.append((lv2, n2))
                used.add(j)
        if len(cluster) >= 2:
            avg = sum(l[0] for l in cluster) / len(cluster)
            result["confluence_zones"].append({
                "price": round(avg, 2),
                "dist_pct": round(((avg - price) / price) * 100, 1),
                "type": "support" if avg < price else "resistance",
                "indicators": [n for _, n in cluster],
            })

    return result


def _fetch_volume(symbol: str, timeframe: str) -> Dict:
    """量能分析。"""
    result = {"ratio": 0, "status": "normal", "divergence": None, "flow": "neutral"}

    df = _get_binance_klines(symbol, timeframe)
    if df is None or len(df) < 50:
        return result

    try:
        vol_col = "quote_volume" if "quote_volume" in df.columns else "volume"
        current = df[vol_col].iloc[-1]
        avg20 = df[vol_col].iloc[-20:].mean()
        result["ratio"] = round(current / avg20, 2) if avg20 > 0 else 0

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

        # 量价背离
        closes = df["close"].iloc[-5:].values
        vols = df[vol_col].iloc[-5:].values
        price_up = closes[-1] > closes[0]
        vol_up = vols[-1] > vols[0]

        if price_up and not vol_up and result["ratio"] < 0.8:
            result["divergence"] = "bearish"
        elif not price_up and vol_up and result["ratio"] > 1.2:
            result["divergence"] = "panic_sell"
        elif price_up and vol_up:
            result["divergence"] = "healthy_up"
        elif not price_up and not vol_up:
            result["divergence"] = "normal_pullback"

        # 资金流向
        up_vol = sum(df[vol_col].iloc[-i] for i in range(1, min(20, len(df))) if df["close"].iloc[-i] > df["close"].iloc[-i - 1])
        dn_vol = sum(df[vol_col].iloc[-i] for i in range(1, min(20, len(df))) if df["close"].iloc[-i] <= df["close"].iloc[-i - 1])

        if up_vol > dn_vol * 1.5:
            result["flow"] = "inflow"
        elif dn_vol > up_vol * 1.5:
            result["flow"] = "outflow"
    except Exception:
        pass
    return result


def _fetch_pattern(symbol: str, timeframe: str, price: float) -> Dict:
    """形态识别。"""
    result = {"name": None, "bias": "neutral", "support": None, "resistance": None}

    df = _get_binance_klines(symbol, timeframe, limit=100)
    if df is None or len(df) < 50:
        return result

    try:
        window = 7 if timeframe in ["1d", "1w", "1M"] else 5
        high_points, low_points = _find_local_extremes(df, window=window)

        cutoff = len(df) // 3
        recent_highs = [p for p in high_points if p["index"] > cutoff]
        recent_lows = [p for p in low_points if p["index"] > cutoff]

        uptrend = None
        if len(recent_lows) >= 2:
            uptrend = _fit_trendline(recent_lows, min_points=2, min_r_squared=0.5)
            if uptrend and uptrend["slope"] < 0:
                uptrend = None

        downtrend = None
        if len(recent_highs) >= 2:
            downtrend = _fit_trendline(recent_highs, min_points=2, min_r_squared=0.5)

        current_idx = len(df) - 1
        pattern_info = _classify_trendline_pattern(uptrend, downtrend, current_idx, price)

        result["name"] = pattern_info.get("pattern")
        result["bias"] = pattern_info.get("bias", "neutral")
        if pattern_info.get("support"):
            result["support"] = round(pattern_info["support"], 2)
        if pattern_info.get("resistance"):
            result["resistance"] = round(pattern_info["resistance"], 2)
    except Exception:
        pass
    return result


def _fetch_reliability(symbol: str, timeframe: str) -> Dict:
    """指标历史可靠性统计。"""
    result = {"best_indicator": None, "role": None, "rate_60d": 0, "advice": None}
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


def _fetch_volatility(symbol: str, timeframe: str) -> Dict:
    """ATR 波动率分析。"""
    result = {"atr": 0, "atr_pct": 0, "ratio": 0, "status": "normal", "sl_suggest": 0}

    df = _get_binance_klines(symbol, timeframe, limit=64)
    if df is None or len(df) < 24:
        return result

    try:
        price = df["close"].iloc[-1]
        atr = ta.atr(df["high"], df["low"], df["close"], length=14)
        if atr is None:
            return result

        current_atr = atr.iloc[-1]
        atr_ma = atr.rolling(window=20).mean().iloc[-1]
        ratio = current_atr / atr_ma if atr_ma > 0 else 0
        atr_pct = (current_atr / price) * 100

        result["atr"] = round(float(current_atr), 2)
        result["atr_pct"] = round(atr_pct, 2)
        result["ratio"] = round(ratio, 2)

        if ratio > 1.5:
            result["status"] = "extreme_high"
            sl_mult = 2.0
        elif ratio > 1.2:
            result["status"] = "elevated"
            sl_mult = 1.5
        elif ratio < 0.7:
            result["status"] = "very_low"
            sl_mult = 1.0
        else:
            result["status"] = "normal"
            sl_mult = 1.2

        result["sl_suggest"] = round(float(current_atr * sl_mult), 2)
        result["sl_suggest_pct"] = round(atr_pct * sl_mult, 2)

        # 布林带 Squeeze 检测
        try:
            bb = ta.bbands(df["close"], length=20, std=2)
            if bb is not None:
                upper = bb.iloc[-1, 0]  # BBU
                lower = bb.iloc[-1, 2]  # BBL
                bb_width = (upper - lower) / price * 100 if price > 0 else 0
                bb_width_20 = []
                for i in range(-20, 0):
                    u = bb.iloc[i, 0]
                    l = bb.iloc[i, 2]
                    p = df["close"].iloc[i]
                    bb_width_20.append((u - l) / p * 100 if p > 0 else 0)
                avg_width = sum(bb_width_20) / len(bb_width_20) if bb_width_20 else 0
                result["bb_width"] = round(bb_width, 2)
                result["bb_squeeze"] = bb_width < avg_width * 0.6  # 宽度低于均值 60% 视为挤压
        except Exception:
            pass

    except Exception:
        pass
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 综合摘要
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _build_overall_summary(data: Dict, symbols: List[str]) -> str:
    """生成一行概要供 Agent 快速阅读。"""
    parts = []

    # 账户
    acct = data.get("account", {})
    avail = acct.get("available", 0)
    if avail:
        parts.append(f"余额${avail:,.0f}")

    # 持仓
    pos = data.get("positions", {})
    if pos.get("count", 0) > 0:
        pos_strs = []
        for p in pos.get("list", []):
            d = "L" if p["direction"] == "LONG" else "S"
            pos_strs.append(f"{p['symbol']}{d}({p['roi']:+.1f}%)")
        parts.append("持仓:" + ",".join(pos_strs))
    else:
        parts.append("空仓")

    # 各标的趋势
    for sym in symbols:
        sym_data = data.get("symbols", {}).get(sym, {})
        if "error" in sym_data:
            continue
        trend = sym_data.get("trend", {})
        if trend:
            emoji = "📈" if trend.get("direction") == "bullish" else ("📉" if trend.get("direction") == "bearish" else "➡️")
            parts.append(f"{sym}{emoji}")

    # 宏观与新闻
    macro = data.get("macro", {})
    if macro.get("fng") is not None:
        parts.append(f"FnG:{macro['fng']}")
        
    news = data.get("news", {})
    if news.get("has_alert"):
        parts.append("🚨紧急新闻预警!")

    return " | ".join(parts)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 合约衍生数据模块 (Open Interest + Long/Short Ratio)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BINANCE_FAPI_BASE = os.environ.get("BINANCE_API_BASE", "https://fapi.binance.com")


def _fetch_derivatives(symbol: str) -> Dict:
    """
    获取合约特有数据：持仓量 (OI) 和多空持仓比。
    
    数据源：Binance Futures 公共 API（无需密钥）。
    
    返回:
        {
            "oi": 12345.67,           # 当前 OI（BTC 计）
            "oi_change_4h": "+5.2%",  # 4h OI 变化率
            "oi_signal": "bullish",   # OI 信号判定
            "ls_ratio": 1.23,         # 全网多空账户比
            "ls_signal": "crowded_long",  # 多空信号
            "top_ls_ratio": 1.45,     # 大户多空持仓比
        }
    """
    result = {
        "oi": None, "oi_change_4h": None, "oi_signal": None,
        "ls_ratio": None, "ls_signal": None,
        "top_ls_ratio": None,
    }
    
    usdt_symbol = f"{symbol}USDT" if not symbol.endswith("USDT") else symbol

    # 1. Open Interest (当前 + 近 4h 历史)
    try:
        # 当前 OI
        oi_url = f"{BINANCE_FAPI_BASE}/fapi/v1/openInterest?symbol={usdt_symbol}"
        oi_resp = requests.get(oi_url, timeout=5).json()
        current_oi = float(oi_resp.get("openInterest", 0))
        result["oi"] = round(current_oi, 2)

        # OI 历史 (5m 粒度, 取 48 条 = 4h)
        oi_hist_url = f"{BINANCE_FAPI_BASE}/futures/data/openInterestHist?symbol={usdt_symbol}&period=5m&limit=48"
        oi_hist = requests.get(oi_hist_url, timeout=5).json()
        if isinstance(oi_hist, list) and len(oi_hist) >= 2:
            old_oi = float(oi_hist[0].get("sumOpenInterest", 0))
            if old_oi > 0:
                oi_change = ((current_oi - old_oi) / old_oi) * 100
                result["oi_change_4h"] = f"{oi_change:+.1f}%"
                
                # OI 信号判定（需要配合价格趋势使用）
                if oi_change > 5:
                    result["oi_signal"] = "rising_fast"  # 新资金快速涌入
                elif oi_change > 1:
                    result["oi_signal"] = "rising"
                elif oi_change < -5:
                    result["oi_signal"] = "falling_fast"  # 大量平仓
                elif oi_change < -1:
                    result["oi_signal"] = "falling"
                else:
                    result["oi_signal"] = "stable"
    except Exception as e:
        print(f"[StrategyContext] _fetch_derivatives OI error for {symbol}: {e}")

    # 2. 全网多空账户比
    try:
        ls_url = f"{BINANCE_FAPI_BASE}/futures/data/globalLongShortAccountRatio?symbol={usdt_symbol}&period=4h&limit=1"
        ls_resp = requests.get(ls_url, timeout=5).json()
        if isinstance(ls_resp, list) and ls_resp:
            ratio = float(ls_resp[0].get("longShortRatio", 1))
            result["ls_ratio"] = round(ratio, 2)

            # 极端值信号
            if ratio > 2.5:
                result["ls_signal"] = "crowded_long"   # 过于拥挤做多 → 反向风险
            elif ratio > 1.5:
                result["ls_signal"] = "leaning_long"
            elif ratio < 0.4:
                result["ls_signal"] = "crowded_short"  # 过于拥挤做空 → 轧空风险
            elif ratio < 0.67:
                result["ls_signal"] = "leaning_short"
            else:
                result["ls_signal"] = "balanced"
    except Exception as e:
        print(f"[StrategyContext] _fetch_derivatives L/S ratio error for {symbol}: {e}")

    # 3. 大户持仓多空比
    try:
        top_url = f"{BINANCE_FAPI_BASE}/futures/data/topLongShortPositionRatio?symbol={usdt_symbol}&period=4h&limit=1"
        top_resp = requests.get(top_url, timeout=5).json()
        if isinstance(top_resp, list) and top_resp:
            result["top_ls_ratio"] = round(float(top_resp[0].get("longShortRatio", 1)), 2)
    except Exception:
        pass

    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Agent 自身历史表现
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _fetch_performance(user_id: str = None) -> Dict:
    """
    从 strategy_logs 表读取 Agent 近期决策和执行表现。

    通过分析 actions_taken 字段判断交易频率和类型，
    供 Agent 参考自身近期的活跃度和操作倾向。

    Returns:
        {
            "total_rounds": 10,          # 近期决策轮数
            "action_rounds": 3,          # 有实际交易的轮数
            "hold_rounds": 7,            # 观望的轮数
            "recent_actions": ["OPEN_LONG_BTC", "ADJUST_SL_BTC", ...],
            "consecutive_holds": 2,      # 连续观望轮数
            "current_positions_pnl": [],  # (由 positions 模块提供，此处不重复)
            "advice": "正常"
        }
    """
    result = {
        "total_rounds": 0,
        "action_rounds": 0,
        "hold_rounds": 0,
        "recent_actions": [],
        "consecutive_holds": 0,
        "advice": None,
    }

    if not user_id:
        return result

    try:
        from app.database import get_db_connection
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # 获取最近 15 轮决策记录
                cur.execute("""
                    SELECT sl.strategy_decision, sl.actions_taken, sl."timestamp" as created_at
                    FROM strategy_logs sl
                    WHERE sl.user_id = %s
                    ORDER BY sl."timestamp" DESC
                    LIMIT 15
                """, (user_id,))
                rows = cur.fetchall()

                if not rows:
                    result["advice"] = "无历史决策记录"
                    return result

                result["total_rounds"] = len(rows)
                consecutive_holds = 0
                counting_holds = True

                for row in rows:
                    actions = row.get("actions_taken") or ""
                    decision = row.get("strategy_decision") or ""

                    # 判断该轮是否有实际交易动作
                    has_trade = any(kw in actions.upper() for kw in [
                        "OPEN_LONG", "OPEN_SHORT", "CLOSE_", "PARTIAL_CLOSE",
                        "ADJUST_SL", "ADJUST_TP", "MODIFY_ORDER"
                    ])

                    if has_trade:
                        result["action_rounds"] += 1
                        counting_holds = False
                        # 提取动作摘要（清洗掉可能存在的 JSON 格式字符如 []"）
                        clean_actions = actions.replace('[', '').replace(']', '').replace('"', '').replace("'", '')
                        action_parts = [a.strip() for a in clean_actions.split(",") if a.strip()]
                        for ap in action_parts[:3]:
                            if len(result["recent_actions"]) < 8:
                                result["recent_actions"].append(ap)
                    else:
                        result["hold_rounds"] += 1
                        if counting_holds:
                            consecutive_holds += 1

                result["consecutive_holds"] = consecutive_holds

                # 生成建议
                if result["total_rounds"] >= 5:
                    action_rate = result["action_rounds"] / result["total_rounds"]
                    if action_rate > 0.7:
                        result["advice"] = "⚠️ 操作频率偏高，注意避免过度交易"
                    elif consecutive_holds >= 5:
                        result["advice"] = f"已连续观望{consecutive_holds}轮，确认是否需要调整策略"
                    else:
                        result["advice"] = "正常"
                else:
                    result["advice"] = "数据不足，正常操作"

        finally:
            conn.close()
    except Exception as e:
        print(f"[StrategyContext] _fetch_performance error: {e}")
        result["advice"] = "数据获取失败"

    return result

def _fetch_critical_news() -> Dict:
    """获取近 24 小时的紧急新闻预警（Impact Score >= 3）。"""
    result = {"has_alert": False, "alerts": []}
    try:
        from app.database import get_db_connection
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT title, impact_score, impact_reason, published_at
                    FROM news_intelligence
                    WHERE impact_score >= 3
                      AND published_at >= NOW() - INTERVAL '24 HOURS'
                    ORDER BY impact_score DESC, published_at DESC
                    LIMIT 3
                """)
                rows = cur.fetchall()
                if rows:
                    result["has_alert"] = True
                    for r in rows:
                        result["alerts"].append({
                            "title": r["title"],
                            "score": r["impact_score"],
                            "reason": r["impact_reason"],
                            "time": str(r["published_at"])
                        })
        finally:
            conn.close()
    except Exception as e:
        print(f"[StrategyContext] _fetch_critical_news error: {e}")
    return result


def _fetch_previous_analysis(user_id: str = None) -> Dict:
    """获取该 trader 实例上一次的分析记忆，注入到策略上下文中。

    让 Agent 每次被唤醒时都能看到上一次的核心结论、交易计划和观察，
    避免重复分析和前后矛盾的决策。
    """
    result = {"available": False}
    if not user_id:
        return result

    try:
        from tools.trading_tools import get_current_trader_id
        trader_id = get_current_trader_id()
        if not trader_id:
            return result

        from agent.execution_memory import load_execution_memory
        memory = load_execution_memory(user_id, trader_id)
        if memory:
            result["available"] = True
            result["last_summary"] = memory.get("last_analysis_summary", {})
            result["active_plan"] = memory.get("active_trade_plan", "")
            result["recent_observations"] = memory.get("observations", [])
            result["memory_age"] = memory.get("updated_at", "")
    except Exception as e:
        print(f"[StrategyContext] _fetch_previous_analysis error: {e}")

    return result

