"""
Exchange Client Abstract Base Class

Unified interface for all exchange clients (Binance, OKX, etc.)
Inspired by nofx/trader/types/interface.go

All exchange implementations must inherit from ExchangeClient and implement
the abstract methods. Return values use unified key names across all exchanges.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Any


class ExchangeClient(ABC):
    """
    统一交易所客户端接口。
    
    所有交易所实现必须继承此基类并实现所有抽象方法。
    返回值需要统一键名，确保上层业务逻辑不需要感知具体交易所差异。
    
    参考: nofx/trader/types/interface.go (Trader interface)
    """

    # ==========================================
    # 连接测试
    # ==========================================

    @abstractmethod
    def test_connection(self) -> dict:
        """
        测试 API 连接是否正常。
        
        Returns:
            {"success": True, "balance": {...}} 成功时
            {"success": False, "error": "..."} 失败时
        """
        pass

    # ==========================================
    # 账户信息
    # ==========================================

    @abstractmethod
    def get_account_info(self) -> dict:
        """
        获取完整账户信息（原始格式）。
        
        Returns:
            交易所原始账户信息 dict
        """
        pass

    @abstractmethod
    def get_usdt_balance(self) -> dict:
        """
        获取 USDT 余额摘要。
        
        Returns (统一键名 — snake_case):
            {
                "wallet_balance": float,       # 钱包总余额 (USDT)
                "available_balance": float,    # 可用余额
                "margin_balance": float,       # 保证金余额 (含未实现盈亏)
                "unrealized_pnl": float,       # 总未实现盈亏
                "assets": [                    # 各资产明细
                    {
                        "asset": "USDT",
                        "walletBalance": float,
                        "marginBalance": float,
                        "unrealizedProfit": float,
                        "availableBalance": float
                    }
                ]
            }
        """
        pass

    # ==========================================
    # 持仓查询
    # ==========================================

    @abstractmethod
    def get_positions(self) -> List[dict]:
        """
        获取所有持仓（仅含非零仓位）。
        
        Returns (每个持仓的统一键名 — snake_case):
            [
                {
                    "symbol": str,              # 统一格式: BTCUSDT（无分隔符/后缀）
                    "direction": str,           # "LONG" | "SHORT"
                    "quantity": float,          # 持仓数量（正数, 方向已由 direction 表示）
                    "entry_price": float,       # 开仓均价
                    "mark_price": float,        # 标记价格
                    "unrealized_pnl": float,    # 未实现盈亏
                    "leverage": int,            # 杠杆倍数
                    "margin_type": str,         # "cross" | "isolated"
                    "liquidation_price": float, # 强平价格
                },
                ...
            ]
        
        注意:
            - symbol 必须为统一格式 XXUSDT，不含 "-"、"_" 或 "-SWAP" 后缀
            - quantity 必须为正数、以 base coin 为单位（OKX 合约张数需乘以 ctVal）
            - leverage 必须为 int 类型
        """
        pass

    # ==========================================
    # 合约信息与精度
    # ==========================================

    def get_instrument_info(self, symbol: str) -> dict:
        """
        获取交易对的精度与最小量信息。
        
        子类可覆盖此方法从交易所 API 动态获取。
        默认实现返回安全的保守值。
        
        Returns:
            {
                "qty_precision": int,       # 数量小数位
                "price_precision": int,     # 价格小数位
                "min_qty": float,           # 最小下单量
                "min_notional": float,      # 最小名义价值 (USDT)
                "ct_val": float,            # 合约面值 (OKX用, 其他交易所=1.0)
            }
        """
        return {
            "qty_precision": 3,
            "price_precision": 2,
            "min_qty": 0.001,
            "min_notional": 5.0,
            "ct_val": 1.0,
        }

    def format_quantity(self, symbol: str, quantity: float) -> float:
        """按交易所精度规则格式化数量。"""
        info = self.get_instrument_info(symbol)
        return round(quantity, info["qty_precision"])

    def format_price(self, symbol: str, price: float) -> float:
        """按交易所精度规则格式化价格。"""
        info = self.get_instrument_info(symbol)
        return round(price, info["price_precision"])

    # ==========================================
    # 缓存层 (减少高频 API 调用)
    # ==========================================

    def get_cached_balance(self, ttl: int = 5) -> dict:
        """
        获取带 TTL 缓存的余额信息。
        
        在同一个 Agent 执行周期内（通常 5-10 秒），多次调用不会重复请求 API。
        下单操作后应调用 invalidate_cache() 清除缓存。
        
        Args:
            ttl: 缓存有效期（秒），默认 5 秒
            
        Returns:
            与 get_usdt_balance() 格式相同
        """
        import time
        now = time.time()
        if hasattr(self, '_balance_cache') and self._balance_cache is not None:
            if now - self._balance_cache_time < ttl:
                return self._balance_cache
        
        result = self.get_usdt_balance()
        if "error" not in result:
            self._balance_cache = result
            self._balance_cache_time = now
        return result

    def get_cached_positions(self, ttl: int = 5) -> list:
        """
        获取带 TTL 缓存的持仓列表。
        
        Args:
            ttl: 缓存有效期（秒），默认 5 秒
            
        Returns:
            与 get_positions() 格式相同
        """
        import time
        now = time.time()
        if hasattr(self, '_positions_cache') and self._positions_cache is not None:
            if now - self._positions_cache_time < ttl:
                return self._positions_cache
        
        result = self.get_positions()
        if isinstance(result, list):
            self._positions_cache = result
            self._positions_cache_time = now
        return result

    def invalidate_cache(self):
        """清除余额和持仓缓存（下单/平仓后调用）。"""
        self._balance_cache = None
        self._balance_cache_time = 0
        self._positions_cache = None
        self._positions_cache_time = 0

    # ==========================================
    # 高层便捷方法
    # ==========================================

    def open_long(self, symbol: str, quantity: float, **kwargs) -> dict:
        """
        做多开仓的便捷方法。
        
        Args:
            symbol: 交易对 (如 BTCUSDT)
            quantity: 数量
            **kwargs: 传递给 place_market_order 的其他参数 (reduce_only, position_side 等)
        
        Returns:
            下单结果 dict
        """
        result = self.place_market_order(symbol, "BUY", quantity, position_side="LONG", **kwargs)
        self.invalidate_cache()
        return result

    def open_short(self, symbol: str, quantity: float, **kwargs) -> dict:
        """做空开仓的便捷方法。"""
        result = self.place_market_order(symbol, "SELL", quantity, position_side="SHORT", **kwargs)
        self.invalidate_cache()
        return result

    def close_long(self, symbol: str, quantity: float, **kwargs) -> dict:
        """平多仓的便捷方法。"""
        result = self.place_market_order(symbol, "SELL", quantity, reduce_only=True, position_side="LONG", **kwargs)
        self.invalidate_cache()
        return result

    def close_short(self, symbol: str, quantity: float, **kwargs) -> dict:
        """平空仓的便捷方法。"""
        result = self.place_market_order(symbol, "BUY", quantity, reduce_only=True, position_side="SHORT", **kwargs)
        self.invalidate_cache()
        return result

    def get_position_for_symbol(self, symbol: str) -> Optional[dict]:
        """
        获取指定交易对的持仓（如果有）。
        
        Args:
            symbol: 交易对 (如 BTCUSDT)
        
        Returns:
            持仓 dict 或 None
        """
        positions = self.get_cached_positions()
        if isinstance(positions, list):
            for pos in positions:
                if pos.get("symbol") == symbol:
                    return pos
        return None

    # ==========================================
    # 下单操作
    # ==========================================

    @abstractmethod
    def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        reduce_only: bool = False,
        position_side: str = None
    ) -> dict:
        """
        市价下单。
        
        Args:
            symbol: 交易对 (e.g. "BTCUSDT")
            side: "BUY" or "SELL"
            quantity: 下单数量
            reduce_only: 是否仅平仓
            position_side: "LONG" or "SHORT" (双向持仓模式)
        
        Returns:
            {"orderId": str, "symbol": str, "status": str, ...}
        """
        pass

    @abstractmethod
    def place_stop_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_price: float,
        reduce_only: bool = True,
        position_side: str = None
    ) -> dict:
        """
        止损市价单。
        
        Args:
            symbol: 交易对
            side: "BUY" or "SELL"
            quantity: 下单数量
            stop_price: 触发价格
            reduce_only: 是否仅平仓
            position_side: "LONG" or "SHORT"
        
        Returns:
            订单响应 dict
        """
        pass

    @abstractmethod
    def place_take_profit_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_price: float,
        reduce_only: bool = True,
        position_side: str = None
    ) -> dict:
        """
        止盈市价单。
        
        Args:
            symbol: 交易对
            side: "BUY" or "SELL"
            quantity: 下单数量
            stop_price: 触发价格
            reduce_only: 是否仅平仓
            position_side: "LONG" or "SHORT"
        
        Returns:
            订单响应 dict
        """
        pass

    # ==========================================
    # 杠杆与保证金
    # ==========================================

    @abstractmethod
    def set_leverage(self, symbol: str, leverage: int) -> dict:
        """
        设置杠杆倍数。
        
        Args:
            symbol: 交易对
            leverage: 杠杆倍数
        
        Returns:
            {"leverage": int, "symbol": str, ...}
        """
        pass

    @abstractmethod
    def set_margin_type(self, symbol: str, margin_type: str) -> dict:
        """
        设置保证金模式。
        
        Args:
            symbol: 交易对
            margin_type: "CROSSED" or "ISOLATED"
        
        Returns:
            操作结果 dict
        """
        pass

    # ==========================================
    # 订单管理
    # ==========================================

    @abstractmethod
    def cancel_order(self, symbol: str, order_id: str) -> dict:
        """
        取消单笔普通挂单。
        
        Args:
            symbol: 交易对
            order_id: 订单 ID
        
        Returns:
            取消结果 dict
        """
        pass

    @abstractmethod
    def cancel_algo_order(self, symbol: str, algo_id: str) -> dict:
        """
        取消单笔条件单（止损/止盈/跟踪止损）。
        
        Args:
            symbol: 交易对
            algo_id: 条件单 ID
        
        Returns:
            取消结果 dict
        """
        pass

    @abstractmethod
    def cancel_all_orders(self, symbol: str) -> dict:
        """
        取消某交易对的所有普通挂单。
        
        Args:
            symbol: 交易对
        
        Returns:
            取消结果 dict
        """
        pass

    @abstractmethod
    def cancel_all_algo_orders(self, symbol: str) -> dict:
        """
        取消某交易对的所有条件单（止损/止盈）。
        
        Args:
            symbol: 交易对
        
        Returns:
            取消结果 dict
        """
        pass

    @abstractmethod
    def cancel_all_orders_and_algo(self, symbol: str) -> dict:
        """
        取消某交易对的所有挂单，包括普通挂单和条件单。
        
        Args:
            symbol: 交易对
        
        Returns:
            取消结果 dict
        """
        pass

    @abstractmethod
    def get_open_orders(self, symbol: Optional[str] = None) -> List[dict]:
        """
        获取所有待成交的普通挂单。
        
        Args:
            symbol: 交易对（None 则查所有）
        
        Returns:
            挂单列表
        """
        pass

    @abstractmethod
    def get_open_algo_orders(self, symbol: Optional[str] = None) -> List[dict]:
        """
        获取所有待触发的条件单。
        
        Args:
            symbol: 交易对（None 则查所有）
        
        Returns:
            条件单列表
        """
        pass

    # ==========================================
    # 行情查询
    # ==========================================

    @abstractmethod
    def get_mark_price(self, symbol: str) -> dict:
        """
        获取标记价格。
        
        Args:
            symbol: 交易对
        
        Returns:
            {"markPrice": float, "indexPrice": float, "lastFundingRate": float, ...}
        """
        pass

    # ==========================================
    # 持仓模式
    # ==========================================

    @abstractmethod
    def get_position_mode(self) -> dict:
        """
        获取持仓模式（单向/双向）。
        
        Returns:
            {"dualSidePosition": bool}  # True = 双向持仓, False = 单向持仓
        """
        pass

    # ==========================================
    # 历史查询
    # ==========================================

    @abstractmethod
    def get_trade_history(self, symbol: str, limit: int = 50, fromId: int = None) -> List[dict]:
        """
        获取成交历史。
        
        Args:
            symbol: 交易对
            limit: 返回数量
            fromId: 起始成交ID
        
        Returns (统一键名):
            [
                {
                    "id": int | str,            # 成交ID
                    "symbol": str,              # 统一格式 XXUSDT
                    "orderId": str | int,       # 关联订单ID
                    "side": str,                # "BUY" | "SELL" 大写
                    "price": float,             # 成交价格 (必须 float)
                    "qty": float,               # 成交数量 (必须 float)
                    "realizedPnl": float,       # 已实现盈亏
                    "commission": float,        # 手续费
                    "time": int,                # 毫秒时间戳
                    "positionSide": str,        # 可选: "LONG" | "SHORT" | "BOTH"
                }
            ]
        """
        pass

    def get_position_history(self, symbol: str, limit: int = 50) -> List[dict]:
        """获取原生仓位历史。子类可选实现。"""
        return []

    @abstractmethod
    def get_order_history(self, symbol: str, limit: int = 50) -> List[dict]:
        """
        获取历史订单。
        
        Args:
            symbol: 交易对
            limit: 返回数量
        
        Returns (统一键名):
            [
                {
                    "orderId": str | int,
                    "symbol": str,              # 统一格式 XXUSDT
                    "side": str,                # "BUY" | "SELL" 大写
                    "type": str,                # "LIMIT" | "MARKET" | ...
                    "origQty": float,
                    "executedQty": float,
                    "price": float,
                    "avgPrice": float,
                    "reduceOnly": bool,
                    "status": str,              # "FILLED" | "CANCELED" | "EXPIRED"
                    "time": int,                # 毫秒时间戳
                    "updateTime": int,
                }
            ]
        """
        pass

    # ==========================================
    # 资金与流水
    # ==========================================

    @abstractmethod
    def get_income_history(
        self,
        symbol: Optional[str] = None,
        income_type: Optional[str] = None,
        limit: int = 100
    ) -> List[dict]:
        """
        获取资金流水（资金费率、已实现盈亏、手续费等）。

        Returns (统一键名):
            [
                {
                    "symbol": str,              # 交易对 (可能为空)
                    "type": str,                # "REALIZED_PNL" | "FUNDING_FEE" | "COMMISSION" | "TRANSFER" | ...
                    "amount": float,            # 金额 (注意: 不是 "income"!)
                    "asset": str,               # "USDT"
                    "time": int,                # 毫秒时间戳 (必须 int)
                    "info": str                 # 备注 (可选)
                },
                ...
            ]
        
        注意:
            - Binance 原始字段为 income/incomeType，必须在客户端层映射为 amount/type
            - OKX type="2" 的记录需拆分为 COMMISSION + REALIZED_PNL 两条
            - amount 和 time 必须为 float / int，不可透传字符串
        """
        pass

    # ==========================================
    # 批量下单
    # ==========================================

    @abstractmethod
    def place_batch_orders(self, orders: list) -> list:
        """
        批量下单 (主订单 + 止盈止损)。

        Args:
            orders: 订单列表，每个订单为 dict 包含:
                - symbol, side, type, quantity, price(limit), positionSide(hedge) ...

        Returns:
            订单结果列表
        """
        pass

    # ==========================================
    # 可选扩展方法 (默认实现)
    # 子类可以覆盖以提供真实数据
    # ==========================================

    def get_funding_rate(self, symbol: str, limit: int = 100) -> List[dict]:
        """获取资金费率历史。子类可选实现。"""
        return []

    def get_leverage_bracket(self, symbol: str = None) -> List[dict]:
        """获取杠杆档位信息。子类可选实现。"""
        return []

    def get_adl_quantile(self, symbol: str = None) -> Any:
        """获取 ADL 风险等级。子类可选实现。"""
        return []

    def get_force_orders(self, symbol: str = None, limit: int = 50) -> List[dict]:
        """获取强平订单历史。子类可选实现。"""
        return []

    def get_commission_rate(self, symbol: str) -> dict:
        """获取佣金费率。子类可选实现。"""
        return {"error": "Not supported by this exchange"}

    # ==========================================
    # 工具方法
    # ==========================================

    def get_exchange_name(self) -> str:
        """
        获取交易所名称（用于日志和 UI 显示）。
        子类可以覆盖此方法。
        """
        return self.__class__.__name__
