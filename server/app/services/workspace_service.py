"""
Workspace service layer for product shell objects.

This module introduces product-facing objects without breaking the
existing strategy runtime and user-level legacy settings.
"""
import json
import os
import re
from decimal import Decimal
from typing import Any

from agno.utils.log import logger
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.models.deepseek import DeepSeek
from agno.models.anthropic import Claude
from agno.models.google import Gemini
from app.database import get_db_connection
from binance_client import (
    disable_user_trading,
    enable_user_trading,
    get_user_api_keys,
    get_user_strategy_config,
    get_user_trading_status,
    has_user_api_keys,
)


def init_workspace_tables():
    """Initialize product shell tables used by the new workspace model."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS exchange_accounts (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    status TEXT DEFAULT 'ACTIVE',
                    credentials_source TEXT DEFAULT 'manual',
                    is_connected BOOLEAN DEFAULT FALSE,
                    is_default BOOLEAN DEFAULT FALSE,
                    metadata_json JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (user_id, slug)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_profiles (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    symbols TEXT DEFAULT 'BTC,ETH,SOL',
                    timeframes TEXT DEFAULT '1h,4h',
                    max_positions INTEGER DEFAULT 3,
                    risk_per_trade DOUBLE PRECISION DEFAULT 0.02,
                    trading_interval INTEGER DEFAULT 60,
                    prompt_template TEXT DEFAULT 'Focus on trend following strategy with strict risk management.',
                    is_enabled BOOLEAN DEFAULT TRUE,
                    source TEXT DEFAULT 'workspace',
                    config_json JSONB DEFAULT '{}'::jsonb,
                    last_analyzed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (user_id, slug)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_configs (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    api_key TEXT NOT NULL,
                    base_url TEXT,
                    is_default BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS trader_instances (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    name TEXT NOT NULL,
                    strategy_profile_id INTEGER REFERENCES strategy_profiles(id) ON DELETE SET NULL,
                    exchange_account_id INTEGER REFERENCES exchange_accounts(id) ON DELETE SET NULL,
                    llm_config_id INTEGER REFERENCES llm_configs(id) ON DELETE SET NULL,
                    llm_provider TEXT DEFAULT 'deepseek',
                    llm_model TEXT DEFAULT 'deepseek-chat',
                    runtime_mode TEXT DEFAULT 'paper',
                    status TEXT DEFAULT 'STOPPED',
                    is_enabled BOOLEAN DEFAULT FALSE,
                    source TEXT DEFAULT 'workspace',
                    config_json JSONB DEFAULT '{}'::jsonb,
                    last_started_at TIMESTAMP,
                    last_stopped_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (user_id, slug)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS trader_runtime_events (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    trader_instance_id INTEGER REFERENCES trader_instances(id) ON DELETE CASCADE,
                    event_type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    payload_json JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS system_notifications (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    type TEXT DEFAULT 'info',
                    is_read BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

            # Migration: ensure llm_config_id column exists in trader_instances
            # (tables created before this column was added won't have it)
            try:
                cursor.execute("SELECT llm_config_id FROM trader_instances LIMIT 0")
            except Exception:
                conn.rollback()
                print("[Workspace] Migrating trader_instances: Adding llm_config_id column")
                cursor.execute(
                    "ALTER TABLE trader_instances ADD COLUMN llm_config_id INTEGER REFERENCES llm_configs(id) ON DELETE SET NULL"
                )
                conn.commit()

            # Migration: ensure last_analyzed_at column exists in strategy_profiles
            try:
                cursor.execute("SELECT last_analyzed_at FROM strategy_profiles LIMIT 0")
            except Exception:
                conn.rollback()
                print("[Workspace] Migrating strategy_profiles: Adding last_analyzed_at column")
                cursor.execute(
                    "ALTER TABLE strategy_profiles ADD COLUMN last_analyzed_at TIMESTAMP"
                )
                conn.commit()
    finally:
        conn.close()


def _normalize_json(value: Any) -> dict:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return {}


def _to_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _slugify(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug or fallback


def _strip_symbol_suffix(sym: str) -> str:
    """去除交易对的稳定币后缀，如 BTCUSDT → BTC，后端API会自动拼接"""
    s = sym.upper().strip()
    for suffix in ('USDT', 'USDC', 'BUSD'):
        if s.endswith(suffix):
            return s[:-len(suffix)]
    return s


def _serialize_list(values: list[str], fallback: str) -> str:
    cleaned = [_strip_symbol_suffix(item) for item in values if item and item.strip()]
    return ",".join(cleaned) if cleaned else fallback


def _build_unique_slug(cursor, table_name: str, user_id: str, preferred_slug: str) -> str:
    base_slug = preferred_slug or "draft"
    slug = base_slug
    suffix = 2

    while True:
        cursor.execute(
            f"SELECT 1 FROM {table_name} WHERE user_id = %s AND slug = %s",
            (user_id, slug),
        )
        if not cursor.fetchone():
            return slug
        slug = f"{base_slug}-{suffix}"
        suffix += 1


def _record_runtime_event(user_id: str, trader_id: int, event_type: str, summary: str, payload: dict | None = None):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO trader_runtime_events (
                    user_id, trader_instance_id, event_type, summary, payload_json
                )
                VALUES (%s, %s, %s, %s, %s::jsonb)
                """,
                (user_id, trader_id, event_type, summary, json.dumps(payload or {})),
            )
            conn.commit()
    finally:
        conn.close()


# Cache: avoid running the expensive legacy sync on every GET request.
# Maps user_id → last_sync_timestamp. Expires after _SYNC_CACHE_TTL seconds.
_sync_cache: dict[str, float] = {}
_SYNC_CACHE_TTL = 60  # seconds


def sync_legacy_workspace_state(user_id: str, force: bool = False):
    """
    Materialize product shell objects from existing user-level config.

    This keeps the new workspace model in sync with the current runtime
    until Strategy Lab and Trader Runtime fully replace legacy settings.

    Uses a per-user TTL cache to avoid redundant DB round-trips on every
    API GET request (the uncached path does ~9 DB queries + 3 UPSERTs).
    """
    if not user_id:
        return

    import time as _time
    now = _time.time()
    if not force and user_id in _sync_cache and (now - _sync_cache[user_id]) < _SYNC_CACHE_TTL:
        return  # recently synced, skip

    exchange_account_id = _sync_legacy_exchange_account(user_id)
    strategy_profile_id = _sync_legacy_strategy_profile(user_id)
    _sync_legacy_trader_instance(user_id, strategy_profile_id, exchange_account_id)

    _sync_cache[user_id] = now



def _sync_legacy_exchange_account(user_id: str):
    keys = get_user_api_keys(user_id)
    trading_status = get_user_trading_status(user_id)

    if not keys and not trading_status.get("is_configured"):
        return None

    environment = "testnet" if keys and keys.get("is_testnet") else "live"
    slug = f"binance-{environment}"
    display_name = "Binance Testnet" if environment == "testnet" else "Binance Live"
    metadata = {
        "legacy": True,
        "provider": "binance",
        "environment": environment,
        "trading_enabled": bool(trading_status.get("is_trading_enabled")),
    }

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO exchange_accounts (
                    user_id, slug, provider, environment, display_name,
                    status, credentials_source, is_connected, is_default,
                    metadata_json, updated_at
                )
                VALUES (%s, %s, 'binance', %s, %s, 'ACTIVE', 'legacy_binance_keys', %s, TRUE, %s::jsonb, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, slug) DO UPDATE SET
                    environment = EXCLUDED.environment,
                    display_name = EXCLUDED.display_name,
                    status = EXCLUDED.status,
                    credentials_source = EXCLUDED.credentials_source,
                    is_connected = EXCLUDED.is_connected,
                    is_default = EXCLUDED.is_default,
                    metadata_json = EXCLUDED.metadata_json,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
                """,
                (
                    user_id,
                    slug,
                    environment,
                    display_name,
                    bool(trading_status.get("is_configured")),
                    json.dumps(metadata),
                ),
            )
            row = cursor.fetchone()
            conn.commit()
            return row["id"] if row else None
    finally:
        conn.close()


def _sync_legacy_strategy_profile(user_id: str):
    config = get_user_strategy_config(user_id)
    # If this is just a default fallback and NOT a real database record, 
    # we should NOT overwrite/create a legacy profile that might conflict
    # with the user's manual setup.
    if config.get("is_default"):
        return None

    metadata = {
        "legacy": True,
        "strategy_enabled": bool(config.get("strategy_enabled", True)),
        "llm_provider": config.get("llm_provider", "deepseek"),
        "llm_model": config.get("llm_model", "deepseek-chat"),
    }

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO strategy_profiles (
                    user_id, slug, name, description, symbols, timeframes,
                    max_positions, risk_per_trade, trading_interval,
                    prompt_template, is_enabled, source, config_json, updated_at
                )
                VALUES (
                    %s, 'legacy-primary', 'Primary Strategy',
                    'Imported from the existing per-user strategy configuration.',
                    %s, '1h,4h', %s, %s, %s, %s, %s, 'legacy_import', %s::jsonb, CURRENT_TIMESTAMP
                )
                ON CONFLICT (user_id, slug) DO UPDATE SET
                    symbols = EXCLUDED.symbols,
                    max_positions = EXCLUDED.max_positions,
                    risk_per_trade = EXCLUDED.risk_per_trade,
                    trading_interval = EXCLUDED.trading_interval,
                    prompt_template = EXCLUDED.prompt_template,
                    is_enabled = EXCLUDED.is_enabled,
                    config_json = EXCLUDED.config_json,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
                """,
                (
                    user_id,
                    config.get("symbols", "BTC,ETH,SOL"),
                    config.get("max_positions", 3),
                    config.get("risk_per_trade", 0.02),
                    config.get("trading_interval", 60),
                    config.get("agent_requirements", "Focus on trend following strategy with strict risk management."),
                    bool(config.get("strategy_enabled", True)),
                    json.dumps(metadata),
                ),
            )
            row = cursor.fetchone()
            conn.commit()
            return row["id"] if row else None
    finally:
        conn.close()


def _sync_legacy_trader_instance(user_id: str, strategy_profile_id: int | None, exchange_account_id: int | None):
    config = get_user_strategy_config(user_id)
    trading_status = get_user_trading_status(user_id)
    keys = get_user_api_keys(user_id)

    environment = "testnet" if keys and keys.get("is_testnet") else "live"
    runtime_mode = "paper" if environment == "testnet" else "live"
    status = "RUNNING" if trading_status.get("is_trading_enabled") else "STOPPED"
    if not exchange_account_id:
        status = "CONFIG_REQUIRED"

    metadata = {
        "legacy": True,
        "exchange_environment": environment,
        "strategy_enabled": bool(config.get("strategy_enabled", True)),
        "legacy_default": config.get("is_default", False)
    }

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO trader_instances (
                    user_id, slug, name, strategy_profile_id, exchange_account_id,
                    llm_provider, llm_model, runtime_mode, status, is_enabled,
                    source, config_json, updated_at, last_started_at, last_stopped_at
                )
                VALUES (
                    %s, 'primary-runtime', 'Primary Trader',
                    %s, %s, %s, %s, %s, %s, %s, 'legacy_import',
                    %s::jsonb, CURRENT_TIMESTAMP,
                    CASE WHEN %s = 'RUNNING' THEN CURRENT_TIMESTAMP ELSE NULL END,
                    CASE WHEN %s = 'STOPPED' THEN CURRENT_TIMESTAMP ELSE NULL END
                )
                ON CONFLICT (user_id, slug) DO UPDATE SET
                    -- sync_legacy 绝不覆盖用户手动设置的值，只填充空位
                    strategy_profile_id = COALESCE(trader_instances.strategy_profile_id, EXCLUDED.strategy_profile_id),
                    exchange_account_id = COALESCE(trader_instances.exchange_account_id, EXCLUDED.exchange_account_id),
                    llm_provider = COALESCE(trader_instances.llm_provider, EXCLUDED.llm_provider),
                    llm_model = COALESCE(trader_instances.llm_model, EXCLUDED.llm_model),
                    runtime_mode = COALESCE(trader_instances.runtime_mode, EXCLUDED.runtime_mode),
                    -- status 和 is_enabled 也保留现有值
                    status = COALESCE(trader_instances.status, EXCLUDED.status),
                    is_enabled = COALESCE(trader_instances.is_enabled, EXCLUDED.is_enabled),
                    config_json = EXCLUDED.config_json,
                    updated_at = CURRENT_TIMESTAMP,
                    last_started_at = CASE
                        WHEN EXCLUDED.status = 'RUNNING' THEN CURRENT_TIMESTAMP
                        ELSE trader_instances.last_started_at
                    END,
                    last_stopped_at = CASE
                        WHEN EXCLUDED.status = 'STOPPED' THEN CURRENT_TIMESTAMP
                        ELSE trader_instances.last_stopped_at
                    END
                """,
                (
                    user_id,
                    strategy_profile_id,
                    exchange_account_id,
                    config.get("llm_provider", "deepseek"),
                    config.get("llm_model", "deepseek-chat"),
                    runtime_mode,
                    status,
                    bool(trading_status.get("is_trading_enabled")),
                    json.dumps(metadata),
                    status,
                    status,
                ),
            )
            conn.commit()
    finally:
        conn.close()


def list_exchange_accounts(user_id: str) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, slug, provider, environment, display_name, status,
                       credentials_source, is_connected, is_default, metadata_json,
                       created_at, updated_at
                FROM exchange_accounts
                WHERE user_id = %s
                ORDER BY is_default DESC, id ASC
                """,
                (user_id,),
            )
            # Ensure rows are dicts if using row["column"]
            # If the driver doesn't support DictCursor by default, we map them manually
            columns = [desc[0] for desc in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        return [
            {
                "id": row["id"],
                "slug": row["slug"],
                "name": row.get("display_name") or "未命名账户",
                "display_name": row.get("display_name") or "未命名账户",
                "exchange": row.get("provider"),
                "provider": row.get("provider"),
                "environment": row.get("environment"),
                "status": row.get("status"),
                "credentials_source": row.get("credentials_source"),
                "is_connected": bool(row.get("is_connected")),
                "is_default": bool(row.get("is_default")),
                "api_key": _mask_api_key(_normalize_json(row.get("metadata_json")).get("api_key", "")),
                "has_secret": bool(_normalize_json(row.get("metadata_json")).get("api_secret")),
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
                "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
            }
            for row in rows
        ]
    finally:
        conn.close()


def list_strategy_profiles(user_id: str) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, slug, name, description, symbols, timeframes, max_positions,
                       risk_per_trade, trading_interval, prompt_template, is_enabled,
                       source, config_json, created_at, updated_at
                FROM strategy_profiles
                WHERE user_id = %s
                ORDER BY id ASC
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
        return [
            {
                "id": row["id"],
                "slug": row["slug"],
                "name": row["name"],
                "description": row["description"],
                "symbols": _to_list(row["symbols"]),
                "timeframes": _to_list(row["timeframes"]),
                "max_positions": row["max_positions"],
                "risk_per_trade": float(row["risk_per_trade"]),
                "trading_interval": row["trading_interval"],
                "prompt_template": row["prompt_template"],
                "is_enabled": bool(row["is_enabled"]),
                "source": row["source"],
                "config": _normalize_json(row["config_json"]),
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            }
            for row in rows
        ]
    finally:
        conn.close()


def list_trader_instances(user_id: str) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT ti.id, ti.slug, ti.name, ti.strategy_profile_id, ti.exchange_account_id,
                       ti.llm_config_id, ti.llm_provider, ti.llm_model, ti.runtime_mode, ti.status,
                       ti.is_enabled, ti.source, ti.config_json, ti.last_started_at,
                       ti.last_stopped_at, ti.created_at, ti.updated_at,
                       sp.name AS strategy_name,
                       ea.display_name AS exchange_name
                FROM trader_instances ti
                LEFT JOIN strategy_profiles sp ON sp.id = ti.strategy_profile_id
                LEFT JOIN exchange_accounts ea ON ea.id = ti.exchange_account_id
                WHERE ti.user_id = %s
                ORDER BY ti.id ASC
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
        return [
            {
                "id": row["id"],
                "slug": row["slug"],
                "name": row["name"],
                "strategy_profile_id": row["strategy_profile_id"],
                "exchange_account_id": row["exchange_account_id"],
                "llm_config_id": row.get("llm_config_id"),
                "strategy_name": row["strategy_name"],
                "exchange_name": row["exchange_name"],
                "llm_provider": row["llm_provider"],
                "llm_model": row["llm_model"],
                "runtime_mode": row["runtime_mode"],
                "status": row["status"],
                "is_enabled": bool(row["is_enabled"]),
                "source": row["source"],
                "config": _normalize_json(row["config_json"]),
                "last_started_at": row["last_started_at"].isoformat() if row["last_started_at"] else None,
                "last_stopped_at": row["last_stopped_at"].isoformat() if row["last_stopped_at"] else None,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            }
            for row in rows
        ]
    finally:
        conn.close()


def list_trader_runtime_events(user_id: str, trader_id: int, limit: int = 20) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, event_type, summary, payload_json, created_at
                FROM trader_runtime_events
                WHERE user_id = %s AND trader_instance_id = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (user_id, trader_id, max(1, min(limit, 200))),
            )
            rows = cursor.fetchall()
        return [
            {
                "id": row["id"],
                "event_type": row["event_type"],
                "summary": row["summary"],
                "payload": _normalize_json(row["payload_json"]),
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in rows
        ]
    finally:
        conn.close()


def add_system_notification(user_id: str, title: str, content: str, type: str = 'info') -> dict:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO system_notifications (user_id, title, content, type)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (user_id, title, content, type),
            )
            row = cursor.fetchone()
            conn.commit()
            return {"success": True, "id": row["id"] if row else None}
    finally:
        conn.close()


def list_system_notifications(user_id: str, unread_only: bool = False, limit: int = 50) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            query = "SELECT id, title, content, type, is_read, created_at FROM system_notifications WHERE user_id = %s"
            params = [user_id]
            if unread_only:
                query += " AND is_read = FALSE"
            query += " ORDER BY id DESC LIMIT %s"
            params.append(min(limit, 100))
            
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "content": row["content"],
                "type": row["type"],
                "is_read": bool(row["is_read"]),
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in rows
        ]
    finally:
        conn.close()


def mark_system_notification_read(user_id: str, notif_id: int = None) -> dict:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if notif_id is not None:
                cursor.execute(
                    "UPDATE system_notifications SET is_read = TRUE WHERE id = %s AND user_id = %s",
                    (notif_id, user_id),
                )
            else:
                # Mark all as read
                cursor.execute(
                    "UPDATE system_notifications SET is_read = TRUE WHERE user_id = %s AND is_read = FALSE",
                    (user_id,),
                )
            conn.commit()
            return {"success": True}
    finally:
        conn.close()


def create_strategy_profile(user_id: str, payload: dict) -> dict:
    symbols = _serialize_list(payload.get("symbols") or ["BTC", "ETH", "SOL"], "BTC,ETH,SOL")
    timeframes = ",".join(payload.get("timeframes") or ["1h", "4h"])
    name = payload.get("name") or "Draft Strategy"
    prompt_template = payload.get("prompt_template") or "Focus on trend following strategy with strict risk management."
    metadata = _normalize_json(payload.get("config"))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            slug = _build_unique_slug(cursor, "strategy_profiles", user_id, _slugify(name, "draft-strategy"))
            cursor.execute(
                """
                INSERT INTO strategy_profiles (
                    user_id, slug, name, description, symbols, timeframes,
                    max_positions, risk_per_trade, trading_interval,
                    prompt_template, is_enabled, source, config_json, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'workspace', %s::jsonb, CURRENT_TIMESTAMP)
                RETURNING id
                """,
                (
                    user_id,
                    slug,
                    name,
                    payload.get("description"),
                    symbols,
                    timeframes,
                    payload.get("max_positions", 3),
                    payload.get("risk_per_trade", 0.02),
                    payload.get("trading_interval", 60),
                    prompt_template,
                    payload.get("is_enabled", True),
                    json.dumps(metadata),
                ),
            )
            row = cursor.fetchone()
            conn.commit()
            return {"success": True, "id": row["id"] if row else None}
    finally:
        conn.close()


def create_trader_instance(user_id: str, payload: dict) -> dict:
    name = payload.get("name") or "Draft Trader"
    metadata = _normalize_json(payload.get("config"))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            slug = _build_unique_slug(cursor, "trader_instances", user_id, _slugify(name, "draft-trader"))
            cursor.execute(
                """
                INSERT INTO trader_instances (
                    user_id, slug, name, strategy_profile_id, exchange_account_id,
                    llm_provider, llm_model, runtime_mode, status, is_enabled,
                    source, config_json, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'workspace', %s::jsonb, CURRENT_TIMESTAMP)
                RETURNING id
                """,
                (
                    user_id,
                    slug,
                    name,
                    payload.get("strategy_profile_id"),
                    payload.get("exchange_account_id"),
                    payload.get("llm_provider", "deepseek"),
                    payload.get("llm_model", "deepseek-chat"),
                    payload.get("runtime_mode", "paper"),
                    payload.get("status", "STOPPED"),
                    payload.get("is_enabled", False),
                    json.dumps(metadata),
                ),
            )
            row = cursor.fetchone()
            conn.commit()
            return {"success": True, "id": row["id"] if row else None}
    finally:
        conn.close()


def update_trader_instance(user_id: str, trader_id: int, payload: dict) -> dict:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, strategy_profile_id, exchange_account_id,
                       llm_provider, llm_model, runtime_mode, status, is_enabled,
                       config_json
                FROM trader_instances
                WHERE id = %s AND user_id = %s
                """,
                (trader_id, user_id),
            )
            previous = cursor.fetchone()
            if not previous:
                raise ValueError("Trader instance not found")

            strategy_profile_id = payload.get("strategy_profile_id") if "strategy_profile_id" in payload else None
            if "strategy_profile_id" in payload and strategy_profile_id is not None:
                cursor.execute(
                    "SELECT id FROM strategy_profiles WHERE id = %s AND user_id = %s",
                    (strategy_profile_id, user_id),
                )
                if not cursor.fetchone():
                    raise ValueError("Linked strategy profile not found")

            exchange_account_id = payload.get("exchange_account_id") if "exchange_account_id" in payload else None
            if "exchange_account_id" in payload and exchange_account_id is not None:
                cursor.execute(
                    "SELECT id FROM exchange_accounts WHERE id = %s AND user_id = %s",
                    (exchange_account_id, user_id),
                )
                if not cursor.fetchone():
                    raise ValueError("Linked exchange account not found")

            updates = []
            values = []
            for key in (
                "name",
                "strategy_profile_id",
                "exchange_account_id",
                "llm_config_id",
                "llm_provider",
                "llm_model",
                "runtime_mode",
                "status",
                "is_enabled",
            ):
                if key in payload:
                    updates.append(f"{key} = %s")
                    values.append(payload[key])

            if "config" in payload:
                updates.append("config_json = %s::jsonb")
                values.append(json.dumps(_normalize_json(payload.get("config"))))

            if not updates:
                return {"success": True}

            updates.append("updated_at = CURRENT_TIMESTAMP")
            values.extend([trader_id, user_id])
            cursor.execute(
                f"UPDATE trader_instances SET {', '.join(updates)} WHERE id = %s AND user_id = %s",
                tuple(values),
            )
            conn.commit()

            changed_fields = {}
            comparable_keys = (
                "name",
                "strategy_profile_id",
                "exchange_account_id",
                "llm_provider",
                "llm_model",
                "runtime_mode",
                "status",
                "is_enabled",
            )
            for key in comparable_keys:
                if key in payload:
                    prev_value = previous[key]
                    next_value = payload[key]
                    if prev_value != next_value:
                        changed_fields[key] = {"from": prev_value, "to": next_value}
            if "config" in payload:
                changed_fields["config"] = {
                    "from": _normalize_json(previous["config_json"]),
                    "to": _normalize_json(payload.get("config")),
                }

            if changed_fields:
                _record_runtime_event(
                    user_id,
                    trader_id,
                    "runtime_binding_updated",
                    "Runtime binding updated",
                    {"changed_fields": changed_fields},
                )

            return {"success": True}
    finally:
        conn.close()


def update_strategy_profile(user_id: str, profile_id: int, payload: dict) -> dict:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM strategy_profiles WHERE id = %s AND user_id = %s",
                (profile_id, user_id),
            )
            if not cursor.fetchone():
                raise ValueError("Strategy profile not found")

            updates = []
            values = []

            if "name" in payload and payload.get("name"):
                updates.append("name = %s")
                values.append(payload["name"])
            if "description" in payload:
                updates.append("description = %s")
                values.append(payload.get("description"))
            if "symbols" in payload:
                updates.append("symbols = %s")
                values.append(_serialize_list(payload.get("symbols") or [], "BTC,ETH,SOL"))
            if "timeframes" in payload:
                timeframes = payload.get("timeframes") or ["1h", "4h"]
                updates.append("timeframes = %s")
                values.append(",".join([str(item).strip() for item in timeframes if str(item).strip()]))
            if "max_positions" in payload:
                updates.append("max_positions = %s")
                values.append(payload.get("max_positions", 3))
            if "risk_per_trade" in payload:
                updates.append("risk_per_trade = %s")
                values.append(payload.get("risk_per_trade", 0.02))
            if "trading_interval" in payload:
                updates.append("trading_interval = %s")
                values.append(payload.get("trading_interval", 60))
            if "prompt_template" in payload:
                updates.append("prompt_template = %s")
                values.append(payload.get("prompt_template") or "Focus on trend following strategy with strict risk management.")
            if "is_enabled" in payload:
                updates.append("is_enabled = %s")
                values.append(bool(payload.get("is_enabled")))
            if "config" in payload:
                updates.append("config_json = %s::jsonb")
                values.append(json.dumps(_normalize_json(payload.get("config"))))

            if not updates:
                return {"success": True}

            updates.append("updated_at = CURRENT_TIMESTAMP")
            values.extend([profile_id, user_id])
            cursor.execute(
                f"UPDATE strategy_profiles SET {', '.join(updates)} WHERE id = %s AND user_id = %s",
                tuple(values),
            )
            conn.commit()
            return {"success": True}
    finally:
        conn.close()


def get_trader_runtime_ready_check(user_id: str, trader_id: int) -> dict:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT ti.id, ti.name, ti.strategy_profile_id, ti.exchange_account_id,
                       sp.symbols AS strategy_symbols, sp.timeframes AS strategy_timeframes,
                       ea.provider AS exchange_provider, ea.environment AS exchange_environment
                FROM trader_instances ti
                LEFT JOIN strategy_profiles sp ON sp.id = ti.strategy_profile_id
                LEFT JOIN exchange_accounts ea ON ea.id = ti.exchange_account_id
                WHERE ti.id = %s AND ti.user_id = %s
                """,
                (trader_id, user_id),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError("Trader instance not found")
    finally:
        conn.close()

    details = {
        "exchange": {"ok": False, "message": "No linked exchange account"},
        "llm": {"ok": False, "message": "No LLM API key configured"},
        "strategy": {"ok": False, "message": "No linked strategy profile"},
    }
    ready = True

    if row["exchange_account_id"] and row["exchange_provider"]:
        if row["exchange_provider"] == "binance":
            # Check legacy keys first, then fall back to workspace-created account credentials
            if has_user_api_keys(user_id):
                details["exchange"] = {
                    "ok": True,
                    "message": f"Binance {row['exchange_environment'] or 'live'} account ready",
                }
            else:
                # Check if the linked exchange_account has credentials in metadata_json
                ea_conn = get_db_connection()
                try:
                    with ea_conn.cursor() as ea_cursor:
                        ea_cursor.execute(
                            "SELECT metadata_json FROM exchange_accounts WHERE id = %s AND user_id = %s",
                            (row["exchange_account_id"], user_id),
                        )
                        ea_row = ea_cursor.fetchone()
                        ea_meta = _normalize_json(ea_row["metadata_json"]) if ea_row else {}
                finally:
                    ea_conn.close()

                if _has_valid_credentials(ea_meta):
                    details["exchange"] = {
                        "ok": True,
                        "message": f"Binance {row['exchange_environment'] or 'live'} account ready (workspace)",
                    }
                else:
                    details["exchange"] = {"ok": False, "message": "Binance API keys are missing"}
                    ready = False
        else:
            details["exchange"] = {"ok": True, "message": f"{row['exchange_provider']} account linked"}
    else:
        ready = False

    config = get_user_strategy_config(user_id) or {}
    if config.get("llm_api_key_encrypted"):
        details["llm"] = {
            "ok": True,
            "message": f"{config.get('llm_provider', 'default')}/{config.get('llm_model', 'default')} ready",
        }
    else:
        # Fall back to checking workspace llm_configs table
        llm_configs = list_llm_configs(user_id)
        if llm_configs and len(llm_configs) > 0:
            default_llm = llm_configs[0]
            details["llm"] = {
                "ok": True,
                "message": f"{default_llm.get('provider', 'default')}/{default_llm.get('model', 'default')} ready (workspace)",
            }
        else:
            ready = False

    has_strategy_link = bool(row["strategy_profile_id"])
    has_strategy_symbols = bool((row["strategy_symbols"] or "").strip())
    if has_strategy_link and has_strategy_symbols:
        details["strategy"] = {
            "ok": True,
            "message": f"Symbols: {row['strategy_symbols']} | Timeframes: {row['strategy_timeframes'] or '1h,4h'}",
        }
    else:
        ready = False

    return {"ready": ready, "details": details, "trader_id": trader_id, "trader_name": row["name"]}


def set_trader_runtime_action(user_id: str, trader_id: int, action: str) -> dict:
    """
    Control trader runtime state.

    For legacy primary runtime, this bridges to the current user-level
    Binance trading enable/disable flow.
    """
    normalized_action = (action or "").strip().lower()
    if normalized_action not in {"start", "stop", "pause"}:
        raise ValueError("Unsupported runtime action")

    sync_legacy_workspace_state(user_id)

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, slug, source, exchange_account_id
                FROM trader_instances
                WHERE id = %s AND user_id = %s
                """,
                (trader_id, user_id),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError("Trader instance not found")

            is_legacy_primary = row["slug"] == "primary-runtime" and row["source"] == "legacy_import"
            if normalized_action == "start" and not row["exchange_account_id"]:
                raise ValueError("Trader has no linked exchange account")
            if normalized_action == "start":
                ready_check = get_trader_runtime_ready_check(user_id, trader_id)
                if not ready_check.get("ready"):
                    details = ready_check.get("details", {})
                    reason_parts = [
                        details[key]["message"]
                        for key in ("exchange", "llm", "strategy")
                        if not details.get(key, {}).get("ok")
                    ]
                    reason = "; ".join(reason_parts) if reason_parts else "Unknown readiness failure"
                    raise ValueError(f"Runtime not ready: {reason}")
                
                # Pre-flight API check
                cursor.execute("SELECT provider, metadata_json, environment FROM exchange_accounts WHERE id = %s AND user_id = %s", (row["exchange_account_id"], user_id))
                ea_row = cursor.fetchone()
                if ea_row:
                    import json
                    from binance_client import decrypt_value
                    meta = ea_row["metadata_json"]
                    
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta)
                        except Exception:
                            meta = {}
                    if not isinstance(meta, dict):
                        meta = {}
                        
                    raw_key = meta.get("api_key", "")
                    raw_secret = meta.get("api_secret", "")
                    raw_passphrase = meta.get("passphrase", "")
                    provider = ea_row.get("provider", "binance")
                    environment = ea_row.get("environment", "demo")
                    
                    api_key = decrypt_value(raw_key) if raw_key and raw_key.startswith("gAAAA") else raw_key
                    api_secret = decrypt_value(raw_secret) if raw_secret and raw_secret.startswith("gAAAA") else raw_secret
                    passphrase = decrypt_value(raw_passphrase) if raw_passphrase and raw_passphrase.startswith("gAAAA") else raw_passphrase
                    
                    try:
                        from exchanges.factory import create_exchange_client
                        # 仅做探活时，统一把 api_key 等灌进去（对 OKX 来说也需要用 passphrase 来走签名验证）
                        client = create_exchange_client(
                            provider=provider,
                            api_key=api_key,
                            api_secret=api_secret,
                            passphrase=passphrase,
                            environment=environment
                        )
                        balance = client.get_usdt_balance()
                        if isinstance(balance, dict) and "error" in balance:
                            raise ValueError(f"交易所凭证校验失败: {balance['error']}")
                    except ValueError as e:
                        raise e
                    except Exception as e:
                        raise ValueError(f"交易所配置无效或不可达: {str(e)}")

            if is_legacy_primary and has_user_api_keys(user_id):
                if normalized_action == "start":
                    result = enable_user_trading(user_id)
                    if not result.get("success"):
                        raise ValueError(result.get("error", "Failed to enable legacy trading runtime"))
                else:
                    result = disable_user_trading(user_id)
                    if not result.get("success"):
                        raise ValueError(result.get("error", "Failed to disable legacy trading runtime"))

            next_status = "RUNNING"
            next_enabled = True
            if normalized_action == "stop":
                next_status = "STOPPED"
                next_enabled = False
            elif normalized_action == "pause":
                next_status = "PAUSED"
                next_enabled = False

            cursor.execute(
                """
                UPDATE trader_instances
                SET status = %s,
                    is_enabled = %s,
                    updated_at = CURRENT_TIMESTAMP,
                    last_started_at = CASE WHEN %s = 'RUNNING' THEN CURRENT_TIMESTAMP ELSE last_started_at END,
                    last_stopped_at = CASE WHEN %s IN ('STOPPED', 'PAUSED') THEN CURRENT_TIMESTAMP ELSE last_stopped_at END
                WHERE id = %s AND user_id = %s
                """,
                (next_status, next_enabled, next_status, next_status, trader_id, user_id),
            )
            conn.commit()

            _record_runtime_event(
                user_id,
                trader_id,
                f"runtime_{normalized_action}",
                f"Runtime {normalized_action} action executed",
                {"next_status": next_status, "is_enabled": next_enabled},
            )
    finally:
        conn.close()


def delete_strategy_profile(user_id: str, profile_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Check if exists and is not legacy (don't allow deleting legacy sync items)
            cursor.execute(
                "SELECT id, slug FROM strategy_profiles WHERE id = %s AND user_id = %s",
                (profile_id, user_id),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError("Strategy profile not found")

            if row["slug"] == "legacy-primary":
                raise ValueError("Cannot delete the primary legacy strategy profile")

            cursor.execute(
                "DELETE FROM strategy_profiles WHERE id = %s AND user_id = %s",
                (profile_id, user_id),
            )
            conn.commit()
    finally:
        conn.close()

def delete_exchange_account(user_id: str, account_id: int):
    """Delete an exchange account and unbind from instances."""
    from binance_client import delete_user_api_keys
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Check if exists and check for legacy flag
            cursor.execute(
                "SELECT metadata_json FROM exchange_accounts WHERE id = %s AND user_id = %s",
                (account_id, user_id),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError("Exchange account not found")
            
            metadata = row[0] or {}
            is_legacy = metadata.get("legacy") is True

            # 1. Decouple from any trader instances (Set to NULL instead of cascading delete)
            cursor.execute(
                "UPDATE trader_instances SET exchange_account_id = NULL, status = 'STOPPED' WHERE exchange_account_id = %s AND user_id = %s",
                (account_id, user_id),
            )

            # 2. If it's a legacy account, clear the underlying API keys to stop sync-back
            if is_legacy:
                try:
                    delete_user_api_keys(user_id)
                    # Also clear trading status
                    cursor.execute("DELETE FROM user_trading_status WHERE user_id = %s", (user_id,))
                except Exception as e:
                    print(f"[Workspace] Error clearing legacy keys during delete: {e}")

            # 3. Perform final deletion of the workspace record
            cursor.execute(
                "DELETE FROM exchange_accounts WHERE id = %s AND user_id = %s",
                (account_id, user_id),
            )
            conn.commit()
    finally:
        conn.close()

def list_llm_configs(user_id: str):
    """List all LLM configurations for a user."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, provider, model, base_url, is_default FROM llm_configs WHERE user_id = %s ORDER BY created_at DESC", 
                (user_id,)
            )
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        conn.close()

def create_llm_config(user_id: str, config_data: dict):
    """Create a new LLM configuration."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO llm_configs (user_id, name, provider, model, api_key, base_url)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    user_id,
                    config_data.get('name'),
                    config_data.get('provider'),
                    config_data.get('model'),
                    config_data.get('api_key'),
                    config_data.get('base_url')
                )
            )
            config_id = cursor.fetchone()[0]
            conn.commit()
            return config_id
    finally:
        conn.close()

def delete_llm_config(user_id: str, config_id: int):
    """Delete an LLM configuration and unbind from instances."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Unbind first
            cursor.execute(
                "UPDATE trader_instances SET llm_config_id = NULL WHERE user_id = %s AND llm_config_id = %s",
                (user_id, config_id)
            )
            # Delete 
            cursor.execute(
                "DELETE FROM llm_configs WHERE user_id = %s AND id = %s",
                (user_id, config_id)
            )
            conn.commit()
            return True
    finally:
        conn.close()

def test_llm_connectivity(config_data: dict):
    """Real connectivity test using Agno framework models."""
    provider = config_data.get('provider', 'openai')
    model_id = config_data.get('model')
    api_key = config_data.get('api_key')
    base_url = config_data.get('base_url')

    if not api_key:
        return {"status": "error", "message": "API Key 缺失"}

    try:
        # 1. Initialize the correct Agno model based on provider
        model = None
        if provider == 'openai':
            model = OpenAIChat(id=model_id, api_key=api_key, base_url=base_url)
        elif provider == 'deepseek':
            # DeepSeek class in new Agno knows its own base_url, but we support overrides
            model = DeepSeek(id=model_id or "deepseek-chat", api_key=api_key, base_url=base_url)
        elif provider == 'anthropic':
            # Note: Agno 2.x uses 'Claude' class for Anthropic models
            model = Claude(id=model_id or "claude-3-5-sonnet-20240620", api_key=api_key)
        elif provider == 'google':
            # Gemini in Agno 2.x uses 'id' and 'api_key'
            model = Gemini(id=model_id or "gemini-1.5-pro", api_key=api_key)
        elif provider in ('custom', 'qwen', 'glm', 'minimax', 'kimi'):
            # Custom provider assumed to be OpenAI-compatible
            model = OpenAIChat(id=model_id, api_key=api_key, base_url=base_url)
        else:
            return {"status": "error", "message": f"不支持的提供商类型: {provider}"}

        # 2. Perform a lightweight handshake (request 'hi')
        # We use a very low-cost Agent.run call for compatibility across model providers.
        probe_agent = Agent(
            model=model,
            instructions=["Reply with 'ok' only."],
            add_history_to_context=False,
            num_history_runs=0,
        )
        response = probe_agent.run("hi")
        
        if response and response.content:
            # 3. Validate response content — reject if it contains auth/error keywords
            content_lower = response.content.lower()
            error_indicators = [
                "authentication fail", "invalid", "unauthorized", "api key",
                "error", "denied", "expired", "quota", "rate limit",
                "forbidden", "not found", "401", "403", "429"
            ]
            for indicator in error_indicators:
                if indicator in content_lower:
                    return {"status": "error", "message": f"API Key 验证失败: {response.content[:200]}"}
            
            return {"status": "success", "message": "连接测试成功，模型响应正常"}
        else:
            return {"status": "error", "message": "模型未返回有效内容，请检查后端配置"}

    except Exception as e:
        logger.error(f"LLM Connectivity test failed: {str(e)}")
        error_msg = str(e)
        
        # Friendly translations for common errors
        if "Incorrect API key" in error_msg or "Authentication" in error_msg or "invalid" in error_msg.lower():
            return {"status": "error", "message": "API Key 无效或已过期"}
        if "404" in error_msg or "not found" in error_msg.lower():
            return {"status": "error", "message": "模型 ID 不存在或接口地址 (Base URL) 错误"}
        if "Connection" in error_msg or "timeout" in error_msg.lower():
            return {"status": "error", "message": "连接超时，请检查网络或代理设置"}
        
        return {"status": "error", "message": f"连接失败: {error_msg}"}

def create_exchange_account(user_id: str, data: dict):
    """Create a new exchange account connection with encrypted credentials."""
    import uuid
    from app.database import get_db_connection
    from binance_client import encrypt_value
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            name = data.get('name') or "Exchange"
            slug_base = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or "exchange"
            slug = f"{slug_base}-{uuid.uuid4().hex[:6]}"
            
            # 加密存储 API 凭证
            raw_key = data.get('api_key') or ""
            raw_secret = data.get('api_secret') or ""
            raw_passphrase = data.get('passphrase') or ""
            
            metadata = {}
            if raw_key:
                try:
                    metadata["api_key"] = encrypt_value(raw_key)
                except Exception as e:
                    print(f"[Workspace] Encryption failed for api_key, storing raw (ENCRYPTION_KEY may not be set): {e}")
                    metadata["api_key"] = raw_key
            if raw_secret:
                try:
                    metadata["api_secret"] = encrypt_value(raw_secret)
                except Exception as e:
                    print(f"[Workspace] Encryption failed for api_secret: {e}")
                    metadata["api_secret"] = raw_secret
            if raw_passphrase:
                try:
                    metadata["passphrase"] = encrypt_value(raw_passphrase)
                except Exception as e:
                    metadata["passphrase"] = raw_passphrase
            
            cursor.execute(
                """
                INSERT INTO exchange_accounts (user_id, slug, provider, environment, display_name, metadata_json)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                RETURNING id
                """,
                (
                    user_id,
                    slug,
                    data.get('exchange'),
                    data.get('environment', 'demo'),
                    name,
                    json.dumps(metadata)
                )
            )
            account_id = cursor.fetchone()[0]
            conn.commit()
            return account_id
    finally:
        conn.close()


def _mask_api_key(key: str) -> str:
    """脱敏 API Key，只显示末尾 4 位。兼容加密后的值（gAAAA 前缀）。"""
    if not key:
        return ""
    # 如果是加密后的值，先解密再脱敏
    if key.startswith("gAAAA"):
        try:
            from binance_client import decrypt_value
            decrypted = decrypt_value(key)
            return f"****{decrypted[-4:]}" if len(decrypted) >= 4 else "****"
        except Exception:
            return "****[encrypted]"
    # 原始明文 key
    return f"****{key[-4:]}" if len(key) >= 4 else "****"


def _has_valid_credentials(meta: dict) -> bool:
    """检查 metadata 中是否包含有效的 API 凭证（兼容加密和明文）。"""
    api_key = meta.get("api_key", "")
    api_secret = meta.get("api_secret", "")
    if not api_key or not api_secret:
        return False
    # 加密后的值以 gAAAA 开头，也视为有效
    return True
