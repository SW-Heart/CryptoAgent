"""
量化回测策略库

所有策略通过统一接口:
  - init(df)  : 预计算指标
  - signal(idx): 每根K线返回交易信号

信号格式:
  {"action": "BUY"|"SELL"|"HOLD", "sl": float, "tp": float, "reason": str}
"""
import pandas as pd
import numpy as np
import pandas_ta as ta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


# ============================================================
# 策略参数定义
# ============================================================

@dataclass
class ParamDef:
    """策略参数定义 (用于前端渲染表单)."""
    name: str
    label: str
    type: str = "int"      # int, float, select
    default: Any = 0
    min: Any = None
    max: Any = None
    step: Any = None
    options: List[dict] = field(default_factory=list)  # for select type
    description: str = ""


# ============================================================
# 基类
# ============================================================

class BaseStrategy:
    """所有回测策略的基类."""

    name: str = "base"
    label: str = "基础策略"
    description: str = ""
    icon: str = "📊"
    category: str = "trend"   # trend, momentum, volatility, multi
    param_defs: List[ParamDef] = []

    def __init__(self, params: dict = None):
        self.params = params or {}
        # 用默认值填充未提供的参数
        for p in self.param_defs:
            if p.name not in self.params:
                self.params[p.name] = p.default
        self._df: Optional[pd.DataFrame] = None
        self._indicators: dict = {}

    def init(self, df: pd.DataFrame) -> None:
        """预计算指标 (回测开始前调用一次)."""
        self._df = df

    def signal(self, idx: int) -> dict:
        """
        每根K线调用一次, 返回交易信号.

        Args:
            idx: 当前K线在 DataFrame 中的索引

        Returns:
            {
                "action": "BUY" | "SELL" | "HOLD",
                "sl": float or None,    # 止损价
                "tp": float or None,    # 止盈价
                "reason": str,          # 信号原因
            }
        """
        return {"action": "HOLD", "sl": None, "tp": None, "reason": ""}

    def to_dict(self) -> dict:
        """序列化策略信息 (用于API返回)."""
        return {
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "icon": self.icon,
            "category": self.category,
            "params": [
                {
                    "name": p.name, "label": p.label, "type": p.type,
                    "default": p.default, "min": p.min, "max": p.max,
                    "step": p.step, "options": p.options,
                    "description": p.description,
                }
                for p in self.param_defs
            ],
        }


# ============================================================
# 1. 双均线金叉/死叉 (EMA Cross)
# ============================================================

class EMACrossStrategy(BaseStrategy):
    name = "ema_cross"
    label = "双均线交叉"
    description = "EMA 快线上穿慢线做多, 下穿做空。经典趋势跟踪策略。"
    icon = "📈"
    category = "trend"
    param_defs = [
        ParamDef("fast_period", "快线周期", "int", 12, 3, 100, 1, description="快速 EMA 周期"),
        ParamDef("slow_period", "慢线周期", "int", 26, 5, 300, 1, description="慢速 EMA 周期"),
        ParamDef("atr_sl_mult", "ATR止损倍数", "float", 1.5, 0.5, 5.0, 0.1, description="止损距离 = ATR × 倍数"),
        ParamDef("rr_ratio", "盈亏比", "float", 2.0, 1.0, 5.0, 0.5, description="止盈 = 止损距离 × 盈亏比"),
    ]

    def init(self, df: pd.DataFrame) -> None:
        self._df = df
        fp = self.params["fast_period"]
        sp = self.params["slow_period"]
        self._indicators["ema_fast"] = ta.ema(df["close"], length=fp)
        self._indicators["ema_slow"] = ta.ema(df["close"], length=sp)
        self._indicators["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)

    def signal(self, idx: int) -> dict:
        if idx < 2:
            return {"action": "HOLD", "sl": None, "tp": None, "reason": ""}

        ema_f = self._indicators["ema_fast"]
        ema_s = self._indicators["ema_slow"]
        atr = self._indicators["atr"]

        if pd.isna(ema_f.iloc[idx]) or pd.isna(ema_s.iloc[idx]) or pd.isna(atr.iloc[idx]):
            return {"action": "HOLD", "sl": None, "tp": None, "reason": "指标预热中"}

        price = float(self._df["close"].iloc[idx])
        atr_val = float(atr.iloc[idx])
        sl_dist = atr_val * self.params["atr_sl_mult"]
        tp_dist = sl_dist * self.params["rr_ratio"]

        # 金叉: 快线从下方穿越慢线
        if ema_f.iloc[idx] > ema_s.iloc[idx] and ema_f.iloc[idx - 1] <= ema_s.iloc[idx - 1]:
            return {
                "action": "BUY",
                "sl": round(price - sl_dist, 2),
                "tp": round(price + tp_dist, 2),
                "reason": f"EMA{self.params['fast_period']}上穿EMA{self.params['slow_period']}",
            }

        # 死叉: 快线从上方穿越慢线
        if ema_f.iloc[idx] < ema_s.iloc[idx] and ema_f.iloc[idx - 1] >= ema_s.iloc[idx - 1]:
            return {
                "action": "SELL",
                "sl": round(price + sl_dist, 2),
                "tp": round(price - tp_dist, 2),
                "reason": f"EMA{self.params['fast_period']}下穿EMA{self.params['slow_period']}",
            }

        return {"action": "HOLD", "sl": None, "tp": None, "reason": ""}


# ============================================================
# 2. RSI 超买超卖 (RSI Reversal)
# ============================================================

class RSIReversalStrategy(BaseStrategy):
    name = "rsi_reversal"
    label = "RSI 反转"
    description = "RSI 超卖区反弹做多, 超买区回落做空。均值回归策略。"
    icon = "🔄"
    category = "momentum"
    param_defs = [
        ParamDef("rsi_period", "RSI周期", "int", 14, 5, 50, 1),
        ParamDef("oversold", "超卖阈值", "int", 30, 10, 40, 5, description="低于此值考虑做多"),
        ParamDef("overbought", "超买阈值", "int", 70, 60, 90, 5, description="高于此值考虑做空"),
        ParamDef("atr_sl_mult", "ATR止损倍数", "float", 2.0, 0.5, 5.0, 0.1),
        ParamDef("rr_ratio", "盈亏比", "float", 1.5, 1.0, 5.0, 0.5),
    ]

    def init(self, df: pd.DataFrame) -> None:
        self._df = df
        self._indicators["rsi"] = ta.rsi(df["close"], length=self.params["rsi_period"])
        self._indicators["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)

    def signal(self, idx: int) -> dict:
        if idx < 2:
            return {"action": "HOLD", "sl": None, "tp": None, "reason": ""}

        rsi = self._indicators["rsi"]
        atr = self._indicators["atr"]

        if pd.isna(rsi.iloc[idx]) or pd.isna(atr.iloc[idx]):
            return {"action": "HOLD", "sl": None, "tp": None, "reason": "指标预热中"}

        rsi_val = float(rsi.iloc[idx])
        rsi_prev = float(rsi.iloc[idx - 1])
        price = float(self._df["close"].iloc[idx])
        atr_val = float(atr.iloc[idx])
        sl_dist = atr_val * self.params["atr_sl_mult"]
        tp_dist = sl_dist * self.params["rr_ratio"]

        oversold = self.params["oversold"]
        overbought = self.params["overbought"]

        # 超卖区反弹: RSI 从下方穿越超卖线
        if rsi_val > oversold and rsi_prev <= oversold:
            return {
                "action": "BUY",
                "sl": round(price - sl_dist, 2),
                "tp": round(price + tp_dist, 2),
                "reason": f"RSI({rsi_val:.0f})从超卖区反弹",
            }

        # 超买区回落: RSI 从上方穿越超买线
        if rsi_val < overbought and rsi_prev >= overbought:
            return {
                "action": "SELL",
                "sl": round(price + sl_dist, 2),
                "tp": round(price - tp_dist, 2),
                "reason": f"RSI({rsi_val:.0f})从超买区回落",
            }

        return {"action": "HOLD", "sl": None, "tp": None, "reason": ""}


# ============================================================
# 3. MACD 信号线交叉
# ============================================================

class MACDCrossStrategy(BaseStrategy):
    name = "macd_cross"
    label = "MACD 交叉"
    description = "MACD 线上穿信号线做多, 下穿做空。兼顾趋势与动量。"
    icon = "📊"
    category = "momentum"
    param_defs = [
        ParamDef("fast", "快线周期", "int", 12, 5, 50, 1),
        ParamDef("slow", "慢线周期", "int", 26, 10, 100, 1),
        ParamDef("signal_period", "信号线周期", "int", 9, 3, 30, 1),
        ParamDef("atr_sl_mult", "ATR止损倍数", "float", 1.5, 0.5, 5.0, 0.1),
        ParamDef("rr_ratio", "盈亏比", "float", 2.0, 1.0, 5.0, 0.5),
    ]

    def init(self, df: pd.DataFrame) -> None:
        self._df = df
        macd_result = ta.macd(
            df["close"],
            fast=self.params["fast"],
            slow=self.params["slow"],
            signal=self.params["signal_period"],
        )
        if macd_result is not None:
            self._indicators["macd_line"] = macd_result.iloc[:, 0]
            self._indicators["signal_line"] = macd_result.iloc[:, 1]
            self._indicators["histogram"] = macd_result.iloc[:, 2]
        self._indicators["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)

    def signal(self, idx: int) -> dict:
        if idx < 2 or "macd_line" not in self._indicators:
            return {"action": "HOLD", "sl": None, "tp": None, "reason": ""}

        macd = self._indicators["macd_line"]
        signal_line = self._indicators["signal_line"]
        atr = self._indicators["atr"]

        if pd.isna(macd.iloc[idx]) or pd.isna(signal_line.iloc[idx]) or pd.isna(atr.iloc[idx]):
            return {"action": "HOLD", "sl": None, "tp": None, "reason": "指标预热中"}

        price = float(self._df["close"].iloc[idx])
        atr_val = float(atr.iloc[idx])
        sl_dist = atr_val * self.params["atr_sl_mult"]
        tp_dist = sl_dist * self.params["rr_ratio"]

        # MACD 金叉
        if macd.iloc[idx] > signal_line.iloc[idx] and macd.iloc[idx - 1] <= signal_line.iloc[idx - 1]:
            return {
                "action": "BUY",
                "sl": round(price - sl_dist, 2),
                "tp": round(price + tp_dist, 2),
                "reason": "MACD金叉",
            }

        # MACD 死叉
        if macd.iloc[idx] < signal_line.iloc[idx] and macd.iloc[idx - 1] >= signal_line.iloc[idx - 1]:
            return {
                "action": "SELL",
                "sl": round(price + sl_dist, 2),
                "tp": round(price - tp_dist, 2),
                "reason": "MACD死叉",
            }

        return {"action": "HOLD", "sl": None, "tp": None, "reason": ""}


# ============================================================
# 4. 布林通道突破 (Bollinger Bands Breakout)
# ============================================================

class BollingerBreakoutStrategy(BaseStrategy):
    name = "bollinger_breakout"
    label = "布林通道突破"
    description = "价格突破上轨做多, 突破下轨做空。捕捉波动率扩张行情。"
    icon = "🎯"
    category = "volatility"
    param_defs = [
        ParamDef("bb_period", "布林周期", "int", 20, 10, 50, 1),
        ParamDef("bb_std", "标准差倍数", "float", 2.0, 1.0, 3.0, 0.5),
        ParamDef("atr_sl_mult", "ATR止损倍数", "float", 1.5, 0.5, 5.0, 0.1),
        ParamDef("rr_ratio", "盈亏比", "float", 2.0, 1.0, 5.0, 0.5),
    ]

    def init(self, df: pd.DataFrame) -> None:
        self._df = df
        bbands = ta.bbands(df["close"], length=self.params["bb_period"], std=self.params["bb_std"])
        if bbands is not None:
            self._indicators["bb_lower"] = bbands.iloc[:, 0]
            self._indicators["bb_mid"] = bbands.iloc[:, 1]
            self._indicators["bb_upper"] = bbands.iloc[:, 2]
        self._indicators["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)

    def signal(self, idx: int) -> dict:
        if idx < 2 or "bb_upper" not in self._indicators:
            return {"action": "HOLD", "sl": None, "tp": None, "reason": ""}

        upper = self._indicators["bb_upper"]
        lower = self._indicators["bb_lower"]
        atr = self._indicators["atr"]

        if pd.isna(upper.iloc[idx]) or pd.isna(atr.iloc[idx]):
            return {"action": "HOLD", "sl": None, "tp": None, "reason": "指标预热中"}

        price = float(self._df["close"].iloc[idx])
        prev_price = float(self._df["close"].iloc[idx - 1])
        atr_val = float(atr.iloc[idx])
        sl_dist = atr_val * self.params["atr_sl_mult"]
        tp_dist = sl_dist * self.params["rr_ratio"]

        # 突破上轨做多
        if price > float(upper.iloc[idx]) and prev_price <= float(upper.iloc[idx - 1]):
            return {
                "action": "BUY",
                "sl": round(price - sl_dist, 2),
                "tp": round(price + tp_dist, 2),
                "reason": "突破布林上轨",
            }

        # 突破下轨做空
        if price < float(lower.iloc[idx]) and prev_price >= float(lower.iloc[idx - 1]):
            return {
                "action": "SELL",
                "sl": round(price + sl_dist, 2),
                "tp": round(price - tp_dist, 2),
                "reason": "突破布林下轨",
            }

        return {"action": "HOLD", "sl": None, "tp": None, "reason": ""}


# ============================================================
# 5. Vegas 通道策略
# ============================================================

class VegasChannelStrategy(BaseStrategy):
    name = "vegas_channel"
    label = "Vegas 通道"
    description = "EMA144/169 构成通道，价格突破通道方向交易。适合中长线趋势。"
    icon = "🎰"
    category = "trend"
    param_defs = [
        ParamDef("ema_short", "短周期EMA", "int", 144, 50, 200, 1),
        ParamDef("ema_long", "长周期EMA", "int", 169, 100, 300, 1),
        ParamDef("atr_sl_mult", "ATR止损倍数", "float", 2.0, 0.5, 5.0, 0.1),
        ParamDef("rr_ratio", "盈亏比", "float", 2.5, 1.0, 5.0, 0.5),
    ]

    def init(self, df: pd.DataFrame) -> None:
        self._df = df
        self._indicators["ema_s"] = ta.ema(df["close"], length=self.params["ema_short"])
        self._indicators["ema_l"] = ta.ema(df["close"], length=self.params["ema_long"])
        self._indicators["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)

    def signal(self, idx: int) -> dict:
        if idx < 2:
            return {"action": "HOLD", "sl": None, "tp": None, "reason": ""}

        ema_s = self._indicators["ema_s"]
        ema_l = self._indicators["ema_l"]
        atr = self._indicators["atr"]

        if pd.isna(ema_s.iloc[idx]) or pd.isna(ema_l.iloc[idx]) or pd.isna(atr.iloc[idx]):
            return {"action": "HOLD", "sl": None, "tp": None, "reason": "指标预热中"}

        price = float(self._df["close"].iloc[idx])
        prev_price = float(self._df["close"].iloc[idx - 1])
        atr_val = float(atr.iloc[idx])
        sl_dist = atr_val * self.params["atr_sl_mult"]
        tp_dist = sl_dist * self.params["rr_ratio"]

        channel_top = max(float(ema_s.iloc[idx]), float(ema_l.iloc[idx]))
        channel_bot = min(float(ema_s.iloc[idx]), float(ema_l.iloc[idx]))
        prev_top = max(float(ema_s.iloc[idx - 1]), float(ema_l.iloc[idx - 1]))
        prev_bot = min(float(ema_s.iloc[idx - 1]), float(ema_l.iloc[idx - 1]))

        # 突破通道上沿做多
        if price > channel_top and prev_price <= prev_top:
            return {
                "action": "BUY",
                "sl": round(price - sl_dist, 2),
                "tp": round(price + tp_dist, 2),
                "reason": "突破Vegas通道上沿",
            }

        # 突破通道下沿做空
        if price < channel_bot and prev_price >= prev_bot:
            return {
                "action": "SELL",
                "sl": round(price + sl_dist, 2),
                "tp": round(price - tp_dist, 2),
                "reason": "跌破Vegas通道下沿",
            }

        return {"action": "HOLD", "sl": None, "tp": None, "reason": ""}


# ============================================================
# 6. 三重EMA过滤 (Triple EMA)
# ============================================================

class TripleEMAStrategy(BaseStrategy):
    name = "triple_ema"
    label = "三重EMA过滤"
    description = "EMA21/55/200 三线多头排列做多, 空头排列做空。强趋势过滤器。"
    icon = "🔀"
    category = "trend"
    param_defs = [
        ParamDef("ema1", "短期EMA", "int", 21, 5, 50, 1),
        ParamDef("ema2", "中期EMA", "int", 55, 20, 100, 1),
        ParamDef("ema3", "长期EMA", "int", 200, 100, 400, 1),
        ParamDef("atr_sl_mult", "ATR止损倍数", "float", 2.0, 0.5, 5.0, 0.1),
        ParamDef("rr_ratio", "盈亏比", "float", 2.0, 1.0, 5.0, 0.5),
    ]

    def init(self, df: pd.DataFrame) -> None:
        self._df = df
        self._indicators["ema1"] = ta.ema(df["close"], length=self.params["ema1"])
        self._indicators["ema2"] = ta.ema(df["close"], length=self.params["ema2"])
        self._indicators["ema3"] = ta.ema(df["close"], length=self.params["ema3"])
        self._indicators["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)

    def signal(self, idx: int) -> dict:
        if idx < 2:
            return {"action": "HOLD", "sl": None, "tp": None, "reason": ""}

        e1 = self._indicators["ema1"]
        e2 = self._indicators["ema2"]
        e3 = self._indicators["ema3"]
        atr = self._indicators["atr"]

        if pd.isna(e3.iloc[idx]) or pd.isna(atr.iloc[idx]):
            return {"action": "HOLD", "sl": None, "tp": None, "reason": "指标预热中"}

        price = float(self._df["close"].iloc[idx])
        atr_val = float(atr.iloc[idx])
        sl_dist = atr_val * self.params["atr_sl_mult"]
        tp_dist = sl_dist * self.params["rr_ratio"]

        e1v, e2v, e3v = float(e1.iloc[idx]), float(e2.iloc[idx]), float(e3.iloc[idx])
        e1p, e2p, e3p = float(e1.iloc[idx - 1]), float(e2.iloc[idx - 1]), float(e3.iloc[idx - 1])

        bull_now = price > e1v > e2v > e3v
        bull_prev = not (float(self._df["close"].iloc[idx - 1]) > e1p > e2p > e3p)

        bear_now = price < e1v < e2v < e3v
        bear_prev = not (float(self._df["close"].iloc[idx - 1]) < e1p < e2p < e3p)

        # 多头排列刚形成
        if bull_now and bull_prev:
            return {
                "action": "BUY",
                "sl": round(price - sl_dist, 2),
                "tp": round(price + tp_dist, 2),
                "reason": "三EMA多头排列形成",
            }

        # 空头排列刚形成
        if bear_now and bear_prev:
            return {
                "action": "SELL",
                "sl": round(price + sl_dist, 2),
                "tp": round(price - tp_dist, 2),
                "reason": "三EMA空头排列形成",
            }

        return {"action": "HOLD", "sl": None, "tp": None, "reason": ""}


# ============================================================
# 7. RSI + EMA 趋势确认
# ============================================================

class RSITrendStrategy(BaseStrategy):
    name = "rsi_trend"
    label = "RSI趋势确认"
    description = "EMA 判方向 + RSI 确认动量。多因子过滤提高胜率。"
    icon = "🎛️"
    category = "multi"
    param_defs = [
        ParamDef("ema_period", "趋势EMA周期", "int", 50, 20, 200, 1),
        ParamDef("rsi_period", "RSI周期", "int", 14, 5, 50, 1),
        ParamDef("rsi_buy_threshold", "RSI买入阈值", "int", 40, 20, 50, 5, description="RSI从下方穿越此线+趋势向上→买入"),
        ParamDef("rsi_sell_threshold", "RSI卖出阈值", "int", 60, 50, 80, 5, description="RSI从上方穿越此线+趋势向下→卖出"),
        ParamDef("atr_sl_mult", "ATR止损倍数", "float", 1.5, 0.5, 5.0, 0.1),
        ParamDef("rr_ratio", "盈亏比", "float", 2.0, 1.0, 5.0, 0.5),
    ]

    def init(self, df: pd.DataFrame) -> None:
        self._df = df
        self._indicators["ema"] = ta.ema(df["close"], length=self.params["ema_period"])
        self._indicators["rsi"] = ta.rsi(df["close"], length=self.params["rsi_period"])
        self._indicators["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)

    def signal(self, idx: int) -> dict:
        if idx < 2:
            return {"action": "HOLD", "sl": None, "tp": None, "reason": ""}

        ema = self._indicators["ema"]
        rsi = self._indicators["rsi"]
        atr = self._indicators["atr"]

        if pd.isna(ema.iloc[idx]) or pd.isna(rsi.iloc[idx]) or pd.isna(atr.iloc[idx]):
            return {"action": "HOLD", "sl": None, "tp": None, "reason": "指标预热中"}

        price = float(self._df["close"].iloc[idx])
        ema_val = float(ema.iloc[idx])
        rsi_val = float(rsi.iloc[idx])
        rsi_prev = float(rsi.iloc[idx - 1])
        atr_val = float(atr.iloc[idx])
        sl_dist = atr_val * self.params["atr_sl_mult"]
        tp_dist = sl_dist * self.params["rr_ratio"]

        buy_th = self.params["rsi_buy_threshold"]
        sell_th = self.params["rsi_sell_threshold"]

        # 趋势向上 + RSI 穿越买入阈值
        if price > ema_val and rsi_val > buy_th and rsi_prev <= buy_th:
            return {
                "action": "BUY",
                "sl": round(price - sl_dist, 2),
                "tp": round(price + tp_dist, 2),
                "reason": f"趋势向上+RSI穿越{buy_th}",
            }

        # 趋势向下 + RSI 穿越卖出阈值
        if price < ema_val and rsi_val < sell_th and rsi_prev >= sell_th:
            return {
                "action": "SELL",
                "sl": round(price + sl_dist, 2),
                "tp": round(price - tp_dist, 2),
                "reason": f"趋势向下+RSI穿越{sell_th}",
            }

        return {"action": "HOLD", "sl": None, "tp": None, "reason": ""}


# ============================================================
# 8. MACD + RSI 多因子
# ============================================================

class MACDRSIStrategy(BaseStrategy):
    name = "macd_rsi"
    label = "MACD+RSI 双因子"
    description = "MACD 金叉 + RSI 未超买时做多, MACD 死叉 + RSI 未超卖时做空。双重过滤假信号。"
    icon = "⚡"
    category = "multi"
    param_defs = [
        ParamDef("macd_fast", "MACD快线", "int", 12, 5, 50, 1),
        ParamDef("macd_slow", "MACD慢线", "int", 26, 10, 100, 1),
        ParamDef("macd_signal", "MACD信号线", "int", 9, 3, 30, 1),
        ParamDef("rsi_period", "RSI周期", "int", 14, 5, 50, 1),
        ParamDef("rsi_overbought", "RSI超买", "int", 70, 60, 90, 5),
        ParamDef("rsi_oversold", "RSI超卖", "int", 30, 10, 40, 5),
        ParamDef("atr_sl_mult", "ATR止损倍数", "float", 1.5, 0.5, 5.0, 0.1),
        ParamDef("rr_ratio", "盈亏比", "float", 2.0, 1.0, 5.0, 0.5),
    ]

    def init(self, df: pd.DataFrame) -> None:
        self._df = df
        macd_result = ta.macd(
            df["close"],
            fast=self.params["macd_fast"],
            slow=self.params["macd_slow"],
            signal=self.params["macd_signal"],
        )
        if macd_result is not None:
            self._indicators["macd_line"] = macd_result.iloc[:, 0]
            self._indicators["signal_line"] = macd_result.iloc[:, 1]
        self._indicators["rsi"] = ta.rsi(df["close"], length=self.params["rsi_period"])
        self._indicators["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)

    def signal(self, idx: int) -> dict:
        if idx < 2 or "macd_line" not in self._indicators:
            return {"action": "HOLD", "sl": None, "tp": None, "reason": ""}

        macd = self._indicators["macd_line"]
        sig = self._indicators["signal_line"]
        rsi = self._indicators["rsi"]
        atr = self._indicators["atr"]

        if pd.isna(macd.iloc[idx]) or pd.isna(rsi.iloc[idx]) or pd.isna(atr.iloc[idx]):
            return {"action": "HOLD", "sl": None, "tp": None, "reason": "指标预热中"}

        price = float(self._df["close"].iloc[idx])
        rsi_val = float(rsi.iloc[idx])
        atr_val = float(atr.iloc[idx])
        sl_dist = atr_val * self.params["atr_sl_mult"]
        tp_dist = sl_dist * self.params["rr_ratio"]

        macd_cross_up = macd.iloc[idx] > sig.iloc[idx] and macd.iloc[idx - 1] <= sig.iloc[idx - 1]
        macd_cross_dn = macd.iloc[idx] < sig.iloc[idx] and macd.iloc[idx - 1] >= sig.iloc[idx - 1]

        # MACD 金叉 + RSI 未超买
        if macd_cross_up and rsi_val < self.params["rsi_overbought"]:
            return {
                "action": "BUY",
                "sl": round(price - sl_dist, 2),
                "tp": round(price + tp_dist, 2),
                "reason": f"MACD金叉+RSI({rsi_val:.0f})未超买",
            }

        # MACD 死叉 + RSI 未超卖
        if macd_cross_dn and rsi_val > self.params["rsi_oversold"]:
            return {
                "action": "SELL",
                "sl": round(price + sl_dist, 2),
                "tp": round(price - tp_dist, 2),
                "reason": f"MACD死叉+RSI({rsi_val:.0f})未超卖",
            }

        return {"action": "HOLD", "sl": None, "tp": None, "reason": ""}


# ============================================================
# 策略注册表
# ============================================================

STRATEGY_REGISTRY: Dict[str, type] = {
    "ema_cross": EMACrossStrategy,
    "rsi_reversal": RSIReversalStrategy,
    "macd_cross": MACDCrossStrategy,
    "bollinger_breakout": BollingerBreakoutStrategy,
    "vegas_channel": VegasChannelStrategy,
    "triple_ema": TripleEMAStrategy,
    "rsi_trend": RSITrendStrategy,
    "macd_rsi": MACDRSIStrategy,
}


def get_strategy(name: str, params: dict = None) -> BaseStrategy:
    """根据策略名称创建策略实例."""
    cls = STRATEGY_REGISTRY.get(name)
    if not cls:
        raise ValueError(f"未知策略类型: {name}. 可选: {list(STRATEGY_REGISTRY.keys())}")
    return cls(params=params)


def list_strategies() -> list:
    """列出所有可用策略 (用于API返回)."""
    result = []
    for name, cls in STRATEGY_REGISTRY.items():
        instance = cls()
        result.append(instance.to_dict())
    return result
