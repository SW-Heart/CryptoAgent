import os
import time
import json
import hmac
import hashlib
import base64
from typing import Optional, Dict, List, Any
import requests

from exchanges.base import ExchangeClient

BITGET_REST_URL = "https://api.bitget.com"
BITGET_TESTNET_URL = "https://api.bitget.com"

class BitgetFuturesClient(ExchangeClient):
    """
    Bitget Futures (V2 API) Client.
    
    Handles Bitget-specific authentication, request signing, and data formatting.
    """
    
    def __init__(self, api_key: str, api_secret: str, passphrase: str, environment: str = "live", **kwargs):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        
        # Determine base URL and productType based on environment
        if environment in ("testnet", "demo"):
            self.base_url = BITGET_TESTNET_URL
            self.simulated = True
            self.product_type = "USDT-FUTURES"
        else:
            self.base_url = BITGET_REST_URL
            self.simulated = False
            self.product_type = "USDT-FUTURES"
            
        self.session = requests.Session()
        
        self._instruments_cache: Dict[str, dict] = {}
        self._instruments_last_fetch = 0
    
    def get_exchange_name(self) -> str:
        return "Bitget"
        
    def _get_timestamp(self) -> str:
        """获取 Bitget 要求的毫秒级时间戳"""
        return str(int(time.time() * 1000))
        
    def _sign(self, timestamp: str, method: str, request_path: str, body_str: str = "") -> str:
        """
        生成 Bitget 签名: BASE64(HMAC_SHA256(timestamp + method + requestPath + body, secretKey))
        """
        message = timestamp + method.upper() + request_path + body_str
        mac = hmac.new(
            bytes(self.api_secret, 'utf-8'),
            bytes(message, 'utf-8'),
            hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode('utf-8')

    def _request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[dict] = None,
        body: Optional[dict] = None
    ) -> dict:
        """发送请求并处理重试机制"""
        request_path = endpoint
        url = self.base_url + endpoint
        
        query_string = ""
        if method.upper() == "GET" and params:
            # Sort params? Bitget actually requires exactly what is passed. 
            parts = [f"{k}={v}" for k, v in params.items()]
            query_string = "&".join(parts)
            request_path += "?" + query_string
            url += "?" + query_string
            
        body_str = ""
        if method.upper() != "GET" and body is not None:
            body_str = json.dumps(body, separators=(',', ':'))
            
        max_retries = 3
        for attempt in range(max_retries):
            timestamp = self._get_timestamp()
            signature = self._sign(timestamp, method, request_path, body_str)
            
            headers = {
                "ACCESS-KEY": self.api_key,
                "ACCESS-SIGN": signature,
                "ACCESS-TIMESTAMP": timestamp,
                "ACCESS-PASSPHRASE": self.passphrase,
                "Content-Type": "application/json",
                "locale": "en-US"
            }
            if getattr(self, "simulated", False):
                headers["PAPTRADING"] = "1"
            
            try:
                if method.upper() == "GET":
                    response = self.session.get(url, headers=headers, timeout=15)
                elif method.upper() == "POST":
                    response = self.session.post(url, headers=headers, data=body_str, timeout=15)
                else:
                    return {"error": f"Unsupported HTTP method: {method}"}
                
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    return {"error": f"Rate limit exceeded after {max_retries} retries."}
                    
                resp_json = response.json()
                ret_code = resp_json.get("code", "99999")
                if ret_code != "00000":
                    msg = resp_json.get("msg", "Unknown error")
                    return {"error": f"Bitget API Error {ret_code}: {msg}"}
                    
                return {"data": resp_json.get("data")}
                
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return {"error": f"Request failed: {str(e)}"}
                
        return {"error": "Maximum retries reached"}

    def _convert_symbol(self, symbol: str) -> str:
        """Bitget USDT Futures symbol usually same as input e.g., BTCUSDT"""
        return symbol.upper()

    def _convert_symbol_back(self, raw_symbol: str) -> str:
        return raw_symbol.upper()

    def test_connection(self) -> dict:
        try:
            res = self._request("GET", "/api/v2/mix/account/accounts", {"productType": self.product_type})
            if "error" in res:
                return {"success": False, "message": res["error"]}
            return {"success": True, "message": "Connected to Bitget"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_instrument_info(self, symbol: str) -> dict:
        now = time.time()
        if symbol in self._instruments_cache and (now - self._instruments_last_fetch) < 3600:
            return self._instruments_cache[symbol]

        try:
            raw_sym = self._convert_symbol(symbol)
            res = self._request("GET", "/api/v2/mix/market/contracts", {"productType": self.product_type, "symbol": raw_sym})
            if "error" in res:
                return {}
            
            data = res.get("data", [])
            if not data:
                return {}
             
            for c in data:
                if c.get("symbol") == raw_sym:
                    # Parse precision from string places like pricePlace, volumePlace
                    parsed = {
                        "qty_precision": int(c.get("volumePlace", 0)),
                        "price_precision": int(c.get("pricePlace", 0)),
                        "min_qty": float(c.get("minTradeNum", 0)),
                        "min_notional": 0.0, # calculate manually later if needed
                        "ct_val": 1.0
                    }
                    self._instruments_cache[symbol] = parsed
                    self._instruments_last_fetch = now
                    return parsed
            return {}
        except Exception:
            return {}

    def get_usdt_balance(self) -> dict:
        res = self._request("GET", "/api/v2/mix/account/accounts", {"productType": self.product_type})
        if "error" in res:
            return res
            
        try:
            data = res.get("data", [])
            for c in data:
                if c.get("marginCoin") == "USDT":
                    equity = float(c.get("equity", 0))
                    wallet_balance = float(c.get("equity", 0)) # Usually same to equity if isolated etc, let's parse safely
                    available = float(c.get("available", 0))
                    unrealized_pnl = float(c.get("unrealizedPL", 0))
                    
                    return {
                        "wallet_balance": equity - unrealized_pnl, # approximate back
                        "available_balance": available,
                        "margin_balance": equity,
                        "unrealized_pnl": unrealized_pnl,
                        "assets": [
                            {
                                "asset": "USDT",
                                "walletBalance": equity - unrealized_pnl,
                                "marginBalance": equity,
                                "unrealizedProfit": unrealized_pnl,
                                "availableBalance": available
                            }
                        ]
                    }
            return {
                "wallet_balance": 0.0,
                "available_balance": 0.0,
                "margin_balance": 0.0,
                "unrealized_pnl": 0.0,
                "assets": []
            }
        except Exception as e:
            return {"error": str(e)}

    def get_positions(self) -> List[dict]:
        res = self._request("GET", "/api/v2/mix/position/all-position", {"productType": self.product_type, "marginCoin": "USDT"})
        if "error" in res:
            return []
            
        positions = []
        try:
            data = res.get("data", [])
            for p in data:
                # size mapping could vary, baseCoin vs contract number. V2 standard size usually base coin.
                size = float(p.get("total", 0))
                if size == 0:
                    continue
                    
                raw_sym = p.get("symbol", "")
                symbol = self._convert_symbol_back(raw_sym)
                
                # holdSide: "long", "short"
                side = p.get("holdSide", "").upper()
                
                # marginMode: "crossed", "isolated"
                margin_type = "isolated" if p.get("marginMode") == "isolated" else "cross"
                
                positions.append({
                    "symbol": symbol,
                    "direction": side,
                    "quantity": size,
                    "entry_price": float(p.get("averageOpenPrice", 0)),
                    "mark_price": float(p.get("markPrice", 0)),
                    "unrealized_pnl": float(p.get("unrealizedPL", 0)),
                    "leverage": int(p.get("leverage", 1)),
                    "margin_type": margin_type,
                    "liquidation_price": float(p.get("liqPx", 0) or 0)
                })
        except Exception as e:
            print(f"[Bitget] Error parsing positions: {e}")
            
        return positions

    def get_mark_price(self, symbol: str) -> dict:
        raw_sym = self._convert_symbol(symbol)
        res = self._request("GET", "/api/v2/mix/market/ticker", {"productType": self.product_type, "symbol": raw_sym})
        if "error" in res:
            return res
        try:
            data = res.get("data", [])
            if data:
                return {"markPrice": float(data[0].get("markPrice", 0))}
            return {"error": "No ticker data found"}
        except Exception as e:
            return {"error": str(e)}
            
    def get_position_mode(self, symbol: str) -> dict:
        return {"dualSidePosition": False} # Simplified

    def place_market_order(self, symbol: str, side: str, quantity: float, reduce_only: bool = False, **kwargs) -> dict:
        qty_str = str(self.format_quantity(symbol, quantity))
        body = {
            "symbol": self._convert_symbol(symbol),
            "productType": self.product_type,
            "side": "buy" if side.upper() == "BUY" else "sell",
            "tradeSide": "open" if not reduce_only else "close",
            "orderType": "market",
            "size": qty_str,
            "marginMode": "isolated"
        }
        res = self._request("POST", "/api/v2/mix/order/place-order", body=body)
        if "error" in res: return res
        return {"orderId": res.get("data", {}).get("orderId", ""), "status": "NEW"}

    def place_stop_market_order(self, symbol: str, side: str, stop_price: float, quantity: float = None, close_position: bool = False) -> dict:
        return {"error": "Not fully implemented for Bitget"}

    def place_take_profit_market_order(self, symbol: str, side: str, stop_price: float, quantity: float = None, close_position: bool = False) -> dict:
        return {"error": "Not fully implemented for Bitget"}

    def cancel_order(self, symbol: str, order_id: str) -> dict:
        body = {
            "symbol": self._convert_symbol(symbol),
            "productType": self.product_type,
            "orderId": order_id,
            "marginCoin": "USDT"
        }
        res = self._request("POST", "/api/v2/mix/order/cancel-order", body=body)
        if "error" in res:
            return res
        return {"success": True, "orderId": order_id}

    def cancel_algo_order(self, symbol: str, algo_id: str) -> dict:
        body = {
            "orderId": algo_id,
            "symbol": self._convert_symbol(symbol),
            "productType": self.product_type,
            "marginCoin": "USDT"
        }
        res = self._request("POST", "/api/v2/mix/order/cancel-plan-order", body=body)
        if "error" in res:
            return res
        return {"success": True, "algoId": algo_id}

    def cancel_all_orders(self, symbol: str) -> dict:
        body = {
            "symbol": self._convert_symbol(symbol),
            "productType": self.product_type,
            "marginCoin": "USDT"
        }
        return self._request("POST", "/api/v2/mix/order/cancel-all-orders", body=body)

    def cancel_all_algo_orders(self, symbol: str) -> dict:
        """取消指定交易对的全部计划委托单"""
        # 先查出所有 algo orders，再逐个取消
        algo_orders = self.get_open_algo_orders(symbol)
        cancelled = 0
        for o in algo_orders:
            algo_id = o.get("algoId") or o.get("orderId")
            if algo_id:
                try:
                    self.cancel_algo_order(symbol, algo_id)
                    cancelled += 1
                except Exception:
                    pass
        return {"success": True, "cancelled": cancelled}

    def cancel_all_orders_and_algo(self, symbol: str) -> dict:
        r1 = self.cancel_all_orders(symbol)
        r2 = self.cancel_all_algo_orders(symbol)
        if isinstance(r1, dict) and "error" in r1:
            return r1
        return r2

    def get_open_orders(self, symbol: str = None) -> list:
        """获取普通挂单（限价单等）"""
        params = {"productType": self.product_type}
        if symbol:
            params["symbol"] = self._convert_symbol(symbol)
        
        res = self._request("GET", "/api/v2/mix/order/orders-pending", params)
        if "error" in res:
            print(f"[Bitget] get_open_orders error: {res['error']}")
            return []
        
        data = res.get("data", {})
        orders_list = data.get("entrustedList", data) if isinstance(data, dict) else data
        if not isinstance(orders_list, list):
            return []
        
        formatted = []
        for o in orders_list:
            raw_sym = o.get("symbol", "")
            side = o.get("side", "").upper()
            order_type = o.get("orderType", "").upper()
            
            # Bitget side: "buy"/"sell", tradeSide: "open"/"close"
            trade_side = o.get("tradeSide", "").lower()
            reduce_only = trade_side == "close"
            
            formatted.append({
                "orderId": o.get("orderId", ""),
                "symbol": self._convert_symbol_back(raw_sym),
                "side": side,
                "type": "LIMIT" if order_type == "LIMIT" else order_type,
                "origQty": float(o.get("size", 0) or 0),
                "executedQty": float(o.get("baseVolume", 0) or 0),
                "price": float(o.get("price", 0) or 0),
                "stopPrice": 0.0,
                "reduceOnly": reduce_only,
                "status": "NEW",
                "time": int(o.get("cTime", 0) or 0),
            })
        return formatted

    def get_open_algo_orders(self, symbol: str = None) -> list:
        """获取触发计划单（止损/止盈等条件单）"""
        params = {"productType": self.product_type}
        if symbol:
            params["symbol"] = self._convert_symbol(symbol)
        
        res = self._request("GET", "/api/v2/mix/order/orders-plan-pending", params)
        if "error" in res:
            print(f"[Bitget] get_open_algo_orders error: {res['error']}")
            return []
        
        data = res.get("data", {})
        orders_list = data.get("entrustedList", data) if isinstance(data, dict) else data
        if not isinstance(orders_list, list):
            return []
        
        formatted = []
        for o in orders_list:
            raw_sym = o.get("symbol", "")
            side = o.get("side", "").upper()
            plan_type = o.get("planType", "").lower()  # "normal_plan", "profit_plan", "loss_plan", "pos_profit", "pos_loss", "moving_plan", "track_plan"
            trade_side = o.get("tradeSide", "").lower()
            reduce_only = trade_side == "close"
            
            # 映射 Bitget planType 到统一 type
            if plan_type in ("profit_plan", "pos_profit"):
                order_type = "TAKE_PROFIT_MARKET"
            elif plan_type in ("loss_plan", "pos_loss"):
                order_type = "STOP_MARKET"
            elif plan_type == "moving_plan" or plan_type == "track_plan":
                order_type = "TRAILING_STOP_MARKET"
            else:
                # normal_plan = 普通计划单
                order_type = "STOP_MARKET" if reduce_only else "LIMIT"
            
            trigger_price = float(o.get("triggerPrice", 0) or 0)
            exec_price = float(o.get("executePrice", 0) or 0)
            
            formatted.append({
                "algoId": o.get("orderId", ""),
                "orderId": o.get("orderId", ""),
                "symbol": self._convert_symbol_back(raw_sym),
                "side": side,
                "type": order_type,
                "algoType": order_type,
                "origQty": float(o.get("size", 0) or 0),
                "quantity": float(o.get("size", 0) or 0),
                "price": exec_price,
                "stopPrice": trigger_price,
                "triggerPrice": trigger_price,
                "reduceOnly": reduce_only,
                "status": "NEW",
                "time": int(o.get("cTime", 0) or 0),
            })
        return formatted

    def get_trade_history(self, symbol: str, limit: int = 50, start_time: int = None, end_time: int = None) -> list:
        return []

    def get_order_history(self, symbol: str, limit: int = 50, start_time: int = None, end_time: int = None) -> list:
        return []

    def get_income_history(self, symbol: str = None, limit: int = 50, start_time: int = None, end_time: int = None) -> list:
        return []

    def set_leverage(self, symbol: str, leverage: int, margin_type: str = "isolated") -> dict:
        body = {
            "symbol": self._convert_symbol(symbol),
            "productType": "USDT-FUTURES",
            "marginCoin": "USDT",
            "leverage": str(leverage),
            "holdSide": "long" # Bitget often requires specifying side or applying to all
        }
        return self._request("POST", "/api/v2/mix/account/set-leverage", body=body)

    def set_margin_type(self, symbol: str, margin_type: str = "isolated") -> dict:
        body = {
            "symbol": self._convert_symbol(symbol),
            "productType": "USDT-FUTURES",
            "marginCoin": "USDT",
            "marginMode": "isolated" if margin_type == "isolated" else "crossed"
        }
        return self._request("POST", "/api/v2/mix/account/set-margin-mode", body=body)

    def get_account_info(self) -> dict:
        return {}
        
    def place_batch_orders(self, orders: list) -> list:
        return []
