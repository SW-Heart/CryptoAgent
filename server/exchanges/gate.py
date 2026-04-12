import os
import time
import json
import hmac
import hashlib
from typing import Optional, Dict, List, Any
import requests

from exchanges.base import ExchangeClient

GATE_REST_URL = "https://api.gateio.ws/api/v4"

class GateFuturesClient(ExchangeClient):
    """
    Gate.io Futures (V4 API) Client.
    """
    
    def __init__(self, api_key: str, api_secret: str, environment: str = "live", **kwargs):
        self.api_key = api_key
        self.api_secret = api_secret
        
        # Gate uses same endpoint mostly, testnet exists but base_url differs
        self.base_url = GATE_REST_URL
        self.simulated = environment in ("testnet", "demo")
            
        self.session = requests.Session()
        
        self._instruments_cache: Dict[str, dict] = {}
        self._instruments_last_fetch = 0
    
    def get_exchange_name(self) -> str:
        return "Gate"
        
    def _gen_sign(self, method: str, url_path: str, query_string: str, body_str: str, timestamp: str) -> str:
        """生成 Gate.io V4 签名"""
        # Hashed body (SHA512)
        if body_str:
            hashed_body = hashlib.sha512(body_str.encode('utf-8')).hexdigest()
        else:
            hashed_body = hashlib.sha512(b"").hexdigest()
            
        payload = f"{method.upper()}\n{url_path}\n{query_string}\n{hashed_body}\n{timestamp}"
        
        sign = hmac.new(
            self.api_secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        return sign

    def _request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[dict] = None,
        body: Optional[dict] = None
    ) -> dict:
        url_path = "/api/v4" + endpoint
        url = "https://api.gateio.ws" + url_path
        
        query_string = ""
        if method.upper() == "GET" and params:
            query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
            url += "?" + query_string
            
        body_str = ""
        if method.upper() != "GET" and body is not None:
            body_str = json.dumps(body)
            
        max_retries = 3
        for attempt in range(max_retries):
            timestamp = str(int(time.time()))
            signature = self._gen_sign(method, url_path, query_string, body_str, timestamp)
            
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "KEY": self.api_key,
                "Timestamp": timestamp,
                "SIGN": signature
            }
            
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
                
                # Check for logic errors
                if isinstance(resp_json, dict) and "label" in resp_json:
                    return {"error": f"Gate API Error: {resp_json.get('message', '')}"}
                    
                return {"data": resp_json}
                
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return {"error": f"Request failed: {str(e)}"}
                
        return {"error": "Maximum retries reached"}

    def _convert_symbol(self, symbol: str) -> str:
        """ gate.io uses BTC_USDT format """
        if "USDT" in symbol and "_" not in symbol:
            return symbol.replace("USDT", "_USDT")
        return symbol

    def _convert_symbol_back(self, raw_symbol: str) -> str:
        return raw_symbol.replace("_", "")

    def test_connection(self) -> dict:
        try:
            res = self._request("GET", "/futures/usdt/accounts")
            if "error" in res:
                return {"success": False, "message": res["error"]}
            return {"success": True, "message": "Connected to Gate"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _fetch_instruments(self):
        """缓存合约信息以获取合约乘数 (ctVal) 和精度信息"""
        now = time.time()
        if now - self._instruments_last_fetch < 3600 and self._instruments_cache:
            return
            
        res = self._request("GET", "/futures/usdt/contracts")
        if "error" not in res:
            data = res.get("data", [])
            for contract in data:
                sym = contract["name"]
                self._instruments_cache[sym] = {
                    "ct_val": float(contract.get("quanto_multiplier", 1)),
                    "min_qty": float(contract.get("order_size_min", 1)),
                }
            self._instruments_last_fetch = now

    def _get_ct_val(self, symbol: str) -> float:
        self._fetch_instruments()
        raw_sym = self._convert_symbol(symbol)
        inst = self._instruments_cache.get(raw_sym)
        return inst["ct_val"] if inst else 1.0

    def get_instrument_info(self, symbol: str) -> dict:
        self._fetch_instruments()
        raw_sym = self._convert_symbol(symbol)
        inst = self._instruments_cache.get(raw_sym)
        if inst:
            return {
                "qty_precision": 0, # Gate order sizes are integer
                "price_precision": 4, # Fallback generic
                "min_qty": inst.get("min_qty", 1.0),
                "min_notional": 5.0, # Approximate
                "ct_val": inst.get("ct_val", 1.0)
            }
        return super().get_instrument_info(symbol)

    def get_usdt_balance(self) -> dict:
        res = self._request("GET", "/futures/usdt/accounts")
        if "error" in res: return res
        
        try:
            d = res.get("data", {})
            equity = float(d.get("total", 0))
            unrealized = float(d.get("unrealised_pnl", 0))
            available = float(d.get("available", 0))
            
            return {
                "wallet_balance": equity - unrealized,
                "available_balance": available,
                "margin_balance": equity,
                "unrealized_pnl": unrealized,
                "assets": []
            }
        except Exception as e:
            return {"error": str(e)}

    def get_positions(self) -> List[dict]:
        res = self._request("GET", "/futures/usdt/positions")
        if "error" in res: return []
        
        positions = []
        try:
            data = res.get("data", [])
            for p in data:
                size = float(p.get("size", 0))
                if size == 0: continue
                
                sym = self._convert_symbol_back(p.get("contract", ""))
                direction = "LONG" if size > 0 else "SHORT"
                
                margin_type = "isolated" if p.get("cross_leverage_limit", 0) == 0 else "cross"
                
                positions.append({
                    "symbol": sym,
                    "direction": direction,
                    "quantity": abs(size),
                    "entry_price": float(p.get("entry_price", 0)),
                    "mark_price": float(p.get("mark_price", 0)),
                    "unrealized_pnl": float(p.get("unrealised_pnl", 0)),
                    "leverage": int(p.get("leverage", 1)),
                    "margin_type": margin_type,
                    "liquidation_price": float(p.get("liq_price", 0) or 0)
                })
        except:
            pass
        return positions

    def get_mark_price(self, symbol: str) -> dict:
        raw_sym = self._convert_symbol(symbol)
        res = self._request("GET", f"/futures/usdt/tickers", {"contract": raw_sym})
        if "error" in res:
            return res
        data = res.get("data", [])
        if data:
            return {"markPrice": float(data[0].get("mark_price", 0))}
        return {"error": "Not found"}
        
    def get_position_mode(self, symbol: str) -> dict:
        return {"dualSidePosition": True}
        
    def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        reduce_only: bool = False,
        position_side: str = None
    ) -> dict:
        contract = self._convert_symbol(symbol)
        qty = quantity / self._get_ct_val(symbol)
        if side.upper() == "SELL":
            qty = -qty
            
        body = {
            "contract": contract,
            "size": int(qty),
            "price": "0",
            "tif": "ioc"
        }
        
        if reduce_only:
            body["reduce_only"] = True
            
        res = self._request("POST", "/futures/usdt/orders", body=body)
        if "error" in res:
            return res
            
        data = res.get("data", {})
        if data.get("id"):
            return {
                "orderId": str(data["id"]),
                "symbol": symbol,
                "status": "NEW"
            }
        return {"error": f"Gate order failed: {data}"}

    def place_stop_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_price: float,
        reduce_only: bool = True,
        position_side: str = None
    ) -> dict:
        contract = self._convert_symbol(symbol)
        qty = quantity / self._get_ct_val(symbol)
        if side.upper() == "SELL":
            qty = -qty
            
        # SL rule:
        # sell to close long SL -> price <= trigger
        # buy to close short SL -> price >= trigger
        rule = 2 if side.upper() == "SELL" else 1
        
        body = {
            "initial": {
                "contract": contract,
                "size": int(qty),
                "price": "0",
                "tif": "ioc",
                "reduce_only": reduce_only
            },
            "trigger": {
                "strategy_type": 0,
                "price_type": 1,
                "price": str(stop_price),
                "rule": rule
            }
        }
        
        res = self._request("POST", "/futures/usdt/price_orders", body=body)
        if "error" in res:
            return res
            
        data = res.get("data", {})
        if data.get("id"):
            return {
                "orderId": str(data["id"]),
                "symbol": symbol,
                "status": "NEW"
            }
        return {"error": f"Gate stop order failed: {data}"}

    def place_take_profit_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_price: float,
        reduce_only: bool = True,
        position_side: str = None
    ) -> dict:
        contract = self._convert_symbol(symbol)
        qty = quantity / self._get_ct_val(symbol)
        if side.upper() == "SELL":
            qty = -qty
            
        # TP rule:
        # sell to close long TP -> price >= trigger
        # buy to close short TP -> price <= trigger
        rule = 1 if side.upper() == "SELL" else 2
        
        body = {
            "initial": {
                "contract": contract,
                "size": int(qty),
                "price": "0",
                "tif": "ioc",
                "reduce_only": reduce_only
            },
            "trigger": {
                "strategy_type": 0, 
                "price_type": 1, 
                "price": str(stop_price),
                "rule": rule
            }
        }
        
        res = self._request("POST", "/futures/usdt/price_orders", body=body)
        if "error" in res:
            return res
            
        data = res.get("data", {})
        if data.get("id"):
            return {
                "orderId": str(data["id"]),
                "symbol": symbol,
                "status": "NEW"
            }
        return {"error": f"Gate TP order failed: {data}"}

    def cancel_order(self, symbol: str, order_id: str) -> dict:
        res = self._request("DELETE", f"/futures/usdt/orders/{order_id}")
        if "error" in res:
            return res
        return {"success": True, "orderId": order_id}

    def cancel_algo_order(self, symbol: str, algo_id: str) -> dict:
        res = self._request("DELETE", f"/futures/usdt/price_orders/{algo_id}")
        if "error" in res:
            return res
        return {"success": True, "algoId": algo_id}

    def cancel_all_orders(self, symbol: str) -> dict:
        contract = self._convert_symbol(symbol)
        res = self._request("DELETE", "/futures/usdt/orders", {"contract": contract})
        return {"success": "error" not in res}

    def cancel_all_algo_orders(self, symbol: str) -> dict:
        contract = self._convert_symbol(symbol)
        res = self._request("DELETE", "/futures/usdt/price_orders", {"contract": contract})
        return {"success": "error" not in res}

    def cancel_all_orders_and_algo(self, symbol: str) -> dict:
        r1 = self.cancel_all_orders(symbol)
        r2 = self.cancel_all_algo_orders(symbol)
        if not r1.get("success"):
            return r1
        return r2

    def get_open_orders(self, symbol: str = None) -> list:
        params = {"status": "open"}
        if symbol:
            params["contract"] = self._convert_symbol(symbol)
        
        res = self._request("GET", "/futures/usdt/orders", params)
        if "error" in res:
            return []
            
        formatted = []
        data = res.get("data", [])
        for o in data:
            raw_sym = o.get("contract", "")
            size = float(o.get("size", 0))
            is_reduce_only = o.get("is_reduce_only", False)
            
            side = "BUY" if size > 0 else "SELL"
            ct_val = self._get_ct_val(raw_sym)
            
            formatted.append({
                "orderId": str(o.get("id", "")),
                "symbol": self._convert_symbol_back(raw_sym),
                "side": side,
                "type": "LIMIT", # Simplify: assume LIMIT open orders commonly
                "origQty": abs(size) * ct_val,
                "executedQty": 0.0,
                "price": float(o.get("price", 0)),
                "stopPrice": 0.0,
                "reduceOnly": is_reduce_only,
                "status": "NEW",
                "time": int(o.get("create_time", 0) * 1000),
            })
        return formatted

    def get_open_algo_orders(self, symbol: str = None) -> list:
        params = {"status": "open"}
        if symbol:
            params["contract"] = self._convert_symbol(symbol)
            
        res = self._request("GET", "/futures/usdt/price_orders", params)
        if "error" in res:
            return []
            
        formatted = []
        data = res.get("data", [])
        for o in data:
            initial = o.get("initial", {})
            trigger = o.get("trigger", {})
            
            raw_sym = initial.get("contract", "")
            size = float(initial.get("size", 0))
            is_reduce_only = initial.get("is_reduce_only", True)
            
            side = "BUY" if size > 0 else "SELL"
            ct_val = self._get_ct_val(raw_sym)
            
            # infer type based on combination of side and trigger rule
            rule = trigger.get("rule", 1) 
            if side == "SELL":
                order_type = "TAKE_PROFIT_MARKET" if rule == 1 else "STOP_MARKET"
            else:
                order_type = "STOP_MARKET" if rule == 1 else "TAKE_PROFIT_MARKET"
                
            trigger_px = float(trigger.get("price", 0))
            
            formatted.append({
                "algoId": str(o.get("id", "")),
                "orderId": str(o.get("id", "")),
                "symbol": self._convert_symbol_back(raw_sym),
                "side": side,
                "type": order_type,
                "algoType": order_type,
                "triggerPrice": trigger_px,
                "stopPrice": trigger_px,
                "price": float(initial.get("price", 0)),
                "origQty": abs(size) * ct_val,
                "quantity": abs(size) * ct_val,
                "reduceOnly": is_reduce_only,
                "status": "NEW",
                "time": int(o.get("create_time", 0) * 1000)
            })
        return formatted

    def get_trade_history(self, symbol: str, limit: int = 50, start_time: int = None, end_time: int = None) -> list:
        return []

    def get_order_history(self, symbol: str, limit: int = 50, start_time: int = None, end_time: int = None) -> list:
        return []

    def get_income_history(self, symbol: str = None, limit: int = 50, start_time: int = None, end_time: int = None) -> list:
        return []

    def set_leverage(self, symbol: str, leverage: int, margin_type: str = "isolated") -> dict:
        return {"success": True}

    def set_margin_type(self, symbol: str, margin_type: str = "isolated") -> dict:
        return {"success": True}


    def get_account_info(self) -> dict:
        return {}
        
    def place_batch_orders(self, orders: list) -> list:
        return []
