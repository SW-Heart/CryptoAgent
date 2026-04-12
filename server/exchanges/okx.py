import os
import time
import json
import hmac
import hashlib
import base64
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
import requests

from exchanges.base import ExchangeClient

OKX_REST_URL = "https://www.okx.com"

class OKXFuturesClient(ExchangeClient):
    """
    OKX Futures (SWAP) API Client.
    
    Handles OKX-specific authentication, request signing, and data formatting
    to match the unified ExchangeClient interface.
    """
    
    def __init__(self, api_key: str, api_secret: str, passphrase: str, simulated: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.simulated = simulated
        self.base_url = OKX_REST_URL
        self.session = requests.Session()
        
        # 缓存合约信息 (用于 base_coin 数量和合约张数转换)
        self._instruments_cache: Dict[str, dict] = {}
        self._instruments_last_fetch = 0
    
    def get_exchange_name(self) -> str:
        return "OKX"
        
    def _get_timestamp(self) -> str:
        """获取符合 OKX 要求的 ISO 时间戳格式: 2020-12-08T09:08:57.715Z"""
        now = datetime.now(timezone.utc)
        return now.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        
    def _sign(self, timestamp: str, method: str, request_path: str, body: str = "") -> str:
        """生成 OKX 签名"""
        message = timestamp + method.upper() + request_path + body
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
        """发送受 OKX 鉴权保护的请求"""
        url = f"{self.base_url}{endpoint}"
        
        request_path = endpoint
        if params:
            # 过滤掉 None 值的参数
            cleaned_params = {k: v for k, v in params.items() if v is not None}
            if cleaned_params:
                import urllib.parse
                query_string = urllib.parse.urlencode(cleaned_params)
                request_path = f"{endpoint}?{query_string}"
                url = f"{self.base_url}{request_path}"
                
        body_str = ""
        if body:
            # OKX 要求 JSON 体没有转义字符，严谨处理
            body_str = json.dumps(body, separators=(',', ':'))

        timestamp = self._get_timestamp()
        signature = self._sign(timestamp, method, request_path, body_str)

        headers = {
            "Content-Type": "application/json",
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase
        }
        
        if self.simulated:
            headers["x-simulated-trading"] = "1"

        try:
            if method.upper() == "GET":
                response = self.session.get(url, headers=headers, timeout=15)
            elif method.upper() == "POST":
                response = self.session.post(url, headers=headers, data=body_str, timeout=15)
            else:
                return {"error": f"Unsupported HTTP method: {method}"}

            if response.status_code == 429:
                return {"error": "Rate limit exceeded", "code": 429}

            if not response.text:
                return {"error": f"Empty response from API (status: {response.status_code})"}

            try:
                data = response.json()
            except ValueError:
                return {"error": f"Invalid JSON response: {response.text[:100]}..."}

            if str(data.get("code")) != "0":
                return {
                    "error": data.get("msg", "Unknown OKX error"),
                    "code": data.get("code")
                }
                
            return data

        except requests.exceptions.RequestException as e:
            return {"error": f"Network Error: {str(e)}"}

    # ==========================================
    # 辅助方法
    # ==========================================

    def _convert_symbol(self, symbol: str) -> str:
        """Binance 'BTCUSDT' -> OKX 'BTC-USDT-SWAP'"""
        if "USDT" in symbol and "-" not in symbol:
            base = symbol.replace("USDT", "")
            return f"{base}-USDT-SWAP"
        return symbol

    def _convert_symbol_back(self, inst_id: str) -> str:
        """OKX 'BTC-USDT-SWAP' -> Binance 'BTCUSDT'"""
        return inst_id.split('-')[0] + inst_id.split('-')[1]

    def _fetch_instruments(self):
        """缓存合约信息以获取合约乘数 (ctVal) 和精度信息"""
        now = time.time()
        # 1 小时缓存
        if now - self._instruments_last_fetch < 3600 and self._instruments_cache:
            return
            
        res = self.session.get(f"{self.base_url}/api/v5/public/instruments?instType=SWAP")
        if res.status_code == 200:
            data = res.json()
            if data.get("code") == "0":
                lines = data.get("data", [])
                for line in lines:
                    inst_id = line["instId"]
                    # lotSz: 数量步长 (e.g. "0.01"), tickSz: 价格步长 (e.g. "0.1")
                    lot_sz = line.get("lotSz", "1")
                    tick_sz = line.get("tickSz", "0.01")
                    min_sz = line.get("minSz", "1")
                    self._instruments_cache[inst_id] = {
                        "ctVal": float(line["ctVal"]),
                        "ctMult": float(line.get("ctMult", 1)),
                        "lotSz": lot_sz,
                        "tickSz": tick_sz,
                        "minSz": min_sz,
                        "qty_precision": self._sz_to_precision(lot_sz),
                        "price_precision": self._sz_to_precision(tick_sz),
                    }
                self._instruments_last_fetch = now

    @staticmethod
    def _sz_to_precision(sz_str: str) -> int:
        """将步长字符串 (如 '0.01') 转换为精度位数 (如 2)"""
        try:
            sz = float(sz_str)
            if sz >= 1:
                return 0
            s = str(sz)
            if '.' in s:
                return len(s.split('.')[1].rstrip('0')) or 0
            return 0
        except (ValueError, TypeError):
            return 2  # 安全默认值

    def _get_ct_val(self, symbol: str) -> float:
        """获取合约乘数，默认返回 1.0 (异常备用)"""
        self._fetch_instruments()
        inst_id = self._convert_symbol(symbol)
        inst = self._instruments_cache.get(inst_id)
        if inst:
            return inst["ctVal"]
        return 1.0

    def get_instrument_info(self, symbol: str) -> dict:
        """覆盖基类方法，从 OKX 合约缓存动态获取精度信息。"""
        self._fetch_instruments()
        inst_id = self._convert_symbol(symbol)
        inst = self._instruments_cache.get(inst_id)
        if inst:
            return {
                "qty_precision": inst.get("qty_precision", 3),
                "price_precision": inst.get("price_precision", 2),
                "min_qty": float(inst.get("minSz", 1)),
                "min_notional": 5.0,
                "ct_val": inst["ctVal"],
            }
        return super().get_instrument_info(symbol)

    # ==========================================
    # 接口实现
    # ==========================================

    def test_connection(self) -> dict:
        result = self.get_usdt_balance()
        if "error" in result:
            return {"success": False, "error": result["error"]}
        return {"success": True, "balance": result}

    def get_account_info(self) -> dict:
        return self._request("GET", "/api/v5/account/balance")

    def get_usdt_balance(self) -> dict:
        res = self.get_account_info()
        if "error" in res:
            return res
            
        data = res.get("data", [])
        if not data:
            return {"wallet_balance": 0.0, "available_balance": 0.0, "margin_balance": 0.0, "unrealized_pnl": 0.0, "assets": []}
            
        details = data[0].get("details", [])
        
        # OKX 账户级别字段
        total_eq = float(data[0].get("totalEq", 0))
        
        usdt_detail = next((d for d in details if d["ccy"] == "USDT"), None)
        if not usdt_detail:
            return {
                "wallet_balance": total_eq,
                "available_balance": 0.0,
                "margin_balance": total_eq,
                "unrealized_pnl": float(data[0].get("upl", 0)),
                "assets": []
            }
            
        avail_bal = float(usdt_detail.get("availBal", 0))
        upl = float(usdt_detail.get("upl", 0))
        
        
        return {
            "wallet_balance": float(usdt_detail.get("eq", total_eq)),
            "available_balance": avail_bal,
            "margin_balance": float(usdt_detail.get("eq", total_eq)),
            "unrealized_pnl": upl,
            "assets": [
                {
                    "asset": "USDT",
                    "walletBalance": float(usdt_detail.get("eq", total_eq)),
                    "marginBalance": float(usdt_detail.get("eq", total_eq)),
                    "unrealizedProfit": upl,
                    "availableBalance": avail_bal
                }
            ]
        }

    def get_positions(self) -> List[dict]:
        res = self._request("GET", "/api/v5/account/positions", {"instType": "SWAP"})
        if "error" in res:
            print(f"[OKXClient] Error getting positions: {res['error']}")
            return []
            
        data = res.get("data", [])
        formatted = []
        
        for pos in data:
            inst_id = pos["instId"]
            symbol = self._convert_symbol_back(inst_id)
            
            # OKX 持仓需要转换 ctVal -> base coin 数量
            ct_val = self._get_ct_val(symbol)
            pos_amt_contracts = float(pos["pos"])
            pos_amt_base = pos_amt_contracts * ct_val
            
            # 处理单向/双向持仓的符号 (+多, -空)
            pos_side = pos["posSide"].upper()
            if pos_side == "SHORT":
                pos_amt_base = -pos_amt_base
            elif pos_side == "NET" and pos_amt_contracts < 0:
                pos_amt_base = -pos_amt_base
                
            mar_type = "isolated" if pos["mgnMode"] == "isolated" else "cross"
            
            formatted.append({
                "symbol": symbol,
                "direction": "LONG" if pos_amt_base > 0 else "SHORT",
                "quantity": abs(pos_amt_base),
                "entry_price": float(pos["avgPx"]),
                "mark_price": float(pos["markPx"]),
                "unrealized_pnl": float(pos["upl"]),
                "leverage": int(float(pos["lever"])),
                "margin_type": mar_type,
                "liquidation_price": float(pos.get("liqPx", 0)) if pos.get("liqPx") else 0.0
            })
            
        return formatted

    def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        reduce_only: bool = False,
        position_side: str = None
    ) -> dict:
        inst_id = self._convert_symbol(symbol)
        sz = quantity / self._get_ct_val(symbol)
        
        # 数量不能小于 1 张
        if sz < 1:
            sz = 1
        sz_str = str(int(sz))
        
        body = {
            "instId": inst_id,
            "tdMode": "cross",
            "side": side.lower(),
            "ordType": "market",
            "sz": sz_str
        }
        
        if position_side:
            body["posSide"] = position_side.lower()
            
        if reduce_only:
            body["reduceOnly"] = True
            
        res = self._request("POST", "/api/v5/trade/order", body=body)
        
        if "error" in res:
            return res
            
        data = res.get("data", [])
        if data and data[0].get("sCode") == "0":
            return {
                "orderId": data[0]["ordId"],
                "symbol": symbol,
                "status": "NEW"
            }
        else:
            msg = data[0].get("sMsg", "Unknown error") if data else "No data"
            return {"error": f"OKX order failed: {msg}"}

    def place_stop_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_price: float,
        reduce_only: bool = True,
        position_side: str = None
    ) -> dict:
        inst_id = self._convert_symbol(symbol)
        sz = quantity / self._get_ct_val(symbol)
        if sz < 1:
            sz = 1
        sz_str = str(int(sz))
        
        body = {
            "instId": inst_id,
            "tdMode": "cross",
            "side": side.lower(),
            "ordType": "conditional",
            "sz": sz_str,
            "slTriggerPx": str(stop_price),
            "slTriggerPxType": "last",
            "slOrdPx": "-1"  # -1 = 市价单
        }
        
        if position_side:
            body["posSide"] = position_side.lower()
        if reduce_only:
            body["reduceOnly"] = True
            
        res = self._request("POST", "/api/v5/trade/order-algo", body=body)
        
        if "error" in res:
            return res
            
        data = res.get("data", [])
        if data and data[0].get("sCode") == "0":
            return {
                "orderId": data[0]["algoId"],
                "symbol": symbol,
                "status": "NEW"
            }
        return {"error": f"OKX algo order failed: {data[0].get('sMsg', '') if data else 'Unknown'}"}

    def place_take_profit_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_price: float,
        reduce_only: bool = True,
        position_side: str = None
    ) -> dict:
        inst_id = self._convert_symbol(symbol)
        sz = quantity / self._get_ct_val(symbol)
        if sz < 1:
            sz = 1
        sz_str = str(int(sz))
        
        body = {
            "instId": inst_id,
            "tdMode": "cross",
            "side": side.lower(),
            "ordType": "conditional",
            "sz": sz_str,
            "tpTriggerPx": str(stop_price),
            "tpTriggerPxType": "last",
            "tpOrdPx": "-1"
        }
        
        if position_side:
            body["posSide"] = position_side.lower()
        if reduce_only:
            body["reduceOnly"] = True
            
        res = self._request("POST", "/api/v5/trade/order-algo", body=body)
        return res

    def set_leverage(self, symbol: str, leverage: int) -> dict:
        inst_id = self._convert_symbol(symbol)
        body = {
            "instId": inst_id,
            "lever": str(leverage),
            "mgnMode": "cross"
        }
        res = self._request("POST", "/api/v5/account/set-leverage", body=body)
        
        if "error" in res:
            return res
            
        return {"leverage": leverage, "symbol": symbol, "success": True}

    def set_margin_type(self, symbol: str, margin_type: str) -> dict:
        # OKX supports setting position mode isolated/cross globally via /api/v5/account/set-position-mode
        # but typical trading implies tdMode in order placing handles it.
        # Returning success for compatibility.
        return {"success": True}

    def cancel_order(self, symbol: str, order_id: str) -> dict:
        inst_id = self._convert_symbol(symbol)
        body = {"instId": inst_id, "ordId": order_id}
        res = self._request("POST", "/api/v5/trade/cancel-order", body=body)
        if "error" in res:
            return res
        data = res.get("data", [])
        if data and data[0].get("sCode") == "0":
            return {"success": True, "orderId": order_id}
        msg = data[0].get("sMsg", "Unknown error") if data else "No data"
        return {"error": f"OKX cancel failed: {msg}"}

    def cancel_algo_order(self, symbol: str, algo_id: str) -> dict:
        inst_id = self._convert_symbol(symbol)
        body = [{"instId": inst_id, "algoId": algo_id}]
        res = self._request("POST", "/api/v5/trade/cancel-algos", body=body)
        if "error" in res:
            return res
        data = res.get("data", [])
        if data and data[0].get("sCode") == "0":
            return {"success": True, "algoId": algo_id}
        msg = data[0].get("sMsg", "Unknown error") if data else "No data"
        return {"error": f"OKX cancel algo failed: {msg}"}

    def cancel_all_orders(self, symbol: str) -> dict:
        inst_id = self._convert_symbol(symbol)
        
        # 1. Fetch pending orders
        res = self._request("GET", "/api/v5/trade/orders-pending", {"instId": inst_id})
        if "error" in res:
            return res
            
        orders = res.get("data", [])
        if not orders:
            return {"success": True, "msg": "No orders to cancel"}
            
        # 2. Cancel them in batch
        body = [{"instId": inst_id, "ordId": o["ordId"]} for o in orders[:20]] # batch max 20
        cancel_res = self._request("POST", "/api/v5/trade/cancel-batch-orders", body=body)
        
        return cancel_res

    def cancel_all_algo_orders(self, symbol: str) -> dict:
        inst_id = self._convert_symbol(symbol)
        res = self._request("GET", "/api/v5/trade/orders-algo-pending", {"instId": inst_id, "algoOrdType": "conditional"})
        
        if "error" in res:
            return res
            
        orders = res.get("data", [])
        if not orders:
            return {"success": True, "msg": "No algo orders"}
            
        body = [{"instId": inst_id, "algoId": o["algoId"]} for o in orders[:20]]
        cancel_res = self._request("POST", "/api/v5/trade/cancel-algos", body=body)
        
        return cancel_res

    def cancel_all_orders_and_algo(self, symbol: str) -> dict:
        o_res = self.cancel_all_orders(symbol)
        a_res = self.cancel_all_algo_orders(symbol)
        
        if "error" in o_res:
             return o_res
        if "error" in a_res:
            return a_res
            
        return {"success": True}

    def get_open_orders(self, symbol: Optional[str] = None) -> List[dict]:
        params = {}
        if symbol:
            params["instId"] = self._convert_symbol(symbol)
            
        res = self._request("GET", "/api/v5/trade/orders-pending", params)
        if "error" in res:
            return []
            
        data = res.get("data", [])
        formatted = []
        for o in data:
            sym = self._convert_symbol_back(o["instId"])
            ct_val = self._get_ct_val(sym)
            formatted.append({
                "orderId": o["ordId"],
                "symbol": sym,
                "side": o["side"].upper(),
                "type": o["ordType"].upper(),
                "origQty": float(o.get("sz", 0)) * ct_val,
                "executedQty": float(o.get("accFillSz", 0)) * ct_val,
                "price": float(o.get("px", 0)),
                "avgPrice": float(o.get("avgPx", 0)),
                "reduceOnly": o.get("reduceOnly", "false").lower() == "true",
                "closePosition": "false",  # OKX doesn't have an explicit closePosition field strictly, often tied to posSide/reduceOnly
                "status": "NEW" if o["state"] == "live" else o["state"].upper(),
                "time": int(o["cTime"]),
                "updateTime": int(o["uTime"])
            })
        return formatted

    def get_open_algo_orders(self, symbol: Optional[str] = None) -> List[dict]:
        orders = []
        for ord_type in ["conditional", "oco"]:
            params = {"ordType": ord_type}
            if symbol:
                params["instId"] = self._convert_symbol(symbol)
            else:
                params["instType"] = "SWAP" # Usually we trade SWAP
            
            res = self._request("GET", "/api/v5/trade/orders-algo-pending", params)
            if "error" not in res and isinstance(res.get("data"), list):
                orders.extend(res["data"])
                
        data = orders
        formatted = []
        for o in data:
            sym = self._convert_symbol_back(o["instId"])
            ct_val = self._get_ct_val(sym)
            
            # Smart determination of OKX algo orders (TP vs SL)
            tp_px = float(o.get("tpTriggerPx") or 0)
            sl_px = float(o.get("slTriggerPx") or 0)
            gen_px = float(o.get("triggerPx") or 0)
            
            algo_type = "CONDITIONAL"
            trigger_px = gen_px
            if tp_px > 0:
                algo_type = "TAKE_PROFIT_MARKET"
                trigger_px = tp_px
            elif sl_px > 0:
                algo_type = "STOP_MARKET"
                trigger_px = sl_px
            elif gen_px > 0:
                algo_type = "CONDITIONAL"
                trigger_px = gen_px
                
            formatted.append({
                "algoId": o["algoId"],
                "orderId": o["algoId"],  # mapping for UI
                "symbol": sym,
                "side": o["side"].upper(),
                "type": algo_type,
                "algoType": algo_type,
                "triggerCondition": "ge" if "ge" in str(o) else "le", # OKX doesn't expose ge/le clearly in simple conditional sometimes, logic can be complex
                "origQty": float(o.get("sz", 0)) * ct_val,
                "triggerPrice": trigger_px,
                "stopPrice": trigger_px,
                "reduceOnly": str(o.get("reduceOnly", "false")).lower() == "true",
                "status": "NEW" if o["state"] == "live" else o["state"].upper(),
                "time": int(o["cTime"])
            })
        return formatted


    def place_batch_orders(self, orders: list) -> list:
        # Fallback implementation: sequence of single orders since payload is usually [main_order]
        results = []
        for order in orders:
            symbol = order.get("symbol")
            inst_id = self._convert_symbol(symbol)
            quantity = float(order.get("quantity", 0))
            sz = quantity / self._get_ct_val(symbol)
            if sz < 1:
                sz = 1
            sz_str = str(int(sz))
            
            body = {
                "instId": inst_id,
                "tdMode": "cross",
                "side": order.get("side", "").lower(),
                "ordType": order.get("type", "market").lower(),
                "sz": sz_str
            }
            if order.get("positionSide"):
                body["posSide"] = order.get("positionSide").lower()
            if order.get("reduceOnly", "").lower() == "true":
                body["reduceOnly"] = True
            if order.get("price") and order.get("type", "").upper() == "LIMIT":
                body["px"] = str(order.get("price"))
                
            res = self._request("POST", "/api/v5/trade/order", body=body)
            if "error" in res:
                results.append({"error": res["error"]})
            else:
                data = res.get("data", [])
                if data and data[0].get("sCode") == "0":
                    results.append({
                        "orderId": data[0]["ordId"],
                        "symbol": symbol,
                        "status": "NEW"
                    })
                else:
                    msg = data[0].get("sMsg", "Unknown error") if data else "No data"
                    results.append({"error": f"OKX order failed: {msg}"})
        return results

    def get_mark_price(self, symbol: str) -> dict:
        inst_id = self._convert_symbol(symbol)
        res = self._request("GET", "/api/v5/public/mark-price", {"instId": inst_id})
        
        if "error" in res:
            return res
            
        data = res.get("data", [])
        if data:
            return {
                "markPrice": float(data[0]["markPx"])
            }
        return {"error": "Not found"}

    def get_position_mode(self) -> dict:
        res = self._request("GET", "/api/v5/account/config")
        if "error" in res:
            return res
            
        data = res.get("data", [])
        pos_mode = data[0].get("posMode") if data else ""
        return {"dualSidePosition": pos_mode == "long_short_mode"}

    @staticmethod
    def _safe_float(val, default=0.0):
        """安全转换为浮点数，处理空字符串和 None"""
        if val is None or val == "":
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    def get_trade_history(self, symbol: str, limit: int = 50, fromId: int = None) -> List[dict]:
        inst_id = self._convert_symbol(symbol)
        params = {"instId": inst_id, "limit": str(limit), "instType": "SWAP"}
        if fromId:
            params["before"] = str(fromId)
        
        # 优先使用 fills-history (3个月归档，含完整 PnL)，失败后降级到 fills (近3天)
        res = self._request("GET", "/api/v5/trade/fills-history", params)
        if "error" in res or not res.get("data"):
            res = self._request("GET", "/api/v5/trade/fills", params)
        if "error" in res:
            return []
            
        data = res.get("data", [])
        formatted = []
        for t in data:
            sym = self._convert_symbol_back(t["instId"])
            ct_val = self._get_ct_val(sym)
            trade_id = t.get("tradeId", "")
            
            # OKX pnl 字段可能是 "pnl" 或 "fillPnl"，都要检查
            pnl_val = self._safe_float(t.get("pnl")) or self._safe_float(t.get("fillPnl"))
            
            # 从 side + posSide 推断持仓方向标签
            side = t.get("side", "").upper()  # BUY / SELL
            pos_side = t.get("posSide", "").upper()  # LONG / SHORT / NET
            
            # 构造 positionSide 字段: LONG / SHORT
            # 以及判断是否为平仓操作
            if pos_side in ("LONG", "SHORT"):
                position_side = pos_side
            elif side == "BUY":
                position_side = "LONG"
            else:
                position_side = "SHORT"
            
            formatted.append({
                "id": int(trade_id) if trade_id.isdigit() else trade_id,
                "symbol": sym,
                "orderId": t.get("ordId", ""),
                "side": side,
                "positionSide": position_side,
                "price": self._safe_float(t.get("fillPx")),
                "qty": self._safe_float(t.get("fillSz")) * ct_val,
                "realizedPnl": pnl_val,
                "marginAsset": "USDT",
                "commission": self._safe_float(t.get("fee")),
                "time": int(t.get("ts", 0))
            })
        # OKX returns newest first. Reverse to match Binance ascending chronological order
        formatted.reverse()
        return formatted

    def get_position_history(self, symbol: str, limit: int = 50) -> List[dict]:
        inst_id = self._convert_symbol(symbol)
        params = {"instId": inst_id, "limit": str(limit)}
        res = self._request("GET", "/api/v5/account/positions-history", params)
        if "error" in res:
            return []
            
        data = res.get("data", [])
        formatted = []
        for pos in data:
            sym = self._convert_symbol_back(pos["instId"])
            ct_val = self._get_ct_val(sym)
            open_avg_px = self._safe_float(pos.get("openAvgPx"))
            close_avg_px = self._safe_float(pos.get("closeAvgPx"))
            realized_pnl = self._safe_float(pos.get("pnl"))
            fee = self._safe_float(pos.get("fee"))
            
            # calculate ROI
            pos_amt_contracts = max(self._safe_float(pos.get("openMaxPos")), self._safe_float(pos.get("closeTotalPos")))
            pos_amt_base = pos_amt_contracts * ct_val
            leverage = int(self._safe_float(pos.get("lever"), 10))
            if leverage == 0: leverage = 10
            
            entry_notional = pos_amt_base * open_avg_px
            margin = entry_notional / leverage
            roi = (realized_pnl / margin * 100) if margin > 0 else 0
            
            close_type = "全部平仓" if pos.get("type") == "2" else "部分平仓"
            if pos.get("type") == "3": close_type = "全部强平"
            if pos.get("type") == "4": close_type = "部分强平"
            
            formatted.append({
                "symbol": sym.replace("USDT", ""),
                "symbol_full": sym,
                "direction": "LONG" if pos.get("posSide", "").upper() == "LONG" else "SHORT",
                "leverage": leverage,
                "margin_mode": "全仓" if pos.get("mgnMode") == "cross" else "逐仓",
                "close_type": close_type,
                "realized_pnl": realized_pnl,
                "roi_percent": roi,
                "closed_quantity": self._safe_float(pos.get("closeTotalPos")) * ct_val,
                "entry_price": open_avg_px,
                "close_price": close_avg_px,
                "max_quantity": self._safe_float(pos.get("openMaxPos")) * ct_val,
                "total_commission": fee,
                "open_time": int(self._safe_float(pos.get("cTime"))),
                "close_time": int(self._safe_float(pos.get("uTime"))),
            })
        return formatted

    def get_order_history(self, symbol: str, limit: int = 50) -> List[dict]:
        inst_id = self._convert_symbol(symbol)
        params = {"instId": inst_id, "limit": limit}
        res = self._request("GET", "/api/v5/trade/orders-history-archive", params)
        if "error" in res:
            return []
            
        data = res.get("data", [])
        formatted = []
        for o in data:
            sym = self._convert_symbol_back(o["instId"])
            ct_val = self._get_ct_val(sym)
            formatted.append({
                "orderId": o["ordId"],
                "symbol": sym,
                "side": o["side"].upper(),
                "type": o["ordType"].upper(),
                "origQty": float(o.get("sz", 0)) * ct_val,
                "executedQty": float(o.get("accFillSz", 0)) * ct_val,
                "price": float(o.get("px", 0)),
                "avgPrice": float(o.get("avgPx", 0)),
                "reduceOnly": o.get("reduceOnly", "false").lower() == "true",
                "status": o["state"].upper(),
                "time": int(o["cTime"]),
                "updateTime": int(o["uTime"])
            })
        return formatted


    def get_income_history(self, symbol: Optional[str] = None, income_type: Optional[str] = None, limit: int = 100) -> List[dict]:
        """获取资金流水（OKX 账户账单）"""
        params = {"limit": str(limit)}
        if symbol:
            params["instId"] = self._convert_symbol(symbol)
        
        res = self._request("GET", "/api/v5/account/bills", params)
        if "error" in res:
            return []
            
        data = res.get("data", [])
        formatted = []
        
        for bill in data:
            b_type = bill.get("type", "")
            inst_id = bill.get("instId", "")
            sym = self._convert_symbol_back(inst_id) if inst_id else ""
            ts = int(bill.get("ts", 0))
            ccy = bill.get("ccy", "USDT")
            
            fee = float(bill.get("fee", 0))
            pnl = float(bill.get("pnl", 0))
            balChg = float(bill.get("balChg", 0))
            
            # OKX 的交易(type="2")会在同一条记录中包含 fee 和 pnl
            # 前端展示(更贴近Binance的行为)期望将手续费和盈亏分开为 COMMISSION 和 REALIZED_PNL
            if b_type == "2":
                if abs(fee) > 0:
                    formatted.append({
                        "symbol": sym,
                        "type": "COMMISSION",
                        "amount": fee,
                        "asset": ccy,
                        "time": ts,
                        "info": bill.get("notes", "")
                    })
                if abs(pnl) > 0:
                    formatted.append({
                        "symbol": sym,
                        "type": "REALIZED_PNL",
                        "amount": pnl,
                        "asset": ccy,
                        "time": ts,
                        "info": bill.get("notes", "")
                    })
            elif b_type == "8" or b_type == "173":
                formatted.append({
                    "symbol": sym,
                    "type": "FUNDING_FEE",
                    "amount": balChg,
                    "asset": ccy,
                    "time": ts,
                    "info": bill.get("notes", "")
                })
            elif b_type == "1":
                formatted.append({
                    "symbol": sym,
                    "type": "TRANSFER",
                    "amount": balChg,
                    "asset": ccy,
                    "time": ts,
                    "info": bill.get("notes", "")
                })
            else:
                if abs(balChg) > 0:
                    type_str = f"OTHER_{b_type}"
                    if b_type == "3": type_str = "DELIVERED_SETTELMENT"
                    if b_type == "5": type_str = "INSURANCE_CLEAR"
                    formatted.append({
                        "symbol": sym,
                        "type": type_str,
                        "amount": balChg,
                        "asset": ccy,
                        "time": ts,
                        "info": bill.get("notes", "")
                    })
        
        return formatted
