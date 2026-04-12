"""
Unified Exchange Client Test Suite
===================================

Exchange-agnostic tests that validate all ExchangeClient implementations
return data in the correct unified format.

Inspired by nofx/trader/exchange_sync_test.go — every new exchange integration
must pass ALL tests in this file before it can be merged.

Usage:
    # Set environment variables first:
    export TEST_EXCHANGE=binance          # or okx
    export TEST_API_KEY=xxx
    export TEST_API_SECRET=xxx
    export TEST_PASSPHRASE=xxx            # OKX only
    export TEST_ENVIRONMENT=demo          # live, testnet, or demo

    cd back && python -m pytest tests/test_exchange_unified.py -v
"""

import os
import sys
import pytest

# Add parent dir to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ==========================================
# Fixtures
# ==========================================

@pytest.fixture(scope="session")
def exchange_config():
    """Load exchange configuration from environment variables."""
    exchange = os.environ.get("TEST_EXCHANGE", "").lower()
    if not exchange:
        pytest.skip("TEST_EXCHANGE not set — skipping live exchange tests")

    api_key = os.environ.get("TEST_API_KEY", "")
    api_secret = os.environ.get("TEST_API_SECRET", "")
    passphrase = os.environ.get("TEST_PASSPHRASE", "")
    environment = os.environ.get("TEST_ENVIRONMENT", "demo")

    if not api_key or not api_secret:
        pytest.skip("TEST_API_KEY / TEST_API_SECRET not set")

    return {
        "provider": exchange,
        "api_key": api_key,
        "api_secret": api_secret,
        "passphrase": passphrase,
        "environment": environment,
    }


@pytest.fixture(scope="session")
def client(exchange_config):
    """Create an ExchangeClient instance via the factory."""
    from exchange_factory import create_exchange_client

    c = create_exchange_client(
        provider=exchange_config["provider"],
        api_key=exchange_config["api_key"],
        api_secret=exchange_config["api_secret"],
        passphrase=exchange_config["passphrase"],
        environment=exchange_config["environment"],
    )
    assert c is not None, f"Factory returned None for provider={exchange_config['provider']}"
    return c


# ==========================================
# Validators — reusable field-level assertions
# ==========================================

def validate_balance(balance: dict):
    """Assert that a balance dict matches the unified schema."""
    assert isinstance(balance, dict), f"Expected dict, got {type(balance)}"
    assert "error" not in balance, f"Balance returned error: {balance.get('error')}"

    required_keys = ["wallet_balance", "available_balance", "margin_balance", "unrealized_pnl"]
    for key in required_keys:
        assert key in balance, f"Missing required key '{key}'. Got: {list(balance.keys())}"

    # Type checks
    assert isinstance(balance["wallet_balance"], (int, float)), \
        f"wallet_balance must be numeric, got {type(balance['wallet_balance'])}"
    assert isinstance(balance["available_balance"], (int, float)), \
        f"available_balance must be numeric, got {type(balance['available_balance'])}"


def validate_position(pos: dict):
    """Assert that a position dict matches the unified schema."""
    assert isinstance(pos, dict), f"Expected dict, got {type(pos)}"

    # Symbol format: XXUSDT, no separators
    assert "symbol" in pos, "Missing 'symbol'"
    symbol = pos["symbol"]
    assert "USDT" in symbol, f"Symbol must contain 'USDT': {symbol}"
    assert "-" not in symbol, f"Symbol must not contain '-': {symbol}"
    assert "_" not in symbol, f"Symbol must not contain '_': {symbol}"

    # Direction
    assert "direction" in pos, "Missing 'direction'"
    assert pos["direction"] in ("LONG", "SHORT"), f"Bad direction: {pos['direction']}"

    # Quantity — must be positive float
    assert "quantity" in pos, "Missing 'quantity'"
    assert isinstance(pos["quantity"], (int, float)), f"quantity must be numeric: {type(pos['quantity'])}"
    assert pos["quantity"] > 0, f"quantity must be positive: {pos['quantity']}"

    # Prices — must be float
    assert "entry_price" in pos and isinstance(pos["entry_price"], (int, float)), \
        f"Bad entry_price: {pos.get('entry_price')}"
    assert "mark_price" in pos and isinstance(pos["mark_price"], (int, float)), \
        f"Bad mark_price: {pos.get('mark_price')}"

    # Leverage — must be int
    assert "leverage" in pos, "Missing 'leverage'"
    assert isinstance(pos["leverage"], int), f"leverage must be int, got {type(pos['leverage'])}"
    assert pos["leverage"] >= 1, f"leverage must be >= 1: {pos['leverage']}"

    # margin_type
    assert "margin_type" in pos, "Missing 'margin_type'"
    assert pos["margin_type"] in ("cross", "isolated"), f"Bad margin_type: {pos['margin_type']}"

    # unrealized_pnl — must be numeric
    assert "unrealized_pnl" in pos and isinstance(pos["unrealized_pnl"], (int, float)), \
        f"Bad unrealized_pnl: {pos.get('unrealized_pnl')}"


def validate_trade(trade: dict):
    """Assert that a trade dict matches the unified schema."""
    assert isinstance(trade, dict)

    assert "symbol" in trade, "Missing 'symbol'"
    assert "side" in trade, "Missing 'side'"
    assert trade["side"] in ("BUY", "SELL"), f"side must be BUY/SELL uppercase: {trade['side']}"

    assert "price" in trade and isinstance(trade["price"], (int, float)), \
        f"price must be numeric: {trade.get('price')}"
    assert "qty" in trade and isinstance(trade["qty"], (int, float)), \
        f"qty must be numeric: {trade.get('qty')}"

    assert "time" in trade and isinstance(trade["time"], int), \
        f"time must be int (ms timestamp): {trade.get('time')}"


def validate_income(record: dict):
    """Assert that an income/flow record matches the unified schema."""
    assert isinstance(record, dict)

    assert "type" in record, f"Missing 'type'. Got keys: {list(record.keys())}"
    assert "amount" in record, f"Missing 'amount'! Got keys: {list(record.keys())}"
    assert isinstance(record["amount"], (int, float)), \
        f"amount must be numeric, got {type(record['amount'])}: {record['amount']}"
    assert "time" in record and isinstance(record["time"], int), \
        f"time must be int, got {type(record.get('time'))}"

    # Validate type value
    valid_types = {"REALIZED_PNL", "FUNDING_FEE", "COMMISSION", "TRANSFER",
                   "INSURANCE_CLEAR", "INTERNAL_TRANSFER", "WELCOME_BONUS"}
    assert record["type"] in valid_types, \
        f"Unknown income type: {record['type']}. Valid: {valid_types}"


def validate_order(order: dict):
    """Assert that an order dict matches the unified schema."""
    assert isinstance(order, dict)

    assert "orderId" in order, "Missing 'orderId'"
    assert "symbol" in order, "Missing 'symbol'"
    assert "side" in order, "Missing 'side'"
    assert order["side"] in ("BUY", "SELL"), f"side must be BUY/SELL: {order['side']}"

    # Quantity should be float
    if "origQty" in order:
        assert isinstance(order["origQty"], (int, float)), \
            f"origQty must be numeric: {type(order['origQty'])}"
    if "time" in order:
        assert isinstance(order["time"], int), \
            f"time must be int: {type(order['time'])}"


# ==========================================
# Tests — Balance
# ==========================================

class TestBalance:
    """Test get_usdt_balance() unified format."""

    def test_balance_returns_dict(self, client):
        result = client.get_usdt_balance()
        assert isinstance(result, dict)

    def test_balance_has_required_fields(self, client):
        result = client.get_usdt_balance()
        validate_balance(result)

    def test_balance_values_are_non_negative(self, client):
        result = client.get_usdt_balance()
        if "error" in result:
            pytest.skip(f"Balance error: {result['error']}")

        assert result["wallet_balance"] >= 0
        assert result["available_balance"] >= 0


# ==========================================
# Tests — Positions
# ==========================================

class TestPositions:
    """Test get_positions() unified format."""

    def test_positions_returns_list(self, client):
        result = client.get_positions()
        assert isinstance(result, list), f"Expected list, got {type(result)}"

    def test_positions_format_when_present(self, client):
        """If there are positions, validate each one's format."""
        positions = client.get_positions()
        for pos in positions:
            validate_position(pos)

    def test_empty_positions_returns_empty_list(self, client):
        """Ensure no error dict is returned when no positions exist."""
        result = client.get_positions()
        # Should be list (possibly empty), not error dict
        assert isinstance(result, list), f"Expected list even if empty, got: {type(result)}"


# ==========================================
# Tests — Trade History
# ==========================================

class TestTradeHistory:
    """Test get_trade_history() unified format."""

    def test_trade_history_returns_list(self, client):
        result = client.get_trade_history("BTCUSDT", limit=5)
        assert isinstance(result, list), f"Expected list, got {type(result)}"

    def test_trade_history_format(self, client):
        """If there are trades, validate format."""
        trades = client.get_trade_history("BTCUSDT", limit=5)
        for trade in trades:
            validate_trade(trade)


# ==========================================
# Tests — Order History
# ==========================================

class TestOrderHistory:
    """Test get_order_history() unified format."""

    def test_order_history_returns_list(self, client):
        result = client.get_order_history("BTCUSDT", limit=5)
        assert isinstance(result, list)

    def test_order_history_format(self, client):
        orders = client.get_order_history("BTCUSDT", limit=5)
        for order in orders:
            validate_order(order)


# ==========================================
# Tests — Income History
# ==========================================

class TestIncomeHistory:
    """Test get_income_history() unified format."""

    def test_income_history_returns_list(self, client):
        result = client.get_income_history(limit=10)
        assert isinstance(result, list)

    def test_income_history_format(self, client):
        records = client.get_income_history(limit=10)
        for record in records:
            validate_income(record)


# ==========================================
# Tests — Open Orders
# ==========================================

class TestOpenOrders:
    """Test get_open_orders() unified format."""

    def test_open_orders_returns_list(self, client):
        result = client.get_open_orders()
        assert isinstance(result, list)

    def test_open_orders_format(self, client):
        orders = client.get_open_orders()
        for order in orders:
            validate_order(order)


# ==========================================
# Tests — Mark Price
# ==========================================

class TestMarkPrice:
    """Test get_mark_price() unified format."""

    def test_mark_price_returns_dict(self, client):
        result = client.get_mark_price("BTCUSDT")
        assert isinstance(result, dict)

    def test_mark_price_has_value(self, client):
        result = client.get_mark_price("BTCUSDT")
        assert "error" not in result, f"Mark price error: {result.get('error')}"
        assert "markPrice" in result, f"Missing 'markPrice'. Got: {list(result.keys())}"
        price = result["markPrice"]
        assert isinstance(price, (int, float)) and price > 0, f"Invalid markPrice: {price}"


# ==========================================
# Tests — Connection
# ==========================================

class TestConnection:
    """Test test_connection() method."""

    def test_connection_success(self, client):
        result = client.test_connection()
        assert isinstance(result, dict)
        assert result.get("success") is True, f"Connection failed: {result}"


# ==========================================
# Tests — Error Handling
# ==========================================

class TestErrorHandling:
    """Ensure error scenarios return proper error dicts, not exceptions."""

    def test_invalid_symbol_mark_price(self, client):
        """Invalid symbol should return error dict, not crash."""
        result = client.get_mark_price("INVALIDXYZ123")
        assert isinstance(result, dict)
        # Should have error key
        assert "error" in result, f"Expected error for invalid symbol, got: {result}"

    def test_trade_history_invalid_symbol(self, client):
        """Invalid symbol for trades should return empty list."""
        result = client.get_trade_history("INVALIDXYZ123", limit=5)
        assert isinstance(result, list), f"Expected list, got {type(result)}"


# ==========================================
# Tests — Exchange Name
# ==========================================

class TestExchangeName:
    """Test get_exchange_name() method."""

    def test_exchange_name_returns_string(self, client):
        name = client.get_exchange_name()
        assert isinstance(name, str)
        assert name in ("Binance", "OKX", "Bybit", "Bitget", "Gate"), f"Unknown exchange name: {name}"


# ==========================================
# Tests — Cache Layer
# ==========================================

class TestCacheLayer:
    """Test get_cached_balance / get_cached_positions."""

    def test_cached_balance_returns_same_as_direct(self, client):
        """Cached balance should match direct call format."""
        cached = client.get_cached_balance(ttl=5)
        assert isinstance(cached, dict)
        if "error" not in cached:
            validate_balance(cached)

    def test_cached_positions_returns_list(self, client):
        cached = client.get_cached_positions(ttl=5)
        assert isinstance(cached, list)

    def test_cache_returns_same_object_within_ttl(self, client):
        """Two rapid calls should return the exact same object (cache hit)."""
        first = client.get_cached_balance(ttl=30)
        second = client.get_cached_balance(ttl=30)
        assert first is second, "Expected cache hit (same object reference)"

    def test_invalidate_cache_clears(self, client):
        """After invalidate_cache, next call should make a fresh request."""
        client.get_cached_balance(ttl=60)
        client.invalidate_cache()
        # After invalidation, _balance_cache should be None
        assert getattr(client, '_balance_cache', None) is None

    def test_get_position_for_symbol(self, client):
        """get_position_for_symbol should return dict or None."""
        result = client.get_position_for_symbol("BTCUSDT")
        assert result is None or isinstance(result, dict)
        if result is not None:
            validate_position(result)


# ==========================================
# Tests — Convenience Methods
# ==========================================

class TestConvenienceMethods:
    """Test open_long/open_short/close_long/close_short exist and have correct signatures."""

    def test_open_long_exists(self, client):
        assert hasattr(client, 'open_long')
        assert callable(client.open_long)

    def test_open_short_exists(self, client):
        assert hasattr(client, 'open_short')
        assert callable(client.open_short)

    def test_close_long_exists(self, client):
        assert hasattr(client, 'close_long')
        assert callable(client.close_long)

    def test_close_short_exists(self, client):
        assert hasattr(client, 'close_short')
        assert callable(client.close_short)


# ==========================================
# Tests — Dynamic Instrument Info
# ==========================================

class TestInstrumentInfo:
    """Test get_instrument_info / format_quantity / format_price."""

    def test_instrument_info_returns_dict(self, client):
        info = client.get_instrument_info("BTCUSDT")
        assert isinstance(info, dict)
        assert "qty_precision" in info
        assert "price_precision" in info
        assert "min_qty" in info
        assert "ct_val" in info

    def test_qty_precision_is_int(self, client):
        info = client.get_instrument_info("BTCUSDT")
        assert isinstance(info["qty_precision"], int)
        assert info["qty_precision"] >= 0

    def test_format_quantity(self, client):
        result = client.format_quantity("BTCUSDT", 0.123456789)
        assert isinstance(result, float)
        # Should have been rounded
        info = client.get_instrument_info("BTCUSDT")
        expected = round(0.123456789, info["qty_precision"])
        assert result == expected

    def test_format_price(self, client):
        result = client.format_price("BTCUSDT", 99999.123456)
        assert isinstance(result, float)


# ==========================================
# Tests — Position Builder (offline, no API needed)
# ==========================================

class TestPositionBuilder:
    """Test position_builder.build_position_history with synthetic data."""

    def test_empty_trades(self):
        from position_builder import build_position_history
        result = build_position_history([], symbol="BTCUSDT")
        assert result == []

    def test_single_round_trip(self):
        """Open long → close long should produce exactly 1 closed position."""
        from position_builder import build_position_history

        trades = [
            {"side": "BUY", "qty": 0.1, "price": 50000.0, "realizedPnl": 0, "commission": 0.5, "time": 1000},
            {"side": "SELL", "qty": 0.1, "price": 51000.0, "realizedPnl": 100.0, "commission": 0.5, "time": 2000},
        ]
        result = build_position_history(trades, symbol="BTCUSDT")
        assert len(result) == 1

        pos = result[0]
        assert pos["direction"] == "LONG"
        assert pos["symbol"] == "BTC"
        assert pos["symbol_full"] == "BTCUSDT"
        assert pos["realized_pnl"] == 100.0
        assert pos["entry_price"] == 50000.0
        assert pos["close_price"] == 51000.0
        assert pos["open_time"] == 1000
        assert pos["close_time"] == 2000

    def test_short_round_trip(self):
        """Open short → close short."""
        from position_builder import build_position_history

        trades = [
            {"side": "SELL", "qty": 1.0, "price": 3000.0, "realizedPnl": 0, "commission": 0.3, "time": 100},
            {"side": "BUY", "qty": 1.0, "price": 2900.0, "realizedPnl": 100.0, "commission": 0.3, "time": 200},
        ]
        result = build_position_history(trades, symbol="ETHUSDT")
        assert len(result) == 1
        assert result[0]["direction"] == "SHORT"
        assert result[0]["realized_pnl"] == 100.0

    def test_multiple_round_trips(self):
        """Two consecutive position cycles."""
        from position_builder import build_position_history

        trades = [
            # Cycle 1: long
            {"side": "BUY", "qty": 0.5, "price": 100.0, "realizedPnl": 0, "commission": 0.1, "time": 1},
            {"side": "SELL", "qty": 0.5, "price": 110.0, "realizedPnl": 5.0, "commission": 0.1, "time": 2},
            # Cycle 2: short
            {"side": "SELL", "qty": 1.0, "price": 120.0, "realizedPnl": 0, "commission": 0.1, "time": 3},
            {"side": "BUY", "qty": 1.0, "price": 115.0, "realizedPnl": 5.0, "commission": 0.1, "time": 4},
        ]
        result = build_position_history(trades, symbol="SOLUSDT")
        assert len(result) == 2

        # Results are sorted by close_time descending
        assert result[0]["direction"] == "SHORT"  # closed later
        assert result[1]["direction"] == "LONG"    # closed earlier

    def test_partial_close_not_emitted(self):
        """If position not fully closed, it should NOT appear in results."""
        from position_builder import build_position_history

        trades = [
            {"side": "BUY", "qty": 1.0, "price": 100.0, "realizedPnl": 0, "commission": 0, "time": 1},
            {"side": "SELL", "qty": 0.3, "price": 110.0, "realizedPnl": 3.0, "commission": 0, "time": 2},
            # Only 30% closed, not enough to trigger
        ]
        result = build_position_history(trades, symbol="BTCUSDT")
        assert len(result) == 0
