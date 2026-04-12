"""
Trading Tools Package - 交易工具集

从原 exchange_trading_tools.py 拆分而来：
- _client: 用户上下文管理和交易客户端获取
- _config: 交易常量和工具函数
- positions: 开仓、平仓、持仓汇总
- orders: 止损/止盈更新、订单管理
- risk: 风控功能（ADL/杠杆/仓位计算）
- cleanup: 孤儿订单清理
"""

# === _client (internal) ===
from tools.trading._client import _get_effective_user_id, _get_trading_client

# === _config ===
from tools.trading._config import (
    DEFAULT_LEVERAGE, FEE_RATE, MIN_ORDER_SIZES,
    PRICE_PRECISION, QTY_PRECISION,
    get_symbol_usdt, round_quantity, round_price, get_min_order_size,
)

# === positions ===
from tools.trading.positions import (
    binance_get_usdt_balance,
    binance_open_position,
    binance_close_position,
    binance_get_positions_summary,
    binance_get_current_price,
)

# === orders ===
from tools.trading.orders import (
    binance_update_stop_loss,
    binance_update_take_profit,
    binance_get_open_orders,
    binance_modify_order,
    binance_get_income_history,
    binance_get_funding_rate,
)

# === risk ===
from tools.trading.risk import (
    binance_get_adl_risk,
    binance_get_force_orders,
    binance_get_leverage_info,
    binance_get_commission_rate,
    binance_place_trailing_stop,
    binance_get_position_mode,
    binance_change_position_mode,
    calculate_position_size,
)

# === cleanup ===
from tools.trading.cleanup import (
    binance_cancel_orphan_orders,
)

# === Generic Aliases (exchange-agnostic names) ===
open_position = binance_open_position
close_position = binance_close_position
get_usdt_balance = binance_get_usdt_balance
get_positions_summary = binance_get_positions_summary
get_current_price = binance_get_current_price
update_stop_loss = binance_update_stop_loss
update_take_profit = binance_update_take_profit
get_open_orders = binance_get_open_orders
modify_order = binance_modify_order
get_income_history = binance_get_income_history
get_funding_rate = binance_get_funding_rate
get_adl_risk = binance_get_adl_risk
get_force_orders = binance_get_force_orders
get_leverage_info = binance_get_leverage_info
get_commission_rate = binance_get_commission_rate
place_trailing_stop = binance_place_trailing_stop
get_position_mode = binance_get_position_mode
change_position_mode = binance_change_position_mode
cancel_orphan_orders = binance_cancel_orphan_orders
