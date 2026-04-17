"""
量化回测引擎

核心流程:
1. 加载历史K线 (复用 data_loader)
2. 预计算指标 (strategy.init)
3. 逐K线循环: 信号 → 止损止盈 → 执行 → 快照
4. 生成统计报告

与旧版 Agent 回测的区别:
- 不调用 LLM, 纯计算, 百倍提速
- 策略用代码表达, 完全可复现
- 支持参数优化 (网格搜索)
"""
import json
import time
import uuid
import threading
import traceback
from typing import Optional, Dict, Any, List
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

from backtest.data_loader import load_historical_klines, estimate_kline_count, INTERVAL_MS
from backtest.sim_portfolio import SimPortfolio
from backtest.strategies import get_strategy, list_strategies
from backtest.report import generate_report


# ============= 全局控制 =============

_backtest_semaphore = threading.Semaphore(3)  # 量化回测很快, 允许 3 个并发

_active_jobs: Dict[str, "BacktestJob"] = {}


class BacktestConfig:
    """回测配置."""
    def __init__(
        self,
        user_id: str,
        symbol: str,
        interval: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 10000,
        leverage: int = 10,
        risk_per_trade: float = 0.02,
        strategy_type: str = "ema_cross",
        strategy_params: dict = None,
    ):
        self.user_id = user_id
        self.symbol = symbol.upper()
        self.interval = interval
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.risk_per_trade = risk_per_trade
        self.strategy_type = strategy_type
        self.strategy_params = strategy_params or {}


class BacktestJob:
    """回测任务实例."""

    def __init__(self, config: BacktestConfig):
        self.id = str(uuid.uuid4())[:12]
        self.config = config
        self.status = "PENDING"       # PENDING → LOADING → RUNNING → COMPLETED / FAILED
        self.progress = 0
        self.total_rounds = 0
        self.result = None
        self.error = None
        self.created_at = datetime.utcnow().isoformat()
        self.started_at = None
        self.completed_at = None
        self.elapsed_ms = 0           # 回测耗时 (毫秒)

    def to_dict(self) -> dict:
        data = {
            "id": self.id,
            "status": self.status,
            "progress": self.progress,
            "total_rounds": self.total_rounds,
            "symbol": self.config.symbol,
            "interval": self.config.interval,
            "start_date": self.config.start_date,
            "end_date": self.config.end_date,
            "initial_capital": self.config.initial_capital,
            "leverage": self.config.leverage,
            "strategy_type": self.config.strategy_type,
            "strategy_params": self.config.strategy_params,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "elapsed_ms": self.elapsed_ms,
            "error": self.error,
        }
        return data


def _run_backtest(job: BacktestJob):
    """回测主循环."""
    config = job.config
    t_start = time.time()

    try:
        job.status = "LOADING"
        _update_job_db(job)

        # 1. 加载历史K线
        print(f"[Backtest#{job.id}] Loading klines: {config.symbol} {config.interval} {config.start_date}~{config.end_date}")
        full_df = load_historical_klines(
            config.symbol, config.interval,
            config.start_date, config.end_date,
            warm_up_bars=200,
        )

        # 确定回测起始位置 (跳过预热区)
        from backtest.data_loader import _date_to_ms
        start_ms = _date_to_ms(config.start_date)
        backtest_start_idx = -1
        for i, row in full_df.iterrows():
            if row["time"] >= start_ms:
                backtest_start_idx = i
                break

        if backtest_start_idx == -1:
            raise ValueError(f"K线数据未能覆盖回测起始时间 ({config.start_date})")

        total_candles = len(full_df) - backtest_start_idx
        job.total_rounds = total_candles
        print(f"[Backtest#{job.id}] Total candles: {total_candles} (warm-up: {backtest_start_idx})")

        # 2. 创建策略和组合
        strategy = get_strategy(config.strategy_type, config.strategy_params)
        sim = SimPortfolio(initial_capital=config.initial_capital)

        # 3. 预计算指标
        strategy.init(full_df)

        job.status = "RUNNING"
        job.started_at = datetime.utcnow().isoformat()
        _update_job_db(job)

        # 4. 回测主循环 (纯计算, 极速)
        for step, idx in enumerate(range(backtest_start_idx, len(full_df))):
            candle = full_df.iloc[idx]
            candle_time_ms = int(candle["time"])
            candle_time_str = datetime.utcfromtimestamp(candle_time_ms / 1000).strftime("%Y-%m-%d %H:%M")
            price = float(candle["close"])

            # 4a. 检查 SL/TP 触发
            candle_dict = {
                "open": float(candle["open"]),
                "high": float(candle["high"]),
                "low": float(candle["low"]),
                "close": price,
            }
            sim.check_sl_tp(candle_dict, candle_time_str)

            # 4b. 获取策略信号
            signal = strategy.signal(idx)

            # 4c. 执行信号 (用下一根K线开盘价模拟)
            if signal["action"] != "HOLD":
                exec_price = float(full_df.iloc[idx + 1]["open"]) if idx + 1 < len(full_df) else price
                sim.execute_signal(
                    signal=signal,
                    symbol=config.symbol,
                    price=exec_price,
                    candle_time=candle_time_str,
                    leverage=config.leverage,
                    risk_pct=config.risk_per_trade,
                )

            # 4d. 权益快照
            current_prices = {config.symbol: price}
            sim.snapshot_equity(current_prices, candle_time_str)

            job.progress = step + 1

        # 5. 回测结束时平掉所有持仓
        final_price = float(full_df.iloc[-1]["close"])
        final_time = datetime.utcfromtimestamp(int(full_df.iloc[-1]["time"]) / 1000).strftime("%Y-%m-%d %H:%M")
        for p in list(sim.positions):
            sim.close_position(
                p.symbol, final_price,
                direction=p.direction,
                exit_time=final_time,
                exit_reason="BACKTEST_END",
            )

        # 6. 生成报告 (含 Buy & Hold 基准)
        elapsed_ms = int((time.time() - t_start) * 1000)
        job.elapsed_ms = elapsed_ms

        # 计算 Buy & Hold 基准
        bh_start_price = float(full_df.iloc[backtest_start_idx]["close"])
        bh_end_price = final_price
        buy_hold_return = round((bh_end_price - bh_start_price) / bh_start_price * 100, 2)

        job.result = generate_report(sim, config)
        job.result["benchmark"] = {
            "buy_hold_return_pct": buy_hold_return,
            "start_price": round(bh_start_price, 2),
            "end_price": round(bh_end_price, 2),
        }
        job.result["elapsed_ms"] = elapsed_ms
        job.result["strategy_type"] = config.strategy_type
        job.result["strategy_params"] = config.strategy_params
        job.status = "COMPLETED"
        job.completed_at = datetime.utcnow().isoformat()

        print(f"[Backtest#{job.id}] ✅ Completed in {elapsed_ms}ms! Trades: {len(sim.closed_trades)}, Return: {job.result['summary']['total_return_pct']}%")
        _update_job_db(job)

    except Exception as e:
        job.status = "FAILED"
        job.error = str(e)
        job.completed_at = datetime.utcnow().isoformat()
        job.elapsed_ms = int((time.time() - t_start) * 1000)
        traceback.print_exc()
        print(f"[Backtest#{job.id}] ❌ FAILED: {e}")
        _update_job_db(job)

    finally:
        _backtest_semaphore.release()


def _run_single_backtest_for_optimize(
    symbol: str,
    interval: str,
    start_date: str,
    end_date: str,
    initial_capital: float,
    leverage: int,
    risk_per_trade: float,
    strategy_type: str,
    strategy_params: dict,
    full_df_json: str,
    backtest_start_idx: int,
) -> dict:
    """
    单次回测 (用于参数优化, 在独立进程中执行).
    接收 JSON 序列化的 DataFrame, 避免进程间传递大对象。
    """
    import pandas as pd
    from backtest.sim_portfolio import SimPortfolio
    from backtest.strategies import get_strategy

    df = pd.read_json(full_df_json)
    strategy = get_strategy(strategy_type, strategy_params)
    sim = SimPortfolio(initial_capital=initial_capital)
    strategy.init(df)

    for idx in range(backtest_start_idx, len(df)):
        candle = df.iloc[idx]
        candle_time_ms = int(candle["time"])
        candle_time_str = datetime.utcfromtimestamp(candle_time_ms / 1000).strftime("%Y-%m-%d %H:%M")
        price = float(candle["close"])

        candle_dict = {
            "open": float(candle["open"]),
            "high": float(candle["high"]),
            "low": float(candle["low"]),
            "close": price,
        }
        sim.check_sl_tp(candle_dict, candle_time_str)

        signal = strategy.signal(idx)
        if signal["action"] != "HOLD":
            exec_price = float(df.iloc[idx + 1]["open"]) if idx + 1 < len(df) else price
            sim.execute_signal(
                signal=signal, symbol=symbol, price=exec_price,
                candle_time=candle_time_str, leverage=leverage,
                risk_pct=risk_per_trade,
            )

        sim.snapshot_equity({symbol: price}, candle_time_str)

    # 平掉所有持仓
    final_price = float(df.iloc[-1]["close"])
    final_time = datetime.utcfromtimestamp(int(df.iloc[-1]["time"]) / 1000).strftime("%Y-%m-%d %H:%M")
    for p in list(sim.positions):
        sim.close_position(p.symbol, final_price, direction=p.direction,
                           exit_time=final_time, exit_reason="BACKTEST_END")

    # 计算核心指标
    final_equity = sim.get_equity({symbol: final_price})
    total_return = round((final_equity - initial_capital) / initial_capital * 100, 2)
    total_trades = len(sim.closed_trades)
    wins = len([t for t in sim.closed_trades if t.pnl > 0])
    win_rate = round(wins / total_trades * 100, 1) if total_trades > 0 else 0

    # 最大回撤
    peak = initial_capital
    max_dd = 0
    for pt in sim.equity_curve:
        eq = pt["equity"]
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100
        if dd > max_dd:
            max_dd = dd

    # 夏普
    import math
    sharpe = 0
    if len(sim.equity_curve) >= 2:
        returns = []
        for i in range(1, len(sim.equity_curve)):
            prev = sim.equity_curve[i - 1]["equity"]
            curr = sim.equity_curve[i]["equity"]
            if prev > 0:
                returns.append((curr - prev) / prev)
        if returns:
            avg_r = sum(returns) / len(returns)
            std_r = math.sqrt(sum((r - avg_r) ** 2 for r in returns) / len(returns)) if len(returns) > 1 else 0
            if std_r > 0:
                sharpe = round(avg_r / std_r * math.sqrt(365 * 24 / max(1, _interval_hours(interval))), 2)

    return {
        "params": strategy_params,
        "total_return_pct": total_return,
        "win_rate": win_rate,
        "total_trades": total_trades,
        "max_drawdown_pct": round(max_dd, 2),
        "sharpe_ratio": sharpe,
        "final_equity": round(final_equity, 2),
    }


def _interval_hours(interval: str) -> float:
    mapping = {
        "1m": 1/60, "5m": 5/60, "15m": 15/60, "30m": 0.5,
        "1h": 1, "2h": 2, "4h": 4, "6h": 6, "8h": 8,
        "12h": 12, "1d": 24, "3d": 72, "1w": 168,
    }
    return mapping.get(interval, 4)


def run_parameter_optimization(
    config: BacktestConfig,
    param_grid: Dict[str, list],
    optimize_target: str = "total_return_pct",
    max_workers: int = 4,
) -> dict:
    """
    网格搜索参数优化.

    Args:
        config: 基础回测配置
        param_grid: 参数搜索网格, 如 {"fast_period": [5,10,20], "slow_period": [20,30,50]}
        optimize_target: 优化目标指标
        max_workers: 并行进程数

    Returns:
        {"results": [...], "best": {...}, "total_combinations": int, "elapsed_ms": int}
    """
    import itertools

    t_start = time.time()

    # 生成所有参数组合
    param_names = list(param_grid.keys())
    param_values = list(param_grid.values())
    combinations = list(itertools.product(*param_values))
    total = len(combinations)

    if total > 1000:
        raise ValueError(f"参数组合数 ({total}) 过多, 请减少参数范围. 最大支持 1000 组.")

    print(f"[Optimize] Starting optimization: {total} combinations, {max_workers} workers")

    # 加载K线数据 (只加载一次)
    full_df = load_historical_klines(
        config.symbol, config.interval,
        config.start_date, config.end_date,
        warm_up_bars=200,
    )

    from backtest.data_loader import _date_to_ms
    start_ms = _date_to_ms(config.start_date)
    backtest_start_idx = -1
    for i, row in full_df.iterrows():
        if row["time"] >= start_ms:
            backtest_start_idx = i
            break

    if backtest_start_idx == -1:
        raise ValueError(f"K线数据未能覆盖回测起始时间")

    # 序列化 DataFrame (用于跨进程传递)
    df_json = full_df.to_json()

    results = []

    # 由于 ProcessPoolExecutor 在某些环境可能有问题, 使用线程池代替
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for combo in combinations:
            params = dict(zip(param_names, combo))
            # 合并基础参数和搜索参数
            merged_params = {**config.strategy_params, **params}

            future = executor.submit(
                _run_single_backtest_for_optimize,
                config.symbol, config.interval,
                config.start_date, config.end_date,
                config.initial_capital, config.leverage,
                config.risk_per_trade, config.strategy_type,
                merged_params, df_json, backtest_start_idx,
            )
            futures[future] = params

        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                params = futures[future]
                results.append({
                    "params": params,
                    "error": str(e),
                    "total_return_pct": -999,
                })

    # 按目标指标排序
    valid_results = [r for r in results if "error" not in r]
    valid_results.sort(key=lambda x: x.get(optimize_target, 0), reverse=True)

    elapsed_ms = int((time.time() - t_start) * 1000)

    return {
        "results": valid_results,
        "best": valid_results[0] if valid_results else None,
        "total_combinations": total,
        "elapsed_ms": elapsed_ms,
        "optimize_target": optimize_target,
    }


def _update_job_db(job: BacktestJob):
    """将任务状态持久化到数据库."""
    try:
        from app.database import get_db_connection
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                result_json = json.dumps(job.result, ensure_ascii=False, default=str) if job.result else None
                cur.execute("""
                    INSERT INTO backtest_jobs (id, user_id, status, symbol, interval, start_date, end_date,
                        initial_capital, leverage, strategy_type, strategy_params,
                        progress, total_rounds, result, error, started_at, completed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        progress = EXCLUDED.progress,
                        total_rounds = EXCLUDED.total_rounds,
                        result = EXCLUDED.result,
                        error = EXCLUDED.error,
                        started_at = EXCLUDED.started_at,
                        completed_at = EXCLUDED.completed_at
                """, (
                    job.id, job.config.user_id, job.status,
                    job.config.symbol, job.config.interval,
                    job.config.start_date, job.config.end_date,
                    job.config.initial_capital, job.config.leverage,
                    job.config.strategy_type,
                    json.dumps(job.config.strategy_params, ensure_ascii=False),
                    job.progress, job.total_rounds,
                    result_json, job.error,
                    job.started_at, job.completed_at,
                ))
                conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print(f"[Backtest] DB update error: {e}")


def start_backtest(config: BacktestConfig) -> BacktestJob:
    """启动回测任务 (异步)."""
    acquired = _backtest_semaphore.acquire(blocking=False)
    if not acquired:
        raise RuntimeError("并发回测任务过多, 请稍后再试")

    job = BacktestJob(config)
    _active_jobs[job.id] = job

    thread = threading.Thread(target=_run_backtest, args=(job,), daemon=True)
    thread.start()

    return job


def get_active_job(job_id: str) -> Optional[BacktestJob]:
    """获取活跃的回测任务."""
    return _active_jobs.get(job_id)


def get_job_from_db(job_id: str, user_id: str) -> Optional[dict]:
    """从数据库获取回测任务."""
    try:
        from app.database import get_db_connection
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM backtest_jobs WHERE id = %s AND user_id = %s", (job_id, user_id))
                row = cur.fetchone()
                if row:
                    return dict(row)
        finally:
            conn.close()
    except Exception as e:
        print(f"[Backtest] DB read error: {e}")
    return None


def list_user_jobs(user_id: str, limit: int = 20) -> list:
    """列出用户的回测历史."""
    try:
        from app.database import get_db_connection
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, status, symbol, interval, start_date, end_date,
                           initial_capital, strategy_type, strategy_params,
                           progress, total_rounds, error,
                           created_at, started_at, completed_at
                    FROM backtest_jobs
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (user_id, limit))
                return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception as e:
        print(f"[Backtest] DB list error: {e}")
        return []
