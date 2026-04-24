"""
量化回测 API 路由

接口:
- GET  /api/backtest/strategies    → 获取可用策略列表
- POST /api/backtest/run           → 启动回测
- POST /api/backtest/optimize      → 启动参数优化
- GET  /api/backtest/status/{id}   → 查询进度
- GET  /api/backtest/result/{id}   → 获取完整结果
- GET  /api/backtest/history       → 回测历史列表
"""
import json
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Dict, List

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


class RunRequest(BaseModel):
    symbol: str
    interval: str
    start_date: str
    end_date: str
    user_id: str
    initial_capital: float = 10000
    leverage: int = 10
    risk_per_trade: float = 0.02
    strategy_type: str = "ema_cross"
    strategy_params: Optional[Dict] = None


class OptimizeRequest(BaseModel):
    symbol: str
    interval: str
    start_date: str
    end_date: str
    user_id: str
    initial_capital: float = 10000
    leverage: int = 10
    risk_per_trade: float = 0.02
    strategy_type: str = "ema_cross"
    strategy_params: Optional[Dict] = None
    param_grid: Dict[str, List] = {}
    optimize_target: str = "total_return_pct"


@router.get("/strategies")
async def get_strategies():
    """获取所有可用的量化策略模板."""
    from backtest.strategies import list_strategies
    return {"strategies": list_strategies()}


@router.post("/run")
async def run_backtest(req: RunRequest):
    """启动量化回测."""
    try:
        from backtest.engine import BacktestConfig, start_backtest

        config = BacktestConfig(
            user_id=req.user_id,
            symbol=req.symbol,
            interval=req.interval,
            start_date=req.start_date,
            end_date=req.end_date,
            initial_capital=req.initial_capital,
            leverage=req.leverage,
            risk_per_trade=req.risk_per_trade,
            strategy_type=req.strategy_type,
            strategy_params=req.strategy_params or {},
        )
        job = start_backtest(config)

        return {
            "status": "started",
            "job_id": job.id,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimize")
async def optimize_strategy(req: OptimizeRequest):
    """参数优化 (同步, 阻塞式)."""
    try:
        from backtest.engine import BacktestConfig, run_parameter_optimization

        if not req.param_grid:
            raise ValueError("param_grid 不能为空")

        config = BacktestConfig(
            user_id=req.user_id,
            symbol=req.symbol,
            interval=req.interval,
            start_date=req.start_date,
            end_date=req.end_date,
            initial_capital=req.initial_capital,
            leverage=req.leverage,
            risk_per_trade=req.risk_per_trade,
            strategy_type=req.strategy_type,
            strategy_params=req.strategy_params or {},
        )

        result = run_parameter_optimization(
            config=config,
            param_grid=req.param_grid,
            optimize_target=req.optimize_target,
        )

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{job_id}")
async def get_backtest_status(
    job_id: str,
    user_id: str = Query(...),
):
    """查询回测进度."""
    from backtest.engine import get_active_job, get_job_from_db

    # 优先查内存中的活跃任务
    job = get_active_job(job_id)
    if job and job.config.user_id == user_id:
        return job.to_dict()

    # 回退到数据库查询
    db_job = get_job_from_db(job_id, user_id)
    if db_job:
        return {
            "id": db_job["id"],
            "status": db_job["status"],
            "progress": db_job["progress"],
            "total_rounds": db_job["total_rounds"],
            "symbol": db_job["symbol"],
            "interval": db_job["interval"],
            "start_date": db_job["start_date"],
            "end_date": db_job["end_date"],
            "initial_capital": db_job["initial_capital"],
            "strategy_type": db_job.get("strategy_type", ""),
            "strategy_params": db_job.get("strategy_params", {}),
            "created_at": str(db_job["created_at"]),
            "started_at": str(db_job["started_at"]) if db_job["started_at"] else None,
            "completed_at": str(db_job["completed_at"]) if db_job["completed_at"] else None,
            "error": db_job.get("error"),
        }

    raise HTTPException(status_code=404, detail="回测任务不存在")


@router.get("/result/{job_id}")
async def get_backtest_result(
    job_id: str,
    user_id: str = Query(...),
):
    """获取完整回测结果."""
    from backtest.engine import get_active_job, get_job_from_db

    # 先查内存
    job = get_active_job(job_id)
    if job and job.config.user_id == user_id:
        if job.status == "COMPLETED" and job.result:
            return job.result
        elif job.status in ("RUNNING", "LOADING", "PENDING"):
            return {"status": job.status, "progress": job.progress, "total_rounds": job.total_rounds}
        else:
            raise HTTPException(status_code=400, detail=job.error or f"任务状态: {job.status}")

    # 回退到数据库
    db_job = get_job_from_db(job_id, user_id)
    if db_job:
        if db_job["status"] == "COMPLETED" and db_job.get("result"):
            result = db_job["result"]
            if isinstance(result, str):
                result = json.loads(result)
            return result
        else:
            raise HTTPException(status_code=400, detail=db_job.get("error") or f"任务状态: {db_job['status']}")

    raise HTTPException(status_code=404, detail="回测任务不存在")


@router.get("/history")
async def list_backtest_history(
    user_id: str = Query(...),
    limit: int = Query(20, le=50),
):
    """列出用户的回测历史."""
    from backtest.engine import list_user_jobs

    jobs = list_user_jobs(user_id, limit)
    for j in jobs:
        for key in ("created_at", "started_at", "completed_at"):
            if j.get(key):
                j[key] = str(j[key])
        # Ensure strategy_params is dict not string
        if isinstance(j.get("strategy_params"), str):
            try:
                j["strategy_params"] = json.loads(j["strategy_params"])
            except (json.JSONDecodeError, TypeError):
                j["strategy_params"] = {}
    return {"jobs": jobs}
