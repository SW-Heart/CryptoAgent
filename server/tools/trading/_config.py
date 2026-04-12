"""
交易配置常量和工具函数
"""

# Default leverage for new positions
DEFAULT_LEVERAGE = 10

# Fee rate (0.05% for market orders)
FEE_RATE = 0.0005

# Minimum order sizes for common pairs (in base currency)
MIN_ORDER_SIZES = {
    "BTCUSDT": 0.001,
    "ETHUSDT": 0.001,
    "SOLUSDT": 0.01,
    "BNBUSDT": 0.01,
    "XRPUSDT": 1,
    "DOGEUSDT": 1,
    "DEFAULT": 0.001
}

# Price decimal places for common pairs (Binance Futures Mainnet)
# Reference: https://www.binance.com/en/futures/trading-rules/perpetual
PRICE_PRECISION = {
    "BTCUSDT": 1,   # 价格精度: 0.1
    "ETHUSDT": 2,   # 价格精度: 0.01
    "SOLUSDT": 3,   # 价格精度: 0.001
    "BNBUSDT": 2,
    "XRPUSDT": 4,
    "DOGEUSDT": 5,
    "DEFAULT": 2
}

# Quantity decimal places for common pairs (Binance Futures Mainnet)
QTY_PRECISION = {
    "BTCUSDT": 3,   # 最小数量: 0.001
    "ETHUSDT": 3,   # 最小数量: 0.001
    "SOLUSDT": 1,   # 最小数量: 0.1
    "BNBUSDT": 2,
    "XRPUSDT": 1,
    "DOGEUSDT": 0,
    "DEFAULT": 3
}


def get_symbol_usdt(symbol: str) -> str:
    """Ensure symbol ends with USDT."""
    symbol = symbol.upper()
    if not symbol.endswith("USDT"):
        return f"{symbol}USDT"
    return symbol


def round_quantity(symbol: str, quantity: float) -> float:
    """Round quantity to appropriate precision for the symbol."""
    symbol = get_symbol_usdt(symbol)
    precision = QTY_PRECISION.get(symbol, QTY_PRECISION["DEFAULT"])
    return round(quantity, precision)


def round_price(symbol: str, price: float) -> float:
    """Round price to appropriate precision for the symbol."""
    symbol = get_symbol_usdt(symbol)
    precision = PRICE_PRECISION.get(symbol, PRICE_PRECISION["DEFAULT"])
    return round(price, precision)


def get_min_order_size(symbol: str) -> float:
    """Get minimum order size for a symbol."""
    symbol = get_symbol_usdt(symbol)
    return MIN_ORDER_SIZES.get(symbol, MIN_ORDER_SIZES["DEFAULT"])

