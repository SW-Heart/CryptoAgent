"""
模拟投资组合 (SimPortfolio)

在回测中替代真实交易所, 模拟:
- 开仓 (含手续费、保证金、杠杆)
- 平仓 (计算真实 PnL)
- 止损/止盈检查 (用 candle 的 high/low)
- 权益快照
- 输出为 strategy_context 兼容格式
"""
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime


@dataclass
class SimPosition:
    """模拟持仓."""
    id: str = ""
    symbol: str = ""
    direction: str = ""       # "LONG" or "SHORT"
    entry_price: float = 0
    quantity: float = 0       # 数量 (币)
    margin: float = 0         # 保证金 (USDT)
    leverage: int = 1
    stop_loss: float = 0
    take_profit: float = 0
    entry_time: str = ""
    entry_fee: float = 0

    def unrealized_pnl(self, current_price: float) -> float:
        """计算未实现盈亏."""
        if self.direction == "LONG":
            return (current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - current_price) * self.quantity

    def roi_pct(self, current_price: float) -> float:
        """计算 ROI%."""
        pnl = self.unrealized_pnl(current_price)
        if self.margin <= 0:
            return 0
        return round(pnl / self.margin * 100, 2)


@dataclass
class ClosedTrade:
    """已平仓交易记录."""
    id: str = ""
    symbol: str = ""
    direction: str = ""
    entry_price: float = 0
    exit_price: float = 0
    quantity: float = 0
    margin: float = 0
    leverage: int = 1
    pnl: float = 0              # 扣除手续费后的净盈亏
    pnl_pct: float = 0          # ROI%
    entry_time: str = ""
    exit_time: str = ""
    exit_reason: str = ""       # "SIGNAL", "SL", "TP", "MANUAL"
    entry_fee: float = 0
    exit_fee: float = 0
    agent_reasoning: str = ""   # Agent 决策原文

    def to_dict(self) -> dict:
        """序列化为字典."""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "quantity": round(self.quantity, 6),
            "margin": round(self.margin, 2),
            "leverage": self.leverage,
            "pnl": round(self.pnl, 2),
            "pnl_pct": self.pnl_pct,
            "entry_time": self.entry_time,
            "exit_time": self.exit_time,
            "exit_reason": self.exit_reason,
            "fees": round(self.entry_fee + self.exit_fee, 4),
        }


class SimPortfolio:
    """
    模拟投资组合管理器.
    
    职责:
    - 维护虚拟资金和仓位状态
    - 模拟开仓/平仓/止损止盈
    - 生成与 strategy_context 兼容的字典
    - 在每根K线上检查 SL/TP 触发
    """

    FEE_RATE = 0.0005  # 0.05% 单边手续费 (Binance taker)

    def __init__(self, initial_capital: float = 10000):
        self.initial_capital = initial_capital
        self.cash = initial_capital      # 可用资金
        self.positions: List[SimPosition] = []
        self.closed_trades: List[ClosedTrade] = []
        self.equity_curve: List[Dict] = []

    def open_position(
        self,
        symbol: str,
        direction: str,
        margin: float,
        leverage: int = 10,
        stop_loss: float = 0,
        take_profit: float = 0,
        entry_price: float = 0,
        entry_time: str = "",
    ) -> dict:
        """
        模拟开仓.
        
        Args:
            margin: 保证金 (USDT)
            entry_price: 入场价格 (回测中为下一根K线开盘价)
        """
        symbol = symbol.upper()
        direction = direction.upper()
        
        if stop_loss <= 0 and take_profit <= 0:
            return {"status": "error", "message": "开仓请求被拒绝: 风险控制要求必须设置有效的 stop_loss 或 take_profit"}

        if margin > self.cash:
            return {"status": "error", "message": f"资金不足: 需要 {margin:.2f}, 可用 {self.cash:.2f}"}

        if entry_price <= 0:
            return {"status": "error", "message": "entry_price 必须 > 0"}

        # 检查是否同时开同方向
        existing_pos = None
        for p in self.positions:
            if p.symbol == symbol and p.direction == direction:
                existing_pos = p
                break

        # 计算数量
        notional = margin * leverage
        quantity = notional / entry_price

        # 手续费
        fee = notional * self.FEE_RATE

        # 扣减可用资金 (保证金 + 手续费)
        self.cash -= (margin + fee)

        if existing_pos:
            # 存在同向持仓, 进行加仓合并 (加权平均价格)
            total_quantity = existing_pos.quantity + quantity
            total_notional = existing_pos.entry_price * existing_pos.quantity + entry_price * quantity
            new_avg_price = total_notional / total_quantity
            
            existing_pos.quantity = total_quantity
            existing_pos.entry_price = new_avg_price
            existing_pos.margin += margin
            existing_pos.entry_fee += fee
            
            # 使用最新的止损止盈设置覆盖
            if stop_loss > 0:
                existing_pos.stop_loss = stop_loss
            if take_profit > 0:
                existing_pos.take_profit = take_profit
                
            return {
                "status": "success",
                "action": "ADD_POSITION",
                "symbol": symbol,
                "direction": direction,
                "avg_price": round(new_avg_price, 4),
                "added_quantity": round(quantity, 6),
                "total_quantity": round(total_quantity, 6),
                "added_margin": margin,
                "fee": round(fee, 4),
            }
        else:
            # 新建持仓
            pos = SimPosition(
                id=str(uuid.uuid4())[:8],
                symbol=symbol,
                direction=direction,
                entry_price=entry_price,
                quantity=quantity,
                margin=margin,
                leverage=leverage,
                stop_loss=stop_loss,
                take_profit=take_profit,
                entry_time=entry_time,
                entry_fee=fee,
            )
            self.positions.append(pos)

            return {
                "status": "success",
                "action": "OPEN",
                "symbol": symbol,
                "direction": direction,
                "entry_price": entry_price,
                "quantity": round(quantity, 6),
                "margin": margin,
                "leverage": leverage,
                "fee": round(fee, 4),
            }

    def close_position(
        self,
        symbol: str,
        exit_price: float,
        direction: str = None,
        exit_time: str = "",
        exit_reason: str = "SIGNAL",
        close_percent: float = 100,
        agent_reasoning: str = "",
    ) -> dict:
        """
        模拟平仓.
        """
        symbol = symbol.upper()
        target = None
        candidates = [p for p in self.positions if p.symbol == symbol]
        if direction:
            candidates = [p for p in candidates if p.direction == direction.upper()]
        
        if not candidates:
            return {"status": "error", "message": f"未找到 {symbol} {direction or ''} 的持仓"}
            
        if len(candidates) > 1 and not direction:
            return {"status": "error", "message": f"未明确方向，且同时持有多空双向，请附带 direction 参数操作"}
            
        target = candidates[0]

        # 计算平仓量
        close_ratio = min(100, max(1, close_percent)) / 100
        close_qty = target.quantity * close_ratio

        # 平仓手续费
        close_notional = close_qty * exit_price
        exit_fee = close_notional * self.FEE_RATE

        # 计算盈亏
        if target.direction == "LONG":
            raw_pnl = (exit_price - target.entry_price) * close_qty
        else:
            raw_pnl = (target.entry_price - exit_price) * close_qty

        # 按比例分摊入场手续费
        entry_fee_share = target.entry_fee * close_ratio
        net_pnl = raw_pnl - entry_fee_share - exit_fee

        # 计算 ROI%
        close_margin = target.margin * close_ratio
        pnl_pct = round(net_pnl / close_margin * 100, 2) if close_margin > 0 else 0

        # 记录已关闭交易
        trade = ClosedTrade(
            id=target.id,
            symbol=symbol,
            direction=target.direction,
            entry_price=target.entry_price,
            exit_price=exit_price,
            quantity=close_qty,
            margin=close_margin,
            leverage=target.leverage,
            pnl=round(net_pnl, 4),
            pnl_pct=pnl_pct,
            entry_time=target.entry_time,
            exit_time=exit_time,
            exit_reason=exit_reason,
            entry_fee=entry_fee_share,
            exit_fee=exit_fee,
            agent_reasoning=agent_reasoning,
        )
        self.closed_trades.append(trade)

        # 归还保证金 + 盈亏到可用资金
        self.cash += close_margin + net_pnl

        # 更新或移除持仓
        if close_ratio >= 1.0:
            self.positions.remove(target)
        else:
            target.quantity -= close_qty
            target.margin -= close_margin
            target.entry_fee -= entry_fee_share

        return {
            "status": "success",
            "action": "CLOSE",
            "symbol": symbol,
            "direction": target.direction,
            "exit_price": exit_price,
            "quantity": round(close_qty, 6),
            "pnl": round(net_pnl, 4),
            "pnl_pct": pnl_pct,
            "exit_reason": exit_reason,
            "fee": round(exit_fee, 4),
        }

    def update_stop_loss(self, symbol: str, new_sl: float, direction: str = None) -> dict:
        """更新止损价格."""
        symbol = symbol.upper()
        candidates = [p for p in self.positions if p.symbol == symbol]
        if direction:
            candidates = [p for p in candidates if p.direction == direction.upper()]
        if not candidates:
            return {"status": "error", "message": f"未找到 {symbol} {direction or ''} 持仓"}
        if len(candidates) > 1 and not direction:
            return {"status": "error", "message": f"存在多空双向，请使用 direction 明确指定更新哪个头寸。"}
            
        target = candidates[0]
        old_sl = target.stop_loss
        target.stop_loss = new_sl
        return {"status": "success", "symbol": symbol, "direction": target.direction, "old_sl": old_sl, "new_sl": new_sl}

    def update_take_profit(self, symbol: str, new_tp: float, direction: str = None) -> dict:
        """更新止盈价格."""
        symbol = symbol.upper()
        candidates = [p for p in self.positions if p.symbol == symbol]
        if direction:
            candidates = [p for p in candidates if p.direction == direction.upper()]
        if not candidates:
            return {"status": "error", "message": f"未找到 {symbol} {direction or ''} 持仓"}
        if len(candidates) > 1 and not direction:
            return {"status": "error", "message": f"存在多空双向，请使用 direction 明确指定更新哪个头寸。"}
            
        target = candidates[0]
        old_tp = target.take_profit
        target.take_profit = new_tp
        return {"status": "success", "symbol": symbol, "direction": target.direction, "old_tp": old_tp, "new_tp": new_tp}

    def check_sl_tp(self, candle: dict, candle_time: str = "") -> List[dict]:
        """
        检查当前K线是否触发止损/止盈.
        
        使用 candle 的 high/low 判定 (而非 close):
        - LONG 止损: low <= sl_price
        - LONG 止盈: high >= tp_price
        - SHORT 止损: high >= sl_price
        - SHORT 止盈: low <= tp_price
        
        当同一根K线同时触发 SL 和 TP 时, 优先执行 SL (保守原则).
        
        Returns:
            触发的平仓事件列表
        """
        events = []
        positions_to_close = []

        for pos in self.positions:
            open_price = candle.get("open", 0)
            high = candle.get("high", 0)
            low = candle.get("low", 0)

            sl_triggered = False
            tp_triggered = False
            exit_price = 0

            if pos.direction == "LONG":
                if pos.stop_loss > 0 and low <= pos.stop_loss:
                    sl_triggered = True
                    # 跳空检测：如果在当前周期开盘价就已经越过止损价，使用更悲观的开盘价作为撤出点
                    exit_price = min(pos.stop_loss, open_price) if open_price > 0 else pos.stop_loss
                if pos.take_profit > 0 and high >= pos.take_profit:
                    tp_triggered = True
                    if not sl_triggered:
                        # 跳空检测：如果开盘就已经超过止盈，用开盘价或最高之间？回测取 tp 较保守
                        exit_price = max(pos.take_profit, open_price) if open_price > 0 else pos.take_profit
            else:  # SHORT
                if pos.stop_loss > 0 and high >= pos.stop_loss:
                    sl_triggered = True
                    exit_price = max(pos.stop_loss, open_price) if open_price > 0 else pos.stop_loss
                if pos.take_profit > 0 and low <= pos.take_profit:
                    tp_triggered = True
                    if not sl_triggered:
                        exit_price = min(pos.take_profit, open_price) if open_price > 0 else pos.take_profit

            # 同时触发时, 优先止损 (保守原则)
            if sl_triggered:
                positions_to_close.append((pos.symbol, pos.direction, exit_price, "SL"))
            elif tp_triggered:
                positions_to_close.append((pos.symbol, pos.direction, exit_price, "TP"))

        for symbol, pos_dir, price, reason in positions_to_close:
            result = self.close_position(
                symbol=symbol,
                exit_price=price,
                direction=pos_dir,
                exit_time=candle_time,
                exit_reason=reason,
            )
            if result.get("status") == "success":
                events.append(result)

        return events

    def get_equity(self, current_prices: Dict[str, float]) -> float:
        """计算当前总权益 = 可用资金 + 所有持仓的保证金 + 未实现盈亏."""
        equity = self.cash
        for pos in self.positions:
            price = current_prices.get(pos.symbol, pos.entry_price)
            equity += pos.margin + pos.unrealized_pnl(price)
        return round(equity, 4)

    def snapshot_equity(self, current_prices: Dict[str, float], time_str: str):
        """记录一个权益快照点."""
        self.equity_curve.append({
            "time": time_str,
            "equity": self.get_equity(current_prices),
            "cash": round(self.cash, 4),
            "positions": len(self.positions),
        })

    def to_context_dict(self, current_prices: Dict[str, float]) -> dict:
        """
        输出为 strategy_context 中 account/positions/open_orders 兼容的字典.
        让 Agent 看到与生产环境一模一样的数据结构.
        """
        # account
        total_equity = self.get_equity(current_prices)
        account = {
            "total_equity": round(total_equity, 2),
            "available": round(self.cash, 2),
            "used_margin": round(sum(p.margin for p in self.positions), 2),
            "unrealized_pnl": round(
                sum(p.unrealized_pnl(current_prices.get(p.symbol, p.entry_price)) for p in self.positions),
                2
            ),
        }

        # positions
        pos_list = []
        for p in self.positions:
            price = current_prices.get(p.symbol, p.entry_price)
            pos_list.append({
                "symbol": p.symbol,
                "direction": p.direction,
                "size": round(p.quantity, 6),
                "entry_price": p.entry_price,
                "mark_price": price,
                "margin": round(p.margin, 2),
                "leverage": p.leverage,
                "unrealized_pnl": round(p.unrealized_pnl(price), 4),
                "roi_pct": p.roi_pct(price),
                "existing_sl_orders": [{"price": p.stop_loss}] if p.stop_loss > 0 else [],
                "existing_tp_orders": [{"price": p.take_profit}] if p.take_profit > 0 else [],
            })

        return {
            "account": account,
            "positions": {"count": len(pos_list), "list": pos_list},
            "open_orders": {"count": 0, "list": []},
        }

    def execute_signal(
        self,
        signal: dict,
        symbol: str,
        price: float,
        candle_time: str,
        leverage: int = 10,
        risk_pct: float = 0.02,
    ) -> dict:
        """
        执行量化策略信号.

        根据信号方向自动处理:
        - BUY: 如有空仓先平仓, 再开多
        - SELL: 如有多仓先平仓, 再开空
        - HOLD: 不操作

        Args:
            signal: {"action": "BUY"/"SELL"/"HOLD", "sl": float, "tp": float, "reason": str}
            symbol: 交易对
            price: 当前价格 (用下一根K线开盘价模拟)
            candle_time: K线时间字符串
            leverage: 杠杆倍数
            risk_pct: 单笔风险占比

        Returns:
            执行结果 dict
        """
        action = signal.get("action", "HOLD")
        if action == "HOLD":
            return {"action": "HOLD"}

        symbol = symbol.upper()
        results = []

        # 计算保证金
        margin = round(self.cash * risk_pct, 2)
        margin = min(margin, self.cash * 0.2)  # 不超过可用资金的 20%
        if margin < 1:
            return {"action": action, "status": "skip", "reason": "资金不足"}

        if action == "BUY":
            # 先平空仓 (如果有)
            for p in list(self.positions):
                if p.symbol == symbol and p.direction == "SHORT":
                    r = self.close_position(symbol, price, direction="SHORT",
                                            exit_time=candle_time, exit_reason="SIGNAL_REVERSE")
                    results.append(r)

            # 检查是否已有多仓
            has_long = any(p.symbol == symbol and p.direction == "LONG" for p in self.positions)
            if not has_long:
                r = self.open_position(
                    symbol=symbol, direction="LONG", margin=margin,
                    leverage=leverage, stop_loss=signal.get("sl") or 0,
                    take_profit=signal.get("tp") or 0,
                    entry_price=price, entry_time=candle_time,
                )
                results.append(r)

        elif action == "SELL":
            # 先平多仓 (如果有)
            for p in list(self.positions):
                if p.symbol == symbol and p.direction == "LONG":
                    r = self.close_position(symbol, price, direction="LONG",
                                            exit_time=candle_time, exit_reason="SIGNAL_REVERSE")
                    results.append(r)

            # 检查是否已有空仓
            has_short = any(p.symbol == symbol and p.direction == "SHORT" for p in self.positions)
            if not has_short:
                r = self.open_position(
                    symbol=symbol, direction="SHORT", margin=margin,
                    leverage=leverage, stop_loss=signal.get("sl") or 0,
                    take_profit=signal.get("tp") or 0,
                    entry_price=price, entry_time=candle_time,
                )
                results.append(r)

        return {"action": action, "results": results, "reason": signal.get("reason", "")}

