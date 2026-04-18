"""
Workspace router for product shell objects.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from pydantic import BaseModel, Field
import oss2
import os
import uuid

from app.services.workspace_service import (
    create_strategy_profile,
    create_trader_instance,
    get_trader_runtime_ready_check,
    list_exchange_accounts,
    list_llm_configs,
    create_llm_config,
    delete_llm_config,
    test_llm_connectivity,
    list_trader_runtime_events,
    list_strategy_profiles,
    list_trader_instances,
    set_trader_runtime_action,
    sync_legacy_workspace_state,
    update_trader_instance,
    update_strategy_profile,
    delete_strategy_profile,
    create_exchange_account,
    delete_exchange_account,
)

router = APIRouter(prefix="/api/workspace", tags=["workspace"])

# 策略广场模板路由
from app.routers.strategy_templates import router as templates_router
router.include_router(templates_router)


@router.get("/strategy-modules")
def get_strategy_modules():
    """返回可用的策略分析模块注册表（前端模块选择器用）"""
    from tools.strategy_context import get_available_modules
    return {"modules": get_available_modules()}


class StrategyProfileCreateRequest(BaseModel):
    name: str = Field(default="Draft Strategy")
    description: str | None = None
    symbols: list[str] = Field(default_factory=lambda: ["BTC", "ETH", "SOL"])
    timeframes: list[str] = Field(default_factory=lambda: ["1h", "4h"])
    max_positions: int = 3
    risk_per_trade: float = 0.02
    trading_interval: int = 60
    prompt_template: str = "Focus on trend following strategy with strict risk management."
    is_enabled: bool = True
    config: dict = Field(default_factory=dict)


class StrategyProfileUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    symbols: list[str] | None = None
    timeframes: list[str] | None = None
    max_positions: int | None = None
    risk_per_trade: float | None = None
    trading_interval: int | None = None
    prompt_template: str | None = None
    is_enabled: bool | None = None
    config: dict | None = None


class TraderInstanceCreateRequest(BaseModel):
    name: str = Field(default="Draft Trader")
    strategy_profile_id: int | None = None
    exchange_account_id: int | None = None
    llm_config_id: int | None = None
    llm_provider: str = "deepseek"
    llm_model: str = "deepseek-chat"
    runtime_mode: str = "paper"
    status: str = "STOPPED"
    is_enabled: bool = False
    config: dict = Field(default_factory=dict)


class ExchangeAccountCreateRequest(BaseModel):
    name: str = Field(default="My Account")
    exchange: str = Field(default="okx")
    api_key: str
    api_secret: str
    passphrase: str | None = None
    environment: str = Field(default="demo") # 'live' or 'demo'


class TraderInstanceUpdateRequest(BaseModel):
    name: str | None = None
    strategy_profile_id: int | None = None
    exchange_account_id: int | None = None
    llm_config_id: int | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    runtime_mode: str | None = None
    status: str | None = None
    is_enabled: bool | None = None
    config: dict | None = None


class TraderRuntimeActionRequest(BaseModel):
    action: str = Field(pattern="^(start|stop|pause)$")


@router.get("/exchange-accounts")
def get_exchange_accounts(user_id: str):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    try:
        sync_legacy_workspace_state(user_id)
        accounts = list_exchange_accounts(user_id)
        return {"accounts": accounts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategy-profiles")
def get_strategy_profiles(user_id: str):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    try:
        sync_legacy_workspace_state(user_id)
        profiles = list_strategy_profiles(user_id)
        return {"profiles": profiles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/strategy-profiles")
def post_strategy_profile(user_id: str, request: StrategyProfileCreateRequest):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    try:
        create_strategy_profile(user_id, request.model_dump())
        profiles = list_strategy_profiles(user_id)
        return {"success": True, "profiles": profiles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/strategy-profiles/{profile_id}")
def put_strategy_profile(profile_id: int, user_id: str, request: StrategyProfileUpdateRequest):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    try:
        update_strategy_profile(user_id, profile_id, request.model_dump(exclude_unset=True))
        profiles = list_strategy_profiles(user_id)
        return {"success": True, "profiles": profiles}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/strategy-profiles/{profile_id}")
def delete_strategy_profile_route(profile_id: int, user_id: str):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    try:
        delete_strategy_profile(user_id, profile_id)
        profiles = list_strategy_profiles(user_id)
        return {"success": True, "profiles": profiles}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trader-instances")
def get_trader_instances(user_id: str):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    try:
        sync_legacy_workspace_state(user_id)
        traders = list_trader_instances(user_id)
        return {"traders": traders}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trader-instances")
def post_trader_instance(user_id: str, request: TraderInstanceCreateRequest):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    try:
        create_trader_instance(user_id, request.model_dump())
        traders = list_trader_instances(user_id)
        return {"success": True, "traders": traders}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/trader-instances/{trader_id}")
def put_trader_instance(trader_id: int, user_id: str, request: TraderInstanceUpdateRequest):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    try:
        update_trader_instance(user_id, trader_id, request.model_dump(exclude_unset=True))
        traders = list_trader_instances(user_id)
        return {"success": True, "traders": traders}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trader-instances/{trader_id}/ready-check")
def get_trader_ready_check(trader_id: int, user_id: str):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    try:
        return get_trader_runtime_ready_check(user_id, trader_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trader-instances/{trader_id}/events")
def get_trader_events(trader_id: int, user_id: str, limit: int = 20):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    try:
        events = list_trader_runtime_events(user_id, trader_id, limit)
        return {"events": events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trader-instances/{trader_id}/runtime-action")
def post_trader_runtime_action(trader_id: int, user_id: str, request: TraderRuntimeActionRequest):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    try:
        return set_trader_runtime_action(user_id, trader_id, request.action)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trader-instances/{trader_id}/trigger")
def post_trader_trigger(trader_id: int, user_id: str, background_tasks: BackgroundTasks):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    try:
        from app.database import get_db_connection
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    ti.id AS trader_instance_id,
                    ti.user_id,
                    ti.llm_config_id,
                    ti.status,
                    sp.id AS strategy_profile_id,
                    sp.symbols,
                    sp.timeframes,
                    sp.trading_interval,
                    sp.prompt_template,
                    sp.last_analyzed_at
                FROM trader_instances ti
                INNER JOIN strategy_profiles sp ON sp.id = ti.strategy_profile_id
                WHERE ti.id = %s AND ti.user_id = %s
            """, (trader_id, user_id))
            full_trader = cursor.fetchone()
        finally:
            conn.close()
            
        if not full_trader:
            raise ValueError("Could not load full trader details")
            
        full_trader_dict = dict(full_trader)
        if full_trader_dict.get("status") != "RUNNING":
            raise ValueError("Trader must be in RUNNING state to trigger analysis manually")

        from scheduler import _run_trader_instance
        import time
        round_id = time.strftime("%Y-%m-%d_%H:%M") + "_manual"
        background_tasks.add_task(_run_trader_instance, full_trader_dict, round_id)
        
        return {"success": True, "message": "Manual trigger scheduled"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/exchange-accounts/{account_id}")
def delete_exchange_account_route(account_id: int, user_id: str):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    try:
        delete_exchange_account(user_id, account_id)
        accounts = list_exchange_accounts(user_id)
        return {"success": True, "accounts": accounts}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ExchangeTestRequest(BaseModel):
    exchange: str = Field(default="okx")
    api_key: str
    api_secret: str
    passphrase: str | None = None
    environment: str = Field(default="demo")


@router.post("/exchange-accounts/test")
def test_exchange_connection(request: ExchangeTestRequest):
    """
    测试交易所 API 连通性（不保存）。
    通过工厂方法创建对应交易所客户端，尝试获取 USDT 余额来验证凭证有效性。
    兼容 Binance / OKX / Bybit / Bitget / Gate.io 全部五家交易所。
    """
    try:
        from exchanges.factory import create_exchange_client

        client = create_exchange_client(
            provider=request.exchange,
            api_key=request.api_key,
            api_secret=request.api_secret,
            passphrase=request.passphrase or "",
            environment=request.environment,
        )
        balance_result = client.get_usdt_balance()

        # get_usdt_balance 返回 dict，如果有 error 字段说明鉴权失败
        if isinstance(balance_result, dict) and "error" in balance_result:
            return {
                "status": "error",
                "message": f"凭证校验失败: {balance_result['error']}",
            }

        # 成功 —— 提取余额信息
        balance_value = None
        if isinstance(balance_result, dict):
            balance_value = balance_result.get("available") or balance_result.get("balance")
        elif isinstance(balance_result, (int, float)):
            balance_value = balance_result

        return {
            "status": "success",
            "message": "连接测试成功",
            "balance": balance_value,
        }

    except ValueError as e:
        # 工厂方法抛的 "不支持的交易所" 等
        return {"status": "error", "message": str(e)}
    except Exception as e:
        error_msg = str(e)
        # 友好翻译常见错误
        if any(kw in error_msg.lower() for kw in ("invalid", "authentication", "unauthorized", "api key", "signature")):
            return {"status": "error", "message": "API Key 或 Secret 无效，请检查后重试"}
        if any(kw in error_msg.lower() for kw in ("timeout", "connection")):
            return {"status": "error", "message": "连接超时，请检查网络环境或 IP 白名单设置"}
        if "ip" in error_msg.lower() or "whitelist" in error_msg.lower():
            return {"status": "error", "message": "服务器 IP 未加入白名单，请在交易所后台添加"}
        return {"status": "error", "message": f"连接失败: {error_msg}"}


@router.post("/exchange-accounts")
def post_exchange_account_route(user_id: str, request: ExchangeAccountCreateRequest):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    try:
        account_id = create_exchange_account(user_id, request.model_dump())
        return {"id": account_id, "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/llm-configs")
def get_llm_configs_route(user_id: str):
    return {"configs": list_llm_configs(user_id)}

@router.post("/llm-configs")
def create_llm_config_route(user_id: str, config: dict):
    config_id = create_llm_config(user_id, config)
    return {"id": config_id, "status": "success"}

@router.delete("/llm-configs/{config_id}")
def delete_llm_config_route(user_id: str, config_id: int):
    delete_llm_config(user_id, config_id)
    return {"status": "success"}

@router.post("/llm-configs/test")
def test_llm_config_route(config: dict):
    return test_llm_connectivity(config)

@router.get("/debug/inspect-user")
def debug_inspect_user_route(user_id: str):
    """Peek into the raw database for a specific user UUID."""
    from app.database import get_db_connection
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        target_uuid = 'ee20fa53-5ac2-44bc-9237-41b308e291d8'
        
        # Check all relevant tables
        cursor.execute("SELECT * FROM llm_configs WHERE user_id = %s", (target_uuid,))
        llm_configs = cursor.fetchall()
        
        cursor.execute("SELECT * FROM trader_instances WHERE user_id = %s", (target_uuid,))
        trader_instances = cursor.fetchall()
        
        cursor.execute("SELECT * FROM user_strategy_config WHERE user_id = %s", (target_uuid,))
        legacy_config = cursor.fetchall()
        
        cursor.execute("SELECT * FROM exchange_accounts WHERE user_id = %s", (target_uuid,))
        exchange_accounts = cursor.fetchall()

        return {
            "uuid": target_uuid,
            "llm_configs_count": len(llm_configs),
            "exchange_accounts_count": len(exchange_accounts),
            "trader_instances": [dict(r) for r in trader_instances],
            "legacy_config": [dict(r) for r in legacy_config]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()

@router.post("/upload-avatar")
async def upload_avatar_route(file: UploadFile = File(...)):
    OSS_ACCESS_KEY_ID = os.getenv("ALIYUN_OSS_ACCESS_KEY_ID", "")
    OSS_ACCESS_KEY_SECRET = os.getenv("ALIYUN_OSS_ACCESS_KEY_SECRET", "")
    OSS_ENDPOINT = os.getenv("ALIYUN_OSS_ENDPOINT", "oss-cn-hangzhou.aliyuncs.com")
    OSS_BUCKET_NAME = os.getenv("ALIYUN_OSS_BUCKET_NAME", "")
    
    if not all([OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET, OSS_BUCKET_NAME]):
        raise HTTPException(status_code=500, detail="OSS configuration is missing in environment.")
    
    try:
        contents = await file.read()
        
        ext = file.filename.split('.')[-1] if '.' in file.filename else 'png'
        filename = f"avatars/{uuid.uuid4().hex}.{ext}"
        
        auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
        bucket = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET_NAME)
        
        bucket.put_object(filename, contents)
        
        endpoint_clean = OSS_ENDPOINT.replace("https://", "").replace("http://", "")
        public_url = f"https://{OSS_BUCKET_NAME}.{endpoint_clean}/{filename}"
        
        return {"url": public_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
