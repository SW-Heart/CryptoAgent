"""
量化回测统计报告生成

从 SimPortfolio 的交易记录和权益曲线计算:
- 基础统计 (胜率、盈亏比、总收益率)
- 风险指标 (最大回撤、夏普比率、Sortino、Calmar)
- 年化收益率
- 多空分拆统计
- 月度收益分布
- 持仓时间统计
- 交易明细列表
- 权益曲线与回撤曲线
"""
import math
from typing import Dict, List, Any
from datetime import datetime


def generate_report(sim_portfolio, config) -> dict:
    """
    从 SimPortfolio 生成完整的量化回测报告.
    """
    trades = sim_portfolio.closed_trades
    equity_curve = sim_portfolio.equity_curve
    initial_capital = sim_portfolio.initial_capital

    # ============ 基础统计 ============
    total_trades = len(trades)
    winning_trades = [t for t in trades if t.pnl > 0]
    losing_trades = [t for t in trades if t.pnl <= 0]

    win_count = len(winning_trades)
    lose_count = len(losing_trades)
    win_rate = round(win_count / total_trades * 100, 1) if total_trades > 0 else 0

    total_profit = sum(t.pnl for t in winning_trades)
    total_loss = abs(sum(t.pnl for t in losing_trades))

    avg_win = round(total_profit / win_count, 2) if win_count > 0 else 0
    avg_loss = round(total_loss / lose_count, 2) if lose_count > 0 else 0
    profit_factor = round(total_profit / total_loss, 2) if total_loss > 0 else float('inf')

    risk_reward = round(avg_win / avg_loss, 2) if avg_loss > 0 else float('inf')

    # 最终权益
    final_equity = equity_curve[-1]["equity"] if equity_curve else initial_capital
    total_return_pct = round((final_equity - initial_capital) / initial_capital * 100, 2)
    net_pnl = round(final_equity - initial_capital, 2)

    # ============ 最大回撤 ============
    max_drawdown_pct = 0
    max_drawdown_usd = 0
    peak = initial_capital
    drawdown_curve = []

    for point in equity_curve:
        equity = point["equity"]
        if equity > peak:
            peak = equity
        drawdown = (peak - equity) / peak * 100
        drawdown_usd = peak - equity
        if drawdown > max_drawdown_pct:
            max_drawdown_pct = drawdown
            max_drawdown_usd = drawdown_usd
        drawdown_curve.append({
            "time": point["time"],
            "drawdown_pct": round(drawdown, 2),
        })

    max_drawdown_pct = round(max_drawdown_pct, 2)
    max_drawdown_usd = round(max_drawdown_usd, 2)

    # ============ 收益率序列 ============
    returns = []
    if len(equity_curve) >= 2:
        for i in range(1, len(equity_curve)):
            prev_eq = equity_curve[i-1]["equity"]
            curr_eq = equity_curve[i]["equity"]
            if prev_eq > 0:
                returns.append((curr_eq - prev_eq) / prev_eq)

    # ============ 夏普比率 ============
    sharpe_ratio = 0
    if returns:
        avg_return = sum(returns) / len(returns)
        std_return = math.sqrt(sum((r - avg_return) ** 2 for r in returns) / len(returns)) if len(returns) > 1 else 0
        if std_return > 0:
            annualization = math.sqrt(365 * 24 / max(1, _interval_hours(config.interval)))
            sharpe_ratio = round(avg_return / std_return * annualization, 2)

    # ============ Sortino 比率 ============
    sortino_ratio = 0
    if returns:
        avg_return = sum(returns) / len(returns)
        downside_returns = [r for r in returns if r < 0]
        if downside_returns:
            downside_std = math.sqrt(sum(r ** 2 for r in downside_returns) / len(downside_returns))
            if downside_std > 0:
                annualization = math.sqrt(365 * 24 / max(1, _interval_hours(config.interval)))
                sortino_ratio = round(avg_return / downside_std * annualization, 2)

    # ============ Calmar 比率 ============
    calmar_ratio = 0
    if max_drawdown_pct > 0 and total_return_pct != 0:
        # 简化: 年化收益 / 最大回撤
        calmar_ratio = round(total_return_pct / max_drawdown_pct, 2)

    # ============ 年化收益率 ============
    annualized_return = 0
    if equity_curve and len(equity_curve) >= 2:
        # 计算回测时长 (小时)
        interval_hours = _interval_hours(config.interval)
        total_hours = len(equity_curve) * interval_hours
        total_years = total_hours / (365 * 24)
        if total_years > 0 and final_equity > 0:
            annualized_return = round(((final_equity / initial_capital) ** (1 / total_years) - 1) * 100, 2)

    # ============ 最大连续亏损/盈利 ============
    max_consecutive_losses = 0
    max_consecutive_wins = 0
    current_loss_streak = 0
    current_win_streak = 0
    for t in trades:
        if t.pnl <= 0:
            current_loss_streak += 1
            current_win_streak = 0
            max_consecutive_losses = max(max_consecutive_losses, current_loss_streak)
        else:
            current_win_streak += 1
            current_loss_streak = 0
            max_consecutive_wins = max(max_consecutive_wins, current_win_streak)

    # ============ 多空分拆 ============
    long_trades = [t for t in trades if t.direction == "LONG"]
    short_trades = [t for t in trades if t.direction == "SHORT"]

    long_wins = len([t for t in long_trades if t.pnl > 0])
    short_wins = len([t for t in short_trades if t.pnl > 0])

    long_pnl = round(sum(t.pnl for t in long_trades), 2)
    short_pnl = round(sum(t.pnl for t in short_trades), 2)

    # ============ 持仓时间统计 ============
    hold_durations = []
    for t in trades:
        try:
            entry_dt = datetime.strptime(t.entry_time, "%Y-%m-%d %H:%M")
            exit_dt = datetime.strptime(t.exit_time, "%Y-%m-%d %H:%M")
            hours = (exit_dt - entry_dt).total_seconds() / 3600
            hold_durations.append(hours)
        except (ValueError, TypeError):
            pass

    avg_hold_hours = round(sum(hold_durations) / len(hold_durations), 1) if hold_durations else 0
    max_hold_hours = round(max(hold_durations), 1) if hold_durations else 0
    min_hold_hours = round(min(hold_durations), 1) if hold_durations else 0

    # ============ 月度收益分布 ============
    monthly_returns = {}
    if equity_curve:
        # 按月份聚合权益变化
        prev_month_equity = initial_capital
        current_month = None
        for point in equity_curve:
            try:
                dt = datetime.strptime(point["time"], "%Y-%m-%d %H:%M")
                month_key = dt.strftime("%Y-%m")
                if month_key != current_month:
                    if current_month is not None:
                        ret = round((prev_point_equity - prev_month_equity) / prev_month_equity * 100, 2)
                        monthly_returns[current_month] = ret
                        prev_month_equity = prev_point_equity
                    current_month = month_key
                prev_point_equity = point["equity"]
            except (ValueError, TypeError):
                pass
        # 最后一个月
        if current_month:
            ret = round((prev_point_equity - prev_month_equity) / prev_month_equity * 100, 2)
            monthly_returns[current_month] = ret

    # ============ 总手续费 ============
    total_fees = round(sum(t.entry_fee + t.exit_fee for t in trades), 2)

    # ============ 交易明细 ============
    trade_list = []
    for t in trades:
        trade_list.append(t.to_dict() if hasattr(t, 'to_dict') else {
            "id": t.id,
            "symbol": t.symbol,
            "direction": t.direction,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "quantity": round(t.quantity, 6),
            "margin": round(t.margin, 2),
            "leverage": t.leverage,
            "pnl": round(t.pnl, 2),
            "pnl_pct": t.pnl_pct,
            "entry_time": t.entry_time,
            "exit_time": t.exit_time,
            "exit_reason": t.exit_reason,
            "fees": round(t.entry_fee + t.exit_fee, 4),
        })

    # ============ 权益曲线 (采样) ============
    sampled_curve = equity_curve
    if len(equity_curve) > 500:
        step = len(equity_curve) // 500
        sampled_curve = equity_curve[::step]
        if equity_curve[-1] not in sampled_curve:
            sampled_curve.append(equity_curve[-1])

    # 回撤曲线也采样
    sampled_dd = drawdown_curve
    if len(drawdown_curve) > 500:
        step = len(drawdown_curve) // 500
        sampled_dd = drawdown_curve[::step]
        if drawdown_curve[-1] not in sampled_dd:
            sampled_dd.append(drawdown_curve[-1])

    return {
        "summary": {
            "total_trades": total_trades,
            "win_count": win_count,
            "lose_count": lose_count,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor if profit_factor != float('inf') else 999,
            "risk_reward": risk_reward if risk_reward != float('inf') else 999,
            "total_return_pct": total_return_pct,
            "annualized_return_pct": annualized_return,
            "net_pnl": net_pnl,
            "final_equity": round(final_equity, 2),
            "initial_capital": initial_capital,
            "max_drawdown_pct": max_drawdown_pct,
            "max_drawdown_usd": max_drawdown_usd,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "calmar_ratio": calmar_ratio,
            "max_consecutive_losses": max_consecutive_losses,
            "max_consecutive_wins": max_consecutive_wins,
            "long_trades": len(long_trades),
            "long_win_rate": round(long_wins / len(long_trades) * 100, 1) if long_trades else 0,
            "long_pnl": long_pnl,
            "short_trades": len(short_trades),
            "short_win_rate": round(short_wins / len(short_trades) * 100, 1) if short_trades else 0,
            "short_pnl": short_pnl,
            "avg_hold_hours": avg_hold_hours,
            "max_hold_hours": max_hold_hours,
            "min_hold_hours": min_hold_hours,
            "total_fees": total_fees,
        },
        "equity_curve": sampled_curve,
        "drawdown_curve": sampled_dd,
        "monthly_returns": monthly_returns,
        "trades": trade_list,
        "config": {
            "symbol": config.symbol,
            "interval": config.interval,
            "start_date": config.start_date,
            "end_date": config.end_date,
            "initial_capital": config.initial_capital,
            "leverage": config.leverage,
            "risk_per_trade": config.risk_per_trade,
        },
    }


def _interval_hours(interval: str) -> float:
    """将 interval 字符串转为小时数."""
    mapping = {
        "1m": 1/60, "5m": 5/60, "15m": 15/60, "30m": 0.5,
        "1h": 1, "2h": 2, "4h": 4, "6h": 6, "8h": 8,
        "12h": 12, "1d": 24, "3d": 72, "1w": 168,
    }
    return mapping.get(interval, 4)
