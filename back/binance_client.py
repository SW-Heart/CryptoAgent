"""
Binance Futures API Client

Provides authenticated access to Binance Futures API (USDT-Margined).
Supports both Testnet and Mainnet environments.

Testnet:
- REST API: https://demo-fapi.binance.com
- WebSocket: wss://fstream.binancefuture.com

Mainnet:
- REST API: https://fapi.binance.com
- WebSocket: wss://fstream.binance.com
"""

import os
import time
import hmac
import hashlib
import sqlite3
from urllib.parse import urlencode
from typing import Optional, Dict, List, Any
from datetime import datetime
import requests
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64

# ==========================================
# Configuration
# ==========================================

# URLs - 注意: demo-fapi.binance.com 在某些网络环境有 SSL 问题，使用 testnet.binancefuture.com 代替
TESTNET_REST_URL = os.getenv("BINANCE_TESTNET_REST_URL", "https://testnet.binancefuture.com")
TESTNET_WS_URL = os.getenv("BINANCE_TESTNET_WS_URL", "wss://stream.binancefuture.com")
MAINNET_REST_URL = os.getenv("BINANCE_MAINNET_REST_URL", "https://fapi.binance.com")
MAINNET_WS_URL = os.getenv("BINANCE_MAINNET_WS_URL", "wss://fstream.binance.com")

# Database path
DB_PATH = os.getenv("DB_PATH", "tmp/test.db")

# Encryption key (must be set in environment)
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")


# ==========================================
# Encryption Utilities
# ==========================================

def _get_fernet() -> Fernet:
    """Get Fernet cipher for encryption/decryption."""
    if not ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY environment variable is not set")
    
    # Use PBKDF2 to derive a proper key from the password
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"binance_api_keys_salt",  # Static salt for deterministic key derivation
        iterations=100000,
        backend=default_backend()
    )
    key = base64.urlsafe_b64encode(kdf.derive(ENCRYPTION_KEY.encode()))
    return Fernet(key)


def encrypt_value(value: str) -> str:
    """Encrypt a string value."""
    fernet = _get_fernet()
    return fernet.encrypt(value.encode()).decode()


def decrypt_value(encrypted_value: str) -> str:
    """Decrypt an encrypted string value."""
    fernet = _get_fernet()
    return fernet.decrypt(encrypted_value.encode()).decode()


# ==========================================
# Database Operations
# ==========================================

from app.database import get_db_connection as _get_db

def init_binance_tables():
    """Initialize Binance-related database tables."""
    conn = _get_db()
    with conn.cursor() as cursor:
        # User API Keys table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_binance_keys (
                user_id TEXT PRIMARY KEY,
                api_key_encrypted TEXT NOT NULL,
                api_secret_encrypted TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    # User Trading Status table
    # User Trading Status table
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_trading_status (
                user_id TEXT PRIMARY KEY,
                is_trading_enabled BOOLEAN DEFAULT FALSE,
                enabled_at TIMESTAMP,
                disabled_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    conn.close()
    
    conn.commit()
    conn.close()


# ==========================================
# API Key Management
# ==========================================

def save_user_api_keys(user_id: str, api_key: str, api_secret: str, is_testnet: bool = True) -> dict:
    """
    Save user's Binance API keys (encrypted).
    
    Args:
        user_id: User ID
        api_key: Binance API Key
        api_secret: Binance API Secret
        is_testnet: Whether to use testnet (default True)
    
    Returns:
        dict with success status
    """
    try:
        encrypted_key = encrypt_value(api_key)
        encrypted_secret = encrypt_value(api_secret)
        
        conn = _get_db()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO user_binance_keys 
                (user_id, api_key_encrypted, api_secret_encrypted, is_testnet, updated_at)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) DO UPDATE SET 
                api_key_encrypted = EXCLUDED.api_key_encrypted,
                api_secret_encrypted = EXCLUDED.api_secret_encrypted,
                is_testnet = EXCLUDED.is_testnet,
                updated_at = CURRENT_TIMESTAMP
            """, (user_id, encrypted_key, encrypted_secret, is_testnet))
            conn.commit()
        conn.close()
        conn.commit()
        conn.close()
        
        return {"success": True, "message": "API keys saved successfully"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_user_api_keys(user_id: str) -> dict:
    """
    Delete user's Binance API keys.
    
    Args:
        user_id: User ID
    
    Returns:
        dict with success status
    """
    conn = _get_db()
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM user_binance_keys WHERE user_id = %s", (user_id,))
        deleted = cursor.rowcount > 0
        
        # Also disable trading
        cursor.execute("""
            UPDATE user_trading_status 
            SET is_trading_enabled = FALSE, disabled_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
        """, (user_id,))
        conn.commit()
    conn.close()
    
    return {"success": True, "deleted": deleted}


def has_user_api_keys(user_id: str) -> bool:
    """Check if user has configured API keys."""
    conn = _get_db()
    with conn.cursor() as cursor:
        cursor.execute("SELECT 1 FROM user_binance_keys WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
    conn.close()
    return row is not None


def get_user_api_keys(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get user's decrypted API keys.
    
    Args:
        user_id: User ID
    
    Returns:
        dict with api_key, api_secret, is_testnet or None if not found
    """
    conn = _get_db()
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT api_key_encrypted, api_secret_encrypted, is_testnet FROM user_binance_keys WHERE user_id = %s",
            (user_id,)
        )
        row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    
    try:
        return {
            "api_key": decrypt_value(row["api_key_encrypted"]),
            "api_secret": decrypt_value(row["api_secret_encrypted"]),
            "is_testnet": bool(row["is_testnet"])
        }
    except Exception as e:
        print(f"[BinanceClient] Failed to decrypt keys for user {user_id}: {e}")
        return None


# ==========================================
# Trading Status Management
# ==========================================

def get_user_trading_status(user_id: str) -> dict:
    """
    Get user's trading status.
    
    Returns:
        dict with is_configured, is_trading_enabled, enabled_at, disabled_at
    """
    is_configured = has_user_api_keys(user_id)
    
    conn = _get_db()
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT is_trading_enabled, enabled_at, disabled_at FROM user_trading_status WHERE user_id = %s",
            (user_id,)
        )
        row = cursor.fetchone()
    conn.close()
    
    if not row:
        return {
            "is_configured": is_configured,
            "is_trading_enabled": False,
            "enabled_at": None,
            "disabled_at": None
        }
    
    return {
        "is_configured": is_configured,
        "is_trading_enabled": bool(row["is_trading_enabled"]) if is_configured else False,
        "enabled_at": row["enabled_at"],
        "disabled_at": row["disabled_at"]
    }


def enable_user_trading(user_id: str) -> dict:
    """
    Enable trading for a user.
    
    Args:
        user_id: User ID
    
    Returns:
        dict with success status
    """
    if not has_user_api_keys(user_id):
        return {"success": False, "error": "API keys not configured"}
    
    conn = _get_db()
    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO user_trading_status 
            (user_id, is_trading_enabled, enabled_at, updated_at)
            VALUES (%s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET
            is_trading_enabled = TRUE,
            enabled_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        """, (user_id,))
        conn.commit()
    conn.close()
    
    return {"success": True, "message": "Trading enabled"}


def disable_user_trading(user_id: str) -> dict:
    """
    Disable trading for a user.
    
    Args:
        user_id: User ID
    
    Returns:
        dict with success status
    """
    conn = _get_db()
    with conn.cursor() as cursor:
        cursor.execute("""
            UPDATE user_trading_status 
            SET is_trading_enabled = FALSE, disabled_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
        """, (user_id,))
        conn.commit()
    conn.close()
    
    return {"success": True, "message": "Trading disabled"}


def get_all_active_trading_users() -> List[str]:
    """
    Get all users with trading enabled (for startup recovery).
    
    Returns:
        List of user IDs with active trading
    """
    conn = _get_db()
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT uts.user_id 
            FROM user_trading_status uts
            JOIN user_binance_keys ubk ON uts.user_id = ubk.user_id
            WHERE uts.is_trading_enabled = TRUE
        """)
        rows = cursor.fetchall()
    conn.close()
    
    return [row["user_id"] for row in rows]


# ==========================================
# Binance Futures API Client
# ==========================================

class BinanceFuturesClient:
    """
    Binance Futures API Client (USDT-Margined).
    
    Handles authentication, request signing, and API calls.
    """
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        """
        Initialize the client.
        
        Args:
            api_key: Binance API Key
            api_secret: Binance API Secret
            testnet: Use testnet if True, mainnet if False
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.base_url = TESTNET_REST_URL if testnet else MAINNET_REST_URL
        self.session = requests.Session()
        self.session.headers.update({
            "X-MBX-APIKEY": api_key,
            "Content-Type": "application/x-www-form-urlencoded"
        })
        
        # 测试网在某些网络环境下可能有 SSL 证书问题，允许跳过验证
        # 注意：仅用于测试网，主网必须验证 SSL
        if testnet:
            self.session.verify = False
            # 禁止 SSL 警告
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    def _get_timestamp(self) -> int:
        """Get current timestamp in milliseconds."""
        return int(time.time() * 1000)
    
    def _sign(self, params: dict) -> str:
        """
        Generate HMAC-SHA256 signature.
        
        Args:
            params: Request parameters
        
        Returns:
            Signature string
        """
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[dict] = None,
        signed: bool = True
    ) -> dict:
        """
        Send API request.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            params: Request parameters
            signed: Whether to sign the request
        
        Returns:
            Response JSON
        """
        url = f"{self.base_url}{endpoint}"
        params = params or {}
        
        if signed:
            params["timestamp"] = self._get_timestamp()
            params["signature"] = self._sign(params)
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=params, timeout=15)
            elif method.upper() == "POST":
                response = self.session.post(url, data=params, timeout=15)
            elif method.upper() == "PUT":
                response = self.session.put(url, data=params, timeout=15)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, params=params, timeout=15)
            else:
                return {"error": f"Unsupported HTTP method: {method}"}
            
            # Handle rate limits
            if response.status_code == 429:
                return {"error": "Rate limit exceeded", "code": 429}
            
            # Check for empty response
            if not response.text or len(response.text.strip()) == 0:
                return {"error": f"Empty response from API (status: {response.status_code})"}
            
            # Try to parse JSON
            try:
                data = response.json()
            except ValueError as e:
                # 响应不是有效 JSON，可能是 HTML 错误页面
                print(f"[BinanceClient] Invalid JSON response: {response.text[:200]}")
                return {"error": f"Invalid JSON response: {response.text[:100]}..."}
            
            # Check for API errors
            if response.status_code >= 400:
                return {
                    "error": data.get("msg", "Unknown error"),
                    "code": data.get("code", response.status_code)
                }
            
            return data
            
        except requests.exceptions.Timeout:
            return {"error": "Request timeout (15s)"}
        except requests.exceptions.SSLError as e:
            return {"error": f"SSL Error: {str(e)}"}
        except requests.exceptions.ConnectionError as e:
            return {"error": f"Connection failed: {str(e)}"}
        except requests.exceptions.RequestException as e:
            return {"error": f"Request failed: {str(e)}"}
        except Exception as e:
            return {"error": f"Unexpected error: {str(e)}"}
    
    # ==========================================
    # Account Endpoints
    # ==========================================
    
    def get_account_info(self) -> dict:
        """
        Get account information including balances and positions.
        
        Returns:
            Account information
        """
        return self._request("GET", "/fapi/v2/account")
    
    def get_balance(self) -> dict:
        """
        Get account balance.
        
        Returns:
            Balance information for all assets
        """
        return self._request("GET", "/fapi/v2/balance")
    
    def get_usdt_balance(self) -> dict:
        """
        获取合约账户余额信息。
        手动汇总各资产的美元价值（稳定币直接取值，非稳定币按市价折算）。
        
        Returns:
            dict with:
            - wallet_balance: 钱包总余额 (USD)
            - margin_balance: 保证金余额 (USD)
            - available_balance: 可用余额 (USD)
            - unrealized_pnl: 总未实现盈亏
            - assets: 各资产明细
        """
        # 使用 account 接口获取完整账户信息
        account = self.get_account_info()
        
        if "error" in account:
            return account
        
        # 稳定币列表（1:1 折算）
        stablecoins = ["USDT", "USDC", "BUSD", "TUSD", "USDP"]
        
        # 汇总各资产
        total_wallet_usd = 0.0
        total_margin_usd = 0.0
        total_available_usd = 0.0
        total_unrealized = 0.0
        assets = []
        
        for asset_info in account.get("assets", []):
            asset_name = asset_info.get("asset", "")
            wallet = float(asset_info.get("walletBalance", 0))
            margin = float(asset_info.get("marginBalance", 0))
            available = float(asset_info.get("availableBalance", 0))
            unrealized = float(asset_info.get("unrealizedProfit", 0))
            
            if wallet <= 0 and margin <= 0 and unrealized == 0:
                continue
            
            # 计算美元价值
            if asset_name in stablecoins:
                # 稳定币直接 1:1
                usd_rate = 1.0
            else:
                # 非稳定币需要获取价格折算
                try:
                    price_data = self.get_mark_price(f"{asset_name}USDT")
                    usd_rate = float(price_data.get("markPrice", 0)) if "error" not in price_data else 0
                except:
                    usd_rate = 0
            
            wallet_usd = wallet * usd_rate
            margin_usd = margin * usd_rate
            available_usd = available * usd_rate
            
            total_wallet_usd += wallet_usd
            total_margin_usd += margin_usd
            total_available_usd += available_usd
            total_unrealized += unrealized
            
            assets.append({
                "asset": asset_name,
                "wallet_balance": wallet,
                "wallet_balance_usd": round(wallet_usd, 2),
                "available_balance": available,
                "unrealized_pnl": unrealized,
                "margin_balance": margin,
                "usd_rate": usd_rate
            })
        
        # 按美元价值降序排序
        assets.sort(key=lambda x: x["wallet_balance_usd"], reverse=True)
        
        return {
            "wallet_balance": round(total_wallet_usd, 2),       # 钱包总余额 (USD)
            "margin_balance": round(total_margin_usd, 2),       # 保证金余额 (USD)
            "available_balance": round(total_available_usd, 2), # 可用余额 (USD)
            "unrealized_pnl": round(total_unrealized, 2),       # 总未实现盈亏
            "assets": assets                                    # 各资产明细
        }
    
    def get_positions(self) -> List[dict]:
        """
        Get current positions.
        
        Returns:
            List of positions with non-zero quantity
        """
        result = self._request("GET", "/fapi/v2/positionRisk")
        
        if "error" in result:
            return result
        
        # Filter positions with non-zero quantity
        positions = []
        for pos in result:
            position_amt = float(pos.get("positionAmt", 0))
            if position_amt != 0:
                positions.append({
                    "symbol": pos.get("symbol"),
                    "direction": "LONG" if position_amt > 0 else "SHORT",
                    "quantity": abs(position_amt),
                    "entry_price": float(pos.get("entryPrice", 0)),
                    "mark_price": float(pos.get("markPrice", 0)),
                    "unrealized_pnl": float(pos.get("unRealizedProfit", 0)),
                    "leverage": int(pos.get("leverage", 1)),
                    "margin_type": pos.get("marginType"),
                    "liquidation_price": float(pos.get("liquidationPrice", 0))
                })
        
        return positions
    
    # ==========================================
    # Trading Endpoints
    # ==========================================
    
    def set_leverage(self, symbol: str, leverage: int) -> dict:
        """
        Set leverage for a symbol.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            leverage: Leverage value (1-125)
        
        Returns:
            Response with leverage and maxNotionalValue
        """
        return self._request("POST", "/fapi/v1/leverage", {
            "symbol": symbol,
            "leverage": leverage
        })
    
    def set_margin_type(self, symbol: str, margin_type: str) -> dict:
        """
        Set margin type for a symbol.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            margin_type: "ISOLATED" or "CROSSED"
        
        Returns:
            Response
        """
        return self._request("POST", "/fapi/v1/marginType", {
            "symbol": symbol,
            "marginType": margin_type
        })
    
    def place_market_order(
        self, 
        symbol: str, 
        side: str, 
        quantity: float,
        reduce_only: bool = False
    ) -> dict:
        """
        Place a market order.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            side: "BUY" or "SELL"
            quantity: Order quantity
            reduce_only: If True, only reduce position
        
        Returns:
            Order response
        """
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "MARKET",
            "quantity": quantity
        }
        
        if reduce_only:
            params["reduceOnly"] = "true"
        
        return self._request("POST", "/fapi/v1/order", params)
    
    def place_stop_market_order(
        self, 
        symbol: str, 
        side: str, 
        quantity: float,
        stop_price: float,
        reduce_only: bool = True
    ) -> dict:
        """
        Place a stop market order (for stop loss).
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            side: "BUY" or "SELL"
            quantity: Order quantity
            stop_price: Trigger price
            reduce_only: If True, only reduce position
        
        Returns:
            Order response
        """
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "STOP_MARKET",
            "quantity": quantity,
            "stopPrice": stop_price
        }
        
        if reduce_only:
            params["reduceOnly"] = "true"
        
        print(f"[BinanceClient] STOP_MARKET order params: {params}")
        result = self._request("POST", "/fapi/v1/order", params)
        print(f"[BinanceClient] STOP_MARKET order result: {result}")
        return result
    
    def place_take_profit_market_order(
        self, 
        symbol: str, 
        side: str, 
        quantity: float,
        stop_price: float,
        reduce_only: bool = True
    ) -> dict:
        """
        Place a take profit market order.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            side: "BUY" or "SELL"
            quantity: Order quantity
            stop_price: Trigger price
            reduce_only: If True, only reduce position
        
        Returns:
            Order response
        """
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "TAKE_PROFIT_MARKET",
            "quantity": quantity,
            "stopPrice": stop_price
        }
        
        if reduce_only:
            params["reduceOnly"] = "true"
        
        print(f"[BinanceClient] TAKE_PROFIT_MARKET order params: {params}")
        result = self._request("POST", "/fapi/v1/order", params)
        print(f"[BinanceClient] TAKE_PROFIT_MARKET order result: {result}")
        return result
    
    def place_batch_orders(self, orders: list) -> dict:
        """
        批量下单 - 一次性提交多个订单（最多5个）。
        
        可用于同时下开仓+止损+止盈订单，实现"一次性带止盈止损开仓"的效果。
        
        Args:
            orders: 订单列表，每个订单是一个 dict，包含:
                - symbol: 交易对
                - side: BUY/SELL
                - type: MARKET/LIMIT/STOP_MARKET/TAKE_PROFIT_MARKET 等
                - quantity: 数量
                - 其他参数依据订单类型
        
        Returns:
            包含所有订单结果的列表
        
        Example:
            orders = [
                {"symbol": "BTCUSDT", "side": "BUY", "type": "MARKET", "quantity": 0.001},
                {"symbol": "BTCUSDT", "side": "SELL", "type": "STOP_MARKET", "quantity": 0.001, 
                 "stopPrice": 85000, "reduceOnly": "true"},
                {"symbol": "BTCUSDT", "side": "SELL", "type": "TAKE_PROFIT_MARKET", "quantity": 0.001,
                 "stopPrice": 95000, "reduceOnly": "true"}
            ]
            result = client.place_batch_orders(orders)
        """
        import json as json_module
        
        if len(orders) > 5:
            return {"error": "Maximum 5 orders allowed per batch"}
        
        # 构建批量订单参数
        # Binance 要求 batchOrders 参数是 JSON 字符串
        params = {
            "batchOrders": json_module.dumps(orders)
        }
        
        print(f"[BinanceClient] Batch orders: {orders}")
        result = self._request("POST", "/fapi/v1/batchOrders", params)
        print(f"[BinanceClient] Batch orders result: {result}")
        return result
    
    def cancel_order(self, symbol: str, order_id: int) -> dict:
        """
        Cancel an order.
        
        Args:
            symbol: Trading pair
            order_id: Order ID to cancel
        
        Returns:
            Cancelled order info
        """
        return self._request("DELETE", "/fapi/v1/order", {
            "symbol": symbol,
            "orderId": order_id
        })
    
    def cancel_all_orders(self, symbol: str) -> dict:
        """
        Cancel all open orders for a symbol.
        
        Args:
            symbol: Trading pair
        
        Returns:
            Response
        """
        return self._request("DELETE", "/fapi/v1/allOpenOrders", {
            "symbol": symbol
        })
    
    # ==========================================
    # Query Endpoints
    # ==========================================
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[dict]:
        """
        Get open orders.
        
        Args:
            symbol: Optional trading pair filter
        
        Returns:
            List of open orders
        """
        params = {}
        if symbol:
            params["symbol"] = symbol
        
        return self._request("GET", "/fapi/v1/openOrders", params)
    
    def get_order_history(self, symbol: str, limit: int = 50) -> List[dict]:
        """
        Get order history.
        
        Args:
            symbol: Trading pair
            limit: Number of orders to return
        
        Returns:
            List of orders
        """
        return self._request("GET", "/fapi/v1/allOrders", {
            "symbol": symbol,
            "limit": limit
        })
    
    def get_trade_history(self, symbol: str, limit: int = 50) -> List[dict]:
        """
        Get trade history.
        
        Args:
            symbol: Trading pair
            limit: Number of trades to return
        
        Returns:
            List of trades
        """
        return self._request("GET", "/fapi/v1/userTrades", {
            "symbol": symbol,
            "limit": limit
        })
    
    def get_mark_price(self, symbol: str) -> dict:
        """
        Get mark price for a symbol (unsigned request).
        
        Args:
            symbol: Trading pair
        
        Returns:
            Mark price info
        """
        return self._request("GET", "/fapi/v1/premiumIndex", {
            "symbol": symbol
        }, signed=False)
    
    def test_connection(self) -> dict:
        """
        Test API connection by getting account info.
        
        Returns:
            dict with success status
        """
        try:
            result = self.get_usdt_balance()
            if "error" in result:
                return {"success": False, "error": result["error"]}
            return {"success": True, "balance": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ==========================================
# User-Specific Client Factory
# ==========================================

def get_user_binance_client(user_id: str) -> Optional[BinanceFuturesClient]:
    """
    Get a Binance client for a specific user.
    
    Args:
        user_id: User ID
    
    Returns:
        BinanceFuturesClient instance or None if not configured
    """
    keys = get_user_api_keys(user_id)
    if not keys:
        return None
    
    return BinanceFuturesClient(
        api_key=keys["api_key"],
        api_secret=keys["api_secret"],
        testnet=keys["is_testnet"]
    )


def test_user_connection(user_id: str) -> dict:
    """
    Test Binance connection for a specific user.
    
    Args:
        user_id: User ID
    
    Returns:
        dict with success status and balance
    """
    if not has_user_api_keys(user_id):
        return {"success": False, "error": "API keys not configured"}
    
    client = get_user_binance_client(user_id)
    if not client:
        return {"success": False, "error": "Failed to create client"}
    
    return client.test_connection()


# Initialize tables on module load
try:
    init_binance_tables()
except Exception as e:
    print(f"[BinanceClient] Warning: Failed to initialize tables: {e}")
