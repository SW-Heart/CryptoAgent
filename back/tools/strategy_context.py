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
from typing import Dict, List, Any

import pandas as pd
import pandas_ta as ta

# ============ 底层数据源导入 ============
from technical_analysis import (
    _get_binance_klines,
    _get_current_price,
)
from pattern_recognition import (
    _find_local_extremes,
    _fit_trendline,
    _classify_trendline_pattern,
    _find_swing_points,
)
from indicator_memory import _calculate_indicator_stats

import requests


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
        "description": "ATR 波幅、波动率比率、自适应止损建议",
        "category": "technical",
        "always_on": False,
        "default_on": False,
        "icon": "🌊",
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
    result["funding"] = _fetch_funding(symbol_list, user_id)

    # ============ 2. 逐标的技术分析 ============
    result["symbols"] = {}
    for symbol in symbol_list:
        price = _get_current_price(symbol)
        if price is None:
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

        result["symbols"][symbol] = sym_data

    # ============ 3. 生成摘要 ============
    result["enabled_modules"] = module_list
    result["summary"] = _build_overall_summary(result, symbol_list)

    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 必选模块数据获取
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _get_binance_client_fallback(user_id: str):
    """
    获取 Binance 客户端，支持两条路径：
    路径 A: user_binance_keys 表（旧系统）
    路径 B: exchange_accounts 表（Workspace 系统）
    返回 (client, error_msg) 元组
    """
    from binance_client import has_user_api_keys, get_user_binance_client, BinanceFuturesClient

    # 路径 A: 优先尝试旧版密钥表
    if has_user_api_keys(user_id):
        client = get_user_binance_client(user_id)
        if client:
            return client, None

    # 路径 B: 回退到 exchange_accounts（通过 trader_instances 关联）
    try:
        from app.database import get_db_connection
        from app.services.workspace_service import _normalize_json
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # 查找用户的 trader_instance，获取关联的 exchange_account_id
                cur.execute("""
                    SELECT ti.exchange_account_id
                    FROM trader_instances ti
                    WHERE ti.user_id = %s AND ti.exchange_account_id IS NOT NULL
                    ORDER BY ti.id ASC LIMIT 1
                """, (user_id,))
                ti_row = cur.fetchone()
                if not ti_row:
                    return None, "No exchange account linked"

                ea_id = ti_row["exchange_account_id"]
                cur.execute(
                    "SELECT provider, metadata_json, environment FROM exchange_accounts WHERE id = %s AND user_id = %s",
                    (ea_id, user_id)
                )
                ea_row = cur.fetchone()
        finally:
            conn.close()

        if not ea_row:
            return None, "Exchange account not found"

        meta = _normalize_json(ea_row["metadata_json"]) if ea_row["metadata_json"] else {}
        raw_key = meta.get("api_key", "")
        raw_secret = meta.get("api_secret", "")
        environment = ea_row.get("environment", "demo")
        is_testnet = environment in ("testnet", "demo")

        # 解密（如果已加密）
        api_key, api_secret = raw_key, raw_secret
        if raw_key and raw_key.startswith("gAAAA"):
            try:
                from binance_client import decrypt_value
                api_key = decrypt_value(raw_key)
            except Exception:
                api_key = ""
        if raw_secret and raw_secret.startswith("gAAAA"):
            try:
                from binance_client import decrypt_value
                api_secret = decrypt_value(raw_secret)
            except Exception:
                api_secret = ""

        passphrase = meta.get("passphrase", "")
        if passphrase and passphrase.startswith("gAAAA"):
            try:
                from binance_client import decrypt_value
                passphrase = decrypt_value(passphrase)
            except Exception:
                passphrase = ""

        if api_key and api_secret:
            provider = ea_row.get("provider", "binance") if "provider" in ea_row.keys() else "binance"
            from exchange_factory import create_exchange_client
            client = create_exchange_client(
                provider=provider,
                api_key=api_key,
                api_secret=api_secret,
                passphrase=passphrase,
                environment=environment
            )
            return client, None
        return None, "API credentials empty"
    except Exception as e:
        return None, str(e)


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

    # 回退：直接通过 exchange_accounts 创建客户端
    if user_id:
        print(f"[StrategyContext] _fetch_account trying path-B for user {user_id[:8]}...")
        client, err = _get_binance_client_fallback(user_id)
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
            result["list"].append({
                "symbol": symbol,
                "direction": "LONG" if pos.get("direction") == "LONG" else "SHORT",
                "margin": pos.get("isolated_margin", 0),
                "entry_price": pos.get("entry_price", 0),
                "mark_price": pos.get("mark_price", 0),
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

    # 回退：直接通过 exchange_accounts 创建客户端
    if user_id:
        client, err = _get_binance_client_fallback(user_id)
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
    
    client, err = _get_binance_client_fallback(user_id) if user_id else (None, "no user_id")
    if not client:
        if err:
            result["error"] = err
        return result
    
    try:
        # 1. 获取普通挂单
        normal_orders = client.get_open_orders()
        if isinstance(normal_orders, list):
            for order in normal_orders:
                order_type = order.get("type", "")
                side = order.get("side", "")
                symbol = order.get("symbol", "").replace("USDT", "")
                
                def _safe_float(v):
                    if v is None or v == "": return 0.0
                    try: return float(v)
                    except: return 0.0
                
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
        
        # 2. 获取 Algo/条件挂单
        try:
            algo_orders = client.get_open_algo_orders()
            if isinstance(algo_orders, list):
                for order in algo_orders:
                    order_type = order.get("type", "")
                    side = order.get("side", "")
                    symbol = order.get("symbol", "").replace("USDT", "")
                    
                    result["list"].append({
                        "symbol": symbol,
                        "type": order_type,
                        "side": side,
                        "quantity": _safe_float(order.get("quantity") or order.get("origQty")),
                        "price": _safe_float(order.get("price")),
                        "stop_price": _safe_float(order.get("triggerPrice") or order.get("stopPrice")),
                        "reduce_only": str(order.get("reduceOnly", "")).lower() == "true",
                        "source": "algo",
                    })
        except Exception as e:
            print(f"[StrategyContext] _fetch_open_orders algo error: {e}")
        
        result["count"] = len(result["list"])
    except Exception as e:
        result["error"] = str(e)
    
    return result

def _fetch_macro() -> Dict:
    """获取市场宏观数据。"""
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
    """多周期趋势结构分析（EMA + Vegas + MACD）。"""
    result = {
        "direction": "neutral",
        "strength": "weak",
        "ema_bull": 0, "ema_bear": 0,
        "vegas_above": 0, "vegas_below": 0,
        "macd_bull": 0, "macd_bear": 0,
        "timeframes": {},
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
        except Exception:
            pass

        result["timeframes"][tf] = tf_data

    # 综合判断
    total_bull = result["ema_bull"] + result["vegas_above"] + result["macd_bull"]
    total_bear = result["ema_bear"] + result["vegas_below"] + result["macd_bear"]

    if total_bull + total_bear > 0:
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


def _fetch_levels(symbol: str, timeframe: str, price: float) -> Dict:
    """支撑阻力关键价位识别。"""
    result = {"nearest_support": None, "nearest_resistance": None, "confluence_zones": []}
    all_levels = []

    df = _get_binance_klines(symbol, timeframe, limit=100)
    if df is None or len(df) < 30:
        return result

    try:
        # EMA 关键位（当前周期）
        for length, label in [(21, "EMA21"), (55, "EMA55"), (200, "EMA200")]:
            if len(df) >= length:
                val = ta.ema(df["close"], length=length)
                if val is not None:
                    all_levels.append((val.iloc[-1], f"{label}_{timeframe}"))

        # 多周期 EMA 关键位
        for tf in ["4h", "1d", "1w"]:
            if tf == timeframe:
                continue
            df_tf = _get_binance_klines(symbol, tf)
            if df_tf is not None and len(df_tf) >= 55:
                ema21_tf = ta.ema(df_tf["close"], length=21).iloc[-1]
                ema55_tf = ta.ema(df_tf["close"], length=55).iloc[-1]
                all_levels.append((ema21_tf, f"EMA21_{tf}"))
                all_levels.append((ema55_tf, f"EMA55_{tf}"))

                if len(df_tf) >= 170:
                    ema144 = ta.ema(df_tf["close"], length=144).iloc[-1]
                    ema169 = ta.ema(df_tf["close"], length=169).iloc[-1]
                    all_levels.append((max(ema144, ema169), f"VegasTop_{tf}"))
                    all_levels.append((min(ema144, ema169), f"VegasBot_{tf}"))

        # Fibonacci 回撤
        swing_high, swing_low = _find_swing_points(df, window=7)
        high_price = swing_high["price"]
        low_price = swing_low["price"]
        diff = high_price - low_price
        is_uptrend = swing_high["index"] > swing_low["index"]
        for fib in [0.382, 0.5, 0.618]:
            level = (high_price - diff * fib) if is_uptrend else (low_price + diff * fib)
            all_levels.append((level, f"Fib_{fib}"))
    except Exception:
        pass

    # 最近支撑/阻力
    supports = [(l, n) for l, n in all_levels if l < price]
    resistances = [(l, n) for l, n in all_levels if l > price]

    if supports:
        supports.sort(key=lambda x: x[0], reverse=True)
        s = supports[0]
        result["nearest_support"] = {
            "price": round(s[0], 2),
            "dist_pct": round(((price - s[0]) / price) * 100, 1),
            "source": s[1],
        }

    if resistances:
        resistances.sort(key=lambda x: x[0])
        r = resistances[0]
        result["nearest_resistance"] = {
            "price": round(r[0], 2),
            "dist_pct": round(((r[0] - price) / price) * 100, 1),
            "source": r[1],
        }

    # 汇聚区
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

    # 宏观
    macro = data.get("macro", {})
    if macro.get("fng") is not None:
        parts.append(f"FnG:{macro['fng']}")

    return " | ".join(parts)
