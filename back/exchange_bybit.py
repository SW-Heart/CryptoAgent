import os
import time
import json
import hmac
import hashlib
from typing import Optional, Dict, List, Any
import requests

from exchange_base import ExchangeClient

BYBIT_REST_URL = "https://api.bybit.com"
BYBIT_TESTNET_URL = "https://api-testnet.bybit.com"

class BybitFuturesClient(ExchangeClient):
    """
    Bybit Futures (Perpetual/V5 API) Client.
    
    Handles Bybit-specific authentication, request signing, and data formatting
    to match the unified ExchangeClient interface.
    """
    
    def __init__(self, api_key: str, api_secret: str, environment: str = "live", **kwargs):
        self.api_key = api_key
        self.api_secret = api_secret
        
        # Determine base URL based on environment
        if environment in ("testnet", "demo"):
            self.base_url = BYBIT_TESTNET_URL
            self.simulated = True
        else:
            self.base_url = BYBIT_REST_URL
            self.simulated = False
            
        self.session = requests.Session()
        
        # 缓存合约信息 (用于 base_coin 精度和 price 精度)
        self._instruments_cache: Dict[str, dict] = {}
        self._instruments_last_fetch = 0
        
        self.recv_window = "5000"
    
    def get_exchange_name(self) -> str:
        return "Bybit"
        
    def _get_timestamp(self) -> str:
        """获取 Bybit 要求的毫秒级时间戳"""
        return str(int(time.time() * 1000))
        
    def _sign(self, timestamp: str, params_str: str, body_str: str) -> str:
        """
        生成 Bybit 签名
        rule: timestamp + api_key + recv_window + queryString + body
        """
        message = timestamp + self.api_key + self.recv_window + params_str + body_str
        mac = hmac.new(
            bytes(self.api_secret, 'utf-8'),
            bytes(message, 'utf-8'),
            hashlib.sha256
        )
        return mac.hexdigest()

    def _request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[dict] = None,
        body: Optional[dict] = None
    ) -> dict:
        """发送受 Bybit 鉴权保护的请求 (带指数退避重试)"""
        url = self.base_url + endpoint
        
        # Prepare params and body strings for signature
        params_str = ""
        if params:
            # Sort params and form custom urlencode exactly as required by Bybit without quote
            sorted_params = sorted(params.items())
            params_str = "&".join([f"{k}={v}" for k, v in sorted_params])
            url += "?" + params_str
            
        body_str = ""
        if body is not None:
            # compact JSON
            body_str = json.dumps(body, separators=(',', ':'))
            
        max_retries = 3
        for attempt in range(max_retries):
            timestamp = self._get_timestamp()
            signature = self._sign(timestamp, params_str, body_str)
            
            headers = {
                "X-BAPI-API-KEY": self.api_key,
                "X-BAPI-TIMESTAMP": timestamp,
                "X-BAPI-SIGN": signature,
                "X-BAPI-RECV-WINDOW": self.recv_window,
                "Content-Type": "application/json"
            }
            
            try:
                if method.upper() == "GET":
                    response = self.session.get(url, headers=headers, timeout=15)
                elif method.upper() == "POST":
                    response = self.session.post(url, headers=headers, data=body_str, timeout=15)
                else:
                    return {"error": f"Unsupported HTTP method: {method}"}
                
                # Handling HTTP 429 Too Many Requests or equivalent rate limits
                if response.status_code == 429 or response.status_code == 418:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        time.sleep(wait_time)
                        continue
                    return {"error": f"Rate limit exceeded after {max_retries} retries."}
                    
                resp_json = response.json()
                
                # Check for logic errors
                ret_code = resp_json.get("retCode", -1)
                # Success code is 0 in Bybit V5
                if ret_code != 0:
                    ret_msg = resp_json.get("retMsg", "Unknown error")
                    return {"error": f"Bybit API Error {ret_code}: {ret_msg}"}
                    
                return resp_json.get("result", {})
                
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    continue
                return {"error": f"Request failed: {str(e)}"}
                
        return {"error": "Maximum retries reached"}

    def _convert_symbol(self, symbol: str) -> str:
        """将统一格式 BTCUSDT 转为交易所原始格式，对于 Bybit USDT 永续，其实也是 BTCUSDT"""
        return symbol.replace("-", "").replace("_", "")

    def _convert_symbol_back(self, raw_symbol: str) -> str:
        """将交易所原始格式转为统一格式"""
        return raw_symbol

    def test_connection(self) -> dict:
        """测试连接: 尝试获取钱包余额（最基本的私有接口之一）"""
        try:
            res = self._request("GET", "/v5/account/wallet-balance", {"accountType": "CONTRACT"})
            if "error" in res:
                return {"success": False, "message": res["error"]}
            return {"success": True, "message": "Connected to Bybit"}
        except Exception as e:
            return {"success": False, "message": str(e)}


    def get_instrument_info(self, symbol: str) -> dict:
        """获取并缓存交易对的精度信息"""
        now = time.time()
        # Cache for 1 hour
        if symbol in self._instruments_cache and (now - self._instruments_last_fetch) < 3600:
            return self._instruments_cache[symbol]

        try:
            raw_sym = self._convert_symbol(symbol)
            res = self._request("GET", "/v5/market/instruments-info", {"category": "linear", "symbol": raw_sym})
            
            if "error" in res:
                return {}
                
            info_list = res.get("list", [])
            if not info_list:
                return {}
                
            info = info_list[0]
            lot_filter = info.get("lotSizeFilter", {})
            price_filter = info.get("priceFilter", {})
            
            qty_step = float(lot_filter.get("qtyStep", 1))
            tick_size = float(price_filter.get("tickSize", 1))
            min_qty = float(lot_filter.get("minOrderQty", 0))
            
            # calculate precision from step string
            qty_step_str = str(lot_filter.get("qtyStep", "1"))
            if "." in qty_step_str:
                qty_precision = len(qty_step_str.rstrip("0").split(".")[1])
            else:
                qty_precision = 0
                
            tick_size_str = str(price_filter.get("tickSize", "1"))
            if "." in tick_size_str:
                price_precision = len(tick_size_str.rstrip("0").split(".")[1])
            else:
                price_precision = 0
                
            parsed = {
                "qty_precision": qty_precision,
                "price_precision": price_precision,
                "min_qty": min_qty,
                "min_notional": float(lot_filter.get("minNotionalValue", 0))
            }
            
            self._instruments_cache[symbol] = parsed
            self._instruments_last_fetch = now
            return parsed
            
        except Exception:
            return {}

    def get_usdt_balance(self) -> dict:
        res = self._request("GET", "/v5/account/wallet-balance", {"accountType": "UNIFIED"})
        if "error" in res:
            # Fallback to CONTRACT for non-unified users
            res = self._request("GET", "/v5/account/wallet-balance", {"accountType": "CONTRACT"})
            if "error" in res:
                return res
        
        try:
            account_list = res.get("list", [])
            if not account_list:
                return {"error": "No account data returned"}
                
            coins = account_list[0].get("coin", [])
            for c in coins:
                if c.get("coin") == "USDT":
                    # Bybit: equity = wallet_balance + unrealised_pnl
                    equity = float(c.get("equity", 0))
                    wallet_balance = float(c.get("walletBalance", 0))
                    available = float(c.get("availableToWithdraw", 0))
                    unrealized_pnl = float(c.get("unrealisedPnl", 0))
                    
                    return {
                        "wallet_balance": wallet_balance,
                        "available_balance": available,
                        "margin_balance": equity,
                        "unrealized_pnl": unrealized_pnl,
                        "assets": [
                            {
                                "asset": "USDT",
                                "walletBalance": wallet_balance,
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
        res = self._request("GET", "/v5/position/list", {"category": "linear", "settleCoin": "USDT"})
        if "error" in res:
            return []
            
        positions = []
        try:
            pos_list = res.get("list", [])
            for p in pos_list:
                size = float(p.get("size", 0))
                if size == 0:
                    continue
                    
                raw_sym = p.get("symbol", "")
                symbol = self._convert_symbol_back(raw_sym)
                
                side = p.get("side", "").upper()
                direction = "LONG" if side == "BUY" else "SHORT"
                
                margin_type = "isolated" if p.get("tradeMode", 0) == 1 else "cross"
                
                positions.append({
                    "symbol": symbol,
                    "direction": direction,
                    "quantity": size,
                    "entry_price": float(p.get("avgPrice", 0)),
                    "mark_price": float(p.get("markPrice", 0)),
                    "unrealized_pnl": float(p.get("unrealisedPnl", 0)),
                    "leverage": int(float(p.get("leverage", 1))),
                    "margin_type": margin_type,
                    "liquidation_price": float(p.get("liqPrice", 0) or 0)
                })
        except Exception as e:
            print(f"[Bybit] Error parsing positions: {e}")
            
        return positions

    def get_mark_price(self, symbol: str) -> float:
        raw_sym = self._convert_symbol(symbol)
        res = self._request("GET", "/v5/market/tickers", {"category": "linear", "symbol": raw_sym})
        try:
            return float(res.get("list", [{}])[0].get("markPrice", 0))
        except:
            return 0.0

    def get_position_mode(self, symbol: str) -> dict:
        return {"dualSidePosition": False}


    def place_market_order(self, symbol: str, side: str, quantity: float, reduce_only: bool = False) -> dict:
        qty_str = str(self.format_quantity(symbol, quantity))
        body = {
            "category": "linear",
            "symbol": self._convert_symbol(symbol),
            "side": side.capitalize(),
            "orderType": "Market",
            "qty": qty_str,
            "reduceOnly": reduce_only,
            "timeInForce": "IOC"
        }
        res = self._request("POST", "/v5/order/create", body=body)
        if "error" in res:
            return res
        return {"orderId": res.get("orderId"), "status": "NEW"}

    def place_stop_market_order(self, symbol: str, side: str, stop_price: float, quantity: Optional[float] = None, close_position: bool = False) -> dict:
        body = {
            "category": "linear",
            "symbol": self._convert_symbol(symbol),
            "side": side.capitalize(),
            "orderType": "Market",
            "triggerPrice": str(self.format_price(symbol, stop_price)),
            "triggerDirection": 1 if side.upper() == "BUY" else 2, # simplified
            "reduceOnly": close_position,
            "closeOnTrigger": close_position
        }
        if quantity:
            body["qty"] = str(self.format_quantity(symbol, quantity))
        else:
            body["qty"] = "0"

        res = self._request("POST", "/v5/order/create", body=body)
        if "error" in res:
            return res
        return {"orderId": res.get("orderId"), "status": "NEW"}

    def place_take_profit_market_order(self, symbol: str, side: str, stop_price: float, quantity: Optional[float] = None, close_position: bool = False) -> dict:
        # Very similar to Stop Market, but trigger logic might vary
        body = {
            "category": "linear",
            "symbol": self._convert_symbol(symbol),
            "side": side.capitalize(),
            "orderType": "Market",
            "triggerPrice": str(self.format_price(symbol, stop_price)),
            "triggerBy": "MarkPrice",
            "reduceOnly": close_position,
            "closeOnTrigger": close_position
        }
        if quantity:
            body["qty"] = str(self.format_quantity(symbol, quantity))
        else:
            body["qty"] = "0"

        res = self._request("POST", "/v5/order/create", body=body)
        if "error" in res:
            return res
        return {"orderId": res.get("orderId"), "status": "NEW"}

    def cancel_order(self, symbol: str, order_id: str) -> dict:
        body = {
            "category": "linear",
            "symbol": self._convert_symbol(symbol),
            "orderId": order_id
        }
        res = self._request("POST", "/v5/order/cancel", body=body)
        if "error" in res:
            return res
        return {"success": True, "orderId": order_id}

    def cancel_algo_order(self, symbol: str, algo_id: str) -> dict:
        # Bybit V5: 条件单和普通单使用同一个撤单接口
        return self.cancel_order(symbol, algo_id)

    def cancel_all_orders(self, symbol: str) -> dict:
        body = {"category": "linear", "symbol": self._convert_symbol(symbol)}
        return self._request("POST", "/v5/order/cancel-all", body=body)

    def cancel_all_algo_orders(self, symbol: str) -> dict:
        body = {"category": "linear", "symbol": self._convert_symbol(symbol), "stopOrderType": "Stop"}
        return self._request("POST", "/v5/order/cancel-all", body=body)

    def cancel_all_orders_and_algo(self, symbol: str) -> dict:
        r1 = self.cancel_all_orders(symbol)
        r2 = self.cancel_all_algo_orders(symbol)
        if "error" in r1: return r1
        if "error" in r2: return r2
        return {"success": True}

    def get_open_orders(self, symbol: Optional[str] = None) -> List[dict]:
        params = {"category": "linear"}
        if symbol:
            params["symbol"] = self._convert_symbol(symbol)

        res = self._request("GET", "/v5/order/realtime", params)
        if "error" in res:
            return []

        orders = []
        for o in res.get("list", []):
            if str(o.get("stopOrderType", "")) != "":
                continue
            orders.append({
                "orderId": o.get("orderId"),
                "symbol": self._convert_symbol_back(o.get("symbol")),
                "side": o.get("side", "").upper(),
                "type": o.get("orderType", "").upper(),
                "origQty": float(o.get("qty", 0) or 0),
                "executedQty": float(o.get("cumExecQty", 0) or 0),
                "price": float(o.get("price", 0) or 0),
                "avgPrice": float(o.get("avgPrice", 0) or 0),
                "reduceOnly": o.get("reduceOnly", False),
                "status": o.get("orderStatus", "NEW").upper(),
                "time": int(o.get("createdTime", 0))
            })
        return orders

    def get_open_algo_orders(self, symbol: Optional[str] = None) -> List[dict]:
        params = {"category": "linear"}
        if symbol:
            params["symbol"] = self._convert_symbol(symbol)

        res = self._request("GET", "/v5/order/realtime", params)
        if "error" in res:
            return []

        orders = []
        for o in res.get("list", []):
            if str(o.get("stopOrderType", "")) == "":
                continue

            orders.append({
                "algoId": o.get("orderId"),
                "orderId": o.get("orderId"),
                "symbol": self._convert_symbol_back(o.get("symbol")),
                "side": o.get("side", "").upper(),
                "type": "CONDITIONAL",
                "algoType": o.get("stopOrderType", "STOP_MARKET").upper(),
                "origQty": float(o.get("qty", 0) or 0),
                "triggerPrice": float(o.get("triggerPrice", 0) or 0),
                "stopPrice": float(o.get("triggerPrice", 0) or 0),
                "reduceOnly": o.get("reduceOnly", False),
                "status": "NEW",
                "time": int(o.get("createdTime", 0))
            })
        return orders

    def get_trade_history(self, symbol: str, limit: int = 50, start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[dict]:
        params = {"category": "linear", "symbol": self._convert_symbol(symbol), "limit": str(limit)}
        if start_time: params["startTime"] = str(start_time)
        if end_time: params["endTime"] = str(end_time)

        res = self._request("GET", "/v5/execution/list", params)
        if "error" in res: return []

        trades = []
        for t in res.get("list", []):
            trades.append({
                "id": t.get("execId"),
                "symbol": self._convert_symbol_back(t.get("symbol")),
                "orderId": t.get("orderId"),
                "side": t.get("side", "").upper(),
                "price": float(t.get("execPrice", 0) or 0),
                "qty": float(t.get("execQty", 0) or 0),
                "realizedPnl": float(t.get("closedPnl", 0) or 0),
                "commission": -1 * float(t.get("execFee", 0) or 0), # fee is positive in bybit, standard expects negative
                "time": int(t.get("execTime", 0))
            })
        return trades

    def get_order_history(self, symbol: str, limit: int = 50, start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[dict]:
        params = {"category": "linear", "symbol": self._convert_symbol(symbol), "limit": str(limit)}
        if start_time: params["startTime"] = str(start_time)
        if end_time: params["endTime"] = str(end_time)

        res = self._request("GET", "/v5/order/history", params)
        if "error" in res: return []

        orders = []
        for o in res.get("list", []):
            orders.append({
                "orderId": o.get("orderId"),
                "symbol": self._convert_symbol_back(o.get("symbol")),
                "side": o.get("side", "").upper(),
                "type": o.get("orderType", "").upper(),
                "origQty": float(o.get("qty", 0) or 0),
                "executedQty": float(o.get("cumExecQty", 0) or 0),
                "price": float(o.get("price", 0) or 0),
                "avgPrice": float(o.get("avgPrice", 0) or 0),
                "reduceOnly": o.get("reduceOnly", False),
                "status": o.get("orderStatus", "FILLED").upper(), # mapped
                "time": int(o.get("createdTime", 0)),
                "updateTime": int(o.get("updatedTime", 0))
            })
        return orders

    def get_income_history(self, symbol: Optional[str] = None, limit: int = 50, start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[dict]:
        params = {"accountType": "UNIFIED", "limit": str(limit)}
        if symbol: params["symbol"] = self._convert_symbol(symbol)
        if start_time: params["startTime"] = str(start_time)
        if end_time: params["endTime"] = str(end_time)

        res = self._request("GET", "/v5/account/transaction-log", params)
        if "error" in res:
            params["accountType"] = "CONTRACT"
            res = self._request("GET", "/v5/account/transaction-log", params)
            if "error" in res: return []

        incomes = []
        type_map = {
            "TRADE": "REALIZED_PNL",
            "SETTLEMENT": "REALIZED_PNL",
            "FUNDING": "FUNDING_FEE",
            "FEE": "COMMISSION",
            "TRANSFER_IN": "TRANSFER",
            "TRANSFER_OUT": "TRANSFER"
        }

        for t in res.get("list", []):
            btype = str(t.get("type", "UNKNOWN"))
            amount = float(t.get("change", 0) or 0)

            # bybit uses positive/negative correctly based on change
            incomes.append({
                "symbol": self._convert_symbol_back(t.get("symbol", "")),
                "type": type_map.get(btype, btype),
                "amount": amount,
                "asset": t.get("currency", "USDT"),
                "time": int(t.get("transactionTime", 0)),
                "info": t.get("info", "")
            })
        return incomes

    def set_leverage(self, symbol: str, leverage: int, margin_type: str = "isolated") -> dict:
        raw_sym = self._convert_symbol(symbol)
        body = {
            "category": "linear",
            "symbol": raw_sym,
            "buyLeverage": str(leverage),
            "sellLeverage": str(leverage)
        }
        return self._request("POST", "/v5/position/set-leverage", body=body)

    def set_margin_type(self, symbol: str, margin_type: str = "isolated") -> dict:
        # tradeMode: 0 cross, 1 isolated
        trade_mode = 1 if margin_type == "isolated" else 0
        body = {
            "category": "linear",
            "symbol": self._convert_symbol(symbol),
            "tradeMode": trade_mode,
            "buyLeverage": "10", # Required by API
            "sellLeverage": "10"
        }
        return self._request("POST", "/v5/position/switch-isolated", body=body)

    def get_account_info(self) -> dict:
        return {}
        
    def place_batch_orders(self, orders: list) -> list:
        return []
