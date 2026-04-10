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
        
        Returns (统一键名):
            {
                "totalWalletBalance": float,     # 总钱包余额
                "availableBalance": float,       # 可用余额
                "totalUnrealizedProfit": float,  # 总未实现盈亏
            }
        """
        pass

    # ==========================================
    # 持仓查询
    # ==========================================

    @abstractmethod
    def get_positions(self) -> List[dict]:
        """
        获取所有持仓。
        
        Returns (每个持仓的统一键名):
            [
                {
                    "symbol": str,           # 交易对 (e.g. "BTCUSDT")
                    "positionAmt": float,    # 持仓数量（正=多，负=空）
                    "entryPrice": float,     # 开仓均价
                    "markPrice": float,      # 标记价格
                    "unRealizedProfit": float,# 未实现盈亏
                    "leverage": int,         # 杠杆倍数
                    "positionSide": str,     # "LONG" / "SHORT" / "BOTH"
                    "marginType": str,       # "cross" / "isolated"
                    "liquidationPrice": float,# 强平价格
                },
                ...
            ]
        """
        pass

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
        
        Returns:
            成交记录列表
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
        
        Returns:
            订单记录列表
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
                    "amount": float,            # 金额
                    "asset": str,               # "USDT"
                    "time": int,                # 毫秒时间戳
                    "info": str                 # 备注 (可选)
                },
                ...
            ]
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
