"""
Backward-compatibility shim.

This file re-exports everything from exchange_trading_tools.py so that
existing code using `from tools.binance_trading_tools import ...` continues to work.

New code should import from `tools.exchange_trading_tools` instead.
"""

from tools.exchange_trading_tools import *  # noqa: F401,F403
from tools.exchange_trading_tools import (  # noqa: F401 — explicit re-export for IDE support
    _get_effective_user_id,
    _get_trading_client,
    get_symbol_usdt,
    round_quantity,
    round_price,
    get_min_order_size,
    # binance_ prefixed (legacy names)
    binance_get_usdt_balance,
    binance_open_position,
    binance_close_position,
    binance_get_positions_summary,
    binance_get_current_price,
    binance_update_stop_loss,
    binance_update_take_profit,
    binance_get_open_orders,
    binance_modify_order,
    binance_get_income_history,
    binance_get_funding_rate,
    binance_get_adl_risk,
    binance_get_force_orders,
    binance_get_leverage_info,
    binance_get_commission_rate,
    binance_place_trailing_stop,
    binance_get_position_mode,
    binance_change_position_mode,
    binance_cancel_orphan_orders,
    # Generic aliases (new names)
    open_position,
    close_position,
    get_usdt_balance,
    get_positions_summary,
    get_current_price,
    update_stop_loss,
    update_take_profit,
    get_open_orders,
    modify_order,
    get_income_history,
    get_funding_rate,
    get_adl_risk,
    get_force_orders,
    get_leverage_info,
    get_commission_rate,
    place_trailing_stop,
    get_position_mode,
    change_position_mode,
    cancel_orphan_orders,
)
