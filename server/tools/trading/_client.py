"""
Exchange Trading Tools for Strategy Nexus
Unified trading operations for all supported exchanges (Binance, OKX, etc.)

This module provides exchange-agnostic trading operations using the unified
ExchangeClient interface. The actual exchange client is resolved at runtime
via exchange_factory based on the user's configured exchange account.

IMPORTANT: These functions use thread-local context to get user_id.
Call trading_tools.set_current_user(user_id) before using these tools.
"""
import os
from datetime import datetime
from typing import Optional, Dict, List, Any

from binance_client import (
    get_user_binance_client,
    get_user_trading_status,
    has_user_api_keys,
    BinanceFuturesClient
)

# Import context management from trading_tools
from tools.trading_tools import get_current_user, STRATEGY_ADMIN_USER_ID


def _get_effective_user_id(user_id: str = None) -> str:
    """
    Get effective user ID from parameter or thread context.
    Falls back to admin user if not set.
    
    Important: Filters out invalid placeholder values like "user" that
    LLMs sometimes generate incorrectly.
    """
    # Filter out invalid placeholder values that LLM might generate
    invalid_values = {"user", "user_id", ""}
    if user_id and user_id.lower() not in invalid_values and len(user_id) >= 10:
        return user_id
    
    # Fall back to context
    context_user = get_current_user()
    if context_user:
        return context_user
    
    return STRATEGY_ADMIN_USER_ID


def _get_trading_client(user_id: str, require_trading_enabled: bool = True):
    """
    统一获取 Binance Client 的入口（支持双路径）。

    路径 A: user_binance_keys 表 + user_trading_status 表（旧系统）
    路径 B: exchange_accounts 表（Workspace 新系统）

    Args:
        user_id: 用户 ID
        require_trading_enabled: 是否检查 is_trading_enabled（下单类操作需要，查询类不需要）

    Returns:
        (client, None) on success
        (None, error_message) on failure
    """
    # ===== 路径 A: 旧系统 =====
    if has_user_api_keys(user_id):
        if require_trading_enabled:
            status = get_user_trading_status(user_id)
            if not status.get("is_trading_enabled"):
                return None, "Trading is not enabled. Please enable trading first."
        client = get_user_binance_client(user_id)
        if client:
            return client, None
        return None, "Failed to create Binance client"

    # ===== 路径 B: 新系统 exchange_accounts =====
    try:
        from app.database import get_db_connection
        from tools.trading_tools import get_current_trader_id
        
        trader_id = None
        try:
            trader_id = get_current_trader_id()
        except Exception:
            pass

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                ea_row = None
                
                # 1. 优先通过上下文中获取到的 trader_id 精准锁定绑定的交易所账户
                if trader_id:
                    cur.execute('''
                        SELECT ea.id, ea.provider, ea.metadata_json, ea.environment
                        FROM trader_instances ti
                        JOIN exchange_accounts ea ON ea.id = ti.exchange_account_id
                        WHERE ti.id = %s AND ti.user_id = %s
                    ''', (trader_id, user_id))
                    ea_row = cur.fetchone()

                # 2. 否则按全局 connected + default 查找
                if not ea_row:
                    cur.execute('''
                        SELECT ea.id, ea.provider, ea.metadata_json, ea.environment
                        FROM exchange_accounts ea
                        WHERE ea.user_id = %s
                        ORDER BY ea.is_connected DESC, ea.is_default DESC, ea.id ASC
                        LIMIT 1
                    ''', (user_id,))
                    ea_row = cur.fetchone()

                # 如果直接查不到，通过 trader_instances 关联查
                if not ea_row:
                    cur.execute("""
                        SELECT ea.id, ea.provider, ea.metadata_json, ea.environment
                        FROM trader_instances ti
                        JOIN exchange_accounts ea ON ea.id = ti.exchange_account_id
                        WHERE ti.user_id = %s AND ti.exchange_account_id IS NOT NULL
                        ORDER BY ti.status = 'RUNNING' DESC, ti.id ASC
                        LIMIT 1
                    """, (user_id,))
                    ea_row = cur.fetchone()
        finally:
            conn.close()

        if not ea_row:
            return None, "No exchange account configured. Please set up your Binance API keys."

        # 解析 metadata_json
        meta = ea_row["metadata_json"]
        if meta and isinstance(meta, str):
            import json as _json
            try:
                meta = _json.loads(meta)
            except Exception:
                meta = {}
        if not isinstance(meta, dict):
            meta = {}

        raw_key = meta.get("api_key", "")
        raw_secret = meta.get("api_secret", "")
        environment = ea_row.get("environment", "demo")
        is_testnet = environment in ("testnet", "demo")

        # 解密（如果已加密）
        from binance_client import decrypt_value
        api_key = raw_key
        api_secret = raw_secret
        passphrase = meta.get("passphrase", "")
        
        if raw_key and raw_key.startswith("gAAAA"):
            try:
                api_key = decrypt_value(raw_key)
            except Exception:
                api_key = ""
        if raw_secret and raw_secret.startswith("gAAAA"):
            try:
                api_secret = decrypt_value(raw_secret)
            except Exception:
                api_secret = ""
        if passphrase and passphrase.startswith("gAAAA"):
            try:
                passphrase = decrypt_value(passphrase)
            except Exception:
                passphrase = ""

        if not api_key or not api_secret:
            return None, "Exchange account API credentials are empty or decryption failed."

        provider = ea_row.get("provider", "binance")
        
        from exchanges.factory import create_exchange_client
        client = create_exchange_client(
            provider=provider,
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            environment=environment
        )
        print(f"[TradingTools] Client created via exchange_accounts (provider={provider}, env={environment}) for user {user_id[:8]}")
        return client, None

    except Exception as e:
        print(f"[BinanceTrading] _get_trading_client fallback error: {e}")
        return None, f"Failed to initialize trading client: {str(e)}"

